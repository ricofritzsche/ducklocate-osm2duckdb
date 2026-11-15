# Synthetic roads fixtures

These JSON files are hand-authored source data for this repository (no OSM extract
or third-party data). Coordinates and tags are artificial. The adjacent PBFs are
deterministically encoded by `python3 scripts/make_roads_fixtures.py`, using a
small independent protobuf writer and Python zlib. It does not import reader code
or generate acceptance answers. Ways precede nodes in separate blocks. Negative
reference deltas, raw/zlib blobs and dense/ordinary nodes are exercised.

The two additional `duplicate-dense` and `split-dense` PBFs are hand-encoded by
`dense_field_fixtures()` in the same independent writer, without source JSON.
They share way 303, highway=track, refs [1,3], and a string table. The first
dense payload has ID delta [1], latitude delta [490000000] and longitude delta
[20000000]. The second has ID deltas [2,1] and latitude/longitude deltas
[10000000,10000000]. Granularity is 100 nanodegrees; all node versions are absent.

- `duplicate-dense` places those payloads in **two occurrences of PrimitiveGroup
  field 2**. The documented singular-field policy requires a statement error in
  both modes. Resetting deltas incorrectly yields nodes 1=(2,49), 2=(1,1),
  3=(2,2), hence a plausible but wrong road LINESTRING(2 49,2 2) with status ok.
- `split-dense` concatenates the same payload bytes inside **one field 2**.
  Its repeated packed ID/latitude/longitude/tag fields are legitimate. Accumulating
  deltas across segments yields nodes 1=(2,49), 3=(3,50), 4=(4,51); way 303 must
  be LINESTRING(2 49,3 50), lineage [way303,node1,node3], status ok in both modes.

Native acceptance compares both tracked files with the independent writer's
bytes without rewriting them. SQLLogicTest checks duplicate rejection in both
modes and the split-field control; native checks also assert exact coordinates
and lineage. The existing ordinary/dense and metadata fixtures remain in use.

Independent derivation:

- valid: 16 ways, two exclusions (102 has area=yes, 103 lacks highway), so 14
  rows. Node 1 is (2,49) version 1, node 2 (3,50) has no version, node 3
  (4,51) version 3. Way 100 therefore has geometry
  LINESTRING(4 51,2 49,3 50,2 49), refs [way100,node3,node1,node2], no way
  version, Unicode name/surface, speed 30*1.609344=48.28032 and backward direction.
  Way 101 closes as a line and does not infer roundabout direction. Way 104
  selects an empty highway value, reverses node order explicitly in the source,
  keeps an empty name, and has speed 10*1.852=18.52. Way 107 is 12.5 km/h and
  both directions. Way 105 and 113 have conditional values; way 114 has scoped
  values; their scalar speed/direction are NULL. Ways 106/108 have two warnings,
  109–112 one unsupported speed warning each; aliases on 109–112 are preserved
  in tags and interpreted forward/both/forward/both. Way 115 has no optional
  attributes. All rows have status ok.
- rejected: 201 misses node 999 (lineage includes resolved 1 and 2); 202 has
  only one ref; 203 has two refs at the same coordinate; 204 has an invalid
  interior latitude, 205 an invalid interior longitude; 207 has no refs.
  All six reject in report mode; fail mode fails on 201. Way 206 has a pole:
  valid in EPSG:4326 but transformation_failed in EPSG:3857. Its source geometry
  keeps (2,49),(2,90),(3,50). These interior failures must not be hidden by a
  finite envelope.
- dense: nodes in ID order [2,1], versions [3,2], way 301 refs [2,1,2], so
  LINESTRING(3 50,2 49,3 50) and unique node lineage [2,1].
- dense-absent: ordinary metadata is absent from dense nodes; both versions
  remain NULL; way 302 refs [1,2]. Uses raw uncompressed data blocks.
- empty: a highway-tagged node is not a way; the only way lacks highway. No rows.
- conflict: node 1 appears at two coordinates; a statement error even in report.

`roads_checks.py` holds the independently written schema, values and expected
issues. It also writes temporary larger, corrupted, relation and resource-limit
fixtures through the independent encoder. Large generated fixtures are not tracked.
No national-scale integration or performance claim is made.
