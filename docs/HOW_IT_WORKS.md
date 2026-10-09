# How CudCampaign works (and how we got here)

A learning guide. Status and findings live in `kisak/PLAN.md` (the retail-exe DLL track is described below, its files were removed) and
`kisak/PLAN.md` (KisakCOD source track, the one we're on now).

---

## 1. The method: observe → guess → cheapest test → read the evidence

Nearly every problem in this project was solved with the same loop:

| Problem | Evidence | Guess | Cheapest test |
|---|---|---|---|
| Black screen after the videos | log ends with `cl_paused 1`, `com_introPlayed 0` | startup intro chain pauses the game | relaunch with `+set com_introPlayed 1` |
| `entity 567 is not a player` | the error names the line and function | `setOrigin` is player-only | use `.origin =` instead |
| DLL sent to `'on/'` instead of `127.0.0.1` | network fine, text garbage | wrong string-table entry size | compare with iw3sp_mod (12 bytes, not 8) |
| "Game pauses when unfocused" | only one `hello` seen | **wrong guess** | counted hellos for 10 s: +10 on both → no pause |
| Replay "out of memory" | log gave file + line | buffer too small? **no** | printed the size read: 2.1 MB, fine → in-game load bug |
| Guest mouse "fights back" | wiggle, snaps back | replay code forces view angles | found `CL_SetViewAngles` in the `demoType` branch |

Lessons: read the log first, make the program tell you what it sees (add a print), and measure before
believing a guess (the focus-pause one cost us time).

---

## 2. Tools

- **`console.log`** (`+set logfile 2`, `+set developer 1`) — the game's diary. Errors come with file/line.
- **`grep`** — most "finding" is searching for the right word: an error message, a function name, a dvar.
- **Reference code** — `iw3sp_mod` (addresses for the retail exe), `KisakCOD` (full rebuildable source).
- **`objdump`** — disassembles the exe into CPU instructions; used to find who reads the focus flag.
- **The build loop** — edit → `make` → copy exe → launch → read log. ~30 s per round.
- **ssh/rsync** — deploy to and read logs from the second machine without walking over.

---

## 3. Two tracks we tried

**Track 1 — retail `iw3sp.exe` + a DLL (early prototype, removed).** The game loads `ddraw.dll` from its own
folder, so a fake `ddraw.dll` runs our code inside the game. It hooks the script-function lookup and
adds new script commands (`coop_send`, `coop_poll`). Got two machines exchanging positions, but without
source code every engine change means reverse-engineering. Kept as a fallback.

```cpp
// coop_dll/coop.cpp — redirect the game's "find script function" call to ours
static xfunction_t __cdecl Scr_GetFunction_Stub(const char **name, int *isDev) {
    for (const auto &n : natives)
        if (!_stricmp(*name, n.name)) { *isDev = 0; return n.fn; }
    return Scr_GetFunction(name, isDev);          // not ours: ask the real game
}
PatchCall(0x5435F1, Scr_GetFunction_Stub);         // rewrite one CALL instruction
```

**Track 2 — KisakCOD (kisak/).** A GPL source reconstruction of the game. We build its campaign exe
ourselves and change the engine directly. This is the current track.

---

## 4. Building KisakCOD on Linux (kisak/README.md has the exact commands)

KisakCOD expects Visual Studio on Windows. We used **clang-cl**, LLVM's Microsoft-compatible compiler:

1. `xwin` downloads Microsoft's C runtime + Windows SDK (you accepted the license).
2. The D3DX package from nuget gives the old DirectX helper library.
3. A CMake *toolchain file* (`kisak/clang-cl-x86.cmake`) says: "target 32-bit Windows, use clang-cl,
   these are the SDK folders".
4. ~10 small fixes for Microsoft-vs-clang differences (`kisak/kisakcod.patch`), e.g.:

```cpp
enum team_t;              // Microsoft guesses the size; clang refuses...
enum team_t : __int32;    // ...so state it, matching the real definition
```

Build and run:

```bash
make -C ~/cudcampaign/KisakCOD/build-linux -j12 KisakCOD-sp       # -> bin/KisakCOD-sp.exe
cd ~/cudcampaign/kisak-run && WINEDLLOVERRIDES='d3d9=n,b' wine KisakCOD-sp.exe \
    +set com_introPlayed 1 +set developer 1 +set logfile 2 +map cargoship
```

`kisak-run/` holds the exe + DLLs and *symlinks* to the real game data, so the game folder is never touched.

---

## 5. The key discovery: the campaign is deterministic

The campaign has a replay system. A replay is **not a video** — it's a savegame plus every input that
can't be predicted (player commands, button presses, some dvar reads, the random seed). Playback
re-runs the whole game with those inputs. We recorded on the PC, played back on the Arch box with the
same exe: **identical**, AI included.

So co-op doesn't need to send the world. It only needs to send **inputs**.

---

## 6. Architecture: "live replay"

```
 HOST (plays + records)                         GUEST (replays live + plays player 1)
 ───────────────────────                        ─────────────────────────────────────
 every frame:                                   on join: load same map, take backlog,
   player 0 input  ─┐                           restart level as a replay, fast-forward
   player 1 input  ─┼─► recording (sv.demo.msg) ── TCP ──►  replay reader runs the same frames
   seed, fx, dvars ─┘        ~10 KB/s                       (≈100 ms behind the host)
        ▲                                                       │
        └──────────────── guest's usercmds (keyboard/mouse) ◄───┘
```

- **Host** (`src/server/sv_coop.cpp`, `SV_CoopHostFrame`): after each frame, send the new recorded
  bytes. Big sends are split into 16 KB pieces; only the last piece says "frame N finished".
- **Guest** (`SV_CoopGuestFrame`): before running frame N, wait until the host finished N+1 (the
  reader peeks one item ahead). If more than 250 ms behind, fast-forward with rendering off.
- **Extra players are part of the recording** — new item types, so every machine runs them identically:

```cpp
// type 12 = "player n joins", type 11 = "player n's input this frame"
MSG_WriteByte(&sv.demo.msg, COOP_DEMO_PLAYERCMD);   // 11
MSG_WriteLong(&sv.demo.msg, framePos);
MSG_WriteByte(&sv.demo.msg, n);
MSG_WriteDeltaUsercmd(&sv.demo.msg, &cl->lastUsercmd, cmd);
cl->lastUsercmd = *cmd;
ClientThink(n);                                      // the host runs it right away
```

- The **guest's screen** is built from player 1 (`SV_BuildClientSnapshot` → `SV_CoopViewClient()`).

---

## 7. Single-player assumptions we removed (the recurring pattern)

The campaign assumes exactly one player everywhere. Each bug was one of those assumptions:

| Assumption | Symptom | Fix |
|---|---|---|
| `g_clients[1]`, `maxclients = 1` | no room for player 2 | `COOP_MAX_CLIENTS 4`, reserve entity slots 0–3 |
| savegame allows 1 client | `WriteField1: client out of range` on checkpoint | raise the limits |
| player entities are never drawn | partner invisible | (phase 3) |
| replay ignores live input | guest keyboard dead | `CL_AllowInput`: allow for a co-op guest |
| replay forces the recorded view | guest mouse fights back | skip that branch for a guest |
| death = reload checkpoint | killing player 1 dropped the guest | respawn beside a living partner |
| death handler never reset | respawned player invulnerable | `ent->handler = ENT_HANDLER_CLIENT` |
| scripts check `level.player` | events only trigger for the host | (phase 5, per mission) |

**Determinism rule:** anything that changes the game must run identically on every machine — so it
must come from the stream or from game state, never from the real-world clock (`Sys_Milliseconds`)
or the local keyboard.

---

## 8. Running a co-op session today

```bash
# host (this PC)
cd ~/cudcampaign/kisak-run && WINEDLLOVERRIDES='d3d9=n,b' wine KisakCOD-sp.exe \
    +set coop_host 1 +set com_introPlayed 1 +set developer 1 +set logfile 2 +map cargoship
# guest (other machine, same exe, same map)
cd ~/cudcampaign/kisak-run && WINEDLLOVERRIDES='d3d9=n,b' wine KisakCOD-sp.exe \
    +set coop_connect 192.168.9.202 +set com_introPlayed 1 +set developer 1 +set logfile 2 +map cargoship
```

Useful extras: F1 = console; `+set coop_autotest 1` (idle test player); `+set coop_view 1` (view
player 1); `+set coop_autocmd "<cmd>" +set coop_autocmd_time <s>` (run a command automatically).
