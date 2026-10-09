# CudCampaign

Play a supported 2007 military shooter's single-player campaign together, up to 4 players, over a LAN, a
virtual LAN, or through a small relay server (room names, nothing exposed). It is built on
[KisakCOD](https://github.com/SwagSoftware/KisakCOD) (a source rebuild of that game): the host runs the real
campaign and every guest replays the host's inputs live ("live replay"), so the world is never sent, only
inputs. You need your own copy of the game.

What works: join mid-mission (snapshot), respawn beside a living partner or reload the checkpoint when
everyone is down, mission changes, visible animated players with weapons, names and join/leave messages,
host-chosen difficulty and enemy count, native controller support, a launcher window built into the exe.

## Where to look
| Path | What |
|---|---|
| `kisak/README.md` | Build KisakCOD, set up the run folder, launcher, launch scripts, all game options |
| `kisak/PLAN.md` | Status, design notes, backlog (read first when continuing the work) |
| `kisak/kisakcod.patch` | Every engine change (apply to KisakCOD commit `8aadf94`) |
| `kisak/launch/` | `host.sh`, `guest.sh`, `setup-run-folder.sh` |
| `kisak/relay/` | The online relay (`relay.py`), bridge and tests; README explains hosting it |
| `kisak/release/` | `make-release.sh` builds the download zip (a `coop/` folder to unpack inside the game folder) |
| `docs/HOW_IT_WORKS.md` | Learning guide to how and why it works |

## Install (from a release zip)
Unzip so the `coop` folder sits inside your game folder, next to `main` and `zone`, then run
`coop/KisakCOD-sp.exe`. See `kisak/release/INSTALL.txt`.

Horde mode: pick "Horde waves" in the launcher (host only) to survive 5-20 waves on any map.

## Credits and licence
Built on [KisakCOD](https://github.com/SwagSoftware/KisakCOD) by SwagSoftware / LWSS and contributors (GPLv3);
this project's changes are GPLv3 too. Call of Duty is a trademark of Activision; no game files are included.

## Quick start (after building, see kisak/README.md)
Start `KisakCOD-sp.exe` with no options for the launcher: Single player, Host, Join (IP), Host online or
Join online (room name + relay address). Or by script: `kisak/launch/host.sh` and `guest.sh <address>`.
