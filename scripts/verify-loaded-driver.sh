#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
echo "Kernel: $(uname -r)"
echo "Module selected on disk: $(modinfo -n amdgpu)"
echo "Module srcversion on disk: $(modinfo -F srcversion amdgpu)"
loaded_version=$(cat /sys/module/amdgpu/srcversion)
echo "Module srcversion loaded now: $loaded_version"

expected_version=$(modinfo -F srcversion "$repo_dir/artifacts/amdgpu-victus.ko")
if [[ $loaded_version != "$expected_version" ]]; then
    echo 'The staged patched driver is not loaded. Post-reboot testing remains pending.'
    exit 2
fi

echo 'The loaded module matches the staged patched module by srcversion.'
journalctl -b -k --no-pager | rg 'HP Victus BOE094D|brightness curve' || true
connector_info=$(modetest -M amdgpu -c)
panel_info=$(printf '%s\n' "$connector_info" | rg -A3 'panel_type' || true)
printf '%s\n' "$panel_info"
panel_failed=false
if ! printf '%s\n' "$panel_info" | rg -q 'value: 2$'; then
    echo 'LCD classification has not been confirmed; a matching driver version does not mean the fix worked.'
    panel_failed=true
fi
for backlight in /sys/class/backlight/amdgpu_bl*; do
    [[ -d $backlight ]] || continue
    echo "Backlight: ${backlight##*/}"
    for field in brightness actual_brightness max_brightness; do
        echo "$field: $(cat "$backlight/$field")"
    done
done
echo 'Now test the slider/keys visually at several levels and after suspend/resume.'
echo 'A loaded module alone does not establish that the physical brightness fix works.'
if [[ "$panel_failed" == true ]]; then
    exit 3
fi
