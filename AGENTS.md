# DuckLocate OSM to DuckDB

An open-source native DuckDB extension written in Rust, with an osm2duckdb CLI.
Both project OpenStreetMap data into structured, queryable datasets using shared
Rust code and profile contracts. The target is DuckDB 2.0.

## Read before working

1. [Concept.md](Concept.md) for product scope, established choices and open design questions.
2. [ducklocate-conventions](.agents/skills/ducklocate-conventions/SKILL.md) for repository work, Rust, verification and Git.
3. The applicable skills below before designing, implementing or reviewing their subject.

| Skill | Read when |
|---|---|
| [duckdb-extension-development](.agents/skills/duckdb-extension-development/SKILL.md) | Working on the native extension, SQL interface, callbacks, bindings, build, compatibility or distribution. |
| [osm-projection-design](.agents/skills/osm-projection-design/SKILL.md) | Working on OSM input, profiles, schemas, tags, geometry, provenance, regional selection or updates. |

## Always applicable

- Write project documentation, code comments and public interfaces in English. Preserve literal source names, tags and identifiers.
- Keep instructions focused: this file is the entry point; skills carry task-specific rules; Concept.md records product choices. Avoid duplicating them.
- Keep implementation consistent with the concept. Report conflicts and record consequential design choices; do not silently rewrite requirements to fit code.
- Support the native extension and osm2duckdb CLI through one Rust projection implementation. REST services, a GUI application and a routing engine are outside the current scope.
- Keep files cohesive and split growing modules by responsibility. Add abstractions and crates for concrete needs.
- Own routine setup and recovery within the requested task. Reuse verified caches and obtain missing tools or inputs when needed; documentation work does not start implementation or large downloads.
- Keep source extracts, local databases, binaries and generated results outside Git. Small documented fixtures may be tracked.
- Leave reference repositories unchanged. Adapt useful principles without importing their product-specific layouts or rules.
- Finish with the outcome, verification actually performed and remaining issues. Distinguish design choices, upstream claims and measurements.
