#!/bin/bash
# Build KisakCOD-sp.exe with the CudCampaign changes, from nothing, on Linux (clang-cl + lld-link + xwin).
# Needs: git cmake make clang lld llvm curl tar unzip (clang-cl, lld-link, llvm-rc, llvm-lib on PATH).
#   WORK   where everything is put (default ~/cudcampaign)
#   JOBS   parallel compile jobs (default: all cores)
# Steps are skipped if already done, so it is safe to re-run after a failure.
# xwin downloads the Microsoft CRT/Windows SDK and asks you to accept Microsoft's licence (--accept-license below
# accepts it on your behalf: read https://go.microsoft.com/fwlink/?LinkId=2086102 first, or remove the flag).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:-$HOME/cudcampaign}"
JOBS="${JOBS:-$(nproc)}"
KISAK_COMMIT=8aadf94cc82795d6829ca06052996a5ec79001c3
XWIN_VER=0.10.0
D3DX_URL=https://api.nuget.org/v3-flatcontainer/microsoft.dxsdk.d3dx/9.29.952.8/microsoft.dxsdk.d3dx.9.29.952.8.nupkg
D3DX_SHA256=ead0906ae8a26c18a7525da7490127a2110f7c58f18293738283e30e97c6ea4b

for t in git cmake make clang-cl lld-link llvm-rc llvm-lib curl tar unzip; do
  command -v "$t" >/dev/null || { echo "missing tool: $t (Arch: pacman -S git cmake make clang lld llvm curl unzip; Debian/Ubuntu: apt install git cmake make clang lld llvm curl unzip)" >&2; exit 1; }
done
mkdir -p "$WORK/winsdk" && cd "$WORK"

echo "== 1/4 KisakCOD source + our patch"
if [ ! -d KisakCOD/.git ]; then git clone https://github.com/SwagSoftware/KisakCOD KisakCOD; fi
cd KisakCOD
if git apply --reverse --check "$HERE/kisakcod.patch" 2>/dev/null; then echo "patch already applied"
else git checkout -q "$KISAK_COMMIT" && git apply "$HERE/kisakcod.patch"; fi
cd "$WORK"

echo "== 2/4 Windows CRT + SDK (xwin)"
if [ ! -d winsdk/sdk/sdk ]; then
  cd winsdk
  [ -x xwin ] || { curl -fsSL "https://github.com/Jake-Shadle/xwin/releases/download/$XWIN_VER/xwin-$XWIN_VER-x86_64-unknown-linux-musl.tar.gz" | tar xz --strip-components=1 --wildcards '*/xwin'; }
  ./xwin --accept-license --arch x86 --cache-dir cache splat --output sdk
  cd "$WORK"
fi

echo "== 3/4 D3DX (nuget)"
if [ ! -d winsdk/d3dx/build/native ]; then
  curl -fsSL "$D3DX_URL" -o winsdk/d3dx.nupkg
  echo "$D3DX_SHA256  winsdk/d3dx.nupkg" | sha256sum -c --status || { echo "d3dx checksum mismatch" >&2; exit 1; }
  mkdir -p winsdk/d3dx && unzip -qo winsdk/d3dx.nupkg -d winsdk/d3dx
fi
[ -e winsdk/d3dx/build/native/Release ] || ln -s release winsdk/d3dx/build/native/Release   # cmake asks for "Release"

echo "== 4/4 configure + build"
export XWIN_DIR="$WORK/winsdk/sdk"
cd KisakCOD
cmake -S . -B build-linux -G "Unix Makefiles" -DCMAKE_TOOLCHAIN_FILE="$HERE/clang-cl-x86.cmake" \
  -DCMAKE_BUILD_TYPE=Release -DCICD=1 -DDXSDK_DIR="$WORK/winsdk/d3dx/build/native"
make -C build-linux -j"$JOBS" KisakCOD-sp
echo
echo "Built: $WORK/KisakCOD/bin/KisakCOD-sp.exe"
echo "Make the release zip with:  KISAK_DIR=$WORK/KisakCOD $HERE/release/make-release.sh"
