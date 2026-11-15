# Native foundation: DuckDB 2.0.0

Verified 15 November 2026. This is the first integration milestone, not an OSM
reader. Only `ducklocate_profiles()` is public; it returns zero rows with the six
README columns. Other proposed functions are absent. No CLI crate, parser,
profile, acquisition workflow, production import or benchmark is included.

## Compatibility and official sources

| Component | Exact verified identity |
|---|---|
| Host | macOS 15.7.4 (24G517), Darwin 24.6.0, arm64; DuckDB platform `osx_arm64` |
| Rust | 1.98.1, `48a229cea` (2026-09-01), edition 2024 |
| Engine | DuckDB v2.0.0, source `d54cbbe3df`, Cyanoptera; Python wheel and native CLI |
| Official starting template | `duckdb/extension-template-rs` at `a679601f8e133db7546777c6637bc7a6c2d2780e` |
| Official build tools submodule | `duckdb/extension-ci-tools` at `2e5d22fa1b1c42e6fc7aa84a8e66a15e6b492b30` |
| Rust binding | `duckdb-neo =0.20000.2`; binding source revision `a8bc7f2de45d8dbaf4b9853c85481722eb4fd699` |
| FFI / macros | `libduckdb-sys =1.20000.2`, `duckdb-loadable-macros =1.20000.2`; Cargo.lock checksums |
| SQLLogicTest | Official Python runner commit `2ac8dbc012ddbd96a57dca37784fd8ee3c0eb021` |
| Python tools | Python 3.11.9, packaging 26.3, termcolor 3.3.0; Make 3.81; Xcode command-line tools available |
| Spatial | Revision `a3dbcd1781ec26c3a1be9bd622be05b376d6f47a`; official v2.0.0/osx_arm64 artifact |
| PROJ | Runtime `9.1.1`; compiled `Rel. 9.1.1, December 1st, 2022` |

Sources were checked before selecting the dependencies, including the template's
manifest/Makefile, packaged binding sources, the engine's exact-release C API
header and Spatial's exact-revision source. This follows the repository skill's
[official-source notes](../.agents/skills/duckdb-extension-development/references/official-sources.md).

