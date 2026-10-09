#!/usr/bin/env python3
"""Co-op relay: lets a host and guests meet by room code without anyone opening a port or typing an IP.

Everybody connects OUT to this relay; it only forwards bytes. Protocol (first line of each connection):
  HOST [name]     -> relay answers "ROOM <code>\\n" (the name if you asked for one and it is free, else a random
                     code); this connection stays open as the host's control line (the host pings it every 20 s),
                     the relay writes "GUEST <id>\\n" on it whenever a guest wants in
  JOIN <code>     -> guest; it must then send the game's 16-byte hello within 5 s (checked here: right magic), only
                     then does the relay ask the host for a data connection (or answers "ERR ...\\n")
  DATA <code> <id>-> the host's answer to "GUEST <id>": a data connection, paired with that guest
After pairing both sides are a byte pipe. The host->guest stream must be well-formed co-op chunks (magic, sane
length and offset) or the link is cut: a guest is protected from a malformed stream, though not from a hostile
savegame inside well-formed chunks. Limits (per IP and global), idle timeouts and a guest->host rate cap stop one
visitor from hogging or flooding the service. Nothing here is encrypted: run it behind TLS/VPN if you need that.

Run:  python3 relay.py --port 28999            (framing checks are on; --no-strict turns them off, tests only)
"""
import argparse, asyncio, collections, secrets, struct, sys, time


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)

COOP_MAGIC = 0x504F4F43       # 'COOP', first field of every host->guest chunk header
CHUNK_HDR = struct.Struct("<IiiII")   # magic, frameDone, hostTime, offset, len  (20 bytes)
COOP_FRAME_RESET = -0x7FFFFFFE        # chunk is a piece of a start savegame / snapshot (hostTime = total size)
HELLO = struct.Struct("<IIii")        # guest -> host, first 16 bytes: magic, passwordHash, nameIndex, query
HELLO_MAGIC = 0x314C4548              # 'HEL1'
MAX_PIECE = 16 * 1024
MAX_SAVE = 64 * 1024 * 1024           # same bounds the game enforces
MAX_OFFSET = 64 * 1024 * 1024
MAX_ROOMS, MAX_GUESTS = 200, 3
MAX_CONN_TOTAL = 1000
MAX_CONN_PER_IP = 16
MAX_ROOMS_PER_IP = 2
HOST_RATE = (6, 60)           # at most 6 HOST requests per IP per 60 s
JOIN_RATE = (30, 60)          # at most 30 JOIN requests per IP per 60 s
MIN_ROOM_NAME = 5
HELLO_TIMEOUT = 5             # seconds a joining guest has to send its hello
IDLE_TIMEOUT = 600            # seconds without any bytes on a pipe
CTL_TIMEOUT = 90              # the host pings every 20 s
GUEST_RATE_BPS = 64 * 1024    # guest -> host: a guest sends ~4 KB/s of input; this is generous
GUEST_BURST = 256 * 1024
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class Room:
    def __init__(self, code, ctl_writer, ip):
        self.code, self.ctl, self.ip, self.pending, self.guests = code, ctl_writer, ip, {}, 0


rooms = {}
STRICT = True
conns = collections.Counter()
events = collections.defaultdict(collections.deque)


def rate_ok(kind, ip, limit):
    n, window = limit
    q, now = events[(kind, ip)], time.monotonic()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= n:
        return False
    q.append(now)
    return True


def clean(s):
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in s)[:40]


async def readline(reader, limit=128):
    try:
        line = await asyncio.wait_for(reader.readuntil(b"\n"), 10)
    except Exception:
        return None
    return line[:limit].decode("ascii", "replace").strip() if len(line) <= limit else None


async def refuse(writer, text):
    try:
        writer.write(text.encode() + b"\n"); await writer.drain()
    except Exception:
        pass
    writer.close()


async def pipe(src, dst, validate=False, on_done=None, rate_bps=None):
    """Forward src -> dst until either side ends. validate: enforce co-op chunk framing (only whole, checked
    chunks are forwarded). rate_bps: cut a sender that exceeds this sustained rate."""
    buf = b""
    tokens, last = float(GUEST_BURST), time.monotonic()
    try:
        while True:
            try:
                data = await asyncio.wait_for(src.read(65536), IDLE_TIMEOUT)
            except asyncio.TimeoutError:
                break
            if not data:
                break
            if rate_bps:
                now = time.monotonic()
                tokens = min(GUEST_BURST, tokens + (now - last) * rate_bps)
                last = now
                tokens -= len(data)
                if tokens < 0:
                    raise ValueError("sending too fast")
            if validate:
                buf += data
                end = 0
                while len(buf) - end >= CHUNK_HDR.size:
                    magic, frame, total, off, ln = CHUNK_HDR.unpack_from(buf, end)
                    if magic != COOP_MAGIC or ln > MAX_PIECE or off > MAX_OFFSET \
                            or (frame == COOP_FRAME_RESET and not (0 <= total <= MAX_SAVE)):
                        raise ValueError("malformed chunk from host")
                    if len(buf) - end < CHUNK_HDR.size + ln:
                        break
                    end += CHUNK_HDR.size + ln
                data, buf = buf[:end], buf[end:]
                if not data:
                    continue
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
    peer = writer.get_extra_info("peername")
    ip = peer[0] if peer else "?"
    if sum(conns.values()) >= MAX_CONN_TOTAL or conns[ip] >= MAX_CONN_PER_IP:
        writer.close()
        return
    conns[ip] += 1
    try:
        await handle_conn(reader, writer, ip)
    finally:
        conns[ip] -= 1
        if conns[ip] <= 0:
            del conns[ip]


