#!/bin/bash
# Downloads the third-party runtime files (Miles audio, Bink video, Steam API stub) the exe needs, from upstream
# KisakCOD, and checks them against deps.txt. Edit deps.txt (BASE line) to use another source. Safe to re-run.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Linux/Wine only: run KisakCOD-sp.exe inside a Wine virtual desktop (Wine registry, per program), for both the default
# prefix (double-clicking the exe) and the prefix play-linux.sh uses. Stops Wine helper popups stealing the game's
# focus on KDE/Wayland. CUD_DESKTOP=0 removes it again. Windows ignores all of this.
cud_desktop() {
  command -v wine >/dev/null || return 0
  local size; size="${CUD_DESKTOP_SIZE:-$(xrandr 2>/dev/null | awk '/\*/{print $1; exit}')}"; size="${size:-1920x1080}"
  for prefix in "${WINEPREFIX:-$HOME/.wine}" "$HOME/.local/share/cudcampaign-wine"; do
    if [ "${CUD_DESKTOP:-1}" = 0 ]; then
      WINEPREFIX="$prefix" WINEDEBUG=-all wine reg delete 'HKCU\Software\Wine\AppDefaults\KisakCOD-sp.exe\Explorer' /v Desktop /f >/dev/null 2>&1
    else
      WINEPREFIX="$prefix" WINEDEBUG=-all wine reg add 'HKCU\Software\Wine\AppDefaults\KisakCOD-sp.exe\Explorer' /v Desktop /d CudCampaign /f >/dev/null 2>&1
      WINEPREFIX="$prefix" WINEDEBUG=-all wine reg add 'HKCU\Software\Wine\Explorer\Desktops' /v CudCampaign /d "$size" /f >/dev/null 2>&1
    fi
  done
}
if [ "$1" = "--desktop-only" ]; then cud_desktop; exit 0; fi
BASE="$(grep '^BASE=' deps.txt | cut -d= -f2-)"
fail=0
grep -v '^\s*#\|^BASE=\|^\s*$' deps.txt | while read -r sum dst src; do
  if [ -f "$dst" ] && echo "$sum  $dst" | sha256sum -c --status 2>/dev/null; then continue; fi
  mkdir -p "$(dirname "$dst")"
  echo "downloading $dst"
  if ! curl -fsSL "$BASE/$src" -o "$dst.tmp" 2>/dev/null && ! wget -q "$BASE/$src" -O "$dst.tmp"; then echo "FAILED to download $BASE/$src" >&2; rm -f "$dst.tmp"; exit 1; fi
  if ! echo "$sum  $dst.tmp" | sha256sum -c --status; then echo "CHECKSUM MISMATCH for $dst (kept as $dst.tmp, not used)" >&2; exit 1; fi
  mv "$dst.tmp" "$dst"
done || { echo "install incomplete" >&2; exit 1; }
[ -d ../main ] && [ -d ../zone ] || echo "WARNING: ../main and ../zone not found - this folder must sit inside your game folder." >&2
cud_desktop && echo "Wine: the game will run in a virtual desktop window (CUD_DESKTOP=0 ./install.sh to turn that off)."
echo "Dependencies ready."
