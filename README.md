# Ducklocate: OSM to DuckDB

An open-source DuckDB extension written in Rust that turns OpenStreetMap data into
structured, queryable tables for roads, buildings, administrative areas and points
of interest, with typed attributes, geometries and source references.

Choose a local OSM file or explicitly download a named region. Select a projection
profile and work through SQL or the `osm2duckdb` command-line tool. Both interfaces
use the same Rust projection code, profile definitions and output schemas.

> **API design:** This README proposes the SQL and CLI contracts for DuckDB 2.0.
> The extension and CLI are not implemented yet; the examples describe the interfaces
> to build. Native loading, geometry interoperability and download execution still
> require integration verification. No community installation is available.

## Contents

- [Workflow](#workflow)
- [Command-line interface](#command-line-interface)
- [API overview](#api-overview)
- [Import selected profiles through SQL](#import-selected-profiles-through-sql)
- [Discover profiles](#discover-profiles)
- [Choose a source](#choose-a-source)
- [Read a profile](#read-a-profile)
- [Output columns](#output-columns)
- [Quality and errors](#quality-and-errors)
- [Store and index tables](#store-and-index-tables)
- [Reproducibility](#reproducibility)
- [Scope and implementation questions](#scope-and-implementation-questions)
- [Development and references](#development-and-references)

## Workflow

Build a database containing selected object classes from a named region:

```sh
osm2duckdb build \
  --region germany \
  --objects roads,buildings,barriers \
  --output germany.duckdb
```

This creates `roads`, `buildings` and `barriers` tables from one source snapshot.
The object names select projection profiles, not raw OSM element types.

Inside DuckDB, the corresponding convenience operation writes into a schema:

```sql
CALL ducklocate_import(
    region := 'germany',
    profiles := ['roads', 'buildings', 'barriers'],
    schema := 'osm'
);
```

This creates `osm.roads`, `osm.buildings` and `osm.barriers`. Both workflows also
store source and profile metadata, including for tables that contain no features.

Using an existing file requires no network access:

```sql
SELECT name, road_class, max_speed_kmh, geometry
FROM ducklocate_read('germany.osm.pbf', profile := 'roads')
WHERE max_speed_kmh > 80;
```

To obtain the file through Ducklocate, download the region first:

```sql
CALL ducklocate_download('germany', directory := './data/germany');

CREATE TABLE roads AS
SELECT *
FROM ducklocate_read('./data/germany/source.osm.pbf', profile := 'roads');
```

The download returns the actual file path and its content hash. It does not
create database tables. Reading a file does not download or refresh anything.
Keep downloaded inputs and generated databases outside Git.

The proposed geometry interface uses DuckDB Spatial's `GEOMETRY` type. Once a
compatible native artifact exists, the intended loading sequence is:

```sql
INSTALL spatial;
LOAD spatial;
LOAD '/absolute/path/to/ducklocate.duckdb_extension';
```

`INSTALL spatial` needs network access when Spatial is not already installed.
Development builds of Ducklocate require a DuckDB process started with unsigned
extension loading enabled. The artifact must match its exact DuckDB release and
platform; targeting the 2.0 family alone does not establish binary compatibility.

## Command-line interface

`osm2duckdb build` creates a persistent DuckDB database. It selects profiles,
obtains one snapshot, projects the requested tables and records their provenance.

Use `--source` instead of `--region` to build from an existing file:

```sh
osm2duckdb build \
  --source ./germany.osm.pbf \
  --objects roads,buildings,barriers \
  --output germany.duckdb
```

| Option | Meaning |
|---|---|
| `--region` | Named region to obtain from the download provider. |
| `--source` | Existing local `.osm.pbf` snapshot; no network access. |
| `--objects` | Required comma-separated profile names. |
| `--output` | Required destination DuckDB database file. |
| `--schema` | Output schema; defaults to `main`. |

Exactly one of `--region` and `--source` is required. Unknown or unavailable
profiles are errors. Each selected profile uses its installed default version;
the effective versions are recorded in the database. A region build resolves the
provider's current snapshot once. Cached bytes may be reused only when verified
as that same snapshot; an older local file is not silently treated as current.

The build creates one table per selected profile, plus `_ducklocate_source` and
`_ducklocate_profiles` in the output schema. These metadata tables store the source
identity/provenance and effective profile/schema/extension identities. Their full
schemas and cache-location controls still need specification.

An existing output file causes an error; there is no implicit replacement.
Publish the output only after the complete build succeeds and the database has
been closed. Failures return a nonzero exit status and must not leave an output
file presented as a completed build. Downloads/cache files are separate artifacts.
The completion summary reports the output path, source hash and per-profile counts.

The CLI and extension share projection rules, geometry, diagnostics and schema
definitions. The CLI may use embedded DuckDB; users do not need to run a database
server or provide a DuckDB shell. Packaging the matching engine, Spatial and
extension artifacts remains part of the native integration work.

## API overview

The SQL surface consists of six table functions. `CALL` is the documented way to
invoke download and import operations; in DuckDB, CALL itself invokes a table
function rather than providing a separate procedure mechanism.

| Function | Purpose | Network access | Persistent writes |
|---|---|---|---|
| `ducklocate_profiles()` | List profiles provided by the installed extension. | No | None |
| `ducklocate_regions(...)` | List named extracts from a provider's current catalogue. | Yes, catalogue only | None |
| `ducklocate_download(...)` | Download one named extract into a new directory. | Yes | Source file and manifest |
| `ducklocate_import(...)` | Obtain one source and materialize selected profiles. | Region input only | Tables, metadata and acquired source/cache |
| `ducklocate_source(path)` | Identify and inspect a local source. | No | None |
| `ducklocate_read(path, ...)` | Project one local source using one profile. | No | None |

Source inspection and profile reads may use bounded temporary working storage,
which is released after execution. They do not create a persistent source cache
or modify user tables. Region lookup and downloads perform network I/O during
execution, never during extension loading, query binding or `EXPLAIN`.

## Import selected profiles through SQL

`ducklocate_import` is the convenience operation for creating a set of tables in
the current database. The lower-level functions remain available for direct
queries and custom materialization SQL.

```sql
CALL ducklocate_import(
    source := './germany.osm.pbf',
    profiles := ['buildings', 'roads'],
    schema := 'osm'
);
```

Exactly one of `region VARCHAR` and `source VARCHAR` is required, together with a
non-empty `profiles VARCHAR[]` and a non-empty `schema VARCHAR`. Profile names
must be unique and available. The default download provider is Geofabrik. Local
source input does not use the network. The schema is an identifier, not a SQL
fragment; it may already exist, but none of the output tables may exist.

The operation creates one table per profile and the two metadata tables described
in the CLI contract. All profiles use one source snapshot and their installed
default versions. It uses the reader's default `fail` policy. Table writes form
one atomic database operation; a failed import must not expose a partially created
set. Downloaded source files are not rolled back with database changes.

The result contains one summary row per profile: `profile VARCHAR`,
`profile_version VARCHAR`, `schema_version VARCHAR`, `table_name VARCHAR`,
`row_count UBIGINT` and `source_sha256 VARCHAR`. Results describe completed tables,
not intermediate progress. Native support for catalogue writes in the caller's
transaction must be verified before implementing this convenience operation;
running independent writes on a second connection is not an equivalent substitute.

## Discover profiles

```sql
SELECT profile, profile_version, schema_version, description
FROM ducklocate_profiles()
ORDER BY profile;
```

The catalogue returns one row per available profile version:

| Column | Type | Meaning |
|---|---|---|
| `profile` | `VARCHAR` | Stable profile name, such as `roads`. |
| `profile_version` | `VARCHAR` | Exact version of its selection and interpretation rules. |
| `schema_version` | `VARCHAR` | Version of the output-column contract. |
| `is_default` | `BOOLEAN` | Whether this is the default version for this profile. |
| `description` | `VARCHAR` | Purpose and significant limitations. |
| `geometry_types` | `VARCHAR[]` | Geometry kinds the profile can produce. |

Only profiles implemented by the installed extension appear here. The broader
design catalogue is not a promise that every profile ships together. Each profile
has exactly one default version; requesting an unavailable version is an error.

Inspect a profile's complete output schema with DuckDB's own SQL:

```sql
DESCRIBE SELECT *
FROM ducklocate_read('germany.osm.pbf', profile := 'roads');
```

The schema comes from the selected profile version, not from sampled tags. Binding
does not scan the PBF to discover columns. Consequently, DESCRIBE is not a source
validation operation.

## Choose a source

### Local files

The initial input contract is one local `.osm.pbf` snapshot. The path is explicit;
there is no connection-global active region. URLs, globs, lists of files,
full-history PBFs and change files are outside this first contract.

```sql
SELECT * FROM ducklocate_source('germany.osm.pbf');
```

This returns one row with `path VARCHAR`, `sha256 VARCHAR`, `size_bytes UBIGINT`,
`data_timestamp TIMESTAMPTZ`, `provider VARCHAR`, `region VARCHAR` and
`source_url VARCHAR`. The hash covers the input file's bytes. The data timestamp
is taken from source metadata when available, not from the file modification time.

Provider, region and URL are nullable provenance supplied by a matching download
manifest, not inferred from a filename. A manifest is trusted only when its hash
matches the file. A manifest/file mismatch is an error; missing metadata is NULL.
Hashing requires reading the whole file. This operation identifies the source;
it does not prove that every feature can be reconstructed or interpreted.

### Named regions

Geofabrik is the proposed first download provider. Its region identifiers come
from its published catalogue; `germany` is an ID, not a free-text place search.

```sql
SELECT region, name, parent, pbf_url
FROM ducklocate_regions(provider := 'geofabrik')
WHERE region = 'germany';
```

`provider` defaults to `geofabrik`. The result columns are `provider VARCHAR`,
`region VARCHAR`, `name VARCHAR`, `parent VARCHAR` and `pbf_url VARCHAR`.
`parent` may be NULL. This operation fetches the current public catalogue; it
fails explicitly when the catalogue cannot be retrieved. It transfers no PBF.

### Download a region

```sql
CALL ducklocate_download(
    'germany',
    directory := './data/germany',
    provider := 'geofabrik'
);
```

The required region and destination directory must be non-empty strings. The
destination directory must not already exist, and its parent must exist. There
is no implicit replacement or refresh of an earlier download. Use a new directory
for a new snapshot; use the existing local file to reuse an earlier one.

Execution resolves the provider's current PBF URL, downloads into a private
staging directory, checks the transfer and PBF container, computes SHA-256, and
publishes the directory only after the file and manifest are ready. A failed or
interrupted transfer must not leave a directory presented as a completed download.

The completed directory contains `source.osm.pbf` and `manifest.json`. The
manifest records the provider/region, resolved URL, content hash and byte size,
available source timestamp, acquisition time, catalogue identity and attribution.
A computed hash identifies downloaded bytes; it is not a publisher signature.

One result row returns `path`, `manifest_path`, `provider`, `region`, `source_url`,
`sha256`, `size_bytes` and `data_timestamp`, using the types from source inspection
and VARCHAR for the additional path. Acquisition time remains in the manifest.

Use a top-level CALL and consume its result. The implementation must account for
table-function rescans and cancellation; this design does not assume CALL provides
exactly-once effects. File downloads are outside DuckDB's database transaction:
rolling back a later SQL statement does not remove downloaded files.

### What a region means

A named region selects a provider's extract. It does not assert that every output
geometry lies strictly inside an official administrative boundary. Geofabrik
documents buffered extract boundaries and retained crossing features.

The initial reader preserves complete available feature geometry and applies no
additional clipping. Spatial filtering can be expressed through SQL after
projection. Filtering rows by intersection retains their original geometry;
clipping is a separate transformation. Missing references at extract edges remain
errors or reported rejections, according to the selected error mode.

## Read a profile

```sql
SELECT *
FROM ducklocate_read('germany.osm.pbf', profile := 'buildings');
```

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `path` | `VARCHAR` | Required, positional | Local snapshot file. |
| `profile` | `VARCHAR` | Required, named | One profile from the installed catalogue. |
| `profile_version` | `VARCHAR` | Installed default | Exact advertised profile version. |
| `expected_sha256` | `VARCHAR` | NULL | Optional 64-character hexadecimal hash to verify. |
| `on_error` | `VARCHAR` | `'fail'` | Feature-reconstruction policy: `fail` or `report`. |

Arguments must be known at bind time; the profile determines the result columns.
Required arguments reject NULL and empty values. Omitted `profile_version` selects
the catalogue default; explicit NULL is rejected. `expected_sha256 := NULL` means
no caller-supplied hash assertion. Unknown options, profiles, versions and error
modes fail explicitly.

Each invocation projects one profile, with a stable schema for that version. To
read roads and buildings, make two calls rather than combining unrelated fields
into one table. A source object may legitimately contribute to both profiles.

The reader resolves referenced elements before constructing geometry. This can
require multiple passes and temporary indexes. LIMIT, column selection and WHERE
clauses do not promise a proportional reduction in source processing. A view
re-executes its reader; separate profile calls are not guaranteed to share work.

## Output columns

All profiles expose the following common columns. Profile-specific fields follow
them in the order defined by the profile's schema version.

| Column | Type | Meaning |
|---|---|---|
| `feature_id` | `VARCHAR` | Deterministic feature key within the profile contract. |
| `osm_type` | `VARCHAR` | Primary source type: `node`, `way` or `relation`. |
| `osm_id` | `BIGINT` | Primary source ID, interpreted together with its type. |
| `osm_version` | `INTEGER` | Primary element version, NULL when absent. |
| `name` | `VARCHAR` | Primary source name, NULL when absent. |
| `geometry` | `GEOMETRY` | Reconstructed geometry; NULL for a rejected feature. |
| `tags` | `MAP(VARCHAR, VARCHAR)` | Unmodified tags of the primary source element. |
| `source_refs` | `STRUCT(osm_type VARCHAR, osm_id BIGINT, osm_version INTEGER)[]` | Unique contributing source references, including geometry dependencies. |
| `status` | `VARCHAR` | `ok` or `rejected`. Warnings can accompany an `ok` row. |
| `issues` | `STRUCT(severity VARCHAR, code VARCHAR, field VARCHAR, raw_value VARCHAR, message VARCHAR)[]` | Feature diagnostics; empty when none. |
| `source_sha256` | `VARCHAR` | Hash identifying the source bytes used for projection. |
| `profile_version` | `VARCHAR` | Effective profile rules. |
| `schema_version` | `VARCHAR` | Effective column contract. |
| `extension_version` | `VARCHAR` | Ducklocate release identity, including a revision for development builds. |

`source_refs` identifies contributing elements; their full tags, member roles and
ordered topology remain accessible in the pinned input. It is not a second copy
of the complete OSM graph. Missing versions remain NULL. Carrying detailed lineage
has a storage cost that must be measured rather than assumed negligible.

Feature IDs must not depend on row order or worker scheduling. Their exact format
belongs to the profile specification. Identity across snapshots is guaranteed only
where that specification defines it; IDs are not universal cross-profile keys.

Geometry uses WGS84 longitude/latitude in degrees: X is longitude, Y is latitude.
No implicit reprojection, simplification, geometry repair or representative-point
substitution is performed. Area features retain their area geometry, including
holes. Any future derived point must be a separately identified field.

### Profile-specific fields

These field families guide the first profile specifications; selection rules,
enum mappings and relation/member deduplication still need individual contracts.
The versions below have not been assigned or implemented.

| Profile | Field examples | Geometry |
|---|---|---|
| `roads` | `road_class VARCHAR`, `surface VARCHAR`, `max_speed_kmh DOUBLE`, `oneway VARCHAR` | LineString / MultiLineString |
| `buildings` | `building_type VARCHAR`, `levels DOUBLE`, `height_m DOUBLE` | Polygon / MultiPolygon |
| `admin_areas` | `boundary_type VARCHAR`, `admin_level INTEGER` | Polygon / MultiPolygon |
| `pois` | `categories VARCHAR[]` | Point, line or area, according to the source feature |
| `barriers` | `barrier_type VARCHAR`, `access VARCHAR`, `max_width_m DOUBLE` | Point, line or area, according to the source feature |

Typed fields do not replace source tags. For example, an unsupported conditional
speed stays in `tags`, leaves `max_speed_kmh` NULL and produces a diagnostic. A
missing access or oneway tag does not become confirmed permission or direction.
Administrative level values alone do not establish equivalent hierarchies across
countries. Road rows do not constitute a routing graph.

## Quality and errors

`on_error := 'fail'` stops execution when a selected feature cannot satisfy the
profile's required reconstruction rules. `on_error := 'report'` instead emits a
`rejected` row with its source identity, tags, provenance and diagnostics. Geometry
and fields that cannot be established are NULL. A rejected feature is not silently
dropped. Relation/member suppression explicitly defined by a profile is a separate
selection rule, not an error policy.

Optional attribute interpretation failures produce warnings and NULL typed values
in either mode when the required feature can still be constructed. Features that
do not match a profile are not rejections. Source elements used only as geometry
dependencies do not automatically become output features.

Materialize a review table to inspect the complete selected profile:

```sql
CREATE TABLE roads_review AS
SELECT *
FROM ducklocate_read('germany.osm.pbf', profile := 'roads', on_error := 'report');

SELECT status, count(*) AS feature_count
FROM roads_review
GROUP BY status;

SELECT r.feature_id, issue.severity, issue.code, issue.field, issue.raw_value
FROM roads_review AS r,
     UNNEST(r.issues) AS diagnostics(issue)
ORDER BY r.feature_id, issue.code;
```

The issues list uses `warning` and `error` severities, stable machine-readable
codes and human-readable messages. `field` and `raw_value` may be NULL when an
issue concerns geometry or a missing reference rather than one tag. Code examples
are `missing_reference`, `invalid_geometry` and `unsupported_value`; their exact
definitions must accompany implementation.

Unreadable/corrupt input, unsupported PBF features, conflicting source records,
hash mismatch, resource exhaustion and cancellation are statement errors in both
modes. `report` does not convert technical failures into empty output. A client
stream can receive rows before a later error, so it must not publish an incomplete
stream as a completed dataset. Counts from LIMIT or filtered queries do not
establish a full quality report or geographic completeness.

## Store and index tables

Materialization uses DuckDB's existing transaction and catalogue operations:

```sql
BEGIN TRANSACTION;

CREATE SCHEMA osm;

CREATE TABLE osm.source AS
SELECT * FROM ducklocate_source('germany.osm.pbf');

CREATE TABLE osm.roads AS
SELECT * FROM ducklocate_read('germany.osm.pbf', profile := 'roads');

CREATE TABLE osm.buildings AS
SELECT * FROM ducklocate_read('germany.osm.pbf', profile := 'buildings');

COMMIT;
```

Run against a new target schema. If a statement fails, roll back the transaction.
Do not replace an existing release implicitly. Keep the input file unchanged
throughout the workflow: a database transaction does not freeze an external PBF.
For automated reproducible builds, pass the recorded hash as `expected_sha256`
to each reader and verify the resulting identities before committing.

CTAS does not add constraints or indexes automatically. Add indexes for actual
queries, for example a Spatial R-tree index:

```sql
CREATE INDEX roads_geometry_idx ON osm.roads USING RTREE (geometry);

SELECT name, road_class
FROM osm.roads
WHERE ST_Intersects(geometry, ST_MakeEnvelope(13.3, 52.4, 13.5, 52.6));
```

The envelope uses longitude/latitude degrees. Geometry distances and areas are
not implicitly metres. R-tree use depends on the predicate and query plan; an
index is not a blanket performance guarantee.

## Reproducibility

A repeatable projection records the source SHA-256, effective profile version,
schema version, extension identity and exact DuckDB/Spatial versions. Record
download provenance separately; `latest` provider URLs can change their content.
The reader computes source identity even when no expected hash was supplied.

An expected hash mismatch fails the statement. Implementations must derive the
reported identity from the same source bytes they project and prevent a changed
input from being accepted as the asserted snapshot. No process-global selected
file or most-recent-download state participates in a query.

Identical declared inputs and versions must produce the same logical rows.
SQL ordering requires ORDER BY. This contract does not promise byte-identical
DuckDB files, complete OSM coverage or compatibility with later profile versions.
An empty profile result remains valid and has the declared schema; retain the
source table and effective profile catalogue for metadata when no feature rows exist.

## Scope and implementation questions

The first interface design covers native SQL access and the `osm2duckdb build`
CLI, local snapshots, named-region acquisition, profile discovery, typed
projection, feature diagnostics and materialization.
Profile configuration files, custom clipping, incremental updates, combined-profile
single-pass builds and additional providers remain separate design work.

Before implementing this interface, resolve and verify:

1. Rust binding support for named arguments, bind-time profile schemas and the selected native GEOMETRY representation.
2. Download callback lifecycle, cancellation, publication races and external-file access under DuckDB's security settings.
3. The first complete profile contract and hand-written acceptance fixture, including relation handling, identity and diagnostics.
4. Bounded reference-resolution storage, source snapshot consistency and the measured cost of hashing and lineage.
5. Source-manifest format and exact-version compatibility checks.
6. Atomic SQL import in the caller's transaction, CLI database publication and shared-core equivalence between both interfaces.

These are integration and design gates, not measured capabilities. There is no
REST service in this design.

## Development and references

[Concept.md](Concept.md) records product scope and durable choices. This README
is the user-facing SQL and CLI proposal. [AGENTS.md](AGENTS.md) points to repository
instructions and the focused development skills. A software license has not yet
been selected; OSM input and derivative data have their own licensing obligations.

Official references used for this proposal:

- [DuckDB Rust extension template](https://github.com/duckdb/extension-template-rs/tree/a679601f8e133db7546777c6637bc7a6c2d2780e): bind-time result columns and native extension lifecycle.
- [DuckDB CALL](https://duckdb.org/docs/2.0/sql/statements/call), [CREATE TABLE](https://duckdb.org/docs/2.0/sql/statements/create_table) and [transactions](https://duckdb.org/docs/2.0/sql/statements/transactions): SQL invocation and materialization.
- [DuckDB Spatial](https://duckdb.org/docs/2.0/core_extensions/spatial/overview) and [R-tree indexes](https://duckdb.org/docs/2.0/core_extensions/spatial/r-tree_indexes): geometry integration and indexing.
- [Geofabrik technical documentation](https://download.geofabrik.de/technical.html) and [download catalogue](https://download.geofabrik.de/index-v1-nogeom.json): region IDs, snapshot URLs and extract semantics.
- [OpenStreetMap copyright and license](https://www.openstreetmap.org/copyright): data origin, licensing and attribution.
