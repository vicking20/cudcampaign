# Option B plan: networked co-op inside KisakCOD SP

## How SP client <-> server talk today (traced 2026-10-07)
Both live in one process; the "network" is direct function calls, hard-wired to client 0.

| Direction | What | Where |
|---|---|---|
| server -> client | world snapshot **already serialized to a byte buffer** (`SV_WriteSnapshotToClient`), handed over with `CL_PacketEvent(msg, seq)` | `server/sv_snapshot.cpp` `SV_BuildAndSendClientSnapshot` |
| server -> client | gamestate (configstrings) via `CL_ParseGamestate(sv.configstrings)` | `server/sv_client.cpp` `SV_SendGameState` |
| server -> client | reliable server commands parsed in place (`CL_ParseCommandString`) | `SV_SendClientMessages` |
| client -> server | input `usercmd_s` -> `SV_ClientThink(cmd)` -> `ClientThink(0)` | `client/cl_input.cpp` `CL_CreateNewCommands` |
| client -> server | text commands -> `SV_ExecuteClientCommand` -> `ClientCommand(0, s)` | same |

Game layer: `g_clients[1]`, `level.maxclients = 1` (`game/g_main.cpp`), but `ClientThink/ClientBegin(int clientNum)`
take an index, `MAX_CLIENTS` is 64, and server code asserts `sv_maxclients` 1..64. Entities are
allocated after the client slots, so raising maxclients reserves player entity slots.

The seams are clean: snapshots are already bytes, input is already a struct.

## Phases (each ends with something testable)
1. **Two players in one process.** `g_clients[N]`, `level.maxclients = N`, `svs.clients[N]`; dev command
   that connects/spawns client 1 driven by an idle usercmd. Test: second player entity exists, AI
   reacts to it, it takes damage. Learn whether SP cgame draws other player entities at all.
2. **Client-only mode + transport.** A KisakCOD-sp instance that loads the map but runs no server/game:
   receives gamestate + snapshot bytes over UDP into `CL_ParseGamestate`/`CL_PacketEvent`, sends its
   `usercmd_s` back; host feeds them to `SV_ClientThink` for client 1. Port netchan pieces from
   `server_mp`/`client_mp` (fragmentation, sequencing). Watch for SP cgame reading server/game memory
   directly (fine in one process, breaks remotely) — find and route those through the snapshot.
3. **Draw other players properly.** Player model + leg/torso animation + weapon in hand, ported from
   MP cgame (MP sources are already compiled into the SP target).
4. **Rules.** Death/downed/revive or checkpoint respawn, host-only saves, cutscenes for all, mission fail.
5. **Scripts.** `level.player` (3,358 refs): make `_utility`/common libs multi-player aware, then
   per-mission fixups (triggers, vehicles, turrets, slow-mo). Repetitive, mission by mission.

