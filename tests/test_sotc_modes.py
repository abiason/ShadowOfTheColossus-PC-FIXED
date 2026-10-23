"""Verify generated loader patches and reject mismatched guest instructions."""
import contextlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from paths import ROOT
import sotc_modes as modes


def fixture():
    # Independent EU 1.01 instruction samples; synthetic discontiguous ELF segments.
    samples = [(0x9367b9, '488d352debad00'), (0x1390090, 'ff25a20567'),
               (0xb0a7a6, 'c745b802000000'), (0x89a47f, 'c7458402000000'),
               (0x89a499, 'c7458002000000')]
    elf, ph = bytearray(), []
    for address, original in samples:
        data = bytes.fromhex(original)
        ph.append(dict(type=1, vaddr=address - 0x400000, filesz=len(data), offset=len(elf)))
        elf.extend(data)
    return elf, ph


def read_patches(path):
    data = path.read_bytes()
    magic, base, count = struct.unpack_from('<8sQQ', data)
    assert magic == b'BBPATCH2' and base == 0x400000
    pos, writes = 24, []
    for _ in range(count):
        offset, size = struct.unpack_from('<QQ', data, pos)
        pos += 16
        writes.append((base + offset, data[pos:pos + size]))
        pos += size
    assert pos == len(data)
    return writes


class EngineFpsModesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'eboot.bin').write_bytes(b'fixture')
        self.elf, self.ph = fixture()

    def generate(self, selected, **extra):
        argv = ['sotc_modes.py', str(self.root), '--out', str(self.root), '--modes', selected]
        for key, value in extra.items():
            argv.extend(['--' + key, value])
        with patch.object(sys, 'argv', argv), \
             patch.object(modes, 'parse_self', return_value=(self.elf, None, self.ph, None, None)), \
             contextlib.redirect_stdout(io.StringIO()):
            modes.main()
        return read_patches(self.root / 'patches.bin')

    def test_engine_mode_patches_all_three_targets_and_adds_cvar(self):
        writes = self.generate('af16, FPS60GAME, fps60game')
        self.assertEqual(writes, [(0xb0a7a6, bytes.fromhex('c745b801000000')),
                                  (0x89a47f, bytes.fromhex('c7458401000000')),
                                  (0x89a499, bytes.fromhex('c7458001000000'))])
        data = (self.root / 'cmdline.bin').read_bytes()
        self.assertEqual(struct.unpack_from('<8sQ', data), (b'SOTCCMD1', 0x5367b9))
        self.assertIn('+TargetFramesPerSeconds=1', data[16:].decode('ascii'))
        self.assertIn('+progSamplerAnisoLevel=16', data[16:].decode('ascii'))

    def test_each_mismatched_instruction_aborts_before_writing(self):
        for segment in self.ph[2:]:
            with self.subTest(address=segment['vaddr']):
                self.elf, _ = fixture()
                self.elf[segment['offset']] = 0x90
                with self.assertRaisesRegex(SystemExit, 'unexpected bytes'):
                    self.generate('fps60game')
                self.assertFalse((self.root / 'patches.bin').exists())
                self.assertFalse((self.root / 'cmdline.bin').exists())

    def test_legacy_unlock_remains_explicit_and_unchanged(self):
        self.assertEqual(self.generate('fps60'), [(0x1390090, b'\x31\xc0\xc3')])
        self.assertFalse((self.root / 'cmdline.bin').exists())

    def test_modes_cannot_combine_engine_target_and_legacy_unlock(self):
        with self.assertRaisesRegex(SystemExit, 'not both'):
            self.generate('fps60,fps60game')
        self.assertFalse((self.root / 'patches.bin').exists())

    def test_unsupported_version_drops_stale_cmdline_and_emits_no_patches(self):
        self.elf[0] = 0x90
        (self.root / 'cmdline.bin').write_bytes(b'old target')
        self.assertEqual(self.generate('fps60game'), [])
        self.assertFalse((self.root / 'cmdline.bin').exists())

    def test_no_modes_does_not_enable_sixty_fps(self):
        self.assertEqual(self.generate(''), [])
        self.assertFalse((self.root / 'cmdline.bin').exists())
