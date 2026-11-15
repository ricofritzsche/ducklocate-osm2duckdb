# Official extension sources

Reviewed 15 November 2026. These notes record upstream observations, not a locally
verified Ducklocate build. Follow the links when the task changes the corresponding
interface or distribution path. Prefer exact source revisions over search snippets.

## DuckDB 2.0 and Rust

- [DuckDB 2.0 C API overview](https://duckdb.org/docs/2.0/clients/c/overview): C API v2 exposes additional extension facilities and is not yet stable. An extension selects v1 or v2, rather than mixing their interfaces.
- [Official Rust template](https://github.com/duckdb/extension-template-rs/tree/a679601f8e133db7546777c6637bc7a6c2d2780e), inspected at commit a679601f8e133db7546777c6637bc7a6c2d2780e.
- Its [Makefile](https://github.com/duckdb/extension-template-rs/blob/a679601f8e133db7546777c6637bc7a6c2d2780e/Makefile) sets TARGET_DUCKDB_VERSION=v2.0.0, CAPI_VERSION=2 and USE_UNSTABLE_C_API=1. It documents the _init_c_api_v2 entrypoint and exact-version binary compatibility.
- Its [Cargo manifest](https://github.com/duckdb/extension-template-rs/blob/a679601f8e133db7546777c6637bc7a6c2d2780e/Cargo.toml) uses edition 2024 and duckdb-neo =0.20000.2 with build-extension. These are an upstream starting point, not a verified dependency selection for this project.
- Its [README](https://github.com/duckdb/extension-template-rs/blob/a679601f8e133db7546777c6637bc7a6c2d2780e/README.md) describes pure Rust builds without C++ glue or compiling DuckDB, metadata-footer packaging, native/Wasm entrypoint crates and SQLLogicTest. Shared CI tooling also uses Python, Make and Git.

## Loading, testing and publication

- [DuckDB 2.0 extension distribution](https://duckdb.org/docs/2.0/extensions/extension_distribution): binaries carry version/platform metadata; local unsigned loading requires an explicit option. Do not strip a packaged extension after its footer is appended. Core/community signing and local development loading are distinct paths.
- [Community development](https://duckdb.org/community_extensions/development): community builds use DuckDB's CI toolchain and a descriptor identifying the source revision.
- [Community submission documentation](https://duckdb.org/community_extensions/documentation): public open-source GitHub repository; description.yml under extensions/extension_name; extension metadata, license, maintainers and source ref. Names permit lowercase letters, numbers, hyphens and underscores.

The generic community documentation currently lists CMake-only builds; the Rust
template says community integration is coming soon. Treat publication support as
unresolved until verified with current tooling. Do not solve documentation drift
by silently changing languages or assuming that a local binary will be accepted.

## Related local conventions

The initial instructions were informed by the geocoding, routing-engine and
PSM-ingest skills reviewed on the same date. Adapted principles are cohesive
modules, explicit processing paths, independent expectations and source lineage.
Their crate layouts, 200-line hard limits, coordinate encodings, unsafe bans,
PostgreSQL transactions and service architecture are not inherited requirements.
