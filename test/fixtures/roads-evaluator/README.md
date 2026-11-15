# Independent evaluator sources

These small XML sources are hand-authored, artificial data for this repository.
The evaluator tests convert them with the existing Osmium CLI into temporary PBFs
outside Git. Neither Ducklocate's reader nor the synthetic protobuf writer supplies
these inputs or expected results. No downloads or external OSM data are involved.

- `zero-selected.osm`: two nodes, two ways and one relation. One way lacks
  `highway`; the other has exact `area=yes`. Both are exclusions, yielding zero
  selected/successful/rejected features, vertices, lineage entries and warnings.
- `empty.osm`: one highway-tagged node, no ways or relations. Nodes do not select
  roads. The full evaluation must persist/reopen the exact 19-column schema with
  zero rows, repeat the empty SHA-256 digest and complete both CRS comparisons.
- `no-relations.osm`: two nodes, one way, no relations. Way 100 v3 selects with
  refs [2,1,2], geometry LINESTRING(3 50,2 49,3 50), speed 30 km/h, no warnings,
  and unique lineage [way100 v3,node2 v2,node1 v1]. The closed count is one.
- `no-elements.osm`: no elements at all. Oracle decoding and reference summaries
  must explicitly report all their fixed counts as zero. This tests the count
  layer directly: Osmium 1.19.0's extended JSON `fileinfo` fails while serializing
  a node-free extent, so a completely node-free source cannot currently complete
  the command-line evaluation. The evaluator continues to propagate that real
  subprocess failure. Empty *profile results* above complete the full workflow.
- `poles.osm`: four nodes, five selected ways, one unselected relation. Way 100
  reaches the north pole at an interior vertex, preserving a repeated final node;
  way 101 reaches the south pole. Both are valid EPSG:4326 lines. Spherical
  Mercator is undefined at either pole, so EPSG:3857 must reject both with
  `transformation_failed` and NULL geometry. Way 102 has a pole plus missing node
  999: `missing_reference` takes precedence. Way 103 repeats the same pole twice:
  `invalid_geometry` takes precedence. Way 104 is an ordinary successful control.
  EPSG:4326 thus has three successes/eight output vertices and two rejections;
  EPSG:3857 has one success/two output vertices and four rejections. All five ways
  retain their identity, tags and resolved lineage across CRSs.

Way 100's warnings must precede its CRS-dependent geometry issue: conditional
`maxspeed:conditional`, unsupported `maxspeed:forward` (lexical scope order), then
unsupported scalar `oneway=alternating`. Its geometry is the first required error
in EPSG:3857 fail mode. The test requires a statement error containing
`transformation_failed` and no published `roads` table. EPSG:4326 fail mode first
fails on way 102's missing reference instead.

The test also deliberately deletes/duplicates persisted output rows to retain
missing/extra-output detection, and independently supplies duplicate source IDs
to ensure oracle errors remain errors. Successful coordinate comparisons retain
the existing absolute tolerances: 1e-12 degree and 1e-6 metre, zero relative
tolerance. No arbitrary CRS operation or provenance metadata is inferred.
