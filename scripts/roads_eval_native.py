"""Isolated native SQL worker for evaluate_roads.py; contains no OSM decoder."""
import hashlib
import json
from pathlib import Path
import sys
import time

import duckdb


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for data in iter(lambda: source.read(1024*1024), b''):
            digest.update(data)
    return digest.hexdigest()


def connect(spec, database=':memory:'):
    conn = duckdb.connect(str(database), config={
        'allow_unsigned_extensions': 'true', 'autoinstall_known_extensions': 'false',
        'autoload_known_extensions': 'false', 'threads': '2', 'memory_limit': '256MB',
        'extension_directory': spec['extension_directory'],
        'temp_directory': str(Path(spec['temp']) / 'duckdb'),
    })
    conn.execute(f'LOAD {literal(spec["extension"])}')
    conn.execute(f'LOAD {literal(spec["spatial"])}')
    installed, spatial_version = conn.execute("SELECT install_path,extension_version "
        "FROM duckdb_extensions() WHERE extension_name='spatial' AND loaded").fetchone()
    assert sha256(installed) == sha256(spec['spatial']), 'Installed Spatial differs from pinned artifact'
    assert spatial_version == 'a3dbcd1781'
    assert conn.execute('SELECT version()').fetchone()[0] == 'v2.0.0'
    return conn


def query(spec):
    return (f'ducklocate_read({literal(spec["source"])}, profile := \'roads\', '
            f'profile_version := \'1.0.0\', expected_sha256 := {literal(spec["sha256"])}, '
            f'on_error := {literal(spec["mode"])}, crs := {literal(spec["crs"])})')


def logical_digest(cursor):
    digest = hashlib.sha256()
    count = 0
    while batch := cursor.fetchmany(256):
        for row in batch:
            normalized = [v.hex() if isinstance(v, bytes) else v for v in row]
            digest.update(json.dumps(normalized, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode() + b'\n')
            count += 1
    return dict(rows=count, logical_sha256=digest.hexdigest())


def worker(spec):
    directory = Path(spec['run'])
    database = directory / 'roads.duckdb'
    result = {}
    conn = connect(spec, database if spec['task'] != 'repeat' else ':memory:')
    result['engine'] = conn.execute('SELECT version(), library_version, source_id FROM pragma_version()').fetchone()
    result['extensions'] = conn.execute("SELECT extension_name,extension_version FROM duckdb_extensions() "
                                        "WHERE loaded ORDER BY extension_name").fetchall()
    result['proj'] = conn.execute('SELECT DuckDB_Proj_Version(), DuckDB_PROJ_Compiled_Version()').fetchone()
    start = time.perf_counter()
    (directory / 'projection.started').touch()
    try:
        if spec['task'] == 'repeat':
            result.update(logical_digest(conn.execute(f'SELECT * FROM {query(spec)} ORDER BY osm_id')))
        else:
            conn.execute(f'CREATE TABLE roads AS SELECT * FROM {query(spec)}')
            conn.execute('CHECKPOINT')
    except duckdb.Error as error:
        if not spec['expect_error'] or spec['expect_error'] not in str(error):
            raise
        result['expected_statement_error'] = str(error)
        assert conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='roads'").fetchone() == (0,)
    else:
        assert not spec['expect_error'], 'Expected geometry failure was absent'
    conn.close()
    result['projection_seconds'] = time.perf_counter() - start
    (directory / 'projection.finished').touch()
    if database.exists():
        result['closed_database_bytes'] = database.stat().st_size
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    worker(json.loads(Path(sys.argv[1]).read_text()))
