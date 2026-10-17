#!/usr/bin/env python3
"""Change the SotC launcher's settings (%APPDATA%/sotc-launcher/settings.json) from a shell.

The launcher keeps its settings in memory and writes them back when it saves, so editing the file
while SotC.exe runs is lost: this tool refuses then (--force skips the check). Every write keeps a
copy in settings.json.bak.

  sotc_cfg.py show                       settings the game run depends on
  sotc_cfg.py set KEY=VALUE ...          launcher keys (true/false/numbers parsed as JSON)
  sotc_cfg.py env                        list the variables of "Extra variables" (extra_env)
  sotc_cfg.py env NAME=VALUE ...         add or replace them; NAME= (empty) removes one
  sotc_cfg.py env --clear                remove them all
  sotc_cfg.py shot [PORT_DIR]            take a game-only screenshot now (needs `shots on`)
  sotc_cfg.py shots on|off              arm/disarm the screenshot trigger (BB_FRAME_DUMP_TRIGGER)
  sotc_cfg.py log [PORT_DIR] [N]         FPS by workload from user/last_run.log (N = older log)
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SETTINGS = Path(os.environ.get('APPDATA', Path.home())) / 'sotc-launcher' / 'settings.json'
DEFAULT_PORT = Path(__file__).resolve().parents[2] / 'prueba a ver que' / 'SotC-PC-opt4'
# The launcher splits "Extra variables" on spaces, so the trigger path must have none.
TRIGGER = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Temp' / 'sotc-shot.trigger'
SHOWN = ('output_res', 'upscaler', 'sharpness', 'fps60', 'af16', 'neo', 'fullscreen',
         'present_mode', 'perf_record_thread', 'perf_dma', 'perf_culling', 'gpu_submit',
         'show_fps', 'fx_fog', 'fx_ssao', 'fx_vignette', 'ui_language', 'language', 'extra_env',
         'engine_cvars')


def running():
    try:
        out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True,
                             timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    names = {line.split(',')[0].strip('"').lower() for line in out.splitlines() if line}
    return [n for n in ('sotc.exe', 'bb-probe.exe') if n in names]


def load():
    return json.loads(SETTINGS.read_text(encoding='utf-8'))


def save(s, force):
    busy = running()
    if busy and not force:
        sys.exit(f'Not written: {", ".join(busy)} is running (the launcher would overwrite it). '
                 'Close it or pass --force.')
    shutil.copy2(SETTINGS, SETTINGS.with_suffix('.json.bak'))
    SETTINGS.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding='utf-8')


def parse_value(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def env_items(s):
    items = {}
    for item in str(s.get('extra_env', '')).split():
        if '=' in item:
            key, value = item.split('=', 1)
            items[key] = value
    return items


def set_env(s, items):
    s['extra_env'] = ' '.join(f'{k}={v}' for k, v in items.items())


def port_dir(args):
    return Path(args[0]) if args else DEFAULT_PORT


def fps_summary(log):
    buckets = {}
    for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
        m = re.match(r'SOTC FPS ([\d.]+) at (\d+)s; (\d+) cmds', line)
        if not m:
            continue
        fps, cmds = float(m.group(1)), int(m.group(3))
        key = ('<2k menus' if cmds < 2000 else '2-4k' if cmds < 4000 else
               '4-6k' if cmds < 6000 else '6k+')
        buckets.setdefault(key, []).append(fps)
    if not buckets:
        print(f'{log}: no SOTC FPS lines (turn on show_fps)')
    for key in sorted(buckets):
        v = buckets[key]
        print(f'  cmds {key:9}: {len(v):3} windows of 5 s, mean {sum(v) / len(v):5.1f} FPS, '
              f'min {min(v):5.1f}')


def main(argv):
    force = '--force' in argv
    argv = [a for a in argv if a != '--force']
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return
    cmd, args = argv[0], argv[1:]
    if cmd == 'show':
        s = load()
        for key in SHOWN:
            print(f'{key:20} = {json.dumps(s.get(key), ensure_ascii=False)}')
        busy = running()
        print('running:', ', '.join(busy) if busy else 'nothing')
    elif cmd == 'set':
        s = load()
        for item in args:
            key, value = item.split('=', 1)
            if key not in s:
                print(f'warning: {key} is not in settings.json yet')
            s[key] = parse_value(value)
        save(s, force)
        print('saved')
    elif cmd == 'env':
        s = load()
        if not args:
            for k, v in env_items(s).items():
                print(f'{k}={v}')
            return
        items = {} if args == ['--clear'] else env_items(s)
        for item in args:
            if item == '--clear':
                continue
            key, value = item.split('=', 1)
            if value == '':
                items.pop(key, None)
            else:
                items[key] = value
        set_env(s, items)
        save(s, force)
        print('extra_env =', s['extra_env'])
    elif cmd == 'shots':
        state = args[0] if args else 'on'
        trigger = TRIGGER
        s = load()
        items = env_items(s)
        if state == 'on':
            items['BB_FRAME_DUMP_TRIGGER'] = str(trigger)
        else:
            items.pop('BB_FRAME_DUMP_TRIGGER', None)
        set_env(s, items)
        save(s, force)
        print('extra_env =', s['extra_env'])
    elif cmd == 'shot':
        TRIGGER.parent.mkdir(parents=True, exist_ok=True)
        TRIGGER.touch()
        print('requested:', TRIGGER, '-> screenshots in', port_dir(args) / 'user' / 'screenshots')
    elif cmd == 'log':
        base = port_dir(args[:1]) / 'user'
        n = args[1] if len(args) > 1 else ''
        fps_summary(base / (f'last_run.{n}.log' if n else 'last_run.log'))
    else:
        sys.exit(f'unknown command {cmd} (see --help)')


if __name__ == '__main__':
    main(sys.argv[1:])
