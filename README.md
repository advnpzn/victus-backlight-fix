# HP Victus BOE094D brightness fix

This LCD advertises an OLED capability through DPCD. Forcing PWM with `amdgpu.backlight=0` selects the correct control method, but the OLED classification still prevents the LCD brightness command. The patch corrects the capability before panel detection, only for the HP/model/panel combination below.

## Tested system

| Component | Details |
| --- | --- |
| Laptop | HP Victus by HP Gaming Laptop 15-fb0xxx |
| BIOS | F.24 |
| Panel | BOE094D (`BOE`, product `0x094d`), LCD, 1920×1080 at 144 Hz |
| Internal-display GPU | AMD Cezanne, PCI `1002:1638` |
| Discrete GPU | NVIDIA RTX 3050 Mobile, PCI `10de:25a2` |
| OS | CachyOS Linux |
| Kernel | `7.3.0-4-cachyos` |
| Desktop | KDE Plasma 6.8.1, Wayland |
| Bootloader | Limine |
| Compiler | Clang/LLD 23.1.3 |

After reboot, the patched driver reports LCD (2), and brightness changes work with the function keys and taskbar slider. Suspend/resume is not yet tested. The test retained `acpi_osi=Linux acpi_backlight=native amdgpu.backlight=0`; these parameters alone had not fixed the issue.

## Download the source

These commands target the exact kernel above. Its matching `linux-cachyos-headers` must already be installed at `/usr/lib/modules/7.3.0-4-cachyos/build`. Build as your normal user with Clang/LLVM, make, patch, and the kernel build dependencies available. Run the commands in order and stop if any step fails.

```bash
git clone https://github.com/advnpzn/victus-backlight-fix.git
cd victus-backlight-fix

curl -fLO https://github.com/CachyOS/linux/releases/download/cachyos-7.3.0-4/cachyos-7.3.0-4.tar.gz
curl -fLO https://github.com/CachyOS/linux/releases/download/cachyos-7.3.0-4/cachyos-7.3.0-4.tar.gz.asc
curl -fL -o source-key.asc \
  https://keys.openpgp.org/vks/v1/by-fingerprint/E8B9AA39F054E30E8290D492C3C4820857F654FE
gpg --batch --dearmor --output source-key.gpg source-key.asc
gpgv --keyring "$PWD/source-key.gpg" \
  cachyos-7.3.0-4.tar.gz.asc cachyos-7.3.0-4.tar.gz
```

The signing fingerprint above belongs to Peter Jung and was checked against the [CachyOS package recipe](https://github.com/CachyOS/linux-cachyos/blob/master/linux-cachyos/PKGBUILD). The source archive SHA-256 is `3c82dd3ae8f12d10c81f46606bbc5ecb2b87efc7fb57519924bc4d6e5e79e0b1`.

## Apply the patch and build

```bash
tar -xzf cachyos-7.3.0-4.tar.gz
cp -a --reflink=auto /usr/lib/modules/7.3.0-4-cachyos/build/. cachyos-7.3.0-4/
patch --batch -d cachyos-7.3.0-4 -p1 < hp-victus-boe094d-lcd.patch
make -C cachyos-7.3.0-4 \
  M=drivers/gpu/drm/amd/amdgpu LLVM=1 -j6 modules

cp cachyos-7.3.0-4/drivers/gpu/drm/amd/amdgpu/amdgpu.ko amdgpu.ko
llvm-strip --strip-debug amdgpu.ko
modinfo -F vermagic ./amdgpu.ko
modinfo -F srcversion ./amdgpu.ko
```

This builds only AMDGPU. The recorded build has vermagic `7.3.0-4-cachyos SMP preempt mod_unload` and srcversion `34FBAD0BCBFF145150C071C`.

## Install and load

For the tested CachyOS/Limine setup, back up the boot image and any existing override, then install the module:

```bash
kernel=7.3.0-4-cachyos
test "$(uname -r)" = "$kernel"
test "$(modinfo -F vermagic ./amdgpu.ko | cut -d ' ' -f1)" = "$kernel"

boot_dir="/boot/$(cat /etc/machine-id)/linux-cachyos"
module_path="/usr/lib/modules/$kernel/updates/amdgpu.ko.zst"
backup_dir="/var/lib/backlight-fix/$(date +%Y%m%d-%H%M%S)"
sudo mkdir -p "$backup_dir"
sudo cp "$boot_dir/initramfs" "$backup_dir/initramfs"
sudo cp /boot/limine.conf "$backup_dir/limine.conf"
sudo cp /etc/default/limine "$backup_dir/limine-default"
if test -f "$module_path"; then
  sudo cp "$module_path" "$backup_dir/previous-amdgpu.ko.zst"
fi

zstd -T2 -19 amdgpu.ko -o amdgpu.ko.zst
sudo install -Dm644 amdgpu.ko.zst "$module_path"
sudo depmod -a "$kernel"
sudo limine-mkinitcpio linux-cachyos
modinfo -n amdgpu
modinfo -F srcversion amdgpu
```

The selected module should be the `updates/amdgpu.ko.zst` override. The packaged driver remains in place. Save your work and reboot to load the replacement:

```bash
reboot
```

After reboot:

```bash
cat /sys/module/amdgpu/srcversion
journalctl -b -k --no-pager | rg 'HP Victus BOE094D'
modetest -M amdgpu -c | rg -A3 panel_type
```

Expect srcversion `34FBAD0BCBFF145150C071C`, the LCD-correction message, and panel type LCD (2). Test the keys and slider visually. This override is specific to `7.3.0-4-cachyos`; later kernels require reviewing the patch and rebuilding against their matching source and headers.
