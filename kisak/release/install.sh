#!/bin/bash
# Downloads the third-party runtime files (Miles audio, Bink video, Steam API stub) the exe needs, from upstream
# KisakCOD, and checks them against deps.txt. Edit deps.txt (BASE line) to use another source. Safe to re-run.
cd "$(dirname "$(readlink -f "$0")")" || exit 1

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
echo "Dependencies ready."
