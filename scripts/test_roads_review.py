"""Targeted native review regressions; accepts an explicit packaged artifact."""
from pathlib import Path
import sys
import unittest

import native_checks
from roads_checks import dense_field_checks, restricted_crs_checks


class RoadsReviewRegressions(unittest.TestCase):
    def test_reprojection_respects_locked_caller_policy(self):
        restricted_crs_checks(native_checks.connect)

    def test_duplicate_dense_message_is_rejected(self):
        with native_checks.connect() as conn:
            dense_field_checks(conn)


if __name__ == '__main__':
    native_checks.ARTIFACT = Path(sys.argv.pop(1)).resolve()
    unittest.main(verbosity=2)
