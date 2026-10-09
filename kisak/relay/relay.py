#!/usr/bin/env python3
"""Co-op relay: lets a host and guests meet by room code without anyone opening a port or typing an IP.

Everybody connects OUT to this relay; it only forwards bytes. Protocol (first line of each connection):
  HOST [name]     -> relay answers "ROOM <code>\\n" (the name if you asked for one and it is free, else a random
                     code); this connection stays open as the host's control line,
                     the relay writes "GUEST <id>\\n" on it whenever a guest wants in
  JOIN <code>     -> guest; relay pairs it with a new host data connection (or answers "ERR ...\\n")
  DATA <code> <id>-> the host's answer to "GUEST <id>": a data connection, paired with that guest
After pairing both sides are a plain byte pipe. --strict also checks the host->guest stream is made of
well-formed co-op chunks (magic + sane length) and drops the connection otherwise: a cheap guard for a
guest against a hostile host (it cannot judge the savegame contents, only the framing).

Run:  python3 relay.py --port 28999 [--strict]
"""
import argparse, asyncio, secrets, struct, sys, time


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)

COOP_MAGIC = 0x504F4F43       # 'COOP', first field of every host->guest chunk header
CHUNK_HDR = struct.Struct("<IiiII")   # magic, frameDone, hostTime, offset, len  (20 bytes)
MAX_PIECE = 16 * 1024
MAX_ROOMS, MAX_GUESTS = 200, 3
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class Room:
    def __init__(self, code, ctl_writer):
        self.code, self.ctl, self.pending, self.guests = code, ctl_writer, {}, 0


rooms = {}
STRICT = False


async def readline(reader, limit=128):
    try:
        line = await asyncio.wait_for(reader.readuntil(b"\n"), 10)
    except Exception:
        return None
    return line[:limit].decode("ascii", "replace").strip() if len(line) <= limit else None


async def pipe(src, dst, validate=False, on_done=None):
    """Forward src -> dst until either side ends. With validate: enforce co-op chunk framing."""
    buf = b""
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            if validate:
                buf += data
                while len(buf) >= CHUNK_HDR.size:
                    magic, _frame, _t, _off, ln = CHUNK_HDR.unpack_from(buf)
                    if magic != COOP_MAGIC or ln > MAX_PIECE:
                        raise ValueError("malformed chunk from host")
                    if len(buf) < CHUNK_HDR.size + ln:
                        break
                    buf = buf[CHUNK_HDR.size + ln:]
                # bytes are forwarded as they arrive; the framing check only decides when to cut the link
            dst.write(data)
            await dst.drain()
    except Exception:
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass
        if on_done:
            on_done()


async def handle(reader, writer):
    line = await readline(reader)
    if not line:
        writer.close()
        return
    parts = line.split()
    cmd = parts[0].upper() if parts else ""
    if cmd == "HOST":
        if len(rooms) >= MAX_ROOMS:
            writer.write(b"ERR busy\n"); await writer.drain(); writer.close(); return
        wanted = parts[1].upper() if len(parts) > 1 else ""
        if wanted:
            if not (3 <= len(wanted) <= 16 and all(c.isalnum() or c in "-_" for c in wanted)):
                writer.write(b"ERR room name must be 3-16 letters, digits, - or _\n"); await writer.drain(); writer.close(); return
            if wanted in rooms:
                writer.write(b"ERR room name already taken\n"); await writer.drain(); writer.close(); return
            code = wanted
        else:
            code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        room = rooms[code] = Room(code, writer)
        writer.write(f"ROOM {code}\n".encode()); await writer.drain()
        log(f"room {code} opened by {writer.get_extra_info('peername')}")
        try:
            while await reader.read(1024):   # control line: the host only listens; EOF = room closed
                pass
        finally:
            log(f"room {code} closed")
            rooms.pop(code, None)
            for fut in room.pending.values():
                fut.cancel()
            writer.close()
    elif cmd == "JOIN" and len(parts) == 2:
        room = rooms.get(parts[1].upper())
        log(f"JOIN {parts[1]} from {writer.get_extra_info('peername')}: " + ("no such room" if not room else f"room has {room.guests} guests"))
        if not room or room.guests >= MAX_GUESTS:
            writer.write(b"ERR no such room or room full\n"); await writer.drain(); writer.close(); return
        gid = secrets.token_hex(4)
        log(f"  guest {gid} waits for the host's data connection")
        fut = asyncio.get_event_loop().create_future()
        room.pending[gid] = fut
        room.guests += 1
        try:
            room.ctl.write(f"GUEST {gid}\n".encode()); await room.ctl.drain()
            host_r, host_w = await asyncio.wait_for(fut, 15)
        except Exception:
            writer.write(b"ERR host did not answer\n"); await writer.drain(); writer.close()
            room.pending.pop(gid, None); room.guests -= 1
            return
        done = lambda: setattr(room, "guests", max(0, room.guests - 1))
        await asyncio.gather(pipe(reader, host_w), pipe(host_r, writer, validate=STRICT, on_done=done))
    elif cmd == "DATA" and len(parts) == 3:
        room = rooms.get(parts[1].upper())
        fut = room.pending.pop(parts[2], None) if room else None
        log(f"DATA {parts[1]} {parts[2]}: " + ("paired" if fut and not fut.done() else "unknown guest"))
        if not fut or fut.done():
            writer.close(); return
        fut.set_result((reader, writer))
        await writer.wait_closed()   # the JOIN handler owns the piping now
    else:
        writer.close()


async def main_async(host, port):
    server = await asyncio.start_server(handle, host, port)
    print(f"relay listening on {host}:{port}{' (strict)' if STRICT else ''}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=28999)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    STRICT = a.strict
    asyncio.run(main_async(a.host, a.port))