## Status
- **Phase 1 PASSED (2026-10-07)** on killhouse: `COOP_MAX_CLIENTS 4` (`universal/q_shared.h`); `g_clients`,
  `g_sv_clients`, `level.maxclients`, entity slots 0..3 reserved; SV_LocateGameData stride fixed to
  `sizeof(gclient_s)`; `Path_InitPaths` only for client 0; savegame limits (WriteField1/ReadField SF_CLIENT,
  client write loop, G_LoadMainState) raised. `coop_addtestclient` / `+set coop_autotest N` spawn idle
  test players (thinking hooked in the server thread's `G_RunFrame` path, not `SV_RunFrame`).
  Result: second player exists, is solid, gets pushed (pmove runs), checkpoint saves work.
  **Invisible** — SP cgame `CG_AddPacketEntity`: `case ET_PLAYER: return;` (Phase 3).
  Not yet tested: enemy AI targeting it (killhouse has no enemies).
- Console: no F1 console and no input line in the KisakCOD sys console window yet.
- **Phase 2 design finding (2026-10-07):** SP snapshots carry only playerstate + entity *numbers*; cgame
  reads entity states (`SV_GetEntityState`) and full animation trees (`Com_GetServerDObj`) straight from
  server memory. State streaming (2a) would mean serializing all of that.
- **Determinism test PASSED:** cargoship played ~5-10 min on PC, `replay_save dtest`, replayed 1:1 on the
  same PC and **1:1 on the Arch box** (same exe hash 7c8f20a9...): every kill, Price/Gaz door clears,
  helicopter strafe, burst pipe. Replay = start savegame + recorded nondeterministic inputs
  (usercmds, client commands, FX visibility, button presses, dvar reads, random seed).
  => **Going with 2b: deterministic input streaming** (host = recorder, guests = live playback).
- Fixes along the way: F1 opens console (KisakCOD lacked `toggleconsole`, console key hard-coded);
  extra player slots cleared on level start (stale test client crashed the next map);
  `loadgame <replay>` from inside a running game hits "Out of memory" (old replay buffer not freed) —
  start replays from a fresh launch (`+loadgame name`) for now.
- **Spectator mode WORKS (2026-10-07), PC host -> Arch guest over LAN:** `src/server/sv_coop.cpp`.
  Host (`+set coop_host 1` = tcp 28970) streams `sv.demo.msg` after each server frame in <=16 KB pieces
  (header: frameDone, hostTime, offset, len; resend from the bit-writer's partial byte). Guest
  (`+set coop_connect <ip> +map <same map>`) loads the map, takes the backlog, restarts as a replay from
  level start (`SV_DemoRestart`, no savegame — seed comes from the stream), fast-forwards to host time,
  then before each frame waits until host finished frame+1. Continuous catch-up: >250 ms behind ->
  `forwardMsec` skip to ~100 ms. Result: identical game on both screens, ~100 ms behind.
  Known limits: guest is view-only; host level change/load drops the guest; 10 MB replay buffer (~17 min).
  Helper: `+set coop_autocmd "<cmd>" +set coop_autocmd_time <s>` runs a console command once.
- **Guest controls player 1 (2026-10-07):** host spawns player 1 when a guest connects and player 0 is
  on the ground (`PM_NORMAL`, has groundEntity — not during the cargoship heli intro). Extra players are
  recorded into the stream (type 12 join, type 11 per-frame input) right after player 0's input in
  `G_UpdatePlayer`, so guests replay them identically (same spawn frame/position verified). Guest sends
  its local usercmd (`clients[0].cmds`) each frame; guest screen built from player 1
  (`SV_BuildClientSnapshot` -> `SV_CoopViewClient`). Fixes: `CL_AllowInput` refused input during replay;
  cgame forced view angles to the recorded player in replay (`demoType` branch in CG_PredictPlayerState) —
  guest now uses normal prediction. Result: guest moves + looks, but choppy own-movement; no weapons.
- **Playable two-player co-op on cargoship (2026-10-08):** guest sends *every* usercmd with its own
  serverTime; host runs them in order (queue per player, recorded as type 11) -> guest prediction matches,
  movement smooth. Player 1 spawns with player 0's loadout (G_GivePlayerWeapon per owned weapon + ammo).
  Shooting/killing works both ways. Death rule: extra players respawn beside player 0 via `respawn()`
  hook (deterministic: level time) instead of the checkpoint reload; handler reset to ENT_HANDLER_CLIENT
  (death sets ENT_HANDLER_CLIENT_DEAD, which made respawned players invulnerable).
  Open: host death/checkpoint reload drops guest; scripted triggers only fire for player 0 (level.player);
  sidearm reload anim glitch on guest; players invisible (phase 3).
- **Respawn rule verified (2026-10-08):** either player dies -> respawns beside the living partner
  (player 0 too, via `SV_CoopShouldRespawn`); checkpoint reload only when nobody is alive. Spawn spot:
  `Coop_FindSpot` sweeps a player capsule out from the anchor (3 distances x 8 directions, fixed order =
  deterministic), skips blocked/no-floor spots, drops to the floor.
- **Phase 3 step 1 - players visible (2026-10-08):** server gives player entities a body
  (`G_SetModel` "body_complete_sp_sas_ct_benjamin" + `G_DObjUpdate`; player 0 gets one when the first
  partner joins), cgame draws ET_PLAYER via `CG_General` unless it's the viewed player, pitch/roll zeroed.
  Bug found: `ClientSpawn` memsets the gclient and never restored `ps.clientNum` (SP only had 0) - player 1
  claimed to be player 0, so the guest hid the host and drew itself. Bodies are in bind pose (no anims yet).
- **Phase 3 animation (2026-10-08):** bodies use the AI `generic_human` anim set
  (`Com_XAnimCreateSmallTree` + `XAnimSetCompleteGoalWeight`), chosen each frame on every machine from
  movement: speed = origin delta / level time (ps->velocity reads 0 there), stance from `PMF_DUCKED` /
  `PMF_PRONE`, hysteresis on walk/run, previous pose faded out explicitly. Anims: casual_stand_idle,
  walk_lowready_F, run_lowready_F, exposed_crouch_aim_5, crouch_fastwalk_F, prone_aim_5, prone_crawl
  (overridable live: `coop_anim_stand` etc.). Up/down aim: cgame pose controller bends `j_spineupper`
  by view pitch (`coop_aim_axis`/`coop_aim_scale`, defaults 0/1 look right).
  **Player 0 can't be animated on its own entity** (its anim goal weights get reset every frame by
  SP player code - not found where), so player 0's body is a separate non-solid follower entity
  (`g_coopBodyEnt`, ET_GENERAL) created when the first partner joins. Both bodies now animate alike.

## WHERE WE STOPPED (2026-10-08)
Working: 2-player co-op over LAN on cargoship - live replay stream, guest controls player 1 (smooth,
predicted), shared loadout, shooting/killing, respawn beside partner, both players visible + animated
(idle/walk/run/crouch/prone/jump, aim pitch).

Run it: see docs/HOW_IT_WORKS.md section 8 (host `+set coop_host 1`, guest `+set coop_connect <ip>`,
same map). Build: kisak/README.md. All engine changes: kisak/kisakcod.patch (apply to KisakCOD 8aadf94).

Next, roughly in order:
1. ~~Weapon in hand~~ DONE (world model on tag_weapon_right, aimed stand/walk/run poses). ADS pose DONE (CQB_stand_aim5). Tracers + muzzle flash DONE (CG_CoopRemoteFire). Still to do: fire/recoil anim/muzzle flash on the other player's view.
2. **Directional/strafe/backpedal anims**, aim-down-sights pose, player 1 crouch blend looks choppy.
3. ~~Checkpoint reloads~~ DONE for same-map reloads (host sends the new start savegame, guest restarts its replay from it, host re-adds the guest; test with `set coop_nomercy 1` on both machines). Level changes (`spmap <map>`) also work: host sends the map name, guest loads it then follows. Body/weapon models are picked from what the map precached. Original item: (everyone dead / scripted mission fail): host sends checkpoint save, guest
   replays from it (replay system supports starting from a save) - today the guest is dropped.
4. **Phase 5 scripts:** (trigger touching now works for every player - G_UpdatePlayerTriggers loop in G_RunFrame; the rest below is still open) triggers/events only react to player 0 (`level.player`); make shared libs
   (`_utility`, trigger helpers) treat any player as "the player", then per-mission fixes.
5. Guest sidearm reload anim glitch; replay buffer is now 64 MB (was 10 MB); COOP-ANIM debug lines need +set coop_debug 1; host level change drops guest;
   (ambient mp3 streams: FIXED - run folder needs KisakCOD's own miles/ set, see kisak/README.md); second guest (players 2-3) untested.

### Polish backlog (from playtests, 2026-10-08)
- DONE: pistol pose, reload, grenade throw, melee swipe (melee_1), Q/E lean (spine tilt, dvars coop_lean_axis/coop_lean_scale). Console overrides coop_anim_<name>.
- Melee shows a gun swipe with no knife model (a knife would have to be a model the map precached).
- Hit flinch exists (health drop -> 0.4 s pose; the return to standing is abrupt). No fire recoil animation on other players' bodies; no dedicated weapon-switch animation.
- Bullets pass visually through the other player on the shooter's screen (damage is applied).
- Guest has to click through the mission briefing on every map change.
- Mission end works: with a guest connected the victory screen is skipped and the host moves on after 3 s (client-side timer g_coopVictoryAtMs, because the victory menu pauses the server loop). Test shortcut: host console `coopmissionend <nextmap>`. Cinematic (video) mission endings are untested.

### Multiple guests (2026-10-08)
Host accepts up to COOP_MAX_GUESTS (3) guests: `CoopGuestConn` array in sv_coop.cpp, each with its own
socket, player slot (index+1), send position and input buffer. The reset message (map name + slot + start
savegame) is sent on connect and on every checkpoint reload / level change; the guest learns its own slot
from it (`s_mySlot`, used by SV_CoopViewClient). Tested with host + 2 guests: all three see and move.
Known: when a guest disconnects its player body stays in the world (no leave event in the stream yet);
a returning guest takes the same slot. COOP_MAX_CLIENTS is still 4.

### Player leave, player count, non-blocking guests (2026-10-09)
- A dropped guest connection records a type-13 LEAVE item (inside a frame, like JOIN); every machine runs
  `Coop_RemovePlayer(n)` at the same frame (sentient freed, entity unlinked, slot stays reserved).
- `coop_maxplayers` (2..4, launcher dropdown) caps accepted guests.
- Host sends to each guest through a per-guest queue on a non-blocking socket (`Coop_Queue/Coop_Flush`);
  a guest that stops reading (pause menu) can no longer freeze the host. A guest more than 24 MB behind is dropped.
- Launcher is borderless with a title line. Joined/left events are log lines only (no on-screen text yet).
- Ideas noted: preset player names to pick from (no free text), difficulty/enemy-count settings, horde mode.

### Late join from a snapshot (2026-10-09)
A guest joining when the host's recording is already long (>150 KB) no longer replays it from the start.
The host takes a snapshot with the engine's own replay-mark machinery (`SV_CoopTakeSnapshot`: savegame +
collision world + free-entity list + position in the recording), sends it as reset kind 1 together with
each player's last input, active flag and the body entity; the guest loads it (`SV_CoopInstallSnapshot`,
`nextLevelSave`) and then streams from that position. Gotchas found: the free-entity list stores raw
gentity addresses (converted to entity numbers for the wire); `G_LoadMainState` refused saves holding
extra clients (now accepted); client records and last inputs are not in the save (`Coop_ApplySnapshotFix`).
`+set coop_nosnapshot 1` forces the old replay-from-start join. Short recordings still use the replay.

