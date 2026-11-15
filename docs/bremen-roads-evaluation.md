# Bremen: roads 1.0.0 real-input evaluation

Evaluated locally on 15 November 2026 against baseline
`dde34f04b4e0d309478694a46b8c79ce40de20f5`. No Rust implementation, public SQL API,
selection rule or resource limit was changed. This is integration evidence for
one small source, alongside the [synthetic acceptance suite](roads-verification.md),
not geographic completeness or national-scale evidence.

## Source and acquisition

The [Geofabrik Bremen page](https://download.geofabrik.de/europe/germany/bremen.html)
was checked before acquisition. It advertised the dated file below at 21,277,127
bytes; an HTTP HEAD independently confirmed that size and HTTP 200 before GET.
This is below the reader's 536,870,912-byte snapshot limit. Existing repository
caches and Bremen-named files in temporary/download caches contained no reusable
PBF. Acquisition was an explicit setup action, outside the extension and tests.

| Identity | Recorded value |
|---|---|
| Original URL | `https://download.geofabrik.de/europe/germany/bremen-261114.osm.pbf` |
| Resolved URL (HEAD) | Same dated URL; no redirect observed |
| Acquisition completed (UTC) | `2026-11-15T19:20:00.460345+00:00` |
| HTTP Last-Modified | `Sun, 15 Nov 2026 04:08:21 GMT` |
| HTTP ETag | `"144a9c7-66048cfe0e950"` |
| Bytes | `21277127` |
| SHA-256 | `fca9ea140a3fd8bd209b41774d9823fded54151543a0956112847f263b663410` |
| Source header timestamp | `2026-11-14T21:20:41Z` |
| Latest element timestamp | `2026-11-14T21:19:47Z` |
| Replication sequence | `4962` |
| Source generator | `osmium/1.16.0` (provider, not evaluation decoder) |
| Download/setup interval | 4.0315 s for HEAD, PBF, provider MD5 and polygon; separate from projection |

The provider's dated `.osm.pbf.md5` was also verified. SHA-256 identifies the
projected bytes; neither the moving `bremen-latest.osm.pbf` alias nor a date alone
is the reproducible identity. Geofabrik may eventually remove dated downloads:
retain a verified local copy rather than substituting a newer snapshot.

The extract definition is Geofabrik `europe/germany/bremen`, including Bremen and
Bremerhaven. [Provider technical documentation](https://download.geofabrik.de/technical.html)
describes polygon-based extraction and retaining border-crossing ways and
multipolygons whole. The advertised [Bremen polygon](https://download.geofabrik.de/europe/germany/bremen.poly)
was saved during setup, 9,910 bytes, SHA-256
`7d008118ef4d1f1f04d2254548acd6bba104dae337a19d4d8ec369d09208687e`.
This is the polygon available at acquisition, not proof of an immutable historical
boundary version. The PBF header bbox is `[8.480959,53.01034,8.991268,53.61063]`;
the actual node extent is `[7.8885267,52.7067577,9.1511067,54.2873748]`.
The evaluation selects from the whole supplied file, without clipping or applying
another regional filter. Thus counts do not mean roads strictly inside a state boundary.

Data attribution: **© OpenStreetMap contributors, processed by Geofabrik GmbH**.
Data and the small source-tag excerpts in [the cases](bremen-roads-cases.json)
are under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), with
[OSM attribution/license information](https://www.openstreetmap.org/copyright).
The public provider extract omits user, uid and changeset metadata. Versions and
timestamps are present for every element in this file. Software licensing remains
the separate project choice recorded in Concept.md.

## Runtime and build identity

| Component | Version actually exercised |
|---|---|
| DuckDB engine and Python client | `2.0.0`, engine source `d54cbbe3df`, `osx_arm64` |
| Baseline release extension footer | `0.1.0-dde34f04b4-f0cb2a6e5d` |
| Baseline packaged extension SHA-256 | `b533f35b7de85354ee607b703e2d66b47777703ee0f73f53a49f36079e2ed380` |
| Profile / schema | `roads` `1.0.0` / `1.0.0` |
| Rust / bindings | `rustc 1.98.1 (48a229cea 2026-09-01)` / `duckdb-neo 0.20000.2` |
| Spatial | `a3dbcd1781` |
| Spatial artifact SHA-256 | `212ca75890f576bec4a9ea71f5a10320581fe9886afceb05b1d47944ebcf03f4` |
| Runtime / compiled PROJ | `9.1.1` / `Rel. 9.1.1, December 1st, 2022` |
| Independent decoder | Osmium CLI `1.19.0`, libosmium `2.23.0` |
| Evaluator | CPython `3.11.9`, Apple Clang `13.0.0` |
| Reference SQLite | Python SQLite `3.45.1` |
| Projection SQLite | bundled SQLite `3.46.0`, `rusqlite 0.32.1`, `libsqlite3-sys 0.30.1` |

The Osmium executable SHA-256 was
`220844c38d74228fbe443ea6853ac5345bb54cf978455694420515ec3baba593`.
Spatial's embedded PROJ database identity remains the hash-pinned one recorded
in [the foundation note](native-foundation.md#coordinate-path-and-provenance).

The baseline was rebuilt with `make release` before adding evaluation scripts,
then retained as `/private/tmp/ducklocate-bremen-20261115/baseline/ducklocate.duckdb_extension`.
Its footer names the exact starting commit and build-input digest. Subsequent
builds include the new Python scripts in their digest and therefore have another
extension identity even though the Rust implementation is unchanged. Version and
platform compatibility checks stayed enabled; only local unsigned loading was
explicitly allowed. The evaluator verifies both loaded and locally installed
Spatial bytes. No installation is performed during evaluation.

## Independent reference and reconciliation

[`roads_oracle.py`](../scripts/roads_oracle.py) runs
`osmium cat SOURCE -f osm --no-progress`, checks its exit status and streams the
decoded XML into a separate SQLite reference. No DuckLocate decoder, Rust rule
function, synthetic fixture encoder, geometry assembler or node-location filter
supplies expected data. All nodes and versions are indexed before resolving ways,
including dependencies outside the selection and regardless of record order.
Duplicate type/ID identities and duplicate tag keys fail the oracle. Ordered node
references are preserved separately from first-reference-order unique lineage.
Missing nodes are listed and required geometry failures are derived before the
native read. `osmium fileinfo -e -j --no-crc` independently cross-checks element
counts and records header/metadata details.

| Counting unit | Independent / native result |
|---|---:|
| Input nodes | 1,668,778 |
| Input ways | 329,676 |
| Input relations | 6,011 |
| Excluded ways without `highway` | 256,452 |
| Excluded highway ways with exact `area=yes` | 475 |
| Selected ways | 72,749 |
| Successful features | 72,749 |
| Rejected features | 0 |
| Missing selected-way references | 0 |
| Ordered output vertices, including repeats | 359,516 |
| Unique-per-feature lineage entries, including primary ways | 431,501 |
| Closed selected ways, retained as lines | 492 |
| Features with optional warnings | 2,605 |
| `unsupported_value` warning instances | 2,443 |
| `conditional_value` warning instances | 314 |
| `missing_reference`, `invalid_geometry`, `transformation_failed` | 0 each |

Reconciliation: `329676 = 256452 + 475 + 72749` and
`72749 = 72749 + 0`. The selected-ID digest is SHA-256 of sorted decimal IDs,
one per newline:
`bd143b8151f6411c2cea640c6be6a466e0513c46f3acf5cabc30d4b6dfea0765`.
Comparison walks both complete ordered ID streams and rejects missing/extra IDs;
it does not rely on matching counts or a sample.

Every row was compared for its primary version, all original tags, name/surface,
class, interpreted speed/direction, ordered coordinates and complete unique lineage
with node versions. It also checks status, ordered issue code/severity/field/raw
value, hash, profile/schema/build identities, CRS and all 19 schema columns/types.
Human-readable issue messages participate in repeat determinism, but are not a
version-stable oracle requirement. All selected primary and dependency versions
are present. No discrepancy or demonstrated implementation defect was found.

Warnings follow the existing strict policy. In particular, `oneway:bicycle`
accounts for 1,232 unsupported warnings; `maxspeed:type` for 816;
`maxspeed:variable` for 226. There are 312 `maxspeed:conditional` and two
`oneway:conditional` warnings. Other `maxspeed:*`/`oneway:*` scopes remain
unsupported, including nested names such as `maxspeed:type:conditional`;
only the exact documented conditional key gets the conditional code. Multiple
issues on a way explain why 2,757 warning instances exceed 2,605 warned features.
Scalar `none` can be suppressed by a scoped tag before scalar parsing.

Observed maxima over all elements were 354 tags, 8,400 UTF-8 tag bytes and 4,897
way references/relation members: below 4,096 / 65,536 / 10,000 respectively.
The total 2,004,465 elements fits the 10-million limit. The native scans also
completed under the unchanged PBF-block and 2 GiB index limits; the oracle does
not independently inspect protobuf field/string-table counts.

## Documented real-way expectations

[Fourteen literal cases](bremen-roads-cases.json) were chosen from Osmium's
source-tag inventory before the native comparison. Their versions, relevant tag
strings and interpreted expectations are pinned to the source hash. Expected
values are independently derived from [roads 1.0.0](roads-v1.md), not captured
native answers. The complete comparison still checks every source tag for every way.

| Way | Derivation from source tags |
|---|---|
| 3999478 v37 | secondary, `50`, `yes` → 50 km/h, forward |
| 3999490 v8 | residential, `30` plus `maxspeed:type=DE:zone30` → NULL speed, scoped warning |
| 4000171 v21 | unclassified, `50`, closed 20-reference line → 50 km/h, NULL direction, closure retained |
| 4000178 v13 | residential, `30`, `yes` plus `oneway:bicycle=no` → 30 km/h, NULL direction, scoped warning |
| 4000247 v34 | path, asphalt, absent speed/direction → both NULL |
| 4003694 v57 | secondary, base `50`, conditional `30 @ (22:00-06:00)` → NULL speed, conditional warning; `yes` → forward |
| 4006412 v24 | motorway, `120` plus `maxspeed:variable=signals` → NULL speed, scoped warning; explicit `yes` → forward |
| 4265275 v20 | unclassified, `50`, `no` → 50 km/h, both |
| 4280092 v18 | tertiary, backward `50` and forward `30` scopes → NULL speed, two lexical-order warnings |
| 4308668 v21 | trunk, `none` plus advisory `40` → NULL speed and advisory warning; explicit `yes` → forward |
| 4351147 v28 | primary, `signals` → NULL speed, unsupported scalar warning |
| 27644505 v11 | service, `-1` → backward; geometry remains in source order |
| 524526965 v6 | residential, `30`, `alternating` → 30 km/h, NULL direction, warning |
| 1153729931 v3 | service, `walk`, `yes` → NULL speed with warning, forward |

The selected data contains 20 distinct scalar maxspeed strings: positive integer
strings and `none`, `signals`, `walk`. No decimal, explicit km/h, mph or knots
scalar occurs. The real extract therefore supplies numeric/symbolic/scoped/
conditional coverage, while the synthetic fixtures retain the precise decimal,
unit-conversion, alias, malformed, missing-reference and rejection coverage.
No real rejection or missing reference was invented to create coverage.

## Native workflow and offline execution

The evaluator runs separate native processes for complete report-mode CTAS,
fail-mode CTAS, a complete repeated report read, and EPSG:3857 CTAS. The initial
table is closed, reopened and compared, including native Spatial LineString/type/
vertex-count queries on its GEOMETRY column and Python nested-value inspection.
Fail mode succeeds with 72,749 rows because only optional warnings occur; its
closed table is also fully compared. This source cannot establish real-input
geometry-error behavior; synthetic tests retain that responsibility.

The repeat comparison uses all columns, rows ordered by osm_id, geometry as WKB
hex and nested values as canonical JSON. Its logical SHA-256 matches the reopened
baseline table: `008c080f2560999056afd50a412d12802a8d663b1e3fd33500307e6b1c3b2fa2`.
This digest includes the extension footer identity; a different build identity
changes it. No byte-identical database-file claim is made.

Every EPSG:3857 vertex is compared with the independent spherical Mercator
equations `x=6378137*radians(lon)` and
`y=6378137*log(tan(pi/4+radians(lat)/2))`, at absolute **1e-6 m**, zero relative
tolerance. Default lon/lat comparisons allow **1e-12 degree** solely for floating
representation. The same reference tags, IDs, versions, interpreted fields and
lineage are checked in both CRSs.
Observed maximum absolute errors were `4.656612873077393e-10 m` in X and
`7.450580596923828e-9 m` in Y. Default-coordinate differences were at most
`1.7763568394002505e-15` longitude / `7.105427357601002e-15` latitude degrees.

The complete run uses macOS `sandbox-exec` with `(deny network*)`, inherited by
Osmium and every native worker. `--require-network-denied` additionally asserts
that a TCP connection attempt fails with EPERM/EACCES, rather than mistaking an
unreachable host for an enforced deny policy. Automatic extension installation
and loading are disabled; locally installed hash-verified Spatial is loaded
explicitly. The internal transformer still enforces its documented caller-policy
restriction. All reads, oracle work, persistence and reprojection complete inside
the network-denied process tree after setup.

## Resource baseline

The first complete measured report-mode materialization, using the pinned
baseline release artifact and EPSG:4326, recorded:

| Measurement | Result |
|---|---:|
| Full CTAS + checkpoint + close | **10.3362 s** |
| Peak native-worker process RSS | **180,158,464 bytes (171.81 MiB)** |
| Sampled peak temporary files, logical size | **113,420,743 bytes (108.17 MiB)** |
| Sampled peak temporary files, allocated blocks | **122,335,232 bytes (116.67 MiB)** |
| Sampled peak working files including output DB/WAL, logical | **113,433,031 bytes** |
| Closed persistent output DB | **7,614,464 bytes (7.26 MiB)** |
| Temporary-storage samples | 417 |
| Temporary files remaining after worker exit | 0 |

Machine: Apple M1, eight CPU cores, 16 GiB RAM; macOS 15.7.4 (`24G517`),
Darwin 24.6.0 arm64. DuckDB uses two threads and `memory_limit='256MB'`, normal
persistent storage/compression, no output R-tree or custom compression tuning.
The transformer uses its existing one-thread isolated session. The existing
reader uses its unchanged 8 MiB SQLite page-cache target, no mmap and on-disk
temporary work. No CPU affinity, host-isolation or cold-cache protocol was used;
previous source/oracle reads may warm the filesystem cache. No speculative
optimization was performed.

`time.perf_counter()` starts immediately before the complete SQL CTAS and stops
after CHECKPOINT and connection close. Connection creation, extension loading
and version queries occur before that interval. The isolated worker's entire
process is wrapped in `/usr/bin/time -l`; its kernel maximum-resident-set value
includes Python, DuckDB, loaded Spatial, Rust buffers and bundled SQLite. This
is process RSS, not DuckDB allocator statistics. Its scope includes setup/load
overhead even though the projection timer excludes that overhead. The first
worker's total OS elapsed time was 10.74 s.

The parent polls a private worker `TMPDIR` and DuckDB `temp_directory` every
20 ms nominally, sums `st_size` and separately `st_blocks*512`, and tolerates
cleanup/rename races. The private source snapshot and SQLite dependency index
are included, along with any DuckDB spill files. At the logical peak, the
21,277,127-byte snapshot plus 92,143,616-byte index account for the measured
113,420,743 bytes. The separately reported working-file peak also includes output
DB/WAL growth. The final output DB size is measured only after checkpoint/close.
APFS allocation, compression and copy-on-write behavior mean allocated blocks
are not a device-wide space-use measurement. Unlinked open files, OS filesystem
cache, sampling gaps and very short peaks are not captured by this disk method.
The sampled disk peaks are observed lower bounds, not hard resource bounds.

Acquisition took 4.0315 s and the formal run's independent decode/reference
preparation took 17.1838 s; neither is projection time. The separate reference
SQLite occupied 144,330,752 bytes and is not charged to the native materialization.
The parent/reference process has no OSM data allocations in the native worker.
Peak memory for the whole evaluator plus oracle is not the reported native RSS.
Supplementary fail/repeat/Mercator worker statistics are retained in local JSON;
the repeat timer includes canonical-JSON comparison work, and some later
verification ran concurrently with Mercator. They are not comparable throughput
benchmarks. These are single-machine observations with no national-scale
extrapolation or performance target.

The finalized-evaluator verification rerun used the same baseline binary and
source: 12.5655 s, 180,011,008-byte peak RSS, the same 113,420,743-byte sampled
logical temporary peak and 7,614,464-byte closed DB. This was not a controlled
performance experiment; the elapsed-time variation is another reason to treat
the first observation as an initial resource measurement.

## Reproduce the evaluation

Use macOS arm64, the repository's pinned runtime/toolchain and Osmium CLI 1.19.0
with libosmium 2.23.0. For a new machine, acquire tools explicitly during setup.
Reuse verified local artifacts where available. These commands are opt-in:

```sh
make configure
configure/venv/bin/python3 scripts/setup_spatial.py
make release
make test_release
```

The native test setup explicitly installs the pinned local Spatial binary into
`.cache/roads-extensions`. To acquire the source explicitly (skip GET for an
already verified local copy):

```sh
mkdir -p /private/tmp/ducklocate-bremen-20261115
curl --fail --location --head https://download.geofabrik.de/europe/germany/bremen-261114.osm.pbf
# Check Content-Length against 536870912 before downloading.
curl --fail --location --output /private/tmp/ducklocate-bremen-20261115/bremen-261114.osm.pbf \
  https://download.geofabrik.de/europe/germany/bremen-261114.osm.pbf
shasum -a 256 /private/tmp/ducklocate-bremen-20261115/bremen-261114.osm.pbf
```

Run the evaluator with a **new** output directory; it never downloads or overwrites
an existing evaluation. It accepts other local paths/hashes; the literal case
file applies only to the pinned Bremen hash. Assertions must remain enabled.

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' \
  configure/venv/bin/python3 scripts/evaluate_roads.py \
  /private/tmp/ducklocate-bremen-20261115/bremen-261114.osm.pbf \
  fca9ea140a3fd8bd209b41774d9823fded54151543a0956112847f263b663410 \
  --output /private/tmp/ducklocate-bremen-20261115/reproduction \
  --cases docs/bremen-roads-cases.json --require-network-denied
```

The measured baseline used the same command with `--extension
/private/tmp/ducklocate-bremen-20261115/baseline/ducklocate.duckdb_extension`,
`--output /private/tmp/ducklocate-bremen-20261115/evaluation` and
`--source-manifest /private/tmp/ducklocate-bremen-20261115/source.json`.
The optional acquisition manifest is validated against source hash and size;
it is not needed for independently checking an already pinned local source.
The finalized evaluator was then run to `evaluation-final`, adding a full
fail-table comparison to the same workflow and retained baseline binary.

Local output contains the independent `oracle.sqlite`, `reference.json`, per-run
worker specifications/logs/time output, persistent native tables and a final
`evaluation.json` written only on complete success. Sources, databases and raw
generated results remain outside Git. The short [README SQL example](../README.md#pinned-real-input-example)
uses the same pinned file and hash.

## Verification of repository changes

The final evaluator passed the complete network-denied workflow described above.
The README's pinned real-input SQL example was executed with the final release
build and returned `ok,72749`. The wrong-source-hash guard failed before creating
an output directory, and Python `-O` was explicitly rejected. Python compilation,
documentation relative-link checks and `git diff --check` passed.
A one-off negative comparison check independently perturbed the first reference
way's ID, version, raw tag, vertex order, node lineage version, speed and issue
list; all seven discrepancies were rejected. Real acceptance expectations and
source bytes were unchanged.

These commands passed from the repository root:

```sh
cargo fmt --all --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
make release
make test_release
configure/venv/bin/python3 scripts/test_native_checks.py
configure/venv/bin/python3 scripts/test_roads_review.py build/release/ducklocate.duckdb_extension
python3 -m py_compile scripts/evaluate_roads.py scripts/roads_oracle.py scripts/roads_eval_native.py scripts/roads_eval_compare.py
git diff --check
```

Cargo passed five tests. Release acceptance passed both SQLLogicTest files and
the full synthetic native roads/security/lifecycle suite. The acceptance-guard
suite passed three tests; the prior roads-review regressions passed two tests.
The final packaged normal-release artifact reported
`0.1.0-dde34f04b4-ee783af79f`, SHA-256
`d4d3c44a63d08553b930e1685a92dcb14e35f181a915f8952fbdb58811d7bee0`.
This artifact differs in footer identity from the separately retained measured
baseline because the build digest includes the new evaluator scripts.
No Rust implementation changes required new defect regression fixtures. Debug
and probe builds were not rerun for this evaluation-only change.

## Oracle and remaining limitations

Osmium/libosmium is a maintained independent decoder, not a second source of OSM
truth. Its [streaming conversion](https://docs.osmcode.org/osmium/latest/osmium-cat.html)
does not validate geographic completeness or all profile semantics; those are
derived explicitly by this evaluator. XML uses libosmium's OSM coordinate precision
(1e-7 degree); this does not validate hypothetical finer-than-OSM PBF coordinates.
Metadata absence can be represented differently by independent decoders; this
file supplies versions everywhere, so absent-version behavior remains synthetic
coverage. XML conversion also cannot establish acceptance/rejection of every
unusual protobuf encoding. No location/area assembler is used, so missing refs,
closed lines and duplicate node references remain visible to the comparison.

Sampling can miss short temporary-storage peaks, and process high-water RSS is
not a bound on all host memory or filesystem cache. This run neither tunes the
implementation nor extrapolates Bremen to Germany. Reader hard limits,
cancellation latency during preparation, abrupt-death cleanup and unresolved
runtime transformation-operation/grid identities remain as documented in the
[roads contract](roads-v1.md) and [native foundation](native-foundation.md).
Downloads, named regions, other profiles, CLI and import operations remain
unimplemented. `.idea/` and `identifier.db` were preserved.

## Evaluator corrections to 1d2b146: separate verification

Verified locally on 2026-11-15. The two findings concern the evaluation tools,
not the native extension or the pinned Bremen results above. Fixed count fields
are now initialized to zero in the independent decoder, reference summary and
native comparison, including documented diagnostic codes. Geometry expectations
are derived for the requested CRS: spherical Mercator is undefined at either
pole, after missing-reference and invalid-source-geometry checks. Optional
warnings retain their order before the geometry error. Successful-coordinate
tolerances remain absolute 1e-12 degree / 1e-6 metre, zero relative tolerance.

The [literal XML sources and their derivations](../test/fixtures/roads-evaluator/README.md)
are independent of DuckLocate's decoder and the synthetic protobuf writer.
Osmium converts them to temporary PBFs outside Git. Before the evaluator fixes,
the five initial regression tests failed: zero-selected and node-only empty
profile results raised `KeyError: 'selected'`; a selected road without relations
raised `KeyError: 'relation'`; the no-elements oracle omitted all zero count
fields; the pole input reached EPSG:3857 comparison and disagreed on the expected
`transformation_failed` issue. These failures used the retained baseline native
artifact, with no native implementation changes.

After correction, all **six evaluator tests pass**. They exercise full empty
evaluations with the exact persisted/reopened 19-column schema, zero rows,
deterministic repeats, both output CRSs and successful fail-mode materialization.
The pole source succeeds for its two polar lines in EPSG:4326, rejects them with
NULL geometry in EPSG:3857 report mode and raises `transformation_failed` in
EPSG:3857 fail mode without publishing a table. Missing-reference and invalid
source-geometry precedence, ordered warnings, identity, raw tags and resolved
lineage are checked across CRSs. Deliberately missing/extra native rows still
fail comparison; duplicate oracle identities still raise an error.

Commands exercised with existing verified local artifacts:

```sh
configure/venv/bin/python3 scripts/test_roads_evaluator.py /private/tmp/ducklocate-bremen-20261115/baseline/ducklocate.duckdb_extension
configure/venv/bin/python3 scripts/test_native_checks.py
configure/venv/bin/python3 scripts/test_roads_review.py build/release/ducklocate.duckdb_extension
make test_release
configure/venv/bin/python3 -m py_compile scripts/evaluate_roads.py scripts/roads_oracle.py scripts/roads_eval_native.py scripts/roads_eval_compare.py scripts/test_roads_evaluator.py
git diff --check
```

The acceptance guards passed **3 tests** (all four wrong-mode rejections,
independent control point and all four +/-5 mm discrepancies). The earlier native
review regressions passed **2 tests**. Release acceptance passed both SQLLogicTest
files and the complete normal native suite. That existing release artifact is
the historical `d4d3c44a63d08553b930e1685a92dcb14e35f181a915f8952fbdb58811d7bee0`
artifact identified above. No Rust, dependency, native build configuration or
native behavior changed; no native rebuild, Rust checks, debug/probe suites,
downloads or setup were performed for this correction. The footer digest includes
Python scripts, but these checks deliberately reuse the identified native bytes.

The complete pinned Bremen evaluation was rerun with the reproduction command
above, adding the retained baseline `--extension` and `--source-manifest`, and
using the new output directory
`/private/tmp/ducklocate-bremen-20261115/evaluation-review-correction`.
macOS `sandbox-exec` enforced `(deny network*)` for the complete process tree;
`--require-network-denied` additionally proved EPERM/EACCES. The outer workspace
sandbox initially refused nested sandbox creation, so the same command ran
outside that outer sandbox while retaining OS-enforced network denial.

Reconciliation with `evaluation-final/evaluation.json` preserves all 72,749
selected/successful ways, zero rejections, 359,516 vertices, 431,501 lineage
entries, 2,605 warned features and warning counts 2,443/314. Both CRS comparisons
preserve geometry, all feature fields, lineage, diagnostics and schema. Default,
fail and repeated logical digests remain
`008c080f2560999056afd50a412d12802a8d663b1e3fd33500307e6b1c3b2fa2`;
the Mercator logical digest and maximum coordinate errors also match the
historical run exactly. The only count-report differences are explicit zero
fields previously omitted. Source, baseline extension, Spatial and Osmium hashes
are unchanged. This is a correctness rerun, not a controlled performance
experiment; its timing/resource samples remain in the separate local output.
The historical benchmark observations above are unchanged.

Full arbitrary transformation-operation/grid provenance remains unresolved;
no operation metadata was fabricated or comparison weakened. Osmium 1.19.0's
extended JSON `fileinfo` errors on a completely node-free extent; this real tool
failure is still propagated. Zero counts for that source are tested directly in
the oracle, while empty profile results complete the full evaluation. Existing
platform, resource and scale limitations continue to apply.
