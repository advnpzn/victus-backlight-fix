#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help ]]; then
    echo 'Build the HP/BOE AMDGPU patch for 7.3.0-4-cachyos. Does not install it.'
    echo 'Run from any directory; downloads and build output stay in this repository.'
    exit 0
fi

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
kernel_release=7.3.0-4-cachyos
source_name=cachyos-7.3.0-4
header_dir=/usr/lib/modules/$kernel_release/build
download_dir=$repo_dir/downloads
build_dir=$repo_dir/build/$source_name
artifact_dir=$repo_dir/artifacts
source_url=https://github.com/CachyOS/linux/releases/download/$source_name/$source_name.tar.gz
source_fingerprint=E8B9AA39F054E30E8290D492C3C4820857F654FE

if (( EUID == 0 )); then
    echo 'Build as your regular user; only installation needs root.' >&2
    exit 1
fi
for tool in curl tar cp patch make clang ld.lld llvm-strip sha256sum gpg gpgv modinfo python; do
    command -v "$tool" >/dev/null
done
[[ -f $header_dir/.config && -f $header_dir/Module.symvers ]]
if [[ -e $build_dir ]]; then
    echo "Build directory already exists: $build_dir" >&2
    echo 'To resume a prepared build, run the make command documented in README.md.' >&2
    exit 1
fi
mkdir -p "$download_dir/gnupg" "$repo_dir/build" "$artifact_dir"
chmod 700 "$download_dir/gnupg"
for suffix in '' .asc; do
    curl -fL --connect-timeout 10 --max-time 300 --retry 1 \
        "$source_url$suffix" -o "$download_dir/$source_name.tar.gz$suffix"
done
curl -fL --connect-timeout 10 --max-time 30 \
    "https://keys.openpgp.org/vks/v1/by-fingerprint/$source_fingerprint" \
    -o "$download_dir/source-key.asc"
gpg --homedir "$download_dir/gnupg" --batch --yes --dearmor \
    --output "$download_dir/source-key.gpg" "$download_dir/source-key.asc"
gpgv --keyring "$download_dir/source-key.gpg" \
    "$download_dir/$source_name.tar.gz.asc" "$download_dir/$source_name.tar.gz"

# Pin the archive to the exact signed source used in the recorded investigation.
python - "$repo_dir" <<'PY'
from pathlib import Path
import hashlib, json, sys
root = Path(sys.argv[1])
expected = json.loads((root/'evidence/observations.json').read_text())['source_archive_sha256']
actual = hashlib.sha256((root/'downloads/cachyos-7.3.0-4.tar.gz').read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit('Source archive differs from the recorded build.')
print('Verified source archive checksum.')
PY

tar -xzf "$download_dir/$source_name.tar.gz" -C "$repo_dir/build"
cp -a --reflink=auto "$header_dir/." "$build_dir/"
patch --batch -d "$build_dir" -p1 < "$repo_dir/patches/hp-victus-boe094d-lcd.patch"
make -C "$build_dir" M=drivers/gpu/drm/amd/amdgpu LLVM=1 -j"${JOBS:-6}" modules \
    2>&1 | tee "$artifact_dir/build.log"
cp --reflink=auto "$build_dir/drivers/gpu/drm/amd/amdgpu/amdgpu.ko" \
    "$artifact_dir/amdgpu-victus.ko"
llvm-strip --strip-debug "$artifact_dir/amdgpu-victus.ko"
vermagic=$(modinfo -F vermagic "$artifact_dir/amdgpu-victus.ko")
[[ ${vermagic%% *} == "$kernel_release" ]]
(cd "$artifact_dir" && sha256sum amdgpu-victus.ko > amdgpu-victus.sha256)
echo "Built and staged $artifact_dir/amdgpu-victus.ko"
