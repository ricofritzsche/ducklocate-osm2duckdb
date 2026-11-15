"""Actual pinned-runtime integration checks; also runs against probe builds.

Every connection disables automatic installation/loading. Spatial is an explicit,
hash-verified local artifact. Run under network denial for the offline check.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import struct
import tempfile

import duckdb

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT: Path
SPATIAL = ROOT / '.cache/spatial/spatial.duckdb_extension'
SPATIAL_SHA = '212ca75890f576bec4a9ea71f5a10320581fe9886afceb05b1d47944ebcf03f4'
CONFIG = {
    'allow_unsigned_extensions': 'true',
    'autoinstall_known_extensions': 'false',
    'autoload_known_extensions': 'false',
    'threads': '2',
}


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def connect(database=':memory:'):
    conn = duckdb.connect(database, config=CONFIG)
    conn.execute(f'LOAD {literal(ARTIFACT)}')
    return conn


def scalar(conn, query):
    return conn.execute(query).fetchone()[0]


def fails(conn, query, message):
    try:
        conn.execute(query).fetchall()
    except duckdb.Error as error:
        assert message.lower() in str(error).lower(), (query, error)
    else:
        raise AssertionError(f'Expected error: {query}')


def assert_mercator_formula(x, y):
    # Independent spherical Mercator formula, WGS84 a=6378137 m, 1 micrometre.
    assert math.isclose(x, 6378137 * math.radians(2), rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(y, 6378137 * math.log(math.tan(math.pi/4 + math.radians(49)/2)), rel_tol=0.0, abs_tol=1e-6)


def geometry_checks(conn):
    conn.execute(f'LOAD {literal(SPATIAL)}')
    schema = conn.execute('DESCRIBE SELECT * FROM ducklocate_probe_rows(0)').fetchall()
    assert [(r[0], r[1]) for r in schema] == [
        ('id', 'BIGINT'), ('geometry', 'GEOMETRY'), ('geometry_crs', 'VARCHAR'),
        ('tags', 'MAP(VARCHAR, VARCHAR)'),
        ('source_refs', 'STRUCT(osm_type VARCHAR, osm_id BIGINT, osm_version INTEGER)[]'),
        ('issues', 'STRUCT(severity VARCHAR, code VARCHAR, field VARCHAR, raw_value VARCHAR, message VARCHAR)[]'),
    ], schema
    assert conn.execute("DESCRIBE SELECT * FROM ducklocate_probe_rows(0, shape := 'id')").fetchall()[0][:2] == ('id', 'BIGINT')
    assert len(conn.execute("DESCRIBE SELECT * FROM ducklocate_probe_rows(0, shape := 'id')").fetchall()) == 1
    assert scalar(conn, 'SELECT count(*) FROM ducklocate_probe_rows(0)') == 0
    for count in [1, 126, 127, 128, 2048, 5000]:
        rows = conn.execute(f'SELECT * FROM ducklocate_probe_rows({count}) ORDER BY id').fetchall()
        assert len(rows) == count
        for i, row in enumerate(rows):
            assert row[0] == i
            if i % 3 == 1:
                assert row[1:] == (None,) * 5, row
                continue
            # Independently decoded OGC WKB from the Rust-produced GEOMETRY.
            assert struct.unpack('<BIdd', row[1]) == (1, 1, 2.0, 49.0), row
            assert row[2] == 'EPSG:4326'
            if i % 3 == 2:
                assert row[3:] == ({}, [], []), row
            else:
                assert row[3] == {'name': 'synthetic 🦆', 'missing': None}
                assert row[4] == [{'osm_type': 'node', 'osm_id': 42, 'osm_version': None}, None]
                assert row[5] == [{'severity': 'warning', 'code': 'synthetic', 'field': None, 'raw_value': None, 'message': 'test only'}]
    assert scalar(conn, 'SELECT count(*) FROM ducklocate_probe_rows(5000) WHERE id >= 4997') == 3
    assert scalar(conn, 'SELECT count(*) FROM ducklocate_probe_rows(5000) WHERE id < 0') == 0
    # Bind data is immutable; a prepared statement and view must scan afresh.
    conn.execute('PREPARE probe AS SELECT count(*),sum(id) FROM ducklocate_probe_rows(5000)')
    for _ in range(3):
        assert conn.execute('EXECUTE probe').fetchall() == [(5000, 12497500)]
    conn.execute('CREATE VIEW probe_view AS SELECT * FROM ducklocate_probe_rows(128)')
    for _ in range(2):
        assert scalar(conn, 'SELECT count(*) FROM probe_view') == 128
    assert scalar(conn, "SELECT ST_AsText(geometry) FROM ducklocate_probe_rows(1)") == 'POINT (2 49)'
    conn.execute('CREATE TABLE retained AS SELECT * FROM ducklocate_probe_rows(5000)')
    assert conn.execute("SELECT typeof(geometry), ST_AsText(geometry), ST_X(geometry), ST_Y(geometry) FROM retained WHERE id=0").fetchone() == ('GEOMETRY', 'POINT (2 49)', 2.0, 49.0)
    conn.execute('CREATE INDEX retained_geometry ON retained USING RTREE(geometry)')
    assert scalar(conn, 'SELECT count(*) FROM retained WHERE ST_Intersects(geometry, ST_MakeEnvelope(1,48,3,50))') == 3333
    for arg, message in [
        ('NULL', 'must not be NULL'), ('-1', 'between'),
        ("1, shape := NULL", 'must not be NULL'), ("1, shape := 'roads'", 'shape'),
        ("1, crs := NULL", 'must not be NULL'), ("1, crs := ''", 'unsupported CRS'),
        ("1, crs := 'EPSG:invalid'", 'unsupported CRS'),
        ("1, crs := 'EPSG:32632'", 'unsupported CRS'),
        ("1, unknown := true", 'unknown'),
        ("1, 'id'", 'No function matches'),
    ]:
        fails(conn, f'SELECT * FROM ducklocate_probe_rows({arg})', message)
    # EXPLAIN binds the schema but must not open the absent Spatial path.
    conn.execute("EXPLAIN SELECT * FROM ducklocate_probe_rows(1, crs := 'EPSG:3857', spatial_path := '/missing/spatial.duckdb_extension')").fetchall()
    projected = f"ducklocate_probe_rows(3, spatial_path := {literal(SPATIAL)}, crs := 'EPSG:3857')"
    x, y, crs = conn.execute(f'SELECT ST_X(geometry), ST_Y(geometry),geometry_crs FROM {projected} WHERE id=0').fetchone()
    # Published PROJ example rounds to 2 decimals: tolerance 1 cm (not source accuracy).
    assert abs(x - 222638.98) < 0.01 and abs(y - 6274861.39) < 0.01, (x, y)
    assert_mercator_formula(x, y)
    assert crs == 'EPSG:3857'
    fails(conn, "SELECT * FROM ducklocate_probe_rows(1, crs := 'EPSG:3857', spatial_path := '/missing/spatial.duckdb_extension')", 'not found')
    # Hand-written WKB LineString and polygon ring exercise non-point geometry.
    line = struct.pack('<BII4d', 1, 2, 2, 2.0, 49.0, 3.0, 50.0)
    polygon = struct.pack('<BIII10d', 1, 3, 1, 5, 2.,49., 3.,49., 3.,50., 2.,50., 2.,49.)
    for wkb, expected in [(line, 'LINESTRING (2 49, 3 50)'), (polygon, 'POLYGON ((2 49, 3 49, 3 50, 2 50, 2 49))')]:
        assert conn.execute('SELECT ST_AsText(geometry) FROM ducklocate_probe_rows(1, geometry_wkb := ?)', [wkb]).fetchone() == (expected,)
        transformed = conn.execute(f"SELECT ST_IsValid(geometry), ST_XMin(geometry), ST_YMin(geometry) FROM ducklocate_probe_rows(1, geometry_wkb := ?, crs := 'EPSG:3857', spatial_path := {literal(SPATIAL)})", [wkb]).fetchone()
        assert transformed[0] and abs(transformed[1]-x) < 1e-6 and abs(transformed[2]-y) < 1e-6
    empty = struct.pack('<BII', 1, 2, 0)
    assert conn.execute(f"SELECT ST_IsEmpty(geometry) FROM ducklocate_probe_rows(1, geometry_wkb := ?, crs := 'EPSG:3857', spatial_path := {literal(SPATIAL)})", [empty]).fetchone() == (True,)
    invalid_point = struct.pack('<BIdd', 1, 1, 2., 91.)
    fails(conn, f"SELECT * FROM ducklocate_probe_rows(1, geometry_wkb := from_hex('{invalid_point.hex()}'), crs := 'EPSG:3857', spatial_path := {literal(SPATIAL)})", 'transformation_failed')
    fails(conn, "SELECT * FROM ducklocate_probe_rows(1, geometry_wkb := from_hex('0101'))", 'Could not convert BLOB to GEOMETRY')
    return {'control_point': [x, y], 'proj': scalar(conn, 'SELECT DuckDB_Proj_Version()')}


def transaction_checks(conn):
    # Sequence advancement survives rollback and witnesses the first CTAS executed.
    conn.execute('CREATE SEQUENCE ducklocate_probe_write_witness START 1')
    count = "SELECT count(*) FROM duckdb_tables() WHERE table_name IN ('ducklocate_probe_first','ducklocate_probe_second')"
    conn.execute('BEGIN')
    conn.execute('CREATE TABLE caller_uncommitted AS SELECT 7 AS value')
    assert conn.execute('PRAGMA ducklocate_probe_transaction(false)').fetchall() == [(2,)]
    assert scalar(conn, count) == 2
    assert scalar(conn, 'SELECT value FROM ducklocate_probe_first') == 1
    conn.execute('ROLLBACK')
    assert scalar(conn, count) == 0
    assert scalar(conn, "SELECT count(*) FROM duckdb_tables() WHERE table_name='caller_uncommitted'") == 0
    conn.execute('BEGIN')
    conn.execute('CREATE TABLE caller_uncommitted AS SELECT 7 AS value')
    fails(conn, 'PRAGMA ducklocate_probe_transaction(true)', 'deliberate_failure')
    fails(conn, 'SELECT * FROM ducklocate_probe_first', 'aborted')
    conn.execute('ROLLBACK')
    assert scalar(conn, "SELECT currval('ducklocate_probe_write_witness')") == 2
    assert scalar(conn, count) == 0
    assert scalar(conn, "SELECT count(*) FROM duckdb_tables() WHERE table_name='caller_uncommitted'") == 0
    # Autocommit statement groups must also leave no partial writes on failure.
    fails(conn, 'PRAGMA ducklocate_probe_transaction(true)', 'deliberate_failure')
    assert scalar(conn, "SELECT currval('ducklocate_probe_write_witness')") == 3
    assert scalar(conn, count) == 0
    # A pre-existing user table is preserved on a collision.
    conn.execute('CREATE TABLE ducklocate_probe_first AS SELECT 99 AS value')
    fails(conn, 'PRAGMA ducklocate_probe_transaction(false)', 'already exists')
    assert scalar(conn, 'SELECT value FROM ducklocate_probe_first') == 99
    conn.execute('DROP TABLE ducklocate_probe_first')
    conn.execute('PRAGMA ducklocate_probe_transaction(false)')
    assert scalar(conn, count) == 2


def concurrent_scan(count):
    with connect() as conn:
        return conn.execute(f"SELECT count(*), max(id) FROM ducklocate_probe_rows({count}, shape := 'id')").fetchone()


def metadata_checks():
    signed_only = dict(CONFIG)
    signed_only['allow_unsigned_extensions'] = 'false'
    with duckdb.connect(config=signed_only) as conn:
        fails(conn, f'LOAD {literal(ARTIFACT)}', 'unsigned')
    data = ARTIFACT.read_bytes()
    fields = [data[-512+i*32:-512+(i+1)*32].rstrip(b'\0').decode() for i in range(8)]
    assert fields[3] == 'C_STRUCT_UNSTABLE' and fields[5:] == ['v2.0.0','osx_arm64','4'], fields
    with tempfile.TemporaryDirectory() as directory:
        bad = Path(directory) / 'ducklocate.duckdb_extension'
        for index, replacement, message in [(5, b'v2.0.1', 'version'), (6, b'osx_amd64', 'platform')]:
            edited = bytearray(data)
            start = len(data)-512+index*32
            edited[start:start+32] = replacement.ljust(32, b'\0')
            bad.write_bytes(edited)
            with duckdb.connect(config=CONFIG) as conn:
                fails(conn, f'LOAD {literal(bad)}', message)
    return fields[4]


def main():
    global ARTIFACT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--expect-mode', choices=['normal', 'probe'], required=True)
    args = parser.parse_args()
    ARTIFACT = args.artifact.resolve()
    probes = args.expect_mode == 'probe'
    with connect() as conn:
        public = {r[0] for r in conn.execute("SELECT function_name FROM duckdb_functions() WHERE function_name LIKE 'ducklocate_%'").fetchall()}
        expected = {'ducklocate_profiles'}
        if probes:
            expected.update({'ducklocate_probe_rows', 'ducklocate_probe_transaction'})
        assert public == expected, (
            f'native function set mismatch for {args.expect_mode} mode: '
            f'expected {sorted(expected)}, got {sorted(public)}'
        )
        assert duckdb.__version__ == '2.0.0'
        identity = metadata_checks()
        assert conn.execute('SELECT version(), platform FROM pragma_platform()').fetchone() == ('v2.0.0', 'osx_arm64')
        assert scalar(conn, 'SELECT count(*) FROM ducklocate_profiles()') == 0
        result = {'artifact': str(ARTIFACT), 'sha256': hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(), 'probes': probes, 'identity': identity}
        if probes:
            assert hashlib.sha256(SPATIAL.read_bytes()).hexdigest() == SPATIAL_SHA
            result.update(geometry_checks(conn))
            transaction_checks(conn)
    if probes:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(concurrent_scan, [128, 5000])) == [(128,127),(5000,4999)]
        # Reopen a persistent CTAS database; type and Spatial operations survive.
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / 'retained.duckdb')
            with connect(db) as conn:
                conn.execute('CREATE TABLE persistent AS SELECT * FROM ducklocate_probe_rows(3)')
            with connect(db) as conn:
                conn.execute(f'LOAD {literal(SPATIAL)}')
                assert scalar(conn, 'SELECT ST_AsText(geometry) FROM persistent WHERE id=0') == 'POINT (2 49)'
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
