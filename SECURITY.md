# Security notes

CudCampaign is a play-with-friends tool, not public matchmaking. Read this before hosting a relay or joining a stranger.

## What a guest trusts
A host sends a guest the game's savegame/snapshot and a stream of recorded inputs. The network layer rejects malformed
or oversized data (all lengths and offsets are overflow-checked, map names must be letters/digits/underscore, sizes are
capped, text from the network cannot start console commands). It cannot judge what is *inside* a savegame: that is
parsed by the original game's loader. **Only join hosts you trust.**

## What a host trusts
Guests send inputs. They are range-checked (weapon indexes, non-finite floats) before they enter the shared recording,
a hello with the right magic and password hash is required, and addresses that fail the hello are refused for a few
seconds. Use `coop_password` for private games.

## The relay
See `kisak/relay/README.md`. Per-address limits, hello-before-pairing, idle timeouts, rate cap and framing checks are
built in. Nothing is encrypted; the password is a hash sent in the clear (a deterrent, not authentication). Share room
codes only with people you trust; leave the room name empty to get a random, unguessable code.

## Reporting a problem
Open an issue or message the maintainer privately for anything that looks like a way to crash or take over another
player's game.
