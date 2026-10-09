#!/bin/bash
# One-click launcher for Linux / Steam Deck (desktop mode). Double click it, or run it in a terminal.
# Uses system Wine with the bundled DXVK (Direct3D -> Vulkan). Needs: wine (32-bit support) and a Vulkan driver.
# Steam users can skip this: add coop/KisakCOD-sp.exe as a non-Steam game and force a Proton version.
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
COOP="$(dirname "$HERE")"; [ -f "$HERE/KisakCOD-sp.exe" ] && COOP="$HERE"
cd "$COOP" || exit 1
[ -f mss32.dll ] || bash ./install.sh || exit 1
[ -f d3d9.dll ] || cp "$COOP/linux/d3d9.dll" d3d9.dll
WINE="$(command -v wine || command -v wine64)"
if [ -z "$WINE" ]; then
  msg="Wine is not installed. Install it (e.g. 'sudo pacman -S wine', 'sudo apt install wine', or the Flatpak 'Bottles'), then run this again."
  command -v zenity >/dev/null && zenity --error --text="$msg" || echo "$msg"
  exit 1
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.local/share/cudcampaign-wine}"
export WINEDLLOVERRIDES="d3d9=n,b;winemenubuilder.exe=d"
export WINEDEBUG="${WINEDEBUG:--all}"
# The game runs inside a Wine virtual desktop (one window that holds everything Wine opens). Without it, on KDE/Wayland
# a Wine helper popup can take the focus mid-game (objectives screen, dead mouse/keyboard). install.sh sets the same
# registry key for the default prefix, so starting KisakCOD-sp.exe directly gets it too. CUD_DESKTOP=0 turns it off.
bash "$COOP/install.sh" --desktop-only >/dev/null 2>&1 || true
exec "$WINE" KisakCOD-sp.exe "$@"
