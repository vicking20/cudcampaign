#!/bin/bash
# Join a co-op game.   ./guest.sh <host-address[:port]> [map]
# The map must be the one the host is on; later map changes are followed automatically.
. "$(dirname "$0")/common.sh"
if [ -z "$1" ]; then echo "usage: $0 <host-address[:port]> [map]" >&2; exit 1; fi
HOST="$1"
[ -n "$2" ] && MAP="$2"
run_game +set coop_connect "$HOST" +map "$MAP"
