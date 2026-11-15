---
title: Status & roadmap
description: Implemented behavior, verified scope, and proposals for future work.
---

## Implemented

| Capability | Current scope |
| --- | --- |
| Native extension | Local development builds; verified on macOS arm64 with DuckDB 2.0.0 |
| Profile discovery | `ducklocate_profiles()` lists roads 1.0.0 |
| Source reads | `ducklocate_read()` reads an existing local OSM PBF |
| Roads | Linear highway-tagged ways; schema 1.0.0 |
| Geometry | Native GEOMETRY; default EPSG:4326, explicit qualified EPSG:3857 |
| Materialization | Caller-owned DuckDB SQL and transactions |
| Diagnostics | Per-feature issues, explicit rejection mode, and statement errors |

See the [reference](../../../README.md) and [roads contract](../../roads-v1.md)
for the exact behavior. The [verification note](../../roads-verification.md)
records evidence; it does not establish national-scale performance or completeness.

## Proposed

These are directions under consideration, not available features or a release schedule.

- **Acquisition:** provider catalogue lookup and explicit downloads of named regions.
- **More profiles:** buildings, administrative areas, POIs, and other themes with versioned contracts.
- **CLI:** an `osm2duckdb` interface using the same Rust projection rules as SQL.
- **Import:** convenience materialization with a specified atomicity contract.
- **Updates:** dependency-aware incremental changes, with results compared to a clean rebuild.
- **Distribution:** additional verified platforms, native binary dependency notices, and a community publication route. The project's software licence is Apache 2.0.

The [concept](../../../Concept.md) records the established direction and open choices.

## Documentation grows with the implementation

Each completed function, command, or profile should ship with its purpose,
prerequisites, runnable example and expected output, arguments or schema,
limitations, and relevant verification evidence in the same change.

New user-facing guides and examples belong here as their behavior becomes
available. Proposals stay labelled until implementation and verification support them.
