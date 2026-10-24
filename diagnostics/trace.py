from pathlib import Path
import os
import time

trace = Path('/sys/kernel/tracing/instances') / f'backlight-check-{os.getpid()}'
bl = Path('/sys/class/backlight/amdgpu_bl2')
panel = Path('/sys/kernel/debug/dri/0000:06:00.0/eDP-1')
original = (bl / 'brightness').read_text()
trace.mkdir()
try:
    events = [p for p in (trace/'events/amdgpu_dm').iterdir()
              if any(s in p.name for s in ('brightness', 'backlight', 'abm', 'power'))]
    print('Matching events:', [p.name for p in events], flush=True)
    for p in events:
        if (p/'enable').exists(): (p/'enable').write_text('1')
    (trace/'tracing_on').write_text('1')
    for percent in (20, 60, 10):
        (bl/'brightness').write_text(str(65535*percent//100))
        time.sleep(2)
        print('Requested', percent, 'actual', (bl/'actual_brightness').read_text().strip(),
              'target_pwm', (panel/'amdgpu_target_backlight_pwm').read_text().strip(),
              'current_pwm', (panel/'amdgpu_current_backlight_pwm').read_text().strip(), flush=True)
    (trace/'tracing_on').write_text('0')
    print((trace/'trace').read_text()[-16000:])
    for name in ('psr_state','psr_capability','replay_state'):
        print(name, (panel/name).read_text().strip())
finally:
    (bl/'brightness').write_text(original)
    (trace/'tracing_on').write_text('0')
    trace.rmdir()
