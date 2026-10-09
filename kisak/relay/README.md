# Online play through a relay

Hosts and guests both connect OUT to a small relay and meet by a room code: nobody opens a router port,
shares an IP or types one. The game talks only to `127.0.0.1` on its own machine. The relay forwards bytes.
The game now has a relay client built in (launcher: "Host online" / "Join online"), so players need
no Python and no bridge; only whoever runs the relay needs Python 3. `bridge.py` (below) is the older way, still
useful for testing. `python3 test_relay.py` tests the relay itself without the game.

## Built-in (recommended)
- Relay machine: `python3 relay.py --port 28999 --strict`
- Host: launcher -> Host online, relay address `relay-machine:28999`, and a Room name you choose (3-16 letters/
  digits/-/_; empty = random code). Nothing listens on the host's machine. The game also shows "Room code: ..."
  at the top left every 30 s until someone joins (also in `coop_room.txt` and the `coop_room` dvar).
- Guest: launcher -> Join online, enter the room name/code and the same relay address.
- By hand: host `+set coop_host 1 +set coop_relay relay:28999 +set coop_roomname NAME`, guest `+set coop_connect ROOM@relay:28999`.

## Run it
1. Somewhere reachable (see below): `python3 relay.py --port 28999 --strict`
2. Host: start the game listening on this machine only, then the bridge:
   `BIND=local kisak/launch/host.sh` and `python3 bridge.py host RELAY_ADDRESS:28999`
   The bridge prints a room code; give it to friends.
3. Guest: `python3 bridge.py join RELAY_ADDRESS:28999 ROOMCODE`, then start the game with
   `+set coop_connect 127.0.0.1:28971` (add `+set coop_password ...` if the host set one).

`--strict` makes the relay check that everything the host sends a guest is well-formed co-op framing
(magic + sane lengths) and drop the link otherwise. It cannot judge the savegame contents, so a guest still
should only join hosts they trust; but a host can no longer push arbitrary bytes at a guest's game.

## Where to run the relay for free
Traffic is tiny (about 10-15 KB/s per player). Options, all needing an account that only you can create, and
all with terms I have not verified (check current limits before relying on any): an always-free cloud VM
(for example Oracle Cloud's free tier, which asks for a card at sign-up), or any home machine with one
forwarded port. The relay is one file with no dependencies. A serverless platform would need the relay
rewritten around WebSockets.

## Next steps (not done)
- Relay-side rate limits per connection, room passwords, a public room list, TLS.
