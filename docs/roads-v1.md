# Roads 1.0.0 (schema 1.0.0)

This contract is defined before its implementation. `roads` has one installed
version, `1.0.0`, also its default. Rules and diagnostic codes are versioned;
human-readable diagnostic messages may change. Extension identity includes the
build revision and source digest (the packaged footer identity).

## OSM conventions and project policy

The official OSM community documentation describes [elements and ordered ways](https://wiki.openstreetmap.org/wiki/Elements),
[highway classification](https://wiki.openstreetmap.org/wiki/Key:highway),
[area](https://wiki.openstreetmap.org/wiki/Key:area),
[maxspeed](https://wiki.openstreetmap.org/wiki/Key:maxspeed) and
[oneway](https://wiki.openstreetmap.org/wiki/Key:oneway) (consulted 2026-11-15).
OSM ways are ordered node references; closure alone does not imply an area.
Speed numbers without a unit conventionally mean km/h; mph and knots are also
used. Oneway direction is relative to the drawn way. Those are community
conventions. The following deliberately restricted interpretation is project policy.

Select every **way with a `highway` key**, including an empty or unknown value,
unless `area` is exactly `yes`. Missing highway tags, nodes and relations are
not selected. `area:highway` alone does not select a way. Other `area` values do
not exclude it. Closed selected ways remain LineStrings, with their closing node
repeated. No implicit area inference, polygon conversion or geometry reversal.
There is one feature per selected way: `roads:way:<signed-decimal-id>`. The key
is independent of source version, snapshot, CRS and scan order. It is only a
roads-profile key, not a universal identity or a routing edge.

Relations (including routes, restrictions and multipolygons), road areas,
clipping, intersection splitting, connectivity, turn restrictions, legal access
and routing topology are outside this profile. A member way is selected by its
own tags, independently of relations. No legal or mode-specific permission is
inferred. No implied one-way rule from motorway or roundabout tags is applied.

## Geometry and dependencies

Resolve all nodes independently of selection and input record order. A selected
way requires at least two references and at least two distinct coordinate pairs.
Every reference must resolve. Every source coordinate must be finite and in
longitude [-180,180], latitude [-90,90]. Every transformed coordinate must also
be finite; EPSG:3857 excludes the poles (abs(latitude) >= 90). Repeated interior
nodes, self intersections and zero-length segments are retained when the whole
line has two distinct coordinates. No repair, snapping, simplification or reversal.
Use the shared validating WKB-to-native-GEOMETRY and offline Spatial/PROJ path.
Default EPSG:4326 is longitude/latitude XY in degrees; EPSG:3857 is XY in metres.
Other CRSs are rejected. The qualified operation and unresolved runtime
operation/grid provenance are described in [native-foundation.md](native-foundation.md).
No operation or grid identities are invented.

The ordered node reference list, including repetitions, remains in the pinned
PBF; geometry follows it exactly. `source_refs` is unique lineage: primary way
first, then **resolved nodes in first-reference order**; missing nodes do not
pretend to contribute a version. Absent versions are NULL. Even rejected rows
retain every resolved dependency. SQL row order requires ORDER BY.

## Exact output schema

Columns below are in order. All columns except those explicitly nullable are
populated even on rejected rows. Tags are unchanged Unicode strings, represented
as a map sorted by key; duplicate tag keys are corrupt input. Empty optional
strings are preserved, not silently treated as missing.

| Column | SQL type | NULL / meaning |
|---|---|---|
| feature_id | VARCHAR | `roads:way:<id>` |
| osm_type | VARCHAR | `way` |
| osm_id | BIGINT | primary ID |
| osm_version | INTEGER | NULL if absent |
| name | VARCHAR | raw name, NULL if absent |
| geometry | GEOMETRY | LineString; NULL for rejection |
| geometry_crs | VARCHAR | requested canonical CRS, XY |
| tags | MAP(VARCHAR, VARCHAR) | all primary way tags, no NULL entries |
| source_refs | STRUCT(osm_type VARCHAR, osm_id BIGINT, osm_version INTEGER)[] | unique lineage as above; no NULL elements |
| status | VARCHAR | `ok` or `rejected` |
| issues | STRUCT(severity VARCHAR, code VARCHAR, field VARCHAR, raw_value VARCHAR, message VARCHAR)[] | no NULL elements; empty when none |
| source_sha256 | VARCHAR | lowercase SHA-256 of private snapshot |
| profile_version | VARCHAR | `1.0.0` |
| schema_version | VARCHAR | `1.0.0` |
| extension_version | VARCHAR | packaged build identity |
| road_class | VARCHAR | raw highway value, including empty/unknown |
| surface | VARCHAR | raw surface, NULL if absent; no enum inference |
| max_speed_kmh | DOUBLE | interpreted scalar, NULL if absent or unsupported |
| oneway | VARCHAR | `forward`, `backward`, `both`, or NULL |

Attribute fields remain available on rejected rows when independently established.
No extra ordered-reference column is added to this common schema.

## Speed and direction

Accept an unsigned positive decimal (`digits` or `digits.digits`), optionally
followed by exactly ` km/h`, ` mph` or ` knots`; trim outer ASCII whitespace.
No exponent, sign, decimal comma, list, lane or directional aggregate. Convert
mph with 1.609344 and knots with 1.852; require a finite positive result.
`none`, `signals`, `walk`, country codes and other symbolic strings are unsupported,
not zero or infinity. Malformed/unsupported scalar values produce
`unsupported_value` and NULL. If `maxspeed:conditional` exists, or maxspeed
contains `@`, emit `conditional_value` and NULL even if a base scalar exists.
Any `maxspeed:*` key other than `maxspeed:conditional` emits `unsupported_value`
and leaves the scalar NULL: the single column cannot express mode, lane or
direction-specific restrictions. Raw tags remain available.

Explicit `oneway=yes|1|true` means `forward`; `-1` means `backward`;
`no|0|false` means `both`. Match exact case-sensitive strings, without trimming.
Absent oneway means NULL, never confirmed two-way access. Reversible, alternating,
unknown or empty values produce `unsupported_value` and NULL. An `@` in
`oneway` produces `conditional_value` and NULL. Any `oneway:*` key suppresses
the scalar: `oneway:conditional` produces `conditional_value`; other scoped keys
produce `unsupported_value`. Both leave oneway NULL. Do not silently reverse
the source geometry. These fields summarize explicit tags, not legal advice or
complete travel permissions.

## Diagnostics and error modes

Diagnostics are ordered: maxspeed scoped keys (lexical), scalar speed if needed,
oneway scoped keys (lexical), scalar oneway if needed, then geometry. Scoped
keys suppress scalar interpretation; each scoped key gets one warning.

| Code | Severity | Meaning |
|---|---|---|
| unsupported_value | warning | optional scalar/scoped value cannot be represented; field is the tag key and raw_value is the source string |
| conditional_value | warning | conditional speed/direction cannot be represented; field and raw_value identify the tag |
| missing_reference | error | at least one node absent; field `geometry`, raw_value NULL |
| invalid_geometry | error | too few refs/distinct coordinates or invalid source coordinate; field `geometry`, raw_value NULL |
| transformation_failed | error | invalid/non-finite coordinate after transformation; field `geometry`, raw_value NULL |

Geometry precedence is missing_reference, then invalid_geometry, then
transformation_failed; at most one geometry issue per row. Fail mode raises a
statement error for required geometry failures. Report mode emits a rejected row
with NULL geometry. Optional warnings do not fail either mode. Nonselected ways
are exclusions, not rejections. Corrupt/truncated PBF, unsupported required PBF
features, duplicate identities (including identical repeated records), conflicting
records, hash mismatch, cancellation, I/O and resource errors always fail the
statement. History/deleted records are unsupported, not latest-version selection.

## Execution, security and resource limits

Bind validates constant arguments and declares the schema without opening input.
Each execution owns its state; repeated scans reopen the source. Source access
uses the caller's DuckDB file system (including enable_external_access and path
allowlists); URL schemes, glob syntax, empty paths and non-regular files are
rejected. Local reads never download. A single open source handle is copied to
private temporary storage while hashing exactly those copied bytes. Replacement
of the pathname cannot redirect later projection. Concurrent in-place writes may
produce a mixed snapshot, but its reported hash always describes the exact copy
projected; expected_sha256 rejects anything other than the asserted bytes.
The reader never hashes one pass and projects another pass of the live file.

Hard per-scan limits: 512 MiB input snapshot; blob header below 64 KiB; 32 MiB encoded
blob and uncompressed block; 1 million protobuf fields per message; 100,000
string-table entries; 10,000 references/members per way/relation; 4,096 tags and
64 KiB total tag UTF-8 per element; 10 million elements; 2 GiB SQLite index.
Raw and zlib blobs and ordinary/dense nodes are supported. Other compression,
LocationsOnWays and unknown required features fail. Unknown optional protobuf
fields are ignored; duplicate singular protobuf fields and malformed lengths,
references and deltas fail explicitly.
These limits deliberately exclude some valid large extracts/records.

Rust holds one bounded block, bounded per-element buffers and one feature at a
time; output chunks contain at most 32 features. SQLite uses an 8 MiB page-cache target,
no mmap, on-disk temporary work and a fixed maximum page count. This storage is
outside DuckDB's memory limit; the limits are independent, not an engine memory
accounting claim. Temporary storage is an OS-private `ducklocate-` directory
under the OS temp root, containing at most the snapshot plus index (2.5 GiB,
plus small SQLite overhead). RAII closes the index before deleting the directory
on EOF, error, early termination or cancellation. Abrupt process death can leave
OS temporary files. The C API v2 context exposes no cancellation polling handle:
DuckDB observes interruption between callbacks; snapshot/index preparation is a
bounded callback and may delay cancellation. No prompt cancellation latency claim.

For EPSG:3857 an isolated in-memory DuckDB session loads **already installed**
Spatial from the caller's extension_directory, with autoload/autoinstall disabled,
then disables external access. It verifies Spatial revision a3dbcd1781 and the
runtime/compiled PROJ 9.1.1 identities. Install the pinned local Spatial artifact explicitly
before use. There is no network or grid acquisition in the reader. Missing Spatial
or transformation configuration is a statement error in either mode.