### Names and join/leave messages (2026-10-09)
Players pick a callsign from a fixed list (`src/server/coop_names.h`, shared by launcher and engine; no free
text). Launcher passes `+set coop_name N`. A guest sends its index in the hello, the host makes it unique
(next free index) and records it in the JOIN item (low 7 bits = name, top bit = announce). The host's own
name travels in the reset message prefix, active players' names in the snapshot header. Join/leave print
"<name> joined/left" on every machine via `SV_GameSendServerCommand(-1, "gm ...")` (top-left of the screen).

### Overnight batch (2026-10-09, branch overnight-features, built but NOT run)
Done: real everyone-dead reload (one respawn-or-reload
rule for every player), host-chosen difficulty (`coop_difficulty`, derived values rebuilt on load) and enemy
multiplier (`coop_enemies`, clones in SpawnActor), native XInput gamepad (win_coop_gamepad.cpp +
CL_CoopGamepadMove). Not done: horde/waves mode, in-game online mode (relay prototype only).

## Horde mode and release packaging (2026-10-09)
- `coop_horde N` (launcher: "Horde waves"): N waves from the map's enemy spawners (classname contains enemy/axis/opfor),
  state in saved dvars `coop_horde_wave/left/next/dl`, logic `Coop_HordeFrame()` in game/actor_spawner.cpp. Untested by hand yet:
  check maps without enemy spawners, wave pacing, victory -> next map.
- Install layout: exe may sit in a `coop/` folder inside the game folder; `Sys_DefaultInstallPath()` looks for `zone` here or one up
  and sets the working directory. `kisak/release/make-release.sh` builds `dist/CudCampaign-<version>.zip`.
