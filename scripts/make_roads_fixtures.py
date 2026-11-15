"""Independent, stdlib-only PBF writer for hand-authored test source JSON.

Uses OSM-binary's public proto field numbers, not reader code or its output.
No downloads. Generated fixture bytes are deterministic (zlib has no timestamp).
"""
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'test/fixtures/roads'


def varint(n):
    n &= (1 << 64) - 1
    out = bytearray()
    while n > 127:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def integer(k, n):
    return varint(k << 3) + varint(n)


def blob(k, b):
    if isinstance(b, str):
        b = b.encode()
    return varint(k << 3 | 2) + varint(len(b)) + b


def zigzag(n):
    return (n << 1) ^ (n >> 63)


def packed(k, values):
    return blob(k, b''.join(varint(n) for n in values))


def deltas(values):
    previous = 0
    for n in values:
        yield zigzag(n - previous)
        previous = n


def frame(kind, data, compressed=True):
    payload = integer(2, len(data)) + blob(3, zlib.compress(data)) if compressed else blob(1, data)
    header = blob(1, kind) + integer(3, len(payload))
    return struct.pack('>I', len(header)) + header + payload


def encode(source):
    strings = ['']
    for element in source.get('ways', []) + source.get('nodes', []):
        for k, v in element.get('tags', {}).items():
            for s in (k, v):
                if s not in strings:
                    strings.append(s)
    def tags(e):
        items = e.get('tags', {}).items()
        return packed(2, [strings.index(k) for k, _ in items]) + packed(3, [strings.index(v) for _, v in items])
    def info(e):
        return blob(4, integer(1, e['version'])) if 'version' in e else b''
    ways = b''
    for w in source.get('ways', []):
        way = integer(1, w['id']) + tags(w) + info(w) + packed(8, deltas(w['refs']))
        ways += blob(3, way)
    nodes = b''
    if source.get('dense'):
        nn = source.get('nodes', [])
        dense = packed(1, deltas([n['id'] for n in nn]))
        if source.get('dense_versions'):
            dense += blob(5, packed(1, [n['version'] for n in nn]))
        dense += packed(8, deltas([round(n['y'] * 1e7) for n in nn]))
        dense += packed(9, deltas([round(n['x'] * 1e7) for n in nn]))
        dense += packed(10, [0] * len(nn))
        nodes = blob(2, dense)
    else:
        for n in source.get('nodes', []):
            node = integer(1, zigzag(n['id'])) + tags(n) + info(n)
            node += integer(8, zigzag(round(n['y'] * 1e7))) + integer(9, zigzag(round(n['x'] * 1e7)))
            nodes += blob(1, node)
    table = blob(1, b''.join(blob(1, s) for s in strings))
    header = blob(4, 'OsmSchema-V0.6') + (blob(4, 'DenseNodes') if source.get('dense') else b'')
    # Ways precede nodes in separate blocks: dependency resolution cannot rely on order.
    result = frame('OSMHeader', header, False)
    for group in (ways, nodes):
        if group:
            result += frame('OSMData', table + blob(2, group), source.get('compressed', True))
    return result


def dense_field_fixtures():
    """Hand-encoded singular-message regression and legal split-packed control."""
    header = frame('OSMHeader', blob(4, 'OsmSchema-V0.6') + blob(4, 'DenseNodes'), False)
    table = blob(1, blob(1, '') + blob(1, 'highway') + blob(1, 'track'))
    way = integer(1, 303) + packed(2, [1]) + packed(3, [2]) + packed(8, [2, 4])
    first = packed(1, [2]) + packed(8, [980000000]) + packed(9, [40000000]) + packed(10, [0])
    second = packed(1, [4, 2]) + packed(8, [20000000, 20000000]) + packed(9, [20000000, 20000000]) + packed(10, [0, 0])
    return {
        'duplicate-dense': header + frame('OSMData', table + blob(2, blob(3, way) + blob(2, first) + blob(2, second))),
        'split-dense': header + frame('OSMData', table + blob(2, blob(3, way) + blob(2, first + second))),
    }


def main():
    for path in sorted(FIXTURES.glob('*.json')):
        path.with_suffix('.osm.pbf').write_bytes(encode(json.loads(path.read_text())))
    for name, data in dense_field_fixtures().items():
        (FIXTURES / (name + '.osm.pbf')).write_bytes(data)


if __name__ == '__main__':
    main()
