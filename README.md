# HP Victus BOE094D backlight investigation

Patch, source changes, build/install instructions, and test evidence for the brightness investigation on [advnpzn.dev](https://advnpzn.dev).

The laptop is a **Victus by HP Gaming Laptop 15-fb0xxx**, with a **BOE094D LCD**, running **CachyOS 7.3.0-4-cachyos**. The AMD driver classified the panel as OLED. Forcing PWM changed the selected backlight method, but a later OLED/LCD check still rejected the brightness command.

## Status

The first patch loaded after reboot (srcversion `33D40CAB47D3C514CE71FDF`), but **failed the physical brightness test**. The panel still reported OLED, and hardware readback stayed at 65536. Its correction ran too late because initial connector detection happens before a backlight index exists.

The canonical patch is now revision 2: it corrects the capability flags before the early return for an unassigned backlight index. It built successfully with srcversion `34FBAD0BCBFF145150C071C`, was installed, and was verified by SHA-256 inside the regenerated initramfs. **Its post-reboot physical test passed:** the panel reports LCD (2), and the user confirmed brightness changes using the function keys and taskbar slider. Suspend/resume remains untested.

No kernel or firmware downgrade was performed. The installed override is specific to `7.3.0-4-cachyos`; this repository does not automatically apply it to later kernels.

## Files

| Path | Contents |
| --- | --- |
| `patches/hp-victus-boe094d-lcd.patch` | Canonical, successfully tested revision-2 patch |
| `docs/manual-build.md` | Manual download, signature verification, compilation, and installation steps |
| `src/drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_backlight.c` | Full modified source file, retaining its upstream license header |
| `changes/limine.patch` | Actual persistent boot-configuration change from this investigation |
| `diagnostics/trace.py` | Temporary brightness tracepoint test, restoring the original brightness |
| `diagnostics/probe.py` | Temporary kprobes exposing the rejected command and swallowed failure |
| `evidence/probe-trace.txt` | Recorded trace from the unpatched running driver |
| `evidence/build.log` | Original successful compilation log |
| `evidence/build-v2.log` | Successful incremental build of revision 2 |
| `changes/attempt-1/` | Failed first patch, preserved for the investigation history |
| `evidence/reboot-v1.txt` | First patch loaded, but OLED classification and brightness remained wrong |
| `evidence/reboot-v2.txt` | Revised driver loaded, LCD classification confirmed, and user confirmed working brightness |
| `evidence/panel-edid.txt` | Decoded panel EDID |
| `evidence/observations.json` | Hardware IDs, checksums, observations, and testing status |
| `scripts/build-driver.sh` | Reproduction of the successful manual download/build steps |
| `scripts/install-driver.py` | Repository-relative copy of the installer used in the investigation |
| `scripts/verify-loaded-driver.sh` | Read-only checks after reboot; does not change brightness |
| `artifacts/` | Locally retained compiled driver and checksum; ignored by Git |

The original download and build tree remain in `~/.local/state/backlight-fix/`. The new scripts use repository-relative paths. They have been syntax-checked; the complete reproduction build script has not been rerun because the equivalent manual build already succeeded. Diagnostic scripts change brightness briefly and require root; they are preserved for reproducibility, not run automatically.

## Build

Clone this repository first:

```bash
git clone https://github.com/advnpzn/victus-backlight-fix.git
cd victus-backlight-fix
```

This build requires the exact `linux-cachyos-headers` for `7.3.0-4-cachyos`, the matching Clang/LLVM toolchain (the recorded build used **23.1.3**), and the normal kernel module build utilities. The machine already had these tools installed. The script downloads the matching signed CachyOS source archive and verifies its signature and recorded checksum.

```bash
bash scripts/build-driver.sh
```

For the individual commands, see [the manual build instructions](docs/manual-build.md).

It builds only the AMDGPU module, using the installed kernel's generated headers, configuration, and symbol table. Downloaded archives, the full source tree, and compiled binaries are ignored by Git.

To resume an already prepared build:

```bash
make -C build/cachyos-7.3.0-4 \
  M=drivers/gpu/drm/amd/amdgpu LLVM=1 -j6 modules
```

After a resumed build, repeat the staging/stripping/checksum steps at the end of `scripts/build-driver.sh` before installing.

## Install and verify

The driver is **already installed on the original machine**. The installer refuses to overwrite an existing local override unless its exact srcversion is explicitly supplied with `--replace-existing-srcversion`; in that case it backs up the previous override as well. For reproducing the installation on the same hardware and exact kernel:

```bash
sudo python scripts/install-driver.py
```

It preserves the packaged driver, installs an override under `updates/`, runs `depmod`, rebuilds only the current kernel's Limine initramfs, and checks the embedded module's checksum. It backs up the boot image and configuration first and restores them if installation or verification fails.

The original backup is `/var/lib/backlight-fix/driver-20261024-103943`. Revision history and installation results are recorded in `evidence/observations.json`.

After reboot:

```bash
bash scripts/verify-loaded-driver.sh
```

The original machine has passed the visible-brightness, keys, and slider checks; these are recorded in `evidence/observations.json`. Suspend/resume still needs testing. A clipped Plasma brightness popup was separately reproduced and resolved by restarting `plasma-plasmashell.service`, without changing or reloading the driver.

## Article

The article is maintained separately in [advnpzn/advnpzn.dev](https://github.com/advnpzn/advnpzn.dev), which uses Jekyll. It links to this repository for the patch and reproduction instructions. The original draft remains locally ignored under `article/`; it is not part of this repository's published files.

## Upstream

This is a local candidate quirk, not an accepted upstream fix. Post-reboot brightness has been tested; suspend/resume remains outstanding. The relevant trackers are [AMDGPU](https://gitlab.freedesktop.org/drm/amd/-/issues) and cross-link the report in [CachyOS's kernel tracker](https://github.com/CachyOS/linux-cachyos/issues). Maintainers may prefer a general correction to the interaction between forced PWM and panel classification.

The patch has no fabricated author, `Signed-off-by`, or `Tested-by` trailers. Add appropriate submission metadata only after review and actual hardware testing. Investigation, code, and article drafting were assisted by Codex. See the [kernel submission guide](https://docs.kernel.org/process/submitting-patches.html) for the current contribution process.
