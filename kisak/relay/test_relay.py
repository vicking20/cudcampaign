#!/usr/bin/env python3
"""End-to-end test of relay.py + bridge.py with a fake 'game' (no game needed): python3 test_relay.py"""
import asyncio, struct, sys
sys.path.insert(0, ".")
import relay, bridge

HDR = relay.CHUNK_HDR
OK = True
GOOD_HELLO = relay.HELLO.pack(relay.HELLO_MAGIC, 0, 0, 0)
relay.HOST_RATE = (1000, 60)   # the tests open many rooms from one address
relay.MAX_ROOMS_PER_IP = 1000


def check(name, cond):
    global OK
    OK &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, flush=True)


def chunk(payload):
    return HDR.pack(relay.COOP_MAGIC, 5, 1000, 0, len(payload)) + payload


async def run(strict, host_sends):
    relay.STRICT = strict
    rsrv = await asyncio.start_server(relay.handle, "127.0.0.1", 0)
    rport = rsrv.sockets[0].getsockname()[1]
    received = {}

    async def fake_game(r, w):          # the host's game: sends host_sends, then echoes what the guest sends
        w.write(host_sends); await w.drain()
        received["hello"] = await r.readexactly(relay.HELLO.size)
        received["from_guest"] = await r.read(5)
        w.write(b"ACK" + received["from_guest"]); await w.drain()

    gsrv = await asyncio.start_server(fake_game, "127.0.0.1", 0)
    gport = gsrv.sockets[0].getsockname()[1]
    ht = asyncio.create_task(bridge.run_host(f"127.0.0.1:{rport}", f"127.0.0.1:{gport}"))
    await asyncio.sleep(0.3)
    code = next(iter(relay.rooms))
    import socket
    with socket.socket() as tmp:
        tmp.bind(("127.0.0.1", 0))
        lport = tmp.getsockname()[1]   # a free local port for the guest-side bridge
    jt = asyncio.create_task(bridge.run_guest(f"127.0.0.1:{rport}", code, f"127.0.0.1:{lport}"))
    await asyncio.sleep(0.3)
    r, w = await asyncio.open_connection("127.0.0.1", lport)       # the guest's game connecting
    w.write(GOOD_HELLO + b"hello")
    await w.drain()
    got = b""
    try:
        while True:
            d = await asyncio.wait_for(r.read(4096), 2)
            if not d:
                break
            got += d
            if len(got) >= len(host_sends) + 8 and not strict:
                break
    except asyncio.TimeoutError:
        pass
    # bad room code answers with an error
    r2, w2 = await asyncio.open_connection("127.0.0.1", rport)
    w2.write(b"JOIN ZZZZZZ\n"); await w2.drain()
    err = await asyncio.wait_for(r2.read(100), 2)
    for t in (ht, jt):
        t.cancel()
    rsrv.close(); gsrv.close()
    return got, received, err


async def main():
    good = chunk(b"x" * 100)
    got, rec, err = await run(False, good)
    check("guest receives the host's chunk through the relay", got.startswith(good))
    check("host's game receives the guest's hello and bytes", rec.get("hello") == GOOD_HELLO and rec.get("from_guest") == b"hello")
    check("guest receives the host's reply (two-way)", got.endswith(b"ACKhello"))
    check("unknown room is refused", err.startswith(b"ERR"))
    relay.rooms.clear()

    got, rec, _ = await run(True, good)
    check("strict mode lets well-formed chunks through", got.startswith(good))
    relay.rooms.clear()

    bad = b"GET / HTTP/1.1\r\n\r\n" + b"\x00" * 64
    got, rec, _ = await run(True, bad)
    check("strict mode cuts a host that sends garbage (nothing forwarded)", bad[:8] not in got)
    relay.rooms.clear()

    huge = HDR.pack(relay.COOP_MAGIC, 5, 0, 0, 50 * 1024 * 1024) + b"y" * 100
    got, rec, _ = await run(True, huge)
    check("strict mode cuts an oversized chunk header", b"yyyy" not in got)
    # a host can choose its own room name; a taken or malformed name is refused
    async def host_line(first):
        r, w = await asyncio.open_connection("127.0.0.1", rport_for_names)
        w.write(first); await w.drain()
        line = await asyncio.wait_for(r.readline(), 2)
        return line, w
    srv = await asyncio.start_server(relay.handle, "127.0.0.1", 0)
    rport_for_names = srv.sockets[0].getsockname()[1]
    line, w1 = await host_line(b"HOST my-lobby\n")
    check("host can choose its room name", line == b"ROOM MY-LOBBY\n")
    line, w2 = await host_line(b"HOST my-lobby\n")
    check("a taken room name is refused", line.startswith(b"ERR"))
    line, w3 = await host_line(b"HOST a!\n")
    check("a malformed room name is refused", line.startswith(b"ERR"))
    line, w4 = await host_line(b"HOST\n")
    check("no name still gets a random code", line.startswith(b"ROOM ") and len(line.strip()) == 11)
    # --- hardening
    relay.rooms.clear()
    lr, lw = await asyncio.open_connection("127.0.0.1", rport_for_names)
    lw.write(b"HOST secure-room\n"); await lw.drain()
    await asyncio.wait_for(lr.readline(), 2)
    r5, w5 = await asyncio.open_connection("127.0.0.1", rport_for_names)
    w5.write(b"JOIN SECURE-ROOM\n" + b"GET / HTTP/1.1\r\n\r\n" + b"x" * 8); await w5.drain()
    err = await asyncio.wait_for(r5.read(100), 3)
    check("a joiner that does not send the game's hello is refused", err.startswith(b"ERR"))
    check("...and does not keep a guest slot", relay.rooms["SECURE-ROOM"].guests == 0)
    r6, w6 = await asyncio.open_connection("127.0.0.1", rport_for_names)
    w6.write(b"JOIN SECURE-ROOM\n"); await w6.drain()          # sends nothing: must time out, not hang forever
    relay.HELLO_TIMEOUT = 0.5
    r7, w7 = await asyncio.open_connection("127.0.0.1", rport_for_names)
    w7.write(b"JOIN SECURE-ROOM\n"); await w7.drain()
    err = await asyncio.wait_for(r7.read(100), 3)
    check("a silent joiner is cut after the hello timeout", err.startswith(b"ERR"))
    relay.MAX_ROOMS_PER_IP = 1
    relay.rooms["X"] = relay.Room("X", None, "127.0.0.1")
    line, _ = await host_line(b"HOST another-room\n")
    check("rooms per address are limited", line.startswith(b"ERR"))
    relay.rooms.pop("X", None)
    relay.MAX_ROOMS_PER_IP = 1000
    relay.HOST_RATE = (2, 60)
    relay.events.clear()
    outs = [(await host_line(b"HOST\n"))[0] for _ in range(4)]
    check("HOST requests are rate limited per address", sum(1 for o in outs if o.startswith(b"ERR")) >= 2)
    relay.HOST_RATE = (1000, 60)
    wrap = HDR.pack(relay.COOP_MAGIC, 5, 0, 0xFFFFFFF0, 0x20) + b"z" * 0x20   # the offset the old guest code wrapped on
    got, rec, _ = await run(True, wrap)
    check("strict mode cuts a chunk with a wrapping/oversized offset", b"zzzz" not in got)
    relay.rooms.clear()
    print("ALL PASS" if OK else "SOME FAILED")
    sys.exit(0 if OK else 1)

asyncio.run(main())
