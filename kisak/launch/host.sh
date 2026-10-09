#!/bin/bash
# Host a co-op game.   ./host.sh [map] [port]
#   BIND=local ./host.sh   -> listen on this machine only (for a relay / launcher that forwards guests in)
# Start the host FIRST and click through the mission briefing before guests join.
. "$(dirname "$0")/common.sh"
[ -n "$1" ] && MAP="$1"
[ -n "$2" ] && PORT="$2"
BINDARG=()
[ "$BIND" = "local" ] && BINDARG=(+set coop_bind local)
run_game +set coop_host "$PORT" +set coop_maxplayers "${PLAYERS:-4}" "${BINDARG[@]}" +map "$MAP"