async def handle_conn(reader, writer, ip):
    line = await readline(reader)
    if not line:
        writer.close()
        return
    parts = line.split()
    cmd = parts[0].upper() if parts else ""
    if cmd == "HOST":
        if len(rooms) >= MAX_ROOMS:
            return await refuse(writer, "ERR busy")
        if not rate_ok("host", ip, HOST_RATE):
            return await refuse(writer, "ERR too many requests, slow down")
        if sum(1 for r in rooms.values() if r.ip == ip) >= MAX_ROOMS_PER_IP:
            return await refuse(writer, "ERR too many rooms from your address")
        wanted = parts[1].upper() if len(parts) > 1 else ""
        if wanted:
            if not (MIN_ROOM_NAME <= len(wanted) <= 16 and all(c.isalnum() or c in "-_" for c in wanted)):
                return await refuse(writer, f"ERR room name must be {MIN_ROOM_NAME}-16 letters, digits, - or _")
            if wanted in rooms:
                return await refuse(writer, "ERR room name already taken")
            code = wanted
        else:
            code = "".join(secrets.choice(ALPHABET) for _ in range(6))
            if code in rooms:
                return await refuse(writer, "ERR busy")
        room = rooms[code] = Room(code, writer, ip)
        writer.write(f"ROOM {code}\n".encode()); await writer.drain()
        log(f"room {code} opened by {ip}")
        try:
            while True:   # control line: the host only pings; silence or EOF = room closed
                try:
                    data = await asyncio.wait_for(reader.read(1024), CTL_TIMEOUT)
                except asyncio.TimeoutError:
                    break
                if not data:
                    break
        finally:
            log(f"room {code} closed")
            if rooms.get(code) is room:
                rooms.pop(code, None)
            for fut in room.pending.values():
                fut.cancel()
            writer.close()
    elif cmd == "JOIN" and len(parts) == 2:
        if not rate_ok("join", ip, JOIN_RATE):
            return await refuse(writer, "ERR too many requests, slow down")
        room = rooms.get(parts[1].upper())
        if not room or room.guests >= MAX_GUESTS:
            log(f"JOIN {clean(parts[1])} from {ip}: refused")
            return await refuse(writer, "ERR no such room or room full")
        room.guests += 1                      # reserved while the guest proves it speaks the protocol
        released = []

        def release():
            if not released:
                released.append(1)
                room.guests = max(0, room.guests - 1)
        try:
            try:
                hello = await asyncio.wait_for(reader.readexactly(HELLO.size), HELLO_TIMEOUT)
                if HELLO.unpack(hello)[0] != HELLO_MAGIC:
                    raise ValueError("bad hello")
            except Exception:
                log(f"JOIN {room.code} from {ip}: no valid hello")
                release()
                return await refuse(writer, "ERR bad hello")
            gid = secrets.token_hex(12)
            fut = asyncio.get_event_loop().create_future()
            room.pending[gid] = fut
            try:
                room.ctl.write(f"GUEST {gid}\n".encode()); await room.ctl.drain()
                host_r, host_w = await asyncio.wait_for(fut, 15)
            except Exception:
                room.pending.pop(gid, None)
                release()
                return await refuse(writer, "ERR host did not answer")
            log(f"guest {gid[:6]} paired in room {room.code}")
            host_w.write(hello)
            await asyncio.gather(pipe(reader, host_w, rate_bps=GUEST_RATE_BPS),
                                 pipe(host_r, writer, validate=STRICT, on_done=release))
        finally:
            release()
    elif cmd == "DATA" and len(parts) == 3:
        room = rooms.get(parts[1].upper())
        fut = room.pending.pop(parts[2], None) if room else None
        if not fut or fut.done():
            writer.close(); return
        fut.set_result((reader, writer))
        await writer.wait_closed()   # the JOIN handler owns the piping now
    else:
        writer.close()


async def main_async(host, port):
    server = await asyncio.start_server(handle, host, port)
    print(f"relay listening on {host}:{port}{' (strict)' if STRICT else ' (framing checks OFF)'}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=28999)
    ap.add_argument("--strict", action="store_true", help="(default now; kept so old command lines work)")
    ap.add_argument("--no-strict", action="store_true", help="turn the framing checks off (tests only)")
    a = ap.parse_args()
    STRICT = not a.no_strict
    asyncio.run(main_async(a.host, a.port))
