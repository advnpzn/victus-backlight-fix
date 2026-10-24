#!/usr/bin/python
"""Install the version-specific HP/BOE driver correction with boot-image backup."""
from pathlib import Path
import argparse
import datetime
import hashlib
import os
import shutil
import subprocess
import tempfile

release = '7.3.0-4-cachyos'
repo = Path(__file__).resolve().parents[1]
work = repo/'artifacts'
module = work/'amdgpu-victus.ko'
target = Path('/usr/lib/modules')/release/'updates/amdgpu.ko.zst'
machine = Path('/etc/machine-id').read_text().strip()
initramfs = Path('/boot')/machine/'linux-cachyos/initramfs'
boot = Path('/boot/limine.conf')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--replace-existing-srcversion', help='Replace only an override with this exact srcversion, backing it up first.')
args = parser.parse_args()

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def output(args):
    return subprocess.check_output(args, text=True).strip()

if os.geteuid() != 0 or os.uname().release != release:
    raise SystemExit('Requires root and the inspected kernel version.')
replacing = target.exists()
if replacing:
    existing = output(['modinfo', '-F', 'srcversion', str(target)])
    if existing != args.replace_existing_srcversion:
        raise SystemExit(f'Existing override {existing}; explicitly specify its srcversion to replace it.')
elif args.replace_existing_srcversion:
    raise SystemExit('Expected an existing override to replace, but none was found.')
if not initramfs.is_file() or not boot.is_file():
    raise SystemExit('Expected Limine boot files not found.')
if output(['modinfo','-F','vermagic',str(module)]).split()[0] != release:
    raise SystemExit('Module kernel version mismatch.')
expected = (work/'amdgpu-victus.sha256').read_text().split()[0]
if hashlib.sha256(module.read_bytes()).hexdigest() != expected:
    raise SystemExit('Module checksum differs from the validated build.')
backup = Path('/var/lib/backlight-fix')/datetime.datetime.now().strftime('driver-%Y%m%d-%H%M%S')
backup.mkdir(parents=True, mode=0o700)
shutil.copy2(initramfs, backup/'initramfs')
shutil.copy2(boot, backup/'limine.conf')
shutil.copy2('/etc/default/limine', backup/'limine-default')
shutil.copy2(repo/'patches/hp-victus-boe094d-lcd.patch', backup/'driver.patch')
if replacing:
    shutil.copy2(target, backup/'previous-amdgpu.ko.zst')
(backup/'stock-module-path').write_text(output(['modinfo','-k',release,'-n','amdgpu'])+'\n')
print(f'Boot-image backup: {backup}', flush=True)
try:
    target.parent.mkdir(exist_ok=True)
    if replacing:
        target.unlink()
    run(['zstd','-q','-T2','-19',str(module),'-o',str(target)])
    target.chmod(0o644)
    run(['depmod','-a',release])
    selected = Path(output(['modinfo','-k',release,'-n','amdgpu'])).resolve()
    if selected != target.resolve():
        raise RuntimeError(f'Module selection did not pick the override: {selected}')
    run(['/usr/bin/limine-mkinitcpio','linux-cachyos'])
    # Verify the exact rebuilt driver is present in the image used at boot.
    with tempfile.TemporaryDirectory(prefix='verify-initramfs-') as tmp:
        run(['lsinitcpio','-x',str(initramfs)],cwd=tmp,stdout=subprocess.DEVNULL)
        embedded = list(Path(tmp).rglob('amdgpu.ko*'))
        if len(embedded) != 1:
            raise RuntimeError(f'Expected one AMDGPU driver in initramfs; found {embedded}')
        p = embedded[0]
        data = subprocess.check_output(['zstd','-dc',str(p)]) if p.suffix == '.zst' else p.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('Initramfs driver checksum does not match the patched driver.')
        print(f'Verified patched driver inside initramfs: {p.relative_to(tmp)}',flush=True)
    print('Driver installed for the current kernel. Restart required to load it.',flush=True)
    print(f'Backup: {backup}',flush=True)
except Exception:
    target.unlink(missing_ok=True)
    if replacing:
        shutil.copy2(backup/'previous-amdgpu.ko.zst', target)
    run(['depmod','-a',release])
    shutil.copy2(backup/'initramfs',initramfs)
    shutil.copy2(backup/'limine.conf',boot)
    subprocess.run(['/usr/bin/limine-enroll-config'],check=False)
    print('Installation failed; restored previous module selection and boot files.',flush=True)
    raise
