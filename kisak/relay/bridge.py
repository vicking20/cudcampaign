#!/usr/bin/env python3
"""Local bridge between a game and the relay (see relay.py). The game only ever talks to 127.0.0.1.

  host:  python3 bridge.py host  RELAY:PORT [--game 127.0.0.1:28970]
         (start the game with coop_host 1 coop_bind local; prints the room code to give your friends)
  guest: python3 bridge.py join  RELAY:PORT ROOMCODE [--listen 127.0.0.1:28971]
         (then start the game with +set coop_connect 127.0.0.1:28971)
"""
import argparse, asyncio


def split(addr, default_port):
    host, _, port = addr.rpartition(":")
    return (host or addr, int(port)) if host else (addr, default_port)


async def pipe(src, dst):
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except Exception:
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass


async def run_host(relay, game):
    rh, rp = split(relay, 28999)
    gh, gp = split(game, 28970)
    r, w = await asyncio.open_connection(rh, rp)
    w.write(b"HOST\n")
    line = (await r.readline()).decode().strip()
    if not line.startswith("ROOM "):
        raise SystemExit(f"relay said: {line or 'nothing'}")
    code = line.split()[1]
    print(f"Room code: {code}  (share it; keep this window open)", flush=True)

    async def serve(gid):
        try:
            dr, dw = await asyncio.open_connection(rh, rp)
            dw.write(f"DATA {code} {gid}\n".encode())
            gr, gw = await asyncio.open_connection(gh, gp)
        except Exception as e:
            print(f"guest {gid}: {e}", flush=True)
            return
        print(f"guest {gid} connected", flush=True)
        await asyncio.gather(pipe(dr, gw), pipe(gr, dw))
        print(f"guest {gid} left", flush=True)

    while True:
        line = await r.readline()
        if not line:
            raise SystemExit("lost the relay")
        parts = line.decode().split()
        if len(parts) == 2 and parts[0] == "GUEST":
            asyncio.create_task(serve(parts[1]))


async def run_guest(relay, code, listen):
    rh, rp = split(relay, 28999)
    lh, lp = split(listen, 28971)

    async def handle(lr, lw):
        try:
            rr, rw = await asyncio.open_connection(rh, rp)
        except Exception as e:
            print(f"cannot reach the relay: {e}", flush=True)
            lw.close()
            return
        rw.write(f"JOIN {code}\n".encode())
        await asyncio.gather(pipe(lr, rw), pipe(rr, lw))

    server = await asyncio.start_server(handle, lh, lp)
    print(f"Ready: start the game with +set coop_connect {lh}:{lp}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    h = sub.add_parser("host"); h.add_argument("relay"); h.add_argument("--game", default="127.0.0.1:28970")
    j = sub.add_parser("join"); j.add_argument("relay"); j.add_argument("room"); j.add_argument("--listen", default="127.0.0.1:28971")
    a = ap.parse_args()
    if a.mode == "host":
        asyncio.run(run_host(a.relay, a.game))
    else:
        asyncio.run(run_guest(a.relay, a.room.upper(), a.listen))
