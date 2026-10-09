#!/bin/bash
# Build the release zip: a single "coop" folder that the player unpacks INTO their game folder
# (next to main/ and zone/). The exe finds the game data one folder up, so nothing is hard-coded.
#   KISAK_DIR  your built KisakCOD checkout (bin/KisakCOD-sp.exe, deps/)   default ~/cudcampaign/KisakCOD
#   VERSION    label for the zip name                                       default today's date
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
KISAK_DIR="${KISAK_DIR:-$HOME/cudcampaign/KisakCOD}"
VERSION="${VERSION:-$(date +%Y%m%d)}"
OUT="$REPO/dist"
STAGE="$(mktemp -d)"
[ -f "$KISAK_DIR/bin/KisakCOD-sp.exe" ] || { echo "build KisakCOD first (no $KISAK_DIR/bin/KisakCOD-sp.exe)" >&2; exit 1; }
D="$KISAK_DIR/deps"
C="$STAGE/coop"
mkdir -p "$C/relay" "$C/docs"
cp "$KISAK_DIR/bin/KisakCOD-sp.exe" "$C/"
# Third-party runtime files (Miles, Bink, Steam API) are NOT shipped: coop/install.sh|ps1 downloads them (see deps.txt).
# FULL=1 bundles them anyway (private/testing use only).
cp "$REPO/kisak/release/deps.txt" "$REPO/kisak/release/install.sh" "$REPO/kisak/release/install.ps1" "$C/"
if [ -n "$FULL" ]; then
  cp "$D"/binklib/*.dll "$C/"; cp "$D/msslib/dlls/mss32.dll" "$C/"; cp -r "$D/msslib/dlls/miles" "$C/miles"
  cp "$D"/steamsdk/*.dll "$C/" 2>/dev/null || true
fi
echo 7940 > "$C/steam_appid.txt"
mkdir -p "$C/linux"
cp "$REPO/kisak/release/linux/d3d9.dll" "$C/linux/"   # DXVK 2.6.2 32-bit (zlib licence, github.com/doitsujin/dxvk)
cp "$REPO/kisak/release/linux/play-linux.sh" "$C/play-linux.sh"
chmod +x "$C/play-linux.sh"
cp "$REPO/kisak/relay/relay.py" "$REPO/kisak/relay/README.md" "$REPO/kisak/relay/cudcampaign-relay.service" "$C/relay/"
cp "$REPO/SECURITY.md" "$C/docs/"
cp "$KISAK_DIR/LICENSE" "$C/LICENSE-GPLv3.txt"
cp "$REPO/kisak/release/INSTALL.txt" "$C/INSTALL.txt"
cp "$REPO/kisak/kisakcod.patch" "$C/docs/our-changes-to-kisakcod.patch"
mkdir -p "$OUT"
ZIP="$OUT/CudCampaign-$VERSION.zip"
rm -f "$ZIP"
(cd "$STAGE" && python3 -c "import shutil,sys; shutil.make_archive(sys.argv[1][:-4], 'zip', '.', 'coop')" "$ZIP")
rm -rf "$STAGE"
echo "Built $ZIP"
python3 -m zipfile -l "$ZIP" | head -40
