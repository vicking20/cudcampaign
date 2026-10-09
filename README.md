# CudCampaign

Unofficial co-op for a single-player campaign, up to 32 players (the host chooses; over 16 is experimental): over a LAN, a virtual LAN (Tailscale, ZeroTier, ...)
or through a small relay server that only passes room names and bytes. It is built on
[KisakCOD](https://github.com/SwagSoftware/KisakCOD), a source reconstruction of the original game. The host runs the
real campaign; every guest replays the host's inputs live, so the world itself is never sent. **You need your own
legitimately obtained copy of the original game. No game files are included here.**

Features: join mid-mission, respawn beside a living partner, mission changes, visible animated players with names,
host-chosen difficulty and enemy count, a wave ("horde") mode on any map, controller support, and a launcher window
built into the exe.

> Early test build. Only join hosts you trust and share room codes only with people you trust: see [SECURITY.md](SECURITY.md).

## Install (players)
1. Go to the [releases page](https://github.com/vicking20/cudcampaign/releases), download the zip from the newest
   release, and unpack it **inside your game folder**, so `coop/` sits next to `main/` and `zone/`.
2. Run `coop/install.ps1` (Windows: right click, Run with PowerShell) or `coop/install.sh` (Linux). It downloads the
   few third-party runtime files the exe needs (list and checksums in `deps.txt`).
3. Run `coop/KisakCOD-sp.exe` (Windows), or `coop/play-linux.sh` (Linux/Steam Deck; needs Wine, DXVK is bundled).
4. Pick Single player / Host / Join / Host online / Join online. Everyone needs the same release.

## Online play
Players need only a relay address (`host:port`). To run one: [kisak/relay/README.md](kisak/relay/README.md).

## Build it yourself (Linux)
`kisak/build-from-scratch.sh` clones KisakCOD at the pinned commit, applies `kisak/kisakcod.patch`, fetches the Windows
SDK (xwin) and D3DX, and builds `KisakCOD-sp.exe`. Then `kisak/release/make-release.sh` builds the zip. Details in
[kisak/README.md](kisak/README.md).

## Layout
| Path | What |
|---|---|
| `kisak/kisakcod.patch` | every change to KisakCOD (applies to commit `8aadf94`) |
| `kisak/relay/` | the relay (`relay.py`), its installer and tests |
| `kisak/release/` | what goes into the zip: installers, `deps.txt`, Linux launcher, `make-release.sh` |
| `kisak/build-from-scratch.sh` | full build on Linux |

## Credits and licence
Built on [KisakCOD](https://github.com/SwagSoftware/KisakCOD) by SwagSoftware / LWSS and contributors (GPLv3). This
project's changes are GPLv3 too (see `LICENSE`). Linux bundle includes [DXVK](https://github.com/doitsujin/dxvk) (zlib).
This is an unofficial fan project, not affiliated with or endorsed by Activision. Call of Duty is a trademark of
Activision.
