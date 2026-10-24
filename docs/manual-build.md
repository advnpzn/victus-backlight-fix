# Build and install for the recorded CachyOS kernel

These steps reproduce the tested HP Victus BOE094D correction for **7.3.0-4-cachyos**. They require that kernel's installed headers/build files and the matching Clang/LLVM toolchain (23.1.3 in the recorded build). The patch matches HP + Victus by HP Gaming Laptop 15-fb0xxx + BOE094D on eDP. This is not an installer for arbitrary kernels or bootloaders.

The supported automated entry point is `bash scripts/build-driver.sh`. It performs the same steps, checks prerequisites, verifies the recorded source checksum, and refuses to overwrite an existing build directory. The full reproduction script was syntax-checked; the equivalent manual build and the revised install script were actually run on the original laptop.

## Download and verify

Run as your normal user, from the repository root:

```bash
mkdir -p downloads build artifacts
curl -fL -o downloads/cachyos-7.3.0-4.tar.gz \
  https://github.com/CachyOS/linux/releases/download/cachyos-7.3.0-4/cachyos-7.3.0-4.tar.gz
curl -fL -o downloads/cachyos-7.3.0-4.tar.gz.asc \
  https://github.com/CachyOS/linux/releases/download/cachyos-7.3.0-4/cachyos-7.3.0-4.tar.gz.asc
curl -fL -o downloads/source-key.asc \
  https://keys.openpgp.org/vks/v1/by-fingerprint/E8B9AA39F054E30E8290D492C3C4820857F654FE
gpg --batch --dearmor --output downloads/source-key.gpg downloads/source-key.asc
gpgv --keyring "$PWD/downloads/source-key.gpg" \
  downloads/cachyos-7.3.0-4.tar.gz.asc downloads/cachyos-7.3.0-4.tar.gz
sha256sum downloads/cachyos-7.3.0-4.tar.gz
```

The source-signing fingerprint is `E8B9AA39F054E30E8290D492C3C4820857F654FE`, checked against the [CachyOS package recipe](https://github.com/CachyOS/linux-cachyos/blob/master/linux-cachyos/PKGBUILD). Verification on the original download reported a good signature from Peter Jung. The archive SHA-256 must match:

```text
3c82dd3ae8f12d10c81f46606bbc5ecb2b87efc7fb57519924bc4d6e5e79e0b1
```

## Prepare and compile

Use a fresh build directory. Do not reapply the patch to an already patched tree.

```bash
tar -xzf downloads/cachyos-7.3.0-4.tar.gz -C build
cp -a --reflink=auto /usr/lib/modules/7.3.0-4-cachyos/build/. \
  build/cachyos-7.3.0-4/
patch --batch -d build/cachyos-7.3.0-4 -p1 \
  < patches/hp-victus-boe094d-lcd.patch
make -C build/cachyos-7.3.0-4 \
  M=drivers/gpu/drm/amd/amdgpu LLVM=1 -j6 modules \
  > artifacts/build.log 2>&1
```

Check that `make` succeeds before continuing. This builds the AMDGPU module, not a whole replacement kernel image. The header overlay provides the installed kernel configuration, generated headers, and symbol table.

## Stage and inspect

```bash
cp --reflink=auto build/cachyos-7.3.0-4/drivers/gpu/drm/amd/amdgpu/amdgpu.ko \
  artifacts/amdgpu-victus.ko
llvm-strip --strip-debug artifacts/amdgpu-victus.ko
(cd artifacts && sha256sum amdgpu-victus.ko > amdgpu-victus.sha256)
modinfo -F vermagic artifacts/amdgpu-victus.ko
modinfo -F srcversion artifacts/amdgpu-victus.ko
```

Recorded revision-2 results:

```text
vermagic:   7.3.0-4-cachyos SMP preempt mod_unload
srcversion: 34FBAD0BCBFF145150C071C
```

The recorded binary checksum is in `evidence/observations.json`. Byte-for-byte reproducibility across different build paths/environments has not been established; the installer checks the staged module against its freshly generated checksum and verifies that exact payload in the initramfs.

## Install and reboot

For a first local override on the inspected kernel and Limine layout:

```bash
sudo python scripts/install-driver.py
```

The installer backs up the current boot image and Limine configuration under `/var/lib/backlight-fix/`, preserves the packaged module, installs `updates/amdgpu.ko.zst`, runs `depmod`, rebuilds the current kernel's Limine initramfs, and verifies its embedded module checksum. If installation fails, it restores the previous override selection and boot files.

If replacing the failed revision 1 specifically, the explicit replacement command is:

```bash
sudo python scripts/install-driver.py \
  --replace-existing-srcversion 33D40CAB47D3C514CE71FDF
```

That option refuses an override with any other srcversion and backs up the previous override before replacing it. Do not rerun installation on the original machine merely to test it: revision 2 is already installed and working.

Save your work and reboot when installation completes. Do not unload the active graphics driver from the running desktop session.

## Verify

```bash
bash scripts/verify-loaded-driver.sh
```

Confirm all of the following:

- The loaded module matches the staged revision-2 module.
- The correction message appears in the boot log.
- The internal panel reports LCD (2).
- The keys and slider visibly change brightness.
- Brightness continues to work after suspend/resume when tested.

The original machine passed the post-reboot, LCD-classification, keys, and slider checks. Suspend/resume has not yet been tested. Full evidence is in `evidence/observations.json` and `evidence/reboot-v2.txt`.

The override is tied to this kernel version. Future kernels require reviewing applicability and rebuilding for their exact ABI; this repository does not automatically reapply the fix after updates.
