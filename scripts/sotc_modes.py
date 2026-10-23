#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""sotc: game modes and engine settings for Shadow of the Colossus EU 1.01 (CUSA08809).

    python scripts/sotc_modes.py GAME --out out --modes af16,fps60 --cvars "r_motionBlurEnable=0 ..."

Writes two files for the loader:
  out/patches.bin  code patches (BBPATCH2, bb-probe --patches):
                   fps60  removes the game's 30 FPS cap (illusion's GoldHEN patch, the shadPS4
                          SotC fork's "SotC-Modes")
                   fps60game  uses the engine's own 60 FPS target (Performance mode),
                          keeping its timing aligned with the requested frame rate
  out/cmdline.bin  the engine command line the game appends to its own (SOTCCMD1,
                   bb-probe --sotc-cmdline): cvars of the Bluepoint engine, e.g.
                   +r_motionBlurEnable=0. Modes that are only cvars:
                   af16   16x anisotropic filtering on every texture
The original bytes are checked first: another game version gets neither file's changes.
"""
import argparse
import re
from pathlib import Path
import struct
from prepare import parse_self

BASE = 0x400000
# The lea that loads the string the game appends to its command line ("+VSyncWindow=10%").
CMDLINE_LEA = 0x009367b9
CMDLINE_ORIGINAL = '+VSyncWindow=10%'
# Code patches: mode -> [(address, expected original bytes, new bytes)]
MODES = {
    'fps60': [
        # the frame limiter's import stub (sceVideoOutSetFlipRate) returns 0
        (0x01390090, bytes.fromhex('ff25a20567'), bytes.fromhex('31c0c3')),
    ],
    # AjncSystem PR #183: TargetFramesPerSeconds=1 (60 FPS), including the
    # graphics/options paths that would otherwise restore 2 (30 FPS).
    'fps60game': [
        (0x00b0a7a6, bytes.fromhex('c745b802000000'), bytes.fromhex('c745b801000000')),
        (0x0089a47f, bytes.fromhex('c7458402000000'), bytes.fromhex('c7458401000000')),
        (0x0089a499, bytes.fromhex('c7458002000000'), bytes.fromhex('c7458001000000')),
    ],
}
# Modes made of cvars only.
CVAR_MODES = {
    'fps60game': ['TargetFramesPerSeconds=1'],
    'af16': ['progSamplerAnisoLevel=16', 'progSamplerAnisoLevel_BasePS4=16', 'progSamplerAnisoLevel_Perf=16',
             'progSamplerAnisoLevel_Cinematic=16', 'linearSamplerAnisoLevel=16'],
}
# EU 1.01: the command line lea and the fps60 site.
VERSION_CHECKS = [(CMDLINE_LEA, bytes.fromhex('488d352debad00')), (0x01390090, bytes.fromhex('ff25a20567'))]
CVAR = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(=[-+.0-9A-Za-z_%]+)?$')  # NAME=VALUE or a flag such as nointro


def image_bytes(elf, ph, vaddr, length):
    for p in ph:
        if p['type'] in (1, 0x61000010) and p['vaddr'] <= vaddr and vaddr + length <= p['vaddr'] + p['filesz']:
            offset = p['offset'] + vaddr - p['vaddr']
            return bytes(elf[offset:offset + length])
    return None


def is_supported(elf, ph):
    return all(image_bytes(elf, ph, address - BASE, len(original)) == original for address, original in VERSION_CHECKS)


def mode_patches(elf, ph, mode):
    """Reject a mismatched instruction before emitting any patches for a mode."""
    writes = []
    for address, original, data in MODES.get(mode, []):
        if image_bytes(elf, ph, address - BASE, len(original)) != original:
            raise SystemExit(f'Mode {mode}: unexpected bytes at {address:#x}; not applied')
        writes.append((address - BASE, data))
    return writes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('game', type=Path)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent.parent / 'out')
    parser.add_argument('--modes', default='', help='comma-separated: ' + ', '.join([*MODES, *CVAR_MODES]))
    parser.add_argument('--cvars', default='', help='engine cvars NAME=VALUE separated by spaces')
    args = parser.parse_args()
    elf, _, ph, _, _ = parse_self((args.game / 'eboot.bin').read_bytes())
    supported = is_supported(elf, ph)
    writes, cvars = [], []
    modes = list(dict.fromkeys(filter(None, (m.strip().lower() for m in args.modes.split(',')))))
    if 'fps60' in modes and 'fps60game' in modes:
        raise SystemExit('Choose fps60game or legacy fps60, not both')
    for mode in modes:
        if mode not in MODES and mode not in CVAR_MODES:
            raise SystemExit(f'unknown mode {mode!r} (known: {", ".join([*MODES, *CVAR_MODES])})')
        if not supported:
            print(f'Mode {mode}: this eboot is not EU 1.01, not applied')
            continue
        writes += mode_patches(elf, ph, mode)
        cvars += CVAR_MODES.get(mode, [])
        print(f'Mode {mode}: on')
    for item in args.cvars.split():
        item = item.lstrip('+')
        if not CVAR.match(item):
            raise SystemExit(f'bad cvar {item!r} (NAME=VALUE or NAME)')
        cvars.append(item)
    blob = struct.pack('<8sQQ', b'BBPATCH2', BASE, len(writes))
    for offset, data in writes:
        blob += struct.pack('<QQ', offset, len(data)) + data
    (args.out / 'patches.bin').write_bytes(blob)
    cmdline = args.out / 'cmdline.bin'
    if supported and cvars:
        text = ' '.join([CMDLINE_ORIGINAL, *('+' + c for c in cvars)])
        cmdline.write_bytes(struct.pack('<8sQ', b'SOTCCMD1', CMDLINE_LEA - BASE) + text.encode('ascii'))
    elif cmdline.exists():
        cmdline.unlink()


if __name__ == '__main__':
    main()
