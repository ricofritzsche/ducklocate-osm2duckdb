---
name: duckdb-extension-development
description: Use when designing, implementing or reviewing Ducklocate's native DuckDB extension, SQL contracts, Rust bindings, callbacks, compatibility, tests or distribution.
---

# DuckDB extension development

Read [Concept.md](../../../Concept.md) and the relevant parts of
[official-source notes](references/official-sources.md) before selecting bindings,
changing compatibility or preparing distribution. Recheck current official sources
for the exact targeted 2.0 release; record changes to the verified baseline.

## Native integration

- The native extension is loaded into DuckDB and called through SQL. It shares Rust projection code with the osm2duckdb CLI; do not implement it as a subprocess wrapper around that CLI or an HTTP service.
- Start from a pinned revision of DuckDB's official Rust extension template and its CI tooling. Keep only the examples and targets needed for this extension. Template Wasm support is not an automatic product requirement.
- DuckDB 2.0's C API v2 and the inspected Rust template require explicit compatibility care. Match the exact engine version, binding, API/entrypoint, platform metadata and test runner; do not silently downgrade to the geocoding project's 1.5 baseline.
- Preserve the metadata-footer generation step. A cargo-built shared library renamed to .duckdb_extension is insufficient. Strip symbols, if desired, before footer generation, never afterwards.
- Permit unsigned loading only for explicitly identified local development artifacts. Keep version/platform checks enabled for acceptance; record the binary hash and actual runtime version.

## SQL contract and callback lifetime

- Define function names, arguments, named options, output columns/types, NULL behavior, errors and side effects before implementing each public operation. Examples in discussions are not established signatures.
- Separate read operations from explicit acquisition and materialization operations. Loading the extension or binding a query must not unexpectedly start a download or mutate user tables. Binding and execution can be repeated by DuckDB; put effects in an explicitly designed execution path.
- Specify ownership and cleanup of bind, global and local state. Do not retain borrowed vectors, strings, contexts or native handles beyond their allowed lifetimes, or mark them Send/Sync without evidence.
- Keep query-specific mutable state out of process globals. Cache identity must include the source snapshot and applicable profile/schema versions; simultaneous connections must not overwrite each other's selection.
- Use chunked output for table scans. Emit correct row counts and validity masks; an empty output chunk signals completion, so filtering away one input batch must not accidentally end the scan.
- Claim filter/projection pushdown only when semantics remain correct. Fully enforce claimed filters; retain source dependencies needed for geometry even if their fields are not projected.
- Respect cancellation and release resources on normal completion, errors and interruption. Bound Rust-side buffers and temporary files explicitly; do not assume DuckDB's memory limit accounts for all external allocations.
- Bind SQL values. Validate and quote identifiers separately when generating materialization SQL. Define transaction and recovery behavior for writes so failure cannot leave output presented as complete.
- Verify geometry types and spatial interoperability against the exact engine and dependencies. Do not label arbitrary WKB bytes as DuckDB GEOMETRY without the required representation/conversion.

## Build and verify

First prove a minimal native extension loads in the pinned DuckDB and executes an
actual SQL function. Then test a small end-to-end OSM projection. Record the source
revision, Rust/binding versions, platform, build command, runtime version and
artifact identity. A template example alone is not the projection milestone.

Use SQLLogicTest for the public SQL contract, alongside Rust tests of the rules.
With the inspected template, the starting commands are make configure,
make debug and make test_debug; release validation uses make release and
make test_release. Adapt these only to the actual maintained build setup and
document the resulting commands. Test errors and NULLs, repeated scans, multiple
chunks and simultaneous connections where applicable. Add empty-scan and pushed
filter cases when implementing table functions.

Only claim platforms and exact DuckDB versions exercised by the recorded checks.

## Distribution

Community publication requires a public open-source repository, a declared
software license, a pinned source descriptor and compatibility with the actual
community CI toolchain. The inspected Rust template still marks community
integration as forthcoming, while older generic guidance describes CMake-only
builds. Resolve that tooling mismatch using the current official repositories
before promising INSTALL FROM community. Native loading and community acceptance
are separate results. Do not submit or publish merely because a build succeeds.
