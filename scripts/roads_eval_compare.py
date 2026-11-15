"""Compare every real selected way to the independently decoded reference."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct

from roads_oracle import features
from roads_eval_native import connect, logical_digest

SCHEMA = [
    ('feature_id', 'VARCHAR'), ('osm_type', 'VARCHAR'), ('osm_id', 'BIGINT'),
    ('osm_version', 'INTEGER'), ('name', 'VARCHAR'), ('geometry', 'GEOMETRY'),
    ('geometry_crs', 'VARCHAR'), ('tags', 'MAP(VARCHAR, VARCHAR)'),
    ('source_refs', 'STRUCT(osm_type VARCHAR, osm_id BIGINT, osm_version INTEGER)[]'),
    ('status', 'VARCHAR'),
    ('issues', 'STRUCT(severity VARCHAR, code VARCHAR, field VARCHAR, raw_value VARCHAR, message VARCHAR)[]'),
    ('source_sha256', 'VARCHAR'), ('profile_version', 'VARCHAR'), ('schema_version', 'VARCHAR'),
    ('extension_version', 'VARCHAR'), ('road_class', 'VARCHAR'), ('surface', 'VARCHAR'),
    ('max_speed_kmh', 'DOUBLE'), ('oneway', 'VARCHAR'),
]


def reference_summary(database, cases_path, expected_hash):
    cases = json.loads(Path(cases_path).read_text()) if cases_path else None
    if cases:
        assert cases['source_sha256'] == expected_hash, 'Cases belong to a different source'
    wanted = {c['id']: c for c in cases['ways']} if cases else {}
    found = []
    counts, diagnostics = Counter(), Counter()
    missing, rejected = {}, {}
    ids = hashlib.sha256()
    for feature in features(database):
        ident, tags = feature['id'], feature['tags']
        ids.update(f'{ident}\n'.encode())
        counts['selected'] += 1
        counts['rejected' if feature['code'] else 'successful'] += 1
        counts['vertices'] += len(feature['ordered_refs'])
        counts['lineage_entries'] += len(feature['lineage'])
        counts['warning_features'] += any(i[0] == 'warning' for i in feature['issues'])
        diagnostics.update(i[1] for i in feature['issues'])
        if feature['code']:
            rejected[ident] = feature['code']
        if feature['missing']:
            missing[ident] = feature['missing']
        if ident in wanted:
            case = wanted[ident]
            assert feature['version'] == case['version'], case
            assert all(tags.get(k) == v for k, v in case['tags'].items()), case
            assert feature['speed'] == case['speed_kmh'], case
            assert feature['direction'] == case['oneway'], case
            assert [list(i[1:]) for i in feature['issues']] == case['issues'], case
            assert (feature['ordered_refs'][0] == feature['ordered_refs'][-1]) == case['closed'], case
            found.append(ident)
    assert set(found) == set(wanted), 'A documented real-way case is missing'
    return dict(counts=dict(counts), diagnostics=dict(diagnostics), missing_references=missing,
                rejected=rejected, selected_ids_sha256=ids.hexdigest(), checked_cases=found)


def coordinates(wkb):
    endian = '<' if wkb[0] == 1 else '>'
    kind, length = struct.unpack_from(endian+'II', wkb, 1)
    assert kind == 2 and len(wkb) == 9+16*length, 'Expected complete LineString WKB'
    return list(struct.iter_unpack(endian+'dd', wkb[9:]))


def compare(database, reference, spec):
    counts, diagnostics = Counter(), Counter()
    max_error = [0., 0.]
    with connect(spec, database) as conn:
        schema = [(r[0], r[1]) for r in conn.execute('DESCRIBE roads').fetchall()]
        assert schema == SCHEMA, schema
        identity = conn.execute("SELECT extension_version FROM duckdb_extensions() "
                                "WHERE extension_name='ducklocate' AND loaded").fetchone()[0]
        cursor = conn.execute('SELECT * FROM roads ORDER BY osm_id')
        batch = iter(())
        for expected in features(reference):
            actual = next(batch, None)
            if actual is None:
                batch = iter(cursor.fetchmany(256))
                actual = next(batch, None)
            assert actual is not None, ('Missing output', expected['id'])
            row = dict(zip((c for c, _ in SCHEMA), actual))
            ident, tags = expected['id'], expected['tags']
            assert row['osm_id'] == ident, ('Selected ID mismatch', ident, row['osm_id'])
            assert row['feature_id'] == f'roads:way:{ident}' and row['osm_type'] == 'way', ident
            assert row['osm_version'] == expected['version'], ident
            assert row['tags'] == tags and list(row['tags']) == sorted(tags), ident
            assert row['source_refs'] == expected['lineage'], ident
            assert row['name'] == tags.get('name') and row['surface'] == tags.get('surface'), ident
            assert row['road_class'] == tags['highway'], ident
            assert row['max_speed_kmh'] == expected['speed'], ident
            assert row['oneway'] == expected['direction'], ident
            assert row['profile_version'] == row['schema_version'] == '1.0.0', ident
            assert row['extension_version'] == identity, ident
            assert row['source_sha256'] == spec['sha256'] and row['geometry_crs'] == spec['crs'], ident
            issues = [(i['severity'], i['code'], i['field'], i['raw_value']) for i in row['issues']]
            assert issues == expected['issues'], (ident, issues, expected['issues'])
            diagnostics.update(i[1] for i in issues)
            if expected['code']:
                assert row['status'] == 'rejected' and row['geometry'] is None, ident
                counts['rejected'] += 1
            else:
                assert row['status'] == 'ok' and row['geometry'] is not None, ident
                points = coordinates(row['geometry'])
                assert len(points) == len(expected['points']), ident
                for (x, y), (lon, lat) in zip(points, expected['points']):
                    if spec['crs'] == 'EPSG:3857':
                        target = (6378137*math.radians(lon),
                                  6378137*math.log(math.tan(math.pi/4+math.radians(lat)/2)))
                        tolerance = 1e-6
                    else:
                        target, tolerance = (lon, lat), 1e-12
                    for axis, (observed, value) in enumerate(zip((x, y), target)):
                        delta = abs(observed-value)
                        assert math.isfinite(observed) and delta <= tolerance, (ident, observed, value, delta)
                        max_error[axis] = max(max_error[axis], delta)
                    counts['vertices'] += 1
                counts['successful'] += 1
        assert next(batch, None) is None and cursor.fetchone() is None, 'Extra selected output IDs'
        digest = logical_digest(conn.execute('SELECT * FROM roads ORDER BY osm_id'))
        # Native Spatial reads the persisted GEOMETRY, rather than a cast VARCHAR/BLOB.
        smoke = conn.execute("SELECT typeof(geometry), ST_GeometryType(geometry), ST_NumPoints(geometry) "
                             "FROM roads WHERE status='ok' ORDER BY osm_id LIMIT 1").fetchone()
        if counts['successful']:
            assert smoke[0] == 'GEOMETRY' and smoke[1] == 'LINESTRING' and smoke[2] >= 2, smoke
    return dict(counts=dict(counts), diagnostics=dict(diagnostics), max_coordinate_error=max_error,
                extension_version=identity, schema=schema, **digest)