- [Pinned official template](https://github.com/duckdb/extension-template-rs/tree/a679601f8e133db7546777c6637bc7a6c2d2780e): retained core/native split, entrypoint and Make targets; omitted examples and Wasm.
- [Pinned tooling](https://github.com/duckdb/extension-ci-tools/tree/2e5d22fa1b1c42e6fc7aa84a8e66a15e6b492b30): original Cargo build, SQLLogicTest and metadata-footer code, kept unchanged as a Git submodule.
- [Binding source](https://github.com/duckdb/duckdb-rs/tree/a8bc7f2de45d8dbaf4b9853c85481722eb4fd699/crates/duckdb-neo): official wrapper ownership and callback rules.
- [DuckDB 2.0 C API](https://duckdb.org/docs/2.0/clients/c/overview): v2 is unstable; an extension chooses v1 or v2.
- [Exact engine header](https://github.com/duckdb/duckdb/blob/v2.0.0/src/include/duckdb_v2.h): context, factory, vector fallback, pragma and statement APIs. Inspected header SHA-256: `73026a28e5b55952afb6e2e9ce80fd4f76614afedce329da895ccaf85a4a8be6`.
- [Spatial source](https://github.com/duckdb/duckdb-spatial/blob/a3dbcd1781ec26c3a1be9bd622be05b376d6f47a/src/spatial/modules/proj/proj_module.cpp): embedded database, disabled networking, CRS operation creation and XY normalization.
- [ST_Transform documentation](https://duckdb.org/docs/2.0/core_extensions/spatial/functions#st_transform) and [PROJ's published example/formula](https://proj.org/en/stable/operations/projections/webmerc.html).

The footer is `C_STRUCT_UNSTABLE`, engine `v2.0.0`, platform `osx_arm64`; the
entrypoint is `ducklocate_init_c_api_v2`. This is exact-version compatibility,
not support for every DuckDB 2.x runtime. Tests alter footer copies to v2.0.1 and
osx_amd64 and confirm that the runtime rejects both. Only unsigned loading of
local development artifacts is enabled; version/platform validation stays on.
Release symbol stripping happens in Cargo **before** the official footer script.

The workspace has just `ducklocate-core` and the `ducklocate` cdylib entrypoint.
The native crate enables the binding's `build-extension` feature. The shared
crate does not require that feature itself, leaving the future CLI free to use
the same code with an embedded engine. Default binding features are disabled:
the loadable extension uses DuckDB's function table and needs no downloaded or
linked engine library. This reduces dependency/build work; all versions and
checksums remain locked. SQL adapters contain no OSM rules.

## Reproduce setup, build and checks

Run from the repository root. Python 3 with venv/pip, Rustup, Make, Git and the
platform compiler/linker must be available. The checked-in rust-toolchain file
selects Rust 1.98.1 with rustfmt and clippy. Do not update dependencies to resolve
routine setup problems; first retry provisioning with the pins intact.

```sh
git submodule update --init --recursive
make configure
configure/venv/bin/python3 scripts/setup_duckdb.py
configure/venv/bin/python3 scripts/setup_spatial.py
cargo fmt --all --check
cargo test --workspace --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
make debug PROBES=1
make test_debug PROBES=1
make release PROBES=1
make test_release PROBES=1
make debug
make test_debug
make release
make test_release
configure/venv/bin/python3 scripts/spatial_identity.py
```

All of these checks passed on the platform above. SQLLogicTest reports
`[1/1] test/sql/catalogue.test` and `SUCCESS` for each build. The Rust rule test
passes; Clippy and formatting are clean. The native harness checks the public
function set and prints artifact SHA-256, footer identity and probe results.
Both normal and probe artifacts are tested. Normal artifacts must register only
the catalogue; probe builds register two extra test-only functions.

`make configure` installs the exact engine/runner; the repository additionally
pins and verifies Python support packages. A partially installed upstream venv
is recoverable by rerunning configure: the verification script fills missing or
mismatched requirements. Local Cargo/pip caches were reused where available;
sandbox DNS failures were recovered by retrying the authorized downloads with
network access. No dependency downgrade or source patch was needed.

`setup_spatial.py` explicitly acquires Spatial only if a matching cached artifact
is absent. It verifies both compressed and decompressed hashes and refuses
changed upstream bytes. Build, configure, target, caches, databases and artifacts
are ignored. No profile data is acquired. Download setup requires network access;
loading the catalogue and running local geometry transformations do not.

`setup_duckdb.py` verifies an existing shell by SHA-256 or acquires the official
[osx_arm64 release archive](https://github.com/duckdb/duckdb/releases/tag/v2.0.0)
into the ignored cache. The installed shell matched those official bytes exactly.
The archive SHA-256 published by GitHub is
`188a36fe8883ef52e69165a0cbb6031ef679c8e6c448a1ce22951964149b7f96`;
the extracted/cached shell SHA-256 is
`432e9c8012d0259e7c4630fa2136bf59fb832769ca7e0f6e374b8af2d2cebed9`.
If the script provisions a shell, use its printed `.cache/bin/duckdb` path.
For the normal release artifact, use that exact v2.0.0 shell:

```sh
duckdb --version
duckdb -unsigned -c "LOAD '$PWD/build/release/ducklocate.duckdb_extension'; DESCRIBE SELECT * FROM ducklocate_profiles(); SELECT count(*) FROM ducklocate_profiles();"
```

The result is the six README column types and a count of **0**. Both debug and
release artifacts also load in the actual shell. The Python harness independently
uses the pinned v2.0.0 wheel. Neither path sets `allow_extensions_metadata_mismatch`.

For an independently enforced offline run on macOS:

```sh
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/probes/debug/ducklocate.duckdb_extension
/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' configure/venv/bin/python3 scripts/native_checks.py build/probes/release/ducklocate.duckdb_extension
```

Both pass. The enclosing Codex sandbox initially refused nested `sandbox_apply`;
rerunning outside that enclosing sandbox with the network-denying profile worked.
Automatic extension installation/loading is also disabled on every harness and
internal transformation connection. No general offline OS security guarantee is
claimed for future code.

`build_identity.py` refreshes the footer on every build with package version,
checkout revision and a digest of Rust/build inputs, including uncommitted edits.
Artifact hashes identify actual binaries; this foundation claims reproducible
setup and logical behavior, not byte-identical output across checkout locations
or builds. The checkout revision can change after the requested local commit.

## Recorded final artifacts

The final pre-commit verification used footer identity
`0.1.0-a812d64e4a-18347c7ad7`. All four artifacts passed SQLLogicTest, native
harness checks and actual v2.0.0 shell loading. Both probe artifacts also passed
the final OS-enforced offline run. These binaries remain in the ignored build
directory; `build/verification.json` records shell results and hashes locally.

| Artifact | SHA-256 |
|---|---|
| `build/debug/ducklocate.duckdb_extension` | `32d3ab7aac4e13d89147691fc2c578c39fb67cdd7996cdf9153bb474a8a0e055` |
| `build/release/ducklocate.duckdb_extension` | `ef712273bc5349d9d518f628a9d137b51a49acc2636dd7d84cbe860a9d0e95d9` |
| `build/probes/debug/ducklocate.duckdb_extension` | `7689a3b5610f5ae7ba7ae6ed5af6231fbbb1b3d6ddcd653a2fc9307893338114` |
| `build/probes/release/ducklocate.duckdb_extension` | `8b4cc881e604c13dac26431474ee9be1b0dc3938855259da8785fb64cadce6c8` |

## Native boundary probes

Build with `PROBES=1`; outputs are under `build/probes/{debug,release}` and cannot
overwrite the normal public artifacts. These symbols are absent from normal builds.

```sql
-- Synthetic values only. There is no implemented OSM profile here.
SELECT * FROM ducklocate_probe_rows(3);
DESCRIBE SELECT * FROM ducklocate_probe_rows(0, shape := 'id');
SELECT ST_AsText(geometry)
FROM ducklocate_probe_rows(
    1, crs := 'EPSG:3857',
    spatial_path := '/absolute/path/to/.cache/spatial/spatial.duckdb_extension'
);
```

Probe signature: positional `count BIGINT` (0..100000), named-only
`shape VARCHAR := 'wide'` (`wide` or `id`), `crs VARCHAR := 'EPSG:4326'`,
`spatial_path VARCHAR := ''`, `geometry_wkb BLOB := NULL`. Other NULL arguments
are rejected; NULL WKB selects the fixed synthetic POINT(2 49). Explicit WKB is
limited to 1 MiB and decoded through DuckDB's validating cast. Unknown names,
unsupported CRS strings and extra positional arguments fail. `shape` selects the
schema at bind time, not just which fields are populated. No projection/filter
pushdown is advertised; tests verify filters that discard early chunks still
reach later rows.

The wide schema is `id BIGINT`, `geometry GEOMETRY`, `geometry_crs VARCHAR`,
`tags MAP(VARCHAR,VARCHAR)`, README-shaped `source_refs STRUCT(...)[]` and
`issues STRUCT(...)[]`. Synthetic refs include a NULL list element to exercise
the native representation; that is not a proposed valid product lineage row.
Every third row cycles between populated nested data, SQL NULLs, and empty
collections. This distinguishes NULL containers, NULL map values, NULL STRUCT
fields, NULL list elements and empty MAP/LIST values; Unicode is retained.

Rust constructs standard WKB, casts it through the C API factory to the actual
native GEOMETRY type (logical type ID 60), then writes owned `Value`s into GEOMETRY
vectors with `duckdb_v2_vector_set_value`. The exact-release header explicitly
requires this fallback for GEOMETRY, which has no committed direct vector view.
Arbitrary WKB bytes are never relabelled as an alias or copied into a guessed
internal layout. Point, line, polygon and empty line geometries are verified with
Spatial operations on the Rust-produced output. Malformed WKB produces a DuckDB
error. CTAS keeps GEOMETRY usable; Spatial predicates and R-tree construction
work, including after closing and reopening a persistent CTAS database.

The scan deliberately emits at most 127 rows per exec. Tests cover 0, 1, 126,
127, 128, 2048 and 5000 rows, validity resets at chunk boundaries, empty filtered
results, prepared statement execution three times, view rescans and simultaneous
sessions with distinct scan sizes. Bind data is immutable. A cursor and owned
geometry belong to fresh worker-local state, not a process global. DuckDB owns
the callback state and drops it on completion/error. No borrowed vectors, contexts
or native handles are retained. The only unsafe entrypoint code is generated by
the official binding macro; no project unsafe implementation was added.

## Coordinate path and provenance

`coordinates.rs` is reusable Rust code, independent of the native entrypoint.
It constructs WGS84 XY WKB, converts through the native cast, and returns the
original owned geometry for EPSG:4326. No transformation or axis swap happens on
the default path. Explicit EPSG:3857 calls Spatial's `ST_Transform` with bound
source/target/geometry parameters and `always_xy := true`.

The shared transformation method takes a connection owned by its caller. Since
a callback cannot issue nested SQL on its calling connection, the probe adapter
creates one isolated in-memory connection per scan, disables auto-install/load,
and explicitly loads the local, signed Spatial artifact when transformation is
requested. The connection lives in worker-local state and never writes to the
caller's database. A future CLI can pass its embedded connection to the same
method. This is a working scalar/value bridge, not a performance-qualified batch
adapter; repeated query preparation and session construction need measurement
before choosing a production strategy. Only the explicit local path is accepted;
missing files fail without a download or fallback.

Qualified policy: only canonical `EPSG:4326` and `EPSG:3857`, 2D XY. Source data is
assumed WGS84; this is not generic source-CRS detection. No custom pipelines,
vertical CRS, epochs, datum/grid transformations or implicit CRS fallback are
supported. Web Mercator uses the WGS84 semimajor radius 6378137 m. No source
accuracy improvement is claimed. Other EPSG codes are explicitly unsupported,
even if Spatial itself knows them. The broader README CRS contract remains a
proposal. No `on_error` profile modes exist yet.

Independent control point: PROJ publishes longitude **2**, latitude **49** as
`222638.98, 6274861.39` metres. Native output is
`222638.98158654713, 6274861.394006575`. The published rounded answer is checked
with **0.01 m** tolerance. Independently evaluating
`x = 6378137 * radians(2)` and
`y = 6378137 * ln(tan(pi/4 + radians(49)/2))`
is checked within **1e-6 m**. These are numerical checks, not accuracy estimates
for OSM. The non-symmetric point catches axis reversal. Lines/polygons also
transform through the same core path. Invalid/empty/NULL CRS, unsupported valid
CRS and missing local Spatial resources fail explicitly. A deliberately invalid
latitude produces infinities in raw Spatial; the shared path detects non-finite
output bounds and returns `transformation_failed` instead of emitting them.
Empty geometries remain valid. Arbitrary malformed/non-finite geometry validation
and future profile-level fail/report behavior need their own qualification.

Identities actually obtained:

| Identity | Evidence |
|---|---|
| Spatial revision | `duckdb_extensions().extension_version = a3dbcd1781` |
| Spatial artifact SHA-256 | `212ca75890f576bec4a9ea71f5a10320581fe9886afceb05b1d47944ebcf03f4` |
| Compressed artifact SHA-256 | `16dadc65e6eb5a212160070063b57cc0ded6ebc24cc8c20c401a17a9e0032cee` |
| PROJ runtime/compiled versions | `DuckDB_Proj_Version()` / `DuckDB_PROJ_Compiled_Version()` |
| Embedded proj.db SHA-256 | `eefcf24f76a86c617f9b3cec75babdad184ed5c4a3b8bee80ea29dc9846a20fc` |
| Embedded database metadata | Layout 1.2; EPSG v10.076, 2022-08-31; PROJ 9.1.1; PROJ_DATA 1.12 |

The 8,302,592-byte embedded SQLite database begins at byte 54,775,640 in this exact
Spatial binary. It was compared byte-for-byte with the decoded array in upstream
`proj_db.c` at the pinned revision (Git blob
`a36ff67f2691695395dd71bab5e9fc08e51b02c5`). `scripts/spatial_identity.py`
reproduces the artifact inspection and reads its metadata read-only. This is not
a runtime SQL metadata facility and its offsets are specific to the pinned binary.

The exact Spatial source calls `proj_create_crs_to_crs`, then
`proj_normalize_for_visualization` for XY. It uses the embedded database and
explicitly disables PROJ networking. The qualified WGS84/Web Mercator operation
needs no grids; offline tests prove it runs without network. SQL exposes neither
the actual selected operation definition/accuracy nor a runtime grid list or grid
checksums. Do not report an inferred EPSG method as a captured operation identity.
Do not fill these metadata fields with invented versions, an empty purported grid
manifest or system-PROJ database details. General CRS support requires an upstream
introspection bridge or another compatible, verified PROJ integration and an
explicit operation/accuracy/resource policy. Pinning this artifact/database is
available today; complete runtime transformation provenance is not.

## Atomic import investigation

The proposed `CALL ducklocate_import(...)` is **not implemented**. A native table
function receives a borrowed `duckdb_v2_context_handle`. In the exact engine
header, context operations expose config, factory, file system and logging, not
a connection or transaction SQL executor. `duckdb_v2_statement_execute` requires
a `duckdb_v2_connection_handle` and refuses execution while that connection has
an active result. The Rust `Context` wrapper likewise exposes no query method.
One extension-input comment says the context can run queries, but the actual
exported context/factory functions expose no such executor. Reinterpreting opaque context handles or calling into C++ internals would have no
supported ownership/reentrancy contract. A new connection has independent
transaction state and is not a substitute. Consequently the documented CALL
interface cannot yet be delivered through this selected API with its required
semantics; there are no independent committed writes hidden behind it.

A concrete alternative is native **query-pragma expansion**. The C API and Rust
binding let a pure callback return a SQL statement group; DuckDB then executes
that group in the caller's transaction. The test-only
`ducklocate_probe_transaction(fail BOOLEAN)` produces two CTAS statements and a
final summary, or deliberately fails its second write. It does no work at bind
other than returning SQL, and does not begin/commit a transaction itself.

Reproducer in a probe-enabled shell:

```sql
CREATE SEQUENCE ducklocate_probe_write_witness START 1;
BEGIN;
CREATE TABLE caller_uncommitted AS SELECT 7 AS value;
PRAGMA ducklocate_probe_transaction(false);
-- summary: completed_tables = 2; both probe tables and caller table exist
ROLLBACK;
-- all three tables are absent

BEGIN;
CREATE TABLE caller_uncommitted AS SELECT 7 AS value;
PRAGMA ducklocate_probe_transaction(true);
-- conversion error containing 'deliberate_failure'
SELECT * FROM ducklocate_probe_first;
-- transaction aborted: must roll back
ROLLBACK;
SELECT currval('ducklocate_probe_write_witness');
-- 2: first CTAS was executed before the deliberate failure
-- all three tables remain absent
```

The first CTAS consumes a sequence value; sequence advancement survives rollback
and is the test-only witness that execution reached the initial write. The
sequence itself is deliberately outside the rolled-back operation and is not a
product metadata table. Additional harness checks confirm failed autocommit
expansion leaves no partial tables, successful autocommit expansion commits both,
and a pre-existing target table causes an error without replacing its data.
No second connection participates in these writes.

Recommended near-term materialization is caller-authored `BEGIN; CTAS ...;
COMMIT;` with explicit rollback on failure, as already proposed in the README.
If a convenience interface is required, consider a separately specified query
pragma that only generates safely quoted SQL and bind-constant options. It would
need review of downloads, identifier quoting, cancellation, repeated execution
and summary behavior before becoming public. Retaining the exact CALL syntax
instead requires an upstream API for transactional plan expansion/execution or
another explicitly reviewed native bridge. The transaction requirement has not
been weakened to fit the chosen binding.

## Remaining scope and next roads milestone

No platform beyond macOS arm64, other DuckDB release, community publication,
Wasm, CLI packaging, large extract or performance claim has been qualified. The
software license remains undecided. Real parser cancellation, bounded dependency
resolution, snapshot stability/hashing and complete CRS provenance need further
work; synthetic chunk bounds are not proof of those product properties.

Next, specify and implement one versioned **roads** profile over a tiny local
hand-written OSM fixture. Fix selection, ordered way-node reconstruction, stable
feature IDs, tags/lineage, speed units and conditional/unknown semantics, missing
references and fail/report results before selecting a parser/storage strategy.
Test intersections/closed ways without assuming they are areas and make relation
support or rejection explicit. Reuse this native geometry/CRS path, verify empty
and rejected profile schemas, and materialize via caller-owned SQL transactions.
Keep downloads and CLI publication for separately scoped milestones.
