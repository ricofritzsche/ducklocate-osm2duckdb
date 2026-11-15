"""Independent real-input reference: Osmium XML, never Ducklocate's PBF code.

Keep the reference database outside Git. Nodes are indexed before comparison, so
reference resolution does not depend on input ordering. No geometry factory,
location cache or area assembler is allowed to drop/repair problematic ways.
"""
from collections import Counter
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

DIAGNOSTIC_CODES = ('unsupported_value', 'conditional_value', 'missing_reference',
                    'invalid_geometry', 'transformation_failed')


def decode(source, destination, osmium):
    db = sqlite3.connect(destination)
    db.executescript('''
        CREATE TABLE nodes(id INTEGER PRIMARY KEY, version INTEGER, x REAL, y REAL);
        CREATE TABLE ways(id INTEGER PRIMARY KEY, version INTEGER, tags TEXT, refs TEXT);
        CREATE TABLE identities(kind TEXT, id INTEGER, PRIMARY KEY(kind,id));
    ''')
    # These are fixed report fields, including categories absent from the source.
    counts = Counter(dict.fromkeys(('node', 'way', 'relation', 'selected',
                                   'excluded_no_highway', 'excluded_area_yes', 'closed'), 0))
    maxima = Counter(dict.fromkeys(('tags', 'tag_utf8_bytes', 'references_or_members'), 0))
    inventory = {key: Counter() for key in ('highway', 'maxspeed', 'oneway')}
    with Path(destination).with_suffix('.stderr').open('w') as errors:
        with subprocess.Popen([osmium, 'cat', str(source), '-f', 'osm', '--no-progress'],
                              stdout=subprocess.PIPE, stderr=errors) as process:
            try:
                parser = ET.iterparse(process.stdout, events=('start', 'end'))
                _, root = next(parser)
                for event, obj in parser:
                    if event != 'end' or obj.tag not in ('node', 'way', 'relation'):
                        continue
                    kind = obj.tag
                    ident = int(obj.attrib['id'])
                    version = obj.get('version')
                    version = int(version) if version else None
                    assert obj.get('visible', 'true') == 'true', (kind, ident, 'deleted')
                    db.execute('INSERT INTO identities VALUES (?,?)', (kind, ident))
                    counts[kind] += 1
                    pairs = [(tag.attrib['k'], tag.attrib['v']) for tag in obj.findall('tag')]
                    tags = dict(pairs)
                    assert len(tags) == len(pairs), (kind, ident, 'duplicate tag key')
                    maxima['tags'] = max(maxima['tags'], len(pairs))
                    maxima['tag_utf8_bytes'] = max(maxima['tag_utf8_bytes'],
                                                 sum(len(k.encode())+len(v.encode()) for k, v in pairs))
                    refs = [int(n.attrib['ref']) for n in obj.findall('nd')]
                    maxima['references_or_members'] = max(maxima['references_or_members'],
                                                         len(refs), len(obj.findall('member')))
                    if kind == 'node':
                        db.execute('INSERT INTO nodes VALUES (?,?,?,?)',
                                   (ident, version, obj.get('lon'), obj.get('lat')))
                    elif kind == 'way':
                        if 'highway' not in tags:
                            counts['excluded_no_highway'] += 1
                        elif tags.get('area') == 'yes':
                            counts['excluded_area_yes'] += 1
                        else:
                            counts['selected'] += 1
                            db.execute('INSERT INTO ways VALUES (?,?,?,?)',
                                       (ident, version, json.dumps(tags), json.dumps(refs)))
                            for key, values in inventory.items():
                                if key in tags:
                                    values[tags[key]] += 1
                            counts['closed'] += bool(refs and refs[0] == refs[-1])
                    root.clear()
                if process.wait() != 0:
                    raise RuntimeError('Osmium failed; inspect oracle.stderr')
            except BaseException:
                process.kill()
                process.wait()
                raise
    assert sum(counts[k] for k in ('node', 'way', 'relation')) <= 10_000_000
    assert maxima['tags'] <= 4096 and maxima['tag_utf8_bytes'] <= 65536
    assert maxima['references_or_members'] <= 10000
    db.commit()
    db.close()
    return dict(counts=dict(counts), maxima=dict(maxima),
                inventory={k: dict(v) for k, v in inventory.items()})


def attributes(tags):
    """Derive scalars and ordered warning tuples from the written 1.0.0 policy."""
    warnings = []
    values = []
    for base in ('maxspeed', 'oneway'):
        scoped = sorted(k for k in tags if k.startswith(base + ':'))
        if scoped:
            warnings.extend(('warning', 'conditional_value' if k == base+':conditional'
                             else 'unsupported_value', k, tags[k]) for k in scoped)
            values.append(None)
            continue
        raw = tags.get(base)
        value = None
        if raw is not None:
            if base == 'maxspeed':
                match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)( km/h| mph| knots)?',
                                     raw.strip(' \t\n\r\v\f'))
                if match:
                    number = float(match[1]) * {None: 1., ' km/h': 1.,
                                                ' mph': 1.609344, ' knots': 1.852}[match[2]]
                    if math.isfinite(number) and number > 0:
                        value = number
            else:
                value = {'yes': 'forward', '1': 'forward', 'true': 'forward',
                         '-1': 'backward', 'no': 'both', '0': 'both', 'false': 'both'}.get(raw)
            if '@' in raw:
                value = None
            if value is None:
                warnings.append(('warning', 'conditional_value' if '@' in raw
                                 else 'unsupported_value', base, raw))
        values.append(value)
    return *values, warnings


def features(database, crs='EPSG:4326'):
    if crs not in ('EPSG:4326', 'EPSG:3857'):
        raise ValueError(f'No independent geometry oracle for {crs}')
    with sqlite3.connect(database) as db:
        for ident, version, raw_tags, raw_refs in db.execute('SELECT * FROM ways ORDER BY id'):
            tags, refs = json.loads(raw_tags), json.loads(raw_refs)
            unique = list(dict.fromkeys(refs))
            nodes = {}
            # One lookup per unique ID also handles lists above SQLite's bind limit.
            for ref in unique:
                node = db.execute('SELECT version,x,y FROM nodes WHERE id=?', (ref,)).fetchone()
                if node is not None:
                    nodes[ref] = node
            points = [(nodes[n][1], nodes[n][2]) for n in refs if n in nodes]
            missing = [n for n in unique if n not in nodes]
            invalid = (len(refs) < 2 or len(set(points)) < 2 or any(
                x is None or y is None or not math.isfinite(x) or not math.isfinite(y)
                or not -180 <= x <= 180 or not -90 <= y <= 90 for x, y in points))
            code = 'missing_reference' if missing else 'invalid_geometry' if invalid else None
            # Spherical Mercator is undefined at either pole. Check its domain
            # before floating-point log/tan can turn +90 into a large finite Y.
            # Source failures take precedence, regardless of the output CRS.
            if code is None and crs == 'EPSG:3857' and any(abs(y) >= 90 for _, y in points):
                code = 'transformation_failed'
            speed, direction, issues = attributes(tags)
            if code:
                issues.append(('error', code, 'geometry', None))
            yield dict(id=ident, version=version, tags=tags, ordered_refs=refs,
                       points=points, missing=missing, code=code, speed=speed,
                       direction=direction, issues=issues,
                       lineage=[dict(osm_type='way', osm_id=ident, osm_version=version)] +
                       [dict(osm_type='node', osm_id=n, osm_version=nodes[n][0])
                        for n in unique if n in nodes])
