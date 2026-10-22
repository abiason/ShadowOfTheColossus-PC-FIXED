"""Offline AppImage safety checks: never run packaging tools or host drivers."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging/linux'))
spec = importlib.util.spec_from_file_location('sotc_appimage_test', ROOT / 'packaging/linux/appimage.py')
appimage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(appimage)


class AppImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_ldd_absolute_loader_name_becomes_basename(self):
        output = ('\tlinux-vdso.so.1 (0x123)\n'
                  '\t/lib64/ld-linux-x86-64.so.2 => /usr/lib/ld-linux-x86-64.so.2 (0x456)\n'
                  '\tlibcodec.so.1 => /usr/lib/libcodec.so.1 (0x789)\n')
        with mock.patch.object(appimage.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output, '')):
            found = appimage.dependencies(self.root / 'binary')
        self.assertEqual(found, [('ld-linux-x86-64.so.2', Path('/usr/lib/ld-linux-x86-64.so.2')),
                                 ('libcodec.so.1', Path('/usr/lib/libcodec.so.1'))])
        self.assertTrue(all(not Path(name).is_absolute() for name, _ in found))

    def test_unresolved_or_failed_ldd_is_rejected(self):
        for result in (subprocess.CompletedProcess([], 0, 'libcodec.so => not found', ''),
                       subprocess.CompletedProcess([], 1, '', 'ldd failed')):
            with self.subTest(result=result), mock.patch.object(appimage.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(ValueError, 'Unresolved dependencies'):
                    appimage.dependencies(self.root / 'binary')

    def test_host_graphics_and_libc_stay_external_but_runtime_libraries_bundle(self):
        external = ('ld-linux-x86-64.so.2', 'libc.so.6', 'libm.so.6', 'libpthread.so.0',
                    'libvulkan.so.1', 'libvulkan_radeon.so', 'libGL.so.1', 'libEGL.so.1',
                    'libGLX_mesa.so.0', 'libgbm.so.1', 'libdrm_amdgpu.so.1',
                    'libgallium-26.2.4.so', 'radeonsi_dri.so', 'iris_dri.so')
        for name in external:
            with self.subTest(name=name):
                self.assertIsNotNone(appimage.HOST_LIBRARIES.match(name))
        for name in ('libcodec.so.1', 'libavcodec.so.62', 'libpython3.14.so.1.0', 'libstdc++.so.6'):
            with self.subTest(name=name):
                self.assertIsNone(appimage.HOST_LIBRARIES.match(name))

    def test_library_collision_rejected_and_copy_destination_stays_in_appdir(self):
        appdir = self.root / 'AppDir'
        (appdir / 'usr/lib').mkdir(parents=True)
        executable = appdir / 'program'
        executable.write_bytes(b'\x7fELFfixture')
        source_one = Path('/usr/lib/vendor-one/libbbb.so')
        source_two = Path('/usr/lib/vendor-two/libbbb.so')
        destinations = []
        def copy(source, destination):
            destinations.append(destination)
            destination.write_bytes(b'\x7fELFcopied')
        def dependencies(binary):
            if binary == executable:
                return [('libbbb.so', source_one)]
            return [('libbbb.so', source_two)]
        with mock.patch.object(appimage, 'dependencies', side_effect=dependencies), \
             mock.patch.object(appimage, 'sha', side_effect=lambda p: 'one' if p == source_one else 'two'), \
             mock.patch.object(appimage.shutil, 'copy2', side_effect=copy), \
             mock.patch.object(appimage, 'run', return_value='fixture-package'):
            with self.assertRaisesRegex(ValueError, 'Conflicting library'):
                appimage.bundle_libraries(appdir)
        self.assertEqual(destinations, [appdir / 'usr/lib/libbbb.so'])
        self.assertTrue(all(path.resolve().is_relative_to(appdir.resolve()) for path in destinations))

    def test_stage_verifies_before_creating_appdir_or_extracting(self):
        appdir = self.root / 'AppDir'
        with mock.patch.object(appimage, 'verify', side_effect=ValueError('Private package refused')) as verify, \
             mock.patch.object(appimage.tarfile, 'open') as tar:
            with self.assertRaisesRegex(ValueError, 'Private package refused'):
                appimage.stage(self.root / 'private.tar.gz', appdir)
        verify.assert_called_once_with(self.root / 'private.tar.gz')
        self.assertFalse(appdir.exists())
        tar.assert_not_called()

    def test_real_private_archive_is_refused_before_appdir_creation(self):
        archive = self.root / 'private.tar.gz'
        manifest = json.dumps({'private_preview_only': True}).encode()
        with tarfile.open(archive, 'w:gz') as tar:
            member = tarfile.TarInfo('SotC/MANIFEST.json')
            member.size = len(manifest)
            tar.addfile(member, io.BytesIO(manifest))
        appdir = self.root / 'AppDir'
        with mock.patch.object(appimage.subprocess, 'run') as run, \
             mock.patch.object(appimage.subprocess, 'check_output') as output:
            with self.assertRaisesRegex(ValueError, 'Private preview cannot be published'):
                appimage.stage(archive, appdir)
        self.assertFalse(appdir.exists())
        run.assert_not_called()
        output.assert_not_called()

    def test_tool_checksum_mismatch_never_writes_or_executes_download(self):
        pins_dir = self.root / 'packaging/linux'
        pins_dir.mkdir(parents=True)
        pins = {name: {'url': 'https://invalid.example/' + name, 'sha256': '0' * 64}
                for name in ('appimagetool', 'runtime', 'runtime-LICENSE.txt')}
        (pins_dir / 'appimage-tools.json').write_text(json.dumps(pins))
        with mock.patch.object(appimage, 'download', return_value=b'untrusted tool') as download, \
             mock.patch.object(appimage, 'atomic_write') as write, \
             mock.patch.object(appimage.subprocess, 'run') as run, \
             mock.patch.object(appimage.subprocess, 'check_output') as output:
            with self.assertRaisesRegex(ValueError, 'Tool checksum mismatch'):
                appimage.tools(self.root)
        download.assert_called_once()
        write.assert_not_called()
        run.assert_not_called()
        output.assert_not_called()
        self.assertEqual(list((self.root / 'out/dependencies/appimage').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
