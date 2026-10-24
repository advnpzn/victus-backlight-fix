from pathlib import Path
import os
import time

root = Path('/sys/kernel/tracing')
group = f'backlight_probe_{os.getpid()}'
trace = root/'instances'/group
events = root/'kprobe_events'
bl = Path('/sys/class/backlight/amdgpu_bl2/brightness')
original = bl.read_text()
created = []
trace.mkdir()
def command(s):
    fd = os.open(events, os.O_WRONLY)
    try: os.write(fd, (s+'\n').encode())
    finally: os.close(fd)
try:
    probes = {
        'percent': 'p:{g}/percent amdgpu:mod_power_set_backlight_percent percent=$arg3:u32',
        'percent_return': 'r:{g}/percent_return amdgpu:mod_power_set_backlight_percent result=$retval:u8',
        'pwm': 'p:{g}/pwm amdgpu:backlight_millipercent_to_pwm percent=$arg2:u32',
        'pwm_return': 'r:{g}/pwm_return amdgpu:backlight_millipercent_to_pwm pwm=$retval:u32',
        'fill': 'p:{g}/fill amdgpu:fill_backlight_level_params pwm=$arg5:u32 control=$arg6:u32',
        'link_return': 'r:{g}/link_return amdgpu:dc_link_set_backlight_level result=$retval:u8',
        'hw_return': 'r:{g}/hw_return amdgpu:dcn21_set_backlight_level result=$retval:u8',
        'dmub_pwm': 'p:{g}/dmub_pwm amdgpu:dmub_abm_set_backlight_level_pwm_ex pwm=$arg2:u32',
        'legacy_pwm': 'p:{g}/legacy_pwm amdgpu:dce_abm_set_backlight_level_pwm pwm=$arg2:u32',
        'dmub_return': 'r:{g}/dmub_return amdgpu:dmub_abm_set_backlight_level_pwm_ex result=$retval:u8',
        'lcd_pwm': 'p:{g}/lcd_pwm amdgpu:dmub_abm_set_backlight_level pwm=$arg2:u32',
        'cacp_pwm': 'p:{g}/cacp_pwm amdgpu:dmub_cacp_set_backlight_level pwm=$arg2:u32',
    }
    for name, spec in probes.items():
        command(spec.format(g=group))
        created.append(name)
    (trace/'events'/group/'enable').write_text('1')
    (trace/'tracing_on').write_text('1')
    for value in (13107,39321):
        bl.write_text(str(value))
        time.sleep(1)
    (trace/'tracing_on').write_text('0')
    result = (trace/'trace').read_text()
    (Path(__file__).resolve().parents[1]/'evidence/probe-trace-latest.txt').write_text(result)
    print(result[-18000:])
finally:
    bl.write_text(original)
    (trace/'tracing_on').write_text('0')
    if (trace/'events'/group/'enable').exists():
        (trace/'events'/group/'enable').write_text('0')
    trace.rmdir()
    for name in reversed(created): command(f'-:{group}/{name}')
