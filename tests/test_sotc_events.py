"""Session journal and launcher integration, with real short-lived fixture processes."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'launcher'))
import sotc_events


def records(directory):
    return [json.loads(line) for line in (directory / 'events.log').read_text().splitlines()]


class SessionEventTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        system = patch.object(sotc_events, '_system', return_value={'platform': 'fixture'})
        system.start()
        self.addCleanup(system.stop)

    def session(self, **kwargs):
        result = sotc_events.SessionEvents(self.root, {'fps60': True, 'neo': True}, **kwargs)
        self.addCleanup(result.close)
        return result

    def test_session_settings_are_whitelisted_and_unicode_is_valid_json(self):
        events = self.session(version='teste ç')
        events.configuration({'SOTC_MODES': 'fps60game', 'BB_FPS_LIMIT': '60', 'API_KEY': 'do-not-record'})
        events.process_started(123)
        events.observe('Entering original x86-64 code at guest offset 0xf120')
        events.finish(0)
        data = records(self.root)
        self.assertEqual([item['event'] for item in data],
                         ['launch_requested', 'configuration_requested', 'process_started',
                          'game_entry', 'process_exit'])
        self.assertEqual(data[0]['launcher_version'], 'teste ç')
        self.assertEqual(data[1]['environment'], {'SOTC_MODES': 'fps60game', 'BB_FPS_LIMIT': '60'})
        self.assertNotIn('do-not-record', (self.root / 'events.log').read_text())
        self.assertEqual(len({item['session'] for item in data}), 1)
        self.assertTrue(all(item['schema'] == 1 and item['time'].endswith('+00:00') for item in data))
        self.assertEqual(data[-1]['pid'], 123)
        self.assertEqual(data[-1]['outcome'], 'exited')

    def test_performance_is_sampled_once_per_minute_and_bad_lines_do_not_consume_interval(self):
        clock = [0.0]
        with patch.object(sotc_events.time, 'monotonic', side_effect=lambda: clock[0]):
            events = self.session()
            events.observe('SOTC FPS . at 5s;')
            events.observe('SOTC FPS 44.3 at 5s; vram 512/8192 MB')
            clock[0] = 59.9
            events.observe('SOTC FPS 33.0 at 60s; vram 700/8192 MB')
            clock[0] = 60
            events.observe('SOTC FPS 55.0 at 65s; vram 800/8192 MB')
            events.finish(0)
        samples = [item for item in records(self.root) if item['event'] == 'performance']
        self.assertEqual([item['fps'] for item in samples], [44.3, 55.0])
        self.assertEqual(samples[-1]['game_seconds'], 65)
        self.assertEqual(samples[-1]['vram_used_mb'], 800)

    def test_error_flood_is_bounded_and_load_status_is_recorded(self):
        events = self.session()
        events.observe('noise that should not become an event')
        events.observe('SOTC pipeline cache: preloaded 3024 pipelines in 100 ms (12 threads)')
        events.observe('st_gameflow() starting game')
        events.observe("Runtime: save data 'slot0' mounted at /savedata0 (existing, read-only)")
        events.observe('SOTC HEAPS: image unavailable or unsupported; watcher not started')
        events.observe('SOTC command processor: idle yield on')
        for _ in range(110):
            events.observe('Guest fault (signal 11) at guest offset 0x49500')
        events.finish(139)
        data = records(self.root)
        self.assertEqual(sum(item['event'] == 'runtime_error' for item in data), 100)
        self.assertEqual(sum(item['event'] == 'runtime_errors_suppressed' for item in data), 1)
        self.assertIn('shader_preload', {item['event'] for item in data})
        self.assertIn('load_started', {item['event'] for item in data})
        self.assertTrue(next(item for item in data if item['event'] == 'save_mounted')['read_only'])
        self.assertTrue(any(item.get('message') == 'SOTC command processor: idle yield on' for item in data))
        self.assertEqual(data[-1]['outcome'], 'failed')

    def test_rotation_preserves_complete_utf8_records_with_bounded_files(self):
        events = self.session(max_bytes=2048)
        for index in range(50):
            events.emit('fixture', index=index, message='á漢' * 40)
        events.finish(0)
        logs = list(self.root.glob('events*.log'))
        self.assertEqual(len(logs), 3)
        for path in logs:
            self.assertLessEqual(path.stat().st_size, 2048)
            self.assertTrue(all(json.loads(line) for line in path.read_text().splitlines()))
        self.assertEqual(records(self.root)[-1]['event'], 'process_exit')

    def test_unwritable_journal_does_not_raise_or_replace_existing_path(self):
        (self.root / 'events.log').mkdir()
        events = self.session()
        events.configuration({'SOTC_MODES': 'fps60game'})
        events.process_started(123)
        events.observe('ERROR: fixture')
        events.finish(0)
        self.assertTrue((self.root / 'events.log').is_dir())

    def test_concurrent_stop_and_reader_events_remain_complete(self):
        events = self.session()
        threads = [threading.Thread(target=lambda n=n: [events.emit('fixture', thread=n, index=i)
                                                       for i in range(25)]) for n in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        events.finish(-15, stopped=True)
        data = records(self.root)
        self.assertEqual(len({(x['thread'], x['index']) for x in data if x['event'] == 'fixture'}), 100)
        self.assertEqual(data[-1]['outcome'], 'stopped')


@unittest.skipIf(os.name == 'nt', 'Linux fixture subprocess integration')
class LauncherEventTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        spec = importlib.util.spec_from_file_location('event_launcher', ROOT / 'launcher/sotc_launcher_win.py')
        self.launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.launcher)
        self.settings = copy.deepcopy(self.launcher.APP_DEFAULTS)
        self.settings.update(game_dir=str(self.root), user_dir=str(self.root / 'user'), fps60=True)
        keys = patch.object(self.launcher, 'write_key_bindings')
        keys.start()
        self.addCleanup(keys.stop)

    def run_fixture(self, code):
        script = ("print('Entering original x86-64 code at guest offset 0xf120'); "
                  "print('SOTC FPS 44.3 at 5s; vram 512/8192 MB'); "
                  "print('ERROR: simulated failure' if %d else 'fixture done'); "
                  "raise SystemExit(%d)" % (code, code))
        with patch.object(self.launcher, 'run_command', return_value=[sys.executable, '-c', script]), \
             patch.object(self.launcher.sys, 'stdout', io.StringIO()):
            self.assertEqual(self.launcher.play_without_window(self.settings), code)
        return records(self.root / 'user')

    def test_headless_real_child_success_and_raw_log_are_preserved(self):
        data = self.run_fixture(0)
        self.assertIn('game_entry', {item['event'] for item in data})
        self.assertEqual(data[-1]['code'], 0)
        self.assertEqual(data[-1]['outcome'], 'exited')
        self.assertIn('fixture done', (self.root / 'user/last_run.log').read_text())

    def test_headless_failure_keeps_exit_event_and_crash_copy(self):
        data = self.run_fixture(7)
        self.assertIn('runtime_error', {item['event'] for item in data})
        self.assertEqual(data[-1]['code'], 7)
        self.assertEqual(data[-1]['outcome'], 'failed')
        self.assertEqual(len(list((self.root / 'user/crashes').glob('*.log'))), 1)

    def test_headless_launch_error_is_journaled_before_propagating(self):
        with patch.object(self.launcher, 'run_command', return_value=[str(self.root / 'missing')]):
            with self.assertRaises(FileNotFoundError):
                self.launcher.play_without_window(self.settings)
        self.assertEqual(records(self.root / 'user')[-1]['event'], 'launch_failed')

    def test_invalid_extra_configuration_is_journaled_without_starting_a_process(self):
        self.settings['extra_env'] = 'BROKEN="unterminated'
        with patch.object(self.launcher.subprocess, 'Popen') as process:
            with self.assertRaises(ValueError):
                self.launcher.play_without_window(self.settings)
            process.assert_not_called()
        self.assertEqual(records(self.root / 'user')[-1]['event'], 'launch_failed')

    def test_journal_failure_does_not_prevent_child_execution(self):
        (self.root / 'user/events.log').mkdir(parents=True)
        with patch.object(self.launcher, 'run_command', return_value=[sys.executable, '-c', 'pass']):
            self.assertEqual(self.launcher.play_without_window(self.settings), 0)
        self.assertIn('[exit code 0', (self.root / 'user/last_run.log').read_text())

    def test_gui_reader_and_stop_distinguish_user_stop_from_crash(self):
        events = self.launcher.SessionEvents(self.root / 'user', self.settings)
        events.process_started(456)
        controller = SimpleNamespace(app=self.settings, output=queue.Queue(), stopping=False,
                                     session_events=events, job=Mock())
        self.launcher.Launcher.stop(controller)
        process = SimpleNamespace(stdout=io.BytesIO(b'SOTC FPS 30.0 at 5s;\n'), wait=lambda: -15)
        with patch.object(self.launcher, 'keep_crash_log') as crash:
            self.launcher.Launcher.read_output(controller, process, events)
            crash.assert_not_called()
        data = records(self.root / 'user')
        self.assertIn('stop_requested', {item['event'] for item in data})
        self.assertEqual(data[-1]['outcome'], 'stopped')
        self.assertEqual(controller.output.get(), 'SOTC FPS 30.0 at 5s;\n')
        self.assertEqual(controller.output.get(), (-15,))

    def test_gui_launch_error_keeps_a_reviewable_event(self):
        controller = SimpleNamespace(app=self.settings, process=None, collect=Mock(),
                                     set_log=Mock(), append=Mock(), messagebox=Mock(), show=Mock())
        with patch.object(self.launcher, 'game_info', return_value={'version': '01.01'}), \
             patch.object(self.launcher.subprocess, 'Popen', side_effect=OSError('fixture failure')):
            self.launcher.Launcher.play(controller)
        self.assertIsNone(controller.process)
        self.assertEqual(records(self.root / 'user')[-1]['event'], 'launch_failed')
