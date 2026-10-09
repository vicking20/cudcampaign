# Shared settings for host.sh / guest.sh (source this; override with environment variables).
# RUNDIR is the folder made by setup-run-folder.sh (exe + DLLs + game data links).
RUNDIR="${RUNDIR:-$HOME/cudcampaign/kisak-run}"
EXE="${EXE:-KisakCOD-sp.exe}"   # EXE=KisakCOD-sp-new.exe ./host.sh runs a staged build next to the normal one
MAP="${MAP:-cargoship}"
PORT="${PORT:-28970}"

run_game() {   # run_game <extra game args...>
    if [ ! -f "$RUNDIR/$EXE" ]; then
        echo "Cannot find $RUNDIR/$EXE - run setup-run-folder.sh first (or set RUNDIR)." >&2
        exit 1
    fi
    cd "$RUNDIR" || exit 1
    WINEDLLOVERRIDES='d3d9=n,b' exec wine "$EXE" \
        +set com_introPlayed 1 +set coop_autostart 1 +set cg_drawFPS Off +set com_statmon 0 +set cg_drawVersion 0 +set replay_time 0 +set replay_autosave 0 +set developer 1 +set logfile 2 "$@"
}
