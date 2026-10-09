# Online play through a relay

Hosts and guests both connect OUT to a small relay and meet by a room code: nobody opens a router port or shares an
IP. The relay only forwards bytes. Players need no Python; only whoever runs the relay does (Python 3.8+, no packages).
The address players enter is just `host:port` (a domain or an IP, no `http://`).

## Playing through it
- Host: launcher -> Host online, relay address, and a room name (5-16 letters/digits/-/_) or empty for a random code.
  The game shows "Room code: ..." until someone joins.
- Guest: launcher -> Join online, the room name/code and the same relay address.
- By hand: host `+set coop_host 1 +set coop_relay relay:28999 +set coop_roomname NAME`, guest
  `+set coop_connect ROOM@relay:28999`.

## Running the relay
- Quick: `nohup python3 relay.py --port 28999 > relay.log 2>&1 &` (no install, no moved folders).
- As a service on a server: `git clone <repo> /opt/cudcampaign && sudo /opt/cudcampaign/kisak/relay/install-relay.sh`
  creates an unprivileged user, a sandboxed systemd unit and the firewall rule. Update with
  `git -C /opt/cudcampaign pull && sudo systemctl restart cudcampaign-relay`.
- Open TCP 28999 in the machine's firewall and in your cloud provider's network rules. Check from outside with
  `nc -vz <address> 28999`.
- Free options: an always-free cloud VM (check current terms), or a home machine with one forwarded port. Traffic is
  about 10-15 KB/s per player. A serverless/HTTP-only host will not work (raw TCP is needed).
- `python3 test_relay.py` tests the relay without the game (`bridge.py` is its test helper).

## What the relay protects against (and what it does not)
Built in: per-address limits (connections, rooms, HOST/JOIN requests per minute), a joiner must send the game's
16-byte hello within 5 s before the host is even asked to connect (a silent or non-game client never takes a slot or
the host's time), 96-bit guest ids, idle timeouts (host control line 90 s, pipes 10 min), a guest->host rate cap, and
host->guest framing checks (magic, chunk length, offset and savegame size bounds). Room names must be at least 5
characters; a random code (leave the room name empty) is not guessable.

Not covered: nothing is encrypted (a relay operator or anyone on the path can read the traffic, including the password
hash); the relay cannot look inside the savegame a host sends; anyone who knows or guesses a room name can try to join
it (use a random room code, and set `coop_password` in the game so strangers are refused by the host).
The practical rule stays: **only join hosts you trust, and only share room codes with people you trust.**

## Hosting it publicly
- Prefer the installer above (it never runs as root). `cudcampaign-relay.service` is the same unit as a sample.
- Open only the relay port (default 28999/tcp) in the firewall. It needs no other inbound port and writes no files.
- Put a connection limit in front of it as well if you can (your host's firewall / cloud security group): the
  per-address limits here protect against one visitor, not against a flood from thousands of addresses.
- Watch the log (`journalctl -u cudcampaign-relay`): it prints one line per room opened or closed and per refused join.
- Because the relay forwards bytes only, you can run several (one per region) and tell players which address to use.
- Anyone can run their own relay, so a takedown of yours does not stop the project.

## Next steps (not done)
- Room passwords on the relay, a public room list, TLS.
