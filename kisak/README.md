# Building KisakCOD (SP) on Linux

KisakCOD = GPL source reimplementation of the game (SP + MP + dedi), checked out at
`/home/deck/cudcampaign/KisakCOD`, commit `8aadf94`. Officially Visual Studio only; this
builds it with **clang-cl + lld-link** (MSVC-compatible, handles its `__asm` blocks;
mingw cannot).

## Quick way: `kisak/build-from-scratch.sh`
Does everything below in one go (clone KisakCOD at the right commit, apply the patch, fetch xwin SDK + D3DX, configure, build)
into `~/cudcampaign` (or `WORK=...`). Then `kisak/release/make-release.sh`. The manual steps follow for reference.

## One-time setup
1. `sudo pacman -S cmake` (clang, lld, llvm already present)
2. Windows CRT/SDK via [xwin](https://github.com/Jake-Shadle/xwin) (accepts Microsoft's license):
   ```bash
   cd ~/cudcampaign/winsdk && ./xwin --accept-license --arch x86 --cache-dir cache splat --output sdk
   ```
3. D3DX: nuget `Microsoft.DXSDK.D3DX` 9.29.952.8 unzipped to `~/cudcampaign/winsdk/d3dx`, plus
   `ln -s release ~/cudcampaign/winsdk/d3dx/build/native/Release` (cmake asks for `Release`).
4. Apply `kisakcod.patch` to KisakCOD (`git apply`). It holds the co-op changes (see PLAN.md status) plus these build fixes, all MSVC-vs-clang:
   - `CMAKE_GENERATOR_PLATFORM` only for Visual Studio generators
   - enum forward decls need the fixed underlying type (`enum team_t : __int32;`)
   - include case (`DynEntity_client.h`), `__m128` union members/brace init (SSE skinning)
   - `alignas` placement in `scr_yacc_structs.h`
   - `static` redefinitions of header-declared functions renamed `_Local` (clang links them as duplicates)

## Build
```bash
cd ~/cudcampaign/KisakCOD
cmake -S . -B build-linux -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE=<repo>/kisak/clang-cl-x86.cmake \
  -DCMAKE_BUILD_TYPE=Release -DCICD=1 -DDXSDK_DIR=$HOME/cudcampaign/winsdk/d3dx/build/native
make -C build-linux -j12 KisakCOD-sp     # -> bin/KisakCOD-sp.exe
```
Configure fetches Tracy (profiler) from GitHub.

## Run
`~/cudcampaign/kisak-run/`: symlinks to the game's `main zone players localization.txt version.inf`,
plus `KisakCOD-sp.exe`, KisakCOD's `deps` DLLs (binkw32, mss32, steam_api) and DXVK `d3d9.dll`.
**`miles/` must be a real copy of KisakCOD's `deps/msslib/dlls/miles/`, NOT a link to the retail game's `miles/`** (the retail codec files do not match KisakCOD's newer `mss32.dll`: every mp3 stream failed with "Error getting sound format"; with the matching set, music and ambience play). Do not use the retail `mss32.dll` either (the game hangs at sound init).
**Do not copy our `ddraw.dll`** — it patches retail iw3sp.exe addresses.
```bash
WINEDLLOVERRIDES='d3d9=n,b' wine KisakCOD-sp.exe +set com_introPlayed 1 +set nextmap "" +set r_fullscreen 0 +set developer 1 +set logfile 2 +map killhouse
```
console.log lands in `main/console.log` (i.e. the real game's main/ via the symlink).

Status 2026-10-07: killhouse loads (2.7 s), AI runs, start-level save written.

## Launch scripts (kisak/launch)
`setup-run-folder.sh` builds the run folder (GAME_DIR, KISAK_DIR, DXVK_D3D9 environment variables, see the
script header). Then `host.sh [map] [port]` hosts and `guest.sh <host-address[:port]> [map]` joins.
Start the host first and click through its briefing. `BIND=local ./host.sh` listens on this machine only
(for a relay/launcher that forwards guests in). Direct play works on a LAN or any virtual LAN
(Tailscale, ZeroTier, ...): the guest types the host's address on that network.

## Launcher window
Started with no command line (double click, Steam shortcut), `KisakCOD-sp.exe` shows a small window:
Single player / Host / Join, mission, host address. It appends the matching `+set coop_host` /
`+set coop_connect` / `+map` options and remembers the choices in `coop_launcher.ini` next to the exe.
Any command line at all skips it (the launch scripts do). No console window opens unless you start the exe with `-console`. Source: `src/win32/win_coop_launcher.cpp`.

## Launcher, password, joining (2026-10-08)
- Launcher: missions are listed in campaign order (act headings). **Host** picks the mission; **Join** hides
  the list - the host sends its map and start savegame as the first message when a guest connects, and the
  guest loads that map and catches up (also after the host reloads a checkpoint or changes level).
- Dvars (all usable as `+set` launch options): `coop_host 1`, `coop_connect <addr[:port]>`,
  `coop_password <word>` (host and guest must match; deterrent only), `coop_bind local` (host listens on
  loopback only), `coop_autostart 1` (passes the mission briefing by itself once loaded), `coop_debug 1`.
- A refused or unreachable guest gets an error and goes back to the main menu.
