# Building

KisakCOD (GPL source reconstruction of the game) is built with **clang-cl + lld-link** (MSVC-compatible; mingw cannot
handle its `__asm` blocks) and the Windows CRT/SDK from [xwin](https://github.com/Jake-Shadle/xwin).

## One command (Linux)
```bash
kisak/build-from-scratch.sh          # WORK=~/cudcampaign by default; needs git cmake make clang lld llvm curl unzip
KISAK_DIR=~/cudcampaign/KisakCOD kisak/release/make-release.sh     # -> dist/CudCampaign-<date>.zip
```
The script clones KisakCOD at commit `8aadf94`, applies `kisakcod.patch`, downloads xwin (it accepts Microsoft's SDK
licence for you; remove `--accept-license` in the script to do it yourself) and the D3DX nuget package, then builds
with `clang-cl-x86.cmake`. Steps already done are skipped, so re-running after a failure is safe.

`kisakcod.patch` holds every engine change plus the MSVC-vs-clang build fixes. To refresh it after editing a KisakCOD
checkout: `git add -N <new files> && git diff HEAD --binary > kisak/kisakcod.patch`.

## Running a build under Wine
Put `KisakCOD-sp.exe`, the DLLs `install.sh` fetches and a 32-bit DXVK `d3d9.dll` in `coop/` inside the game folder
(or just unpack the release zip) and use `coop/play-linux.sh`. The sound codec set (`miles/`) must be KisakCOD's own,
not the retail one. Do not copy the retail `ddraw.dll`.

## Launcher and game options
Started with no command line the exe shows the launcher and remembers its choices in `coop_launcher.ini`. Any command
line skips it. Useful dvars (`+set name value`): `coop_host 1|<port>`, `coop_connect <addr[:port]|ROOM@relay>`,
`coop_password`, `coop_maxplayers 2-32`, `coop_difficulty 0-3`, `coop_enemies 1-4`, `coop_horde 0|5|10|15|20`,
`coop_relay <addr>`, `coop_roomname <name>`, `coop_autostart 1`. A console window is only created with `-console`.
