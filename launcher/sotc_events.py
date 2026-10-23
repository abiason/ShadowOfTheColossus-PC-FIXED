# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded session event journal; failures must never prevent playing the game."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import threading
import time
import uuid

MAX_BYTES = 2 * 1024 * 1024
KEPT = 3
ENVIRONMENT = ('SOTC_MODES', 'BB_FPS_LIMIT', 'BB_VBLANK_HZ', 'BB_DMEM_MB',
               'SOTC_NEO', 'BB_DIRECT_MEMORY_ACCESS', 'BB_READBACKS', 'SOTC_RB_ASYNC',
               'SOTC_RB_HOT', 'SOTC_LOD_LINGER', 'SOTC_LOD_POOL_LOW', 'SOTC_HEAP_WATCH',
               'SOTC_PARALLEL_WARMUP', 'SOTC_EOP_DEFER', 'SOTC_OUTPUT_RES',
               'BB_FSR1', 'BB_RCAS', 'BB_RCAS_ATTENUATION', 'SOTC_CVARS')
SETTINGS = ('fps60', 'neo', 'fullscreen', 'output_res', 'upscaler', 'preset',
            'sharpness', 'af16', 'perf_dma', 'volume', 'mouse', 'mouse_sens')
FPS = re.compile(r'^SOTC FPS ([0-9.]+) at ([0-9]+)s;')
VRAM = re.compile(r'vram ([0-9]+)/([0-9]+) MB')


def _value(value):
    if isinstance(value, (bool, int)) or value is None:
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return str(value)[:512]


def _system(game):
    result = {'platform': platform.system(), 'release': platform.release(),
              'machine': platform.machine(), 'logical_cpus': os.cpu_count()}
    try:
        pages, page_size = os.sysconf('SC_PHYS_PAGES'), os.sysconf('SC_PAGE_SIZE')
        if pages > 0 and page_size > 0:
            result['ram_bytes'] = pages * page_size
    except (AttributeError, OSError, ValueError):
        pass
    if os.name != 'nt' and game:
        try:
            device = os.stat(game).st_dev
            block = Path(f'/sys/dev/block/{os.major(device)}:{os.minor(device)}').resolve()
            for candidate in (block / 'queue/rotational', block.parent / 'queue/rotational'):
                if candidate.is_file():
                    value = candidate.read_text().strip()
                    if value in ('0', '1'):
                        result['disk_rotational'] = value == '1'
                    break
        except (OSError, ValueError):
            pass
    return result


class SessionEvents:
    def __init__(self, directory, settings, version='', max_bytes=MAX_BYTES):
        self.path = Path(directory) / 'events.log'
        self.session = uuid.uuid4().hex
        self.started_at = time.monotonic()
        self.pid = None
        self._stream = None
        self._size = 0
        self._max_bytes = max_bytes
        self._lock = threading.RLock()
        self._last_performance = -math.inf
        self._errors = 0
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._stream = self.path.open('ab', buffering=0)
            self._size = os.fstat(self._stream.fileno()).st_size
        except OSError:
            self.close()
        self.emit('launch_requested', launcher_version=version, system=_system(settings.get('game_dir')),
                  settings={key: _value(settings[key]) for key in SETTINGS if key in settings})

    def _rotate(self):
        self._stream.close()
        self._stream = None
        for index in range(KEPT - 1, 0, -1):
            source = self.path if index == 1 else self.path.with_name(f'events.{index - 1}.log')
            if source.exists():
                source.replace(self.path.with_name(f'events.{index}.log'))
        self._stream = self.path.open('ab', buffering=0)
        self._size = 0

    def emit(self, event, **fields):
        with self._lock:
            if self._stream is None:
                return
            record = {'schema': 1, 'time': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
                      'elapsed_s': round(max(0, time.monotonic() - self.started_at), 3),
                      'session': self.session, 'pid': self.pid, 'event': event, **fields}
            try:
                data = (json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
            except (TypeError, ValueError):
                return
            if len(data) > self._max_bytes:
                return
            try:
                if self._size + len(data) > self._max_bytes:
                    self._rotate()
                self._stream.write(data)
                self._size += len(data)
            except OSError:
                self.close()

    def configuration(self, environment):
        self.emit('configuration_requested', environment={key: _value(environment[key])
                  for key in ENVIRONMENT if key in environment})

    def process_started(self, pid):
        self.pid = pid
        self.emit('process_started')

    def observe(self, line):
        text = line[:2048].strip()
        match = FPS.match(text)
        if match:
            now = time.monotonic()
            if now - self._last_performance >= 60:
                try:
                    fields = {'fps': float(match[1]), 'game_seconds': int(match[2])}
                except ValueError:
                    return
                if not math.isfinite(fields['fps']):
                    return
                self._last_performance = now
                vram = VRAM.search(text)
                if vram:
                    fields.update(vram_used_mb=int(vram[1]), vram_total_mb=int(vram[2]))
                self.emit('performance', **fields)
        elif text.startswith(('Guest fault', 'Host fault', 'Fault (signal', 'STOP:', 'ERROR:')) or \
                (text.startswith('GPU ') and ('<Error>' in text or '<Critical>' in text)):
            self._errors += 1
            if self._errors <= 100:
                self.emit('runtime_error', message=text[:1024])
            elif self._errors == 101:
                self.emit('runtime_errors_suppressed', limit=100)
        elif 'Entering original x86-64 code' in text:
            self.emit('game_entry')
        elif text.startswith('SOTC pipeline cache:'):
            self.emit('shader_preload', message=text[:512])
        elif text.startswith(('GPU:', 'VideoOut:', 'Upscaler:', 'SOTC HEAPS:', 'SOTC LOD:')):
            self.emit('runtime_status', message=text[:512])
        elif 'st_gameflow() starting game' in text:
            self.emit('load_started')
        elif text.startswith("Runtime: save data '") and ' mounted at ' in text:
            self.emit('save_mounted', read_only='read-only' in text, message=text[:512])

    def launch_failed(self, error):
        with self._lock:
            self.emit('launch_failed', message=str(error)[:1024])
            self.close()

    def finish(self, code, stopped=False):
        with self._lock:
            self.emit('process_exit', code=code,
                      outcome='stopped' if stopped else 'exited' if code == 0 else 'failed')
            self.close()

    def close(self):
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.close()
                except OSError:
                    pass
                self._stream = None
