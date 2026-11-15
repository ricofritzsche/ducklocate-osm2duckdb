# Roads vertical slice verification

The original milestone evidence below is historical. The final section records
the subsequent corrections to the two review findings at `a8946c6`; its artifact
identities are separate from the original results.

Verified locally on 2026-11-15, macOS arm64. This milestone retains DuckDB **2.0.0**,
Rust **1.98.1**, `duckdb-neo` **0.20000.2**, C API v2 `C_STRUCT_UNSTABLE`, platform
`osx_arm64`, and the existing footer/version/platform/signature acceptance guards.
The public normal function set is exactly `{ducklocate_profiles, ducklocate_read}`.
Probe builds add exactly `{ducklocate_probe_rows, ducklocate_probe_transaction}`.
The harness rejects either build mode presented as the other before accepting it.
No downloads, other profiles, CLI, source-inspection/import API or updates were added.

## Contracts and independent input

[Roads 1.0.0](roads-v1.md) was specified before implementing the reader and is
linked from the README. Official OSM element/tag documentation is cited there.
The decoder follows the [OSM PBF format](https://wiki.openstreetmap.org/wiki/PBF_Format)
and [OSM-binary protocol schemas](https://github.com/openstreetmap/OSM-binary/tree/master/osmpbf);
protocol interpretation is separate from project profile policy.

Six small tracked PBFs come from [hand-authored JSON](../test/fixtures/roads/README.md).
`scripts/make_roads_fixtures.py` is an independent Python/std-lib encoder, not the
reader or an expected-output generator. Native acceptance verifies its bytes
match the tracked PBFs without rewriting them. Counts, coordinates, attributes,
lineage and expected diagnostics are derived in the fixture note and explicitly
asserted in `scripts/roads_checks.py` and SQLLogicTest. The main valid fixture has
14 selected ways; its SHA-256 is
`3327c5e3b88bf280d0c53d9ffd6ddecd39f835d6eca818c9b7745b8f4c128480`.
A temporary 5,000-way fixture exercises chunks and full nested values; it is not
tracked or presented as a scale benchmark.

## Commands and results

All commands ran from the repository root. Rust checks passed:

```sh
cargo fmt --all --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
```

Five Rust tests passed: source XY/range validation, every-vertex WKB validation,
malformed protobuf wire decoding, numeric speed grammar/units, and hash assertion
before decoding. Native acceptance is the principal end-to-end correctness check.

All four build/test combinations passed. Each test target runs both
`test/sql/catalogue.test` and `test/sql/roads.test`, followed by the native suite:

```sh
make debug
make test_debug
make release
make test_release
make debug PROBES=1
make test_debug PROBES=1
make release PROBES=1
make test_release PROBES=1
configure/venv/bin/python3 scripts/test_native_checks.py
```

The acceptance-guard unit suite passed 3 tests: four wrong-mode combinations,
the recorded control point and four independent ±5 mm discrepancy cases.
Normal and probe suites check the actual engine release/platform, unsigned-loading
rejection, deliberately wrong engine/platform footers and the exact function set.

The full debug and release probe suites also passed under enforced network denial:

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/probes/debug/ducklocate.duckdb_extension --expect-mode probe
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/probes/release/ducklocate.duckdb_extension --expect-mode probe
```

The local Spatial artifact SHA-256 remains
`212ca75890f576bec4a9ea71f5a10320581fe9886afceb05b1d47944ebcf03f4`.
The reader verifies Spatial revision `a3dbcd1781`, runtime PROJ `9.1.1` and compiled
PROJ `Rel. 9.1.1, December 1st, 2022` before transformation. Line vertices are
checked against independent spherical Mercator equations with absolute tolerance
**1e-6 m** and zero relative tolerance. This is numerical agreement, not source
accuracy. The embedded database identity and unresolved operation/grid provenance
remain as described in [the foundation evidence](native-foundation.md#coordinate-path-and-provenance).

## Historical roads artifact identities

All four packaged artifacts report `0.1.0-77be3fba8f-34169724e7`. The revision prefix is
the parent checkout revision; the digest identifies the uncommitted build inputs,
as in the foundation build-identity scheme. Artifacts are ignored local outputs.

| Artifact | SHA-256 |
|---|---|
| normal debug | `7bad7b42e26228ee071eb371772bae04a3273841e54fe4e8416d9a3a036bd1cf` |
| normal release | `9e8f3f8dc7d759fa0094292ae6e2ab473ec2fba68b5e1da1756db18fd1c0f2c0` |
| probe debug | `036a15014b1fc55a646c51e27de239bfb676e8523b8d7d22c5cf47b3d44f0c1b` |
| probe release | `7a0723e5a8adbc914add301f251076edacbfe4b43d00c737f4574e064e8d62d3` |

The README local-file and offline-reprojection shell examples were also executed
successfully. The hardened macOS shell needs an absolute extension LOAD path;
the runnable examples expand `$PWD` in the shell.

## Native checks exercised

- Exact 19-column schema and nested maps/lists/structs; absent versions, Unicode,
  empty strings, NULL scalars, stable diagnostic codes/order and unique lineage.
- Highway presence, unknown/empty classes, area exclusion, closed lines, way-node
  order, shared nodes, ways before nodes in separate blocks, raw/zlib blocks,
  ordinary/dense nodes with present/absent metadata; relations do not select rows.
- Numeric/default/km/h/mph/knots speeds, conditional/scoped/symbolic/malformed
  values, explicit direction aliases, backward direction without geometry reversal,
  absent direction and no inferred roundabout/motorway direction.
- Missing references, short/empty/degenerate lines, invalid interior latitude and
  longitude, Web Mercator poles, both error modes and independently established
  attributes retained on rejection. Probe tests also reject an interior NaN after
  transformation, including when surrounding coordinates are finite.
- Empty output, full 5,000-row nested values across small chunks, changing validity
  and issue lists, filtered scans, LIMIT, repeated prepared statements/views,
  simultaneous selections in one connection and across two connections.
- Caller-owned transactional CTAS/rollback after a rejected source; persistent CTAS
  reopened with genuine GEOMETRY/nested types, Spatial text/predicate and R-tree use.
- Correct/uppercase/NULL hash assertions, mismatch, source pathname replacement
  after opening, and live-file in-place mutation after snapshotting. Successful
  results retain the original snapshot hash and original feature count.
- NULL/unknown/malformed arguments; DESCRIBE/EXPLAIN with an absent path; corrupt
  framing/protobuf/UTF-8/dense arrays, unsupported history, duplicate/conflicting
  identities (including identical duplicates), source/reference resource limits.
- Source policy under disabled external access, path/directory allowlists and
  disabled LocalFileSystem; missing installed Spatial fails in both error modes,
  even for empty output. No implicit install/autoload is enabled in the reader.
- Temporary cleanup after EOF, LIMIT, feature/technical failures and interruption
  while scan-owned files exist. Each acceptance process has a private temp root
  so concurrent harnesses cannot confuse active files with leaks. A harness race
  discovered during verification was fixed by isolating those roots; checks were
  rerun. Interruption may wait for bounded snapshot/index preparation because the
  pinned callback context has no cancellation-poll API.

## Remaining limits

Only local snapshot PBFs and roads 1.0.0 are implemented. No real/national extract
performance, peak-memory measurement or broader-platform support is claimed.
The hard input/index/record limits deliberately reject some valid inputs. Rust
buffers and the SQLite cache are outside DuckDB memory accounting. Abrupt process
termination can leave OS temp files. Empty materializations need caller-retained
metadata. Complete runtime transformation operation/grid provenance is unresolved.
The CLI, downloads, regions, other profiles, incremental updates, routing and
`ducklocate_import` remain outside this milestone.

## Review corrections to a8946c6

Verified locally on 2026-11-15 against the same pinned runtime and platform.
The SQL signatures, 19-column schema, profiles and foundation acceptance guards
remain unchanged. No downloads or additional product operations were introduced.

### Regressions before the corrections

Before editing either Rust file, `make debug` rebuilt the original Rust code with
the new regression harness. That packaged baseline reported
`0.1.0-a8946c61ca-8704c97474`, SHA-256
`36827f1a380813f0ea26898f399a072a2a3f991947317933bdbcec3d9a38f2ec`.
Its parent revision is `a8946c6`; the digest includes the uncommitted test changes.
The baseline artifact was retained outside Git for the comparison:

```sh
configure/venv/bin/python3 scripts/test_roads_review.py /tmp/ducklocate-review-baseline/ducklocate.duckdb_extension
```

Result: **2 tests failed**, each because a required statement error was absent.
Additional direct queries against this same baseline established the full matrix:

- Allowlist only the individual source, set `enable_external_access=false`, then
  `lock_configuration=true`. The caller's `LOAD spatial` failed with
  `Loading external extensions is disabled through configuration`, but
  EPSG:3857 reads succeeded: 14 rows for `valid`, zero rows for `empty`, in both
  `fail` and `report` modes (four unintended successes).
- `duplicate-dense` returned way 303 with status `ok` and
  LINESTRING(2 49,2 2) in both modes. The control `split-dense`, containing the
  same payload bytes inside one DenseNodes message, returned
  LINESTRING(2 49,3 50) in both modes. The independently derived delta arithmetic
  is recorded in [the fixture note](../test/fixtures/roads/README.md).

### Corrected observable contract

The transformation path reads the caller's external-access setting before
looking up the extension directory or creating/loading the internal instance.
When disabled it raises
`EPSG:3857 requires loading Spatial; caller has enable_external_access=false`.
This is a statement error for both modes, including an empty source. Default
EPSG:4326 reads still return 14/zero rows for the respective allowlisted inputs
under the same locked configuration. The tests also assert that external access
stays disabled and configuration stays locked. The current integration requires
its own Spatial load even if the caller already loaded Spatial; the restriction
is documented in [the contract](roads-v1.md#execution-security-and-resource-limits)
and README. There is no process-global transformation engine.

PrimitiveGroup field 2 now uses the existing singular-field accessor: duplicates
raise `invalid PBF: duplicate singular field` in both modes. No protobuf message
merging is implemented. The paired legal split-packed fixture still has the
independently expected coordinates, status, empty issues and lineage in both
modes. Existing ordinary/dense-node, metadata and numeric-array tests remain.
Both regressions run in every normal/probe native suite; SQLLogicTest additionally
checks duplicate rejection in both modes and the legal split-field control.

### Correction verification and artifact identities

All of these commands passed from the repository root:

```sh
cargo fmt --all --check
cargo test --workspace --locked
cargo test --workspace --all-features --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
make debug
make test_debug
make release
make test_release
make debug PROBES=1
make test_debug PROBES=1
make release PROBES=1
make test_release PROBES=1
configure/venv/bin/python3 scripts/test_roads_review.py build/debug/ducklocate.duckdb_extension
configure/venv/bin/python3 scripts/test_native_checks.py
```

Both Cargo test configurations passed **5 tests**, with no ignored or failed
tests. Each of the four native test targets passed **2 SQLLogicTest files**
(`catalogue.test`, `roads.test`) and the complete native acceptance suite.
The targeted review suite passed **2 tests**, versus its two baseline failures.
The acceptance-guard suite passed **3 tests**, retaining all four wrong-mode
rejections and all four independent +/-5 mm discrepancy rejections. Footer,
engine/platform, unsigned-loading and exact function-set checks remain enabled.

All four complete native suites also passed with OS-enforced network denial:

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/debug/ducklocate.duckdb_extension --expect-mode normal
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/release/ducklocate.duckdb_extension --expect-mode normal
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/probes/debug/ducklocate.duckdb_extension --expect-mode probe
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/probes/release/ducklocate.duckdb_extension --expect-mode probe
```

The workspace sandbox initially refused to create the nested macOS sandbox
(`sandbox_apply: Operation not permitted`). The same commands ran successfully
outside that outer sandbox, retaining the explicit `deny network*` policy.
Permitted EPSG:3857 reads succeeded in every run, using the existing local Spatial
artifact. Its hash and Spatial/PROJ version checks remain unchanged. Road vertices
retain absolute **1e-6 m** tolerance with **zero relative tolerance** against the
independent Mercator equations. Probe runs again measured the control point
`(222638.98158654713, 6274861.394006575)`.

The corrected artifacts all report `0.1.0-a8946c61ca-f0cb2a6e5d`. As before,
the revision identifies the parent checkout and the digest identifies the actual
uncommitted build inputs; these are local verification artifacts, not a claim that
the footer names the subsequent correction commit.

| Corrected artifact | SHA-256 |
|---|---|
| normal debug | `3fc5675c817627c324fb25f6080bbed0eb25f25c69a6f485816681cedf1fd899` |
| normal release | `ff9827eef88a1058784ceab968e40d4f21488c9b5c9af826b41640c95f571d05` |
| probe debug | `402fe4fe69d5e04afd824e4c79d092b39a9fb07904233f72ecaeed73081e76db` |
| probe release | `4c97e9f1cb4d9733ef52d54c9d996a2d355b5d48dd135f18dc5b0a97b3fa4285` |

Diff whitespace checks and updated documentation relative-link target checks
passed. No issues remain for these two findings. The earlier platform, scale,
resource-accounting and transformation-provenance limits remain; no additional
support or performance claim is made by this correction.
