"""Regression checks for the native acceptance harness; build all four artifacts first."""
from pathlib import Path
import subprocess
import sys
import unittest

from native_checks import assert_mercator_formula

ROOT = Path(__file__).resolve().parents[1]


class NativeAcceptanceGuards(unittest.TestCase):
    def test_wrong_build_modes_fail_before_acceptance(self):
        for configuration in ['debug', 'release']:
            for directory, mode in [('build', 'probe'), ('build/probes', 'normal')]:
                with self.subTest(configuration=configuration, expected_mode=mode):
                    artifact = ROOT / directory / configuration / 'ducklocate.duckdb_extension'
                    result = subprocess.run(
                        [sys.executable, str(ROOT / 'scripts/native_checks.py'),
                         str(artifact), '--expect-mode', mode],
                        capture_output=True, text=True, timeout=60,
                    )
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(f'native function set mismatch for {mode} mode', result.stderr)

    def test_recorded_control_point_passes(self):
        assert_mercator_formula(222638.98158654713, 6274861.394006575)

    def test_five_millimetre_discrepancies_fail(self):
        # Check each ordinate separately; relative tolerance used to admit 5 mm in Y.
        for dx, dy in [(0.005, 0), (-0.005, 0), (0, 0.005), (0, -0.005)]:
            with self.subTest(dx=dx, dy=dy):
                with self.assertRaises(AssertionError):
                    assert_mercator_formula(222638.98158654713 + dx, 6274861.394006575 + dy)


if __name__ == '__main__':
    unittest.main(verbosity=2)
