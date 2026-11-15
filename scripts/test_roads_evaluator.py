"""Independent evaluator regressions using literal XML and Osmium, not reader code.

Usage: configure/venv/bin/python3 scripts/test_roads_evaluator.py EXTENSION
Requires the same existing local artifacts as evaluate_roads.py; no setup/downloads.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from evaluate_roads import native_run
from roads_eval_compare import compare, reference_summary
from roads_eval_native import connect
from roads_oracle import decode

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / 'build/release/ducklocate.duckdb_extension'
EMPTY_DIGEST = hashlib.sha256(b'').hexdigest()


class RoadsEvaluatorRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='ducklocate-evaluator-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.osmium = shutil.which('osmium')
        if not cls.osmium:
            raise RuntimeError('Explicit local Osmium setup is required')
        for fixture in sorted((ROOT / 'test/fixtures/roads-evaluator').glob('*.osm')):
            subprocess.run([cls.osmium, 'cat', str(fixture), '-o',
                            str(cls.directory / (fixture.stem + '.osm.pbf'))], check=True)

    def evaluate(self, name):
        source = self.directory / (name + '.osm.pbf')
        output = self.directory / (self._testMethodName + '-' + name)
        result = subprocess.run([
            sys.executable, str(ROOT / 'scripts/evaluate_roads.py'), str(source),
            hashlib.sha256(source.read_bytes()).hexdigest(), '--output', str(output),
            '--extension', str(ARTIFACT), '--osmium', self.osmium,
        ], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads((output / 'evaluation.json').read_text()), output

    def assert_empty(self, report):
        self.assertEqual(report['reference']['counts'], dict(
            selected=0, successful=0, rejected=0, vertices=0,
            lineage_entries=0, warning_features=0))
        self.assertEqual(report['reference']['selected_ids_sha256'], EMPTY_DIGEST)
        self.assertEqual(report['reference']['rejected'], {})
        expected_schema = [
            ['feature_id', 'VARCHAR'], ['osm_type', 'VARCHAR'], ['osm_id', 'BIGINT'],
            ['osm_version', 'INTEGER'], ['name', 'VARCHAR'], ['geometry', 'GEOMETRY'],
            ['geometry_crs', 'VARCHAR'], ['tags', 'MAP(VARCHAR, VARCHAR)'],
            ['source_refs', 'STRUCT(osm_type VARCHAR, osm_id BIGINT, osm_version INTEGER)[]'],
            ['status', 'VARCHAR'],
            ['issues', 'STRUCT(severity VARCHAR, code VARCHAR, field VARCHAR, raw_value VARCHAR, message VARCHAR)[]'],
            ['source_sha256', 'VARCHAR'], ['profile_version', 'VARCHAR'],
            ['schema_version', 'VARCHAR'], ['extension_version', 'VARCHAR'],
            ['road_class', 'VARCHAR'], ['surface', 'VARCHAR'],
            ['max_speed_kmh', 'DOUBLE'], ['oneway', 'VARCHAR'],
        ]
        for key in ('comparison', 'fail_comparison', 'mercator_comparison'):
            with self.subTest(comparison=key):
                result = report[key]
                self.assertEqual(result['schema'], expected_schema)
                self.assertEqual(result['rows'], 0)
                self.assertEqual(result['counts'], dict(successful=0, rejected=0, vertices=0))
                self.assertEqual(result['logical_sha256'], EMPTY_DIGEST)
                self.assertEqual(result['diagnostics'], dict(
                    unsupported_value=0, conditional_value=0, missing_reference=0,
                    invalid_geometry=0, transformation_failed=0))
        self.assertEqual(report['repeat']['rows'], 0)
        self.assertEqual(report['repeat']['logical_sha256'], EMPTY_DIGEST)
        for key in ('materialization', 'fail_mode', 'mercator'):
            self.assertGreater(report[key]['closed_database_bytes'], 0)
            self.assertTrue(report[key]['temp_cleanup'])

    def test_zero_selected_full_evaluation(self):
        report, _ = self.evaluate('zero-selected')
        self.assertEqual(report['oracle']['counts'], dict(
            node=2, way=2, relation=1, selected=0, excluded_no_highway=1,
            excluded_area_yes=1, closed=0))
        self.assert_empty(report)

    def test_empty_full_evaluation(self):
        report, _ = self.evaluate('empty')
        self.assertEqual(report['oracle']['counts'], dict(
            node=1, way=0, relation=0, selected=0, excluded_no_highway=0,
            excluded_area_yes=0, closed=0))
        self.assert_empty(report)

    def test_no_elements_oracle_counts(self):
        reference = self.directory / 'no-elements.sqlite'
        result = decode(self.directory / 'no-elements.osm.pbf', reference, self.osmium)
        self.assertEqual(result['counts'], dict(
            node=0, way=0, relation=0, selected=0, excluded_no_highway=0,
            excluded_area_yes=0, closed=0))
        for crs in ('EPSG:4326', 'EPSG:3857'):
            summary = reference_summary(reference, None, None, crs=crs)
            self.assertEqual(summary['counts'], dict(
                selected=0, successful=0, rejected=0, vertices=0,
                lineage_entries=0, warning_features=0))

    def test_no_relations_full_evaluation(self):
        report, output = self.evaluate('no-relations')
        self.assertEqual(report['oracle']['counts'], dict(
            node=2, way=1, relation=0, selected=1, excluded_no_highway=0,
            excluded_area_yes=0, closed=1))
        self.assertEqual(report['reference']['counts'], dict(
            selected=1, successful=1, rejected=0, vertices=3,
            lineage_entries=3, warning_features=0))
        for key in ('comparison', 'fail_comparison', 'mercator_comparison'):
            self.assertEqual(report[key]['rows'], 1)
            self.assertEqual(report[key]['counts'], dict(successful=1, rejected=0, vertices=3))
        self.assertEqual(report['repeat']['logical_sha256'], report['comparison']['logical_sha256'])
        spec = json.loads((output / 'materialize/spec.json').read_text())
        for name, mutation, message in (
            ('missing', 'DELETE FROM roads', 'Missing output'),
            ('extra', 'INSERT INTO roads SELECT * FROM roads', 'Extra selected output IDs'),
        ):
            with self.subTest(guard=name):
                database = output / (name + '.duckdb')
                shutil.copyfile(output / 'materialize/roads.duckdb', database)
                with connect(spec, database) as conn:
                    conn.execute(mutation)
                with self.assertRaisesRegex(AssertionError, message):
                    compare(database, output / 'oracle.sqlite', spec)

    def test_duplicate_identity_remains_an_error(self):
        source = self.directory / 'duplicate.osm'
        source.write_text('<osm version="0.6">'
                          '<node id="1" lon="2" lat="49"/>'
                          '<node id="1" lon="2" lat="49"/></osm>')
        with self.assertRaises(sqlite3.IntegrityError):
            decode(source, self.directory / 'duplicate.sqlite', self.osmium)

    def test_poles_full_evaluation_and_mercator_fail_mode(self):
        report, output = self.evaluate('poles')
        self.assertEqual(report['reference']['rejected'],
                         {'102': 'missing_reference', '103': 'invalid_geometry'})
        self.assertEqual(report['comparison']['counts'], dict(successful=3, rejected=2, vertices=8))
        self.assertEqual(report['mercator_comparison']['counts'], dict(successful=1, rejected=4, vertices=2))
        self.assertEqual(report['mercator_comparison']['diagnostics'], dict(
            unsupported_value=2, conditional_value=1, missing_reference=1,
            invalid_geometry=1, transformation_failed=2))
        spec = json.loads((output / 'mercator/spec.json').read_text())
        result, _ = native_run(spec, 'mercator-fail', mode='fail', crs='EPSG:3857',
                               expect_error='transformation_failed')
        self.assertIn('transformation_failed', result['expected_statement_error'])
        for crs, rejected in (
            ('EPSG:4326', {102: 'missing_reference', 103: 'invalid_geometry'}),
            ('EPSG:3857', {100: 'transformation_failed', 101: 'transformation_failed',
                           102: 'missing_reference', 103: 'invalid_geometry'}),
        ):
            summary = reference_summary(output / 'oracle.sqlite', None, None, crs=crs)
            self.assertEqual(summary['rejected'], rejected)
            self.assertEqual(summary['counts']['selected'], 5)
            self.assertEqual(summary['counts']['rejected'], len(rejected))
            self.assertEqual(summary['counts']['warning_features'], 1)
        # Independently require pole identity, raw tags, resolved lineage and
        # ordered optional warnings to survive the change of CRS.
        default = json.loads((output / 'materialize/spec.json').read_text())
        with connect(default, output / 'materialize/roads.duckdb') as conn:
            source_rows = conn.execute('SELECT * EXCLUDE (geometry, geometry_crs, status, issues) '
                                       'FROM roads ORDER BY osm_id').fetchall()
            self.assertEqual(conn.execute("SELECT status, ST_AsText(geometry) FROM roads WHERE osm_id=100").fetchone(),
                             ('ok', 'LINESTRING (2 49, 2 90, 3 50, 2 49)'))
        with connect(spec, output / 'mercator/roads.duckdb') as conn:
            self.assertEqual(conn.execute('SELECT * EXCLUDE (geometry, geometry_crs, status, issues) '
                                          'FROM roads ORDER BY osm_id').fetchall(), source_rows)
            row = conn.execute('SELECT status, geometry, issues FROM roads WHERE osm_id=100').fetchone()
            self.assertEqual(row[:2], ('rejected', None))
            self.assertEqual([(i['severity'], i['code'], i['field'], i['raw_value']) for i in row[2]], [
                ('warning', 'conditional_value', 'maxspeed:conditional', '20 @ (wet)'),
                ('warning', 'unsupported_value', 'maxspeed:forward', '30'),
                ('warning', 'unsupported_value', 'oneway', 'alternating'),
                ('error', 'transformation_failed', 'geometry', None),
            ])


if __name__ == '__main__':
    ARTIFACT = Path(sys.argv.pop(1)).resolve()
    unittest.main(verbosity=2)
