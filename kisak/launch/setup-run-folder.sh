#!/bin/bash
# Build the run folder next to the built game.
#   GAME_DIR   your retail game folder (main, zone, players, localization.txt, version.inf)
#   KISAK_DIR  your built KisakCOD checkout (bin/KisakCOD-sp.exe, deps/)
#   DXVK_D3D9  a 32-bit DXVK d3d9.dll (needed under Wine/Linux; skip on Windows)
#   RUNDIR     where to create it (default ~/cudcampaign/kisak-run)
set -e
: "${GAME_DIR:?set GAME_DIR to your retail game folder}"
: "${KISAK_DIR:?set KISAK_DIR to your built KisakCOD checkout}"
RUNDIR="${RUNDIR:-$HOME/cudcampaign/kisak-run}"
mkdir -p "$RUNDIR"
cd "$RUNDIR"
for f in main zone players localization.txt version.inf; do ln -sfn "$GAME_DIR/$f" "$f"; done
cp "$KISAK_DIR/bin/KisakCOD-sp.exe" .
D="$KISAK_DIR/deps"
cp "$D/binklib/"*.dll . 2>/dev/null || true
cp "$D/msslib/dlls/mss32.dll" .
cp "$D/steamsdk/"*.dll . 2>/dev/null || true
# the matching sound codec set must be a real copy of KisakCOD's own, NOT the retail miles/ (see kisak/README.md)
rm -rf miles && cp -r "$D/msslib/dlls/miles" miles
[ -n "$DXVK_D3D9" ] && cp "$DXVK_D3D9" d3d9.dll
echo "7940" > steam_appid.txt
echo "Run folder ready: $RUNDIR"
echo "Do NOT copy the retail ddraw.dll into it."
