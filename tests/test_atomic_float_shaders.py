"""Validate production SPIR-V and execute its fallback paths without a Vulkan GPU.

Build first: ninja -C out/gpu atomic-float-shader-test
"""
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / 'out/gpu/atomic-float-shader-test'


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def floating(value):
    return struct.unpack('<f', struct.pack('<I', value))[0]


def instructions(text):
    for line in text.splitlines():
        match = re.fullmatch(r'\s*(?:(%\S+) = )?(Op\w+)(?: (.*))?', line)
        if match:
            yield match[1], match[2], (match[3] or '').split()


def execute_fallback(text, incoming, initial):
    """Small interpreter for the instructions in these real backend fixtures.

    Reject unknown operations so test coverage cannot silently omit a new side effect.
    Each atomic returns the pre-write bits, exactly as the shader consumes them.
    """
    code = list(instructions(text))
    values, types, variables = {}, {}, {}
    for result, op, args in code:
        if op in ('OpTypeFloat', 'OpTypeInt'):
            types[result] = op
        elif op == 'OpConstant':
            values[result] = float(args[1]) if types.get(args[0]) == 'OpTypeFloat' else int(args[1])
        elif op == 'OpVariable':
            variables[result] = args[1]
    start = next(i for i, (_, op, _) in enumerate(code) if op == 'OpFunction') + 1
    labels = {result: i for i, (result, op, _) in enumerate(code) if op == 'OpLabel'}
    pc, previous, label, output = start, None, None, None
    memory, writes = bits(initial), 0
    for _ in range(len(code) * 2):
        result, op, args = code[pc]
        pc += 1
        if op == 'OpLabel':
            label = result
        elif op == 'OpAccessChain':
            values[result] = variables[args[1]]
        elif op == 'OpLoad':
            assert values[args[1]] == 'Input'
            values[result] = incoming
        elif op == 'OpBitcast':
            values[result] = (bits(values[args[1]]) if types[args[0]] == 'OpTypeInt'
                              else floating(values[args[1]]))
        elif op == 'OpBitwiseAnd':
            values[result] = values[args[1]] & values[args[2]]
        elif op == 'OpINotEqual':
            values[result] = values[args[1]] != values[args[2]]
        elif op in ('OpAtomicUMin', 'OpAtomicUMax', 'OpAtomicSMin', 'OpAtomicSMax'):
            assert values[args[1]] == 'StorageBuffer'
            candidate = values[args[-1]]
            old = memory
            signed = lambda x: x - (1 << 32) if x & (1 << 31) else x
            old_cmp = signed(old) if op.startswith('OpAtomicS') else old
            new_cmp = signed(candidate) if op.startswith('OpAtomicS') else candidate
            if (new_cmp < old_cmp if op.endswith('Min') else new_cmp > old_cmp):
                memory = candidate
            values[result] = old
            writes += 1
        elif op == 'OpSelectionMerge':
            pass
        elif op == 'OpBranchConditional':
            previous = label
            pc = labels[args[1] if values[args[0]] else args[2]]
        elif op == 'OpBranch':
            previous = label
            pc = labels[args[0]]
        elif op == 'OpPhi':
            values[result] = next(values[args[i]] for i in range(1, len(args), 2)
                                  if args[i + 1] == previous)
        elif op == 'OpStore':
            assert values[args[0]] == 'Output'
            output = values[args[1]]
        elif op == 'OpReturn':
            return memory, bits(output), writes
        else:
            raise AssertionError(f'Unexpected fixture instruction: {op}')
    raise AssertionError('Fixture did not return')


@unittest.skipUnless(BINARY.is_file() and shutil.which('spirv-val') and shutil.which('spirv-dis'),
                     'Build atomic-float-shader-test and install SPIR-V tools first')
class AtomicFloatShaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        env = dict(os.environ, SHADPS4_LOOP_LIMIT_PER_LOOP='0')
        subprocess.run([str(BINARY), str(cls.root)], env=env, check=True,
                       capture_output=True, text=True, timeout=20)

    def test_native_and_fallback_modules_are_valid_vulkan_spirv(self):
        for name in ('min-native', 'max-native', 'min-fallback', 'max-fallback'):
            with self.subTest(shader=name):
                subprocess.run(['spirv-val', '--target-env', 'vulkan1.3',
                                str(self.root / (name + '.spv'))], check=True,
                               capture_output=True, text=True, timeout=10)
                if name.endswith('native'):
                    text = subprocess.check_output(
                        ['spirv-dis', str(self.root / (name + '.spv'))], text=True, timeout=10)
                    atomics = [op for _, op, _ in instructions(text) if op.startswith('OpAtomic')]
                    self.assertEqual(atomics, ['OpAtomicFMinEXT' if name.startswith('min')
                                               else 'OpAtomicFMaxEXT'])

    def test_fallback_updates_once_and_returns_previous_value_for_both_signs(self):
        cases = (-math.inf, -7.0, -3.0, -0.0, 0.0, 3.0, 7.0, math.inf)
        for maximum in (False, True):
            shader = self.root / ('max-fallback.spv' if maximum else 'min-fallback.spv')
            text = subprocess.check_output(['spirv-dis', str(shader)], text=True, timeout=10)
            for initial in cases:
                for incoming in cases:
                    with self.subTest(maximum=maximum, initial=initial, incoming=incoming):
                        actual, returned, writes = execute_fallback(text, incoming, initial)
                        expected = max(initial, incoming) if maximum else min(initial, incoming)
                        if initial == 0 and incoming == 0:
                            signs = (math.copysign(1, initial), math.copysign(1, incoming))
                            negative = all(s < 0 for s in signs) if maximum else any(s < 0 for s in signs)
                            expected = -0.0 if negative else 0.0
                        self.assertEqual(actual, bits(expected))
                        self.assertEqual(returned, bits(initial))
                        self.assertEqual(writes, 1)
