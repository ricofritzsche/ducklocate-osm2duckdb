# Ducklocate: OSM to DuckDB

A native DuckDB extension written in Rust that projects OpenStreetMap snapshots
into typed, queryable features with geometry, original tags and source lineage.
The shared Rust projection code is intended for a future `osm2duckdb` CLI.

**Implemented:** local OSM PBF reads through `ducklocate_read` and discovery through
`ducklocate_profiles`. The only profile is **roads 1.0.0**, schema **1.0.0**:
one LineString per selected highway-tagged way. The verified platform is macOS
arm64, **DuckDB 2.0.0**, Rust 1.98.1, `duckdb-neo` 0.20000.2. No community
installation is available. Downloads, named regions, other profiles, source
inspection, convenience import, CLI and updates remain proposals.

- [Roads contract: selection, schema, diagnostics and limits](docs/roads-v1.md)
- [Roads milestone verification](docs/roads-verification.md)
- [Native foundation and CRS provenance limits](docs/native-foundation.md)
- [Concept and future scope](Concept.md)

## Build and test

From the repository root:

```sh
git submodule update --init --recursive
make configure
configure/venv/bin/python3 scripts/setup_duckdb.py
configure/venv/bin/python3 scripts/setup_spatial.py
cargo fmt --all --check
cargo test --workspace --locked
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
configure/venv/bin/python3 scripts/test_native_checks.py
```

Setup explicitly acquires hash-checked development dependencies; reading a local
file never downloads. Use the verified shell reported by `setup_duckdb.py`
(`duckdb` or `.cache/bin/duckdb`). Python 3 with venv/pip, Make, Git and platform
build tools are required. Rustup installs the pinned toolchain if needed.
Normal artifacts are under `build/{debug,release}`; isolated probe builds are
under `build/probes/{debug,release}`. Each test target runs SQLLogicTest and native
acceptance, including exact public function sets and metadata rejection safeguards.
Acceptance installs the pinned local Spatial artifact into `.cache/roads-extensions`.
Caches, generated databases and build outputs are ignored.

The build retains the metadata footer from the [pinned official Rust template](https://github.com/duckdb/extension-template-rs/tree/a679601f8e133db7546777c6637bc7a6c2d2780e).
`-unsigned` is required for these local development artifacts. Exact DuckDB
version/platform checks remain enabled; targeting the 2.0 family is insufficient.
Do not strip or rename a raw Cargo library as a packaged extension.

## Read a local file

Run this from the repository root after `make release` (the absolute LOAD path
also works in the hardened macOS shell):

```sh
duckdb -unsigned <<SQL
LOAD '$PWD/build/release/ducklocate.duckdb_extension';
SELECT * FROM ducklocate_profiles();

SELECT feature_id, name, road_class, max_speed_kmh, oneway, geometry_crs
FROM ducklocate_read('test/fixtures/roads/valid.osm.pbf', profile := 'roads')
WHERE osm_id = 100;
-- roads:way:100 | Straße 東京 🦆 | future_road | 48.28032 | backward | EPSG:4326
SQL
```

Use your own existing snapshot path in place of the synthetic fixture. The
reader returns native `GEOMETRY`; Spatial is unnecessary for default reads.
Load a matching local Spatial artifact to use `ST_AsText`, spatial predicates
or an R-tree index. In a session with Ducklocate loaded:

```sql
DESCRIBE SELECT * FROM ducklocate_read('test/fixtures/roads/valid.osm.pbf');

BEGIN TRANSACTION;
CREATE TABLE roads AS
SELECT * FROM ducklocate_read(
    'test/fixtures/roads/valid.osm.pbf',
    profile_version := '1.0.0',
    expected_sha256 := '3327c5e3b88bf280d0c53d9ffd6ddecd39f835d6eca818c9b7745b8f4c128480',
    on_error := 'report'
);
COMMIT;

SELECT r.feature_id, issue.code, issue.raw_value
FROM roads r, UNNEST(r.issues) AS diagnostics(issue)
ORDER BY r.feature_id, issue.code;
```

Materialization and transactions belong to the caller. Roll back after a failed
statement. CTAS adds no implicit constraints, indexes or metadata tables. Keep the
recorded source hash and effective profile/schema/extension/CRS dependencies
separately when retaining an empty table. Views and prepared statements scan
again on each execution; a transaction does not freeze a live external source.

## Public SQL interface

```sql
ducklocate_profiles()
ducklocate_read(path, profile := 'roads', profile_version := '1.0.0',
                expected_sha256 := NULL, on_error := 'fail', crs := 'EPSG:4326')
```

| Reader argument | Type | Exact default and validation |
|---|---|---|
| path | VARCHAR, positional | Required non-NULL/nonempty local regular file; no `:`, NUL, `*`, `?`, `[` or `]` (no URLs/globs). Relative paths and DuckDB `~` expansion are supported. |
| profile | VARCHAR, named | `roads`; all other values and NULL rejected. |
| profile_version | VARCHAR, named | `1.0.0`, the installed default; all other values and NULL rejected. |
| expected_sha256 | VARCHAR, named | NULL means no assertion; otherwise exactly 64 hex characters, case insensitive. Empty/malformed/mismatching hashes fail. |
| on_error | VARCHAR, named | `fail`; only `fail` and `report`, case sensitive, non-NULL. |
| crs | VARCHAR, named | `EPSG:4326`; only exact `EPSG:4326` and `EPSG:3857`, non-NULL/nonempty. |

All arguments must be bind-time constants of the declared SQL types. Unknown
options and additional positional arguments fail. Binding/DESCRIBE/EXPLAIN
validate configuration and declare the schema without opening the input.
Execution validates and processes the entire source even for an empty selection.
No filter/projection pushdown is claimed; LIMIT/WHERE do not guarantee reduced
source work. Each invocation has private execution state and temporary storage.

`ducklocate_profiles()` returns exactly one row for roads. Its schema is:
`profile VARCHAR, profile_version VARCHAR, schema_version VARCHAR, is_default BOOLEAN,
description VARCHAR, geometry_types VARCHAR[]`. No placeholder profiles appear.

The reader exposes the existing common columns followed by `road_class VARCHAR`,
`surface VARCHAR`, `max_speed_kmh DOUBLE`, `oneway VARCHAR`. The [complete ordered
19-column schema and NULL rules](docs/roads-v1.md#exact-output-schema) are part of
the profile contract. Original tags remain unchanged; interpreted scalars do not
replace them. Feature IDs are `roads:way:<id>`, independent of CRS and snapshot.

## Geometry and errors

Select ways containing `highway`, including empty/unknown values, except exact
`area=yes`. Closure alone leaves a LineString. Resolve nodes independently of
selection and retain source reference order. Geometry is never silently reversed,
repaired, clipped or simplified. Relations, road areas, access inference and
routing topology are outside roads 1.0.0.

Default coordinates are WGS84 longitude/latitude, XY degrees. Required geometry
needs all references, at least two references and two distinct coordinate pairs.
Validate every coordinate, including interior vertices, before and after any
transformation. Missing references/invalid required geometry fail in `fail` mode;
`report` emits a `rejected` row with NULL geometry and a stable diagnostic.
Warnings for unsupported optional attributes leave the scalar NULL in both modes.
Raw tags, identity and resolved lineage survive rejection. See the [exact speed,
direction and diagnostic rules](docs/roads-v1.md#speed-and-direction).

Corrupt/truncated input, unsupported required PBF features, duplicate/conflicting
records, hash mismatch, I/O/resource failures and interruption remain statement
errors. A partial client stream must not be published as a completed dataset.
SQL ordering requires ORDER BY. Counts from filtered/LIMIT queries do not establish
source completeness or a full quality report.

## Offline reprojection

Only EPSG:4326 and EPSG:3857 are qualified. EPSG:3857 uses the same shared
Spatial/PROJ coordinate path as the foundation. It requires an **already installed**
Spatial `a3dbcd1781`, runtime PROJ `9.1.1`, compiled PROJ
`Rel. 9.1.1, December 1st, 2022`; mismatching identities fail. The test/setup
artifact is hash-pinned. Operation pipeline/grid identities remain unavailable
through the selected SQL API; the reader does not fabricate them or claim full
transformation provenance. See [CRS evidence](docs/native-foundation.md#coordinate-path-and-provenance).

After explicit `setup_spatial.py`, this is runnable from the repository root:

```sh
duckdb -unsigned <<SQL
SET extension_directory = '$PWD/.cache/roads-extensions';
INSTALL '$PWD/.cache/spatial/spatial.duckdb_extension';
LOAD spatial;
LOAD '$PWD/build/release/ducklocate.duckdb_extension';
SELECT feature_id, ST_AsText(geometry), geometry_crs
FROM ducklocate_read('test/fixtures/roads/valid.osm.pbf', crs := 'EPSG:3857')
WHERE osm_id = 100;
SQL
```

The reader's isolated transformation session inherits `extension_directory`,
disables automatic installation/loading, loads installed Spatial, then disables
external access. Because this integration requires its own extension load,
EPSG:3857 requires the caller's `enable_external_access=true`. With external
access disabled, it fails before looking up/loading Spatial in both error modes,
including for empty sources and when Spatial was previously loaded in the caller.
Path allowlisting and locked configuration do not grant permission to load an
extension. Default EPSG:4326 reads remain available for allowlisted inputs.
No grids or network acquisition occur during reads. The pole
latitudes are rejected for Web Mercator; a transformation failure never produces
unchanged coordinates labelled with the target CRS. Attribute units (km/h) do not
change with geometry CRS. Web Mercator metres are not accurate ground distances.

## Snapshot identity, security and limits

The caller's DuckDB file-system policy controls source access, including
`enable_external_access`, `allowed_paths`, `allowed_directories` and disabled
file systems. Local byte access does not bypass it through Rust file reads.
A private copy is hashed while being written; projection reads only that copy.
Replacing/mutating the input cannot label later projected bytes with an earlier
hash. Concurrent mutation during copying can create a mixed snapshot, whose hash
still identifies precisely the bytes projected; use `expected_sha256` to assert
an externally established snapshot.

Hard scan limits include **512 MiB input**, **32 MiB PBF blocks**, **10 million
elements**, **10,000 references per element**, **4,096 tags / 64 KiB tag bytes**,
and a **2 GiB on-disk index**. Rust holds bounded block/feature buffers; SQLite
uses an 8 MiB page-cache target and no mmap. These allocations are independent of
DuckDB's memory limit. This first implementation deliberately rejects some valid
large inputs. It makes no national-scale performance claim.

Temporary files live in an OS-private `ducklocate-` directory and are removed on
completion, failure, early termination and cancellation. Abrupt process death can
leave files for OS/manual cleanup. The pinned C API context cannot poll
cancellation; bounded snapshot/index preparation may delay interruption until
its callback returns. Full limits, supported PBF encodings and lifecycle details
are in the [roads contract](docs/roads-v1.md#execution-security-and-resource-limits).

## Future interface proposals

The following functions are **not registered or implemented**:

| Proposed interface | Intended purpose |
|---|---|
| ducklocate_regions(provider := 'geofabrik') | Explicit provider catalogue lookup; network access. |
| ducklocate_download(region, directory := ..., provider := 'geofabrik') | Explicit snapshot acquisition to a new directory. |
| ducklocate_source(path) | Local snapshot/manifest inspection. |
| ducklocate_import(source := ... / region := ..., profiles := [...], schema := ..., crs := ...) | Convenience materialization with atomic catalogue behavior. |
| osm2duckdb build --source ... / --region ... --objects ... --output ... | Future CLI using shared Rust rules. |

Buildings, administrative areas, POIs, barriers and other profiles need their own
versioned contracts. Downloads, named regions, CLI, incremental updates and import
are outside this milestone. The C API callback has no caller-transaction SQL
executor; the [query-pragma probe](docs/native-foundation.md#atomic-import-investigation)
remains an isolated experiment, not a public import API. Caller-owned SQL and
transactions are the implemented materialization workflow.

[AGENTS.md](AGENTS.md) links the project skills. Software licensing is still an
open project choice; [OSM attribution and data licensing](https://www.openstreetmap.org/copyright)
are separate obligations. Synthetic fixtures contain no real OSM data.
