---
name: osm-projection-design
description: Use when designing, implementing or reviewing OSM projection profiles, source resolution, typed schemas, tag normalization, geometry, regional selection, provenance or updates in Ducklocate.
---

# OSM projection design

Read [Concept.md](../../../Concept.md). Define a profile's observable contract and
small independent fixtures before optimizing its implementation. Consult the
[OSM element model](https://wiki.openstreetmap.org/wiki/Elements) and the specific
tag/relation documentation when introducing interpretation rules; cite the source
and distinguish community tagging conventions from this project's policy.

## Source identity and dependencies

- An OSM identity includes element type and ID. Keep source identity distinct from projected feature identity; define one-to-many and many-to-one lineage explicitly.
- Preserve way-node order, relation members and roles, original tags and available source versions. Missing metadata must be explicit. A source snapshot is not necessarily a full-history input.
- Resolve geometry dependencies beyond the output selection. A tag or region filter that removes needed nodes or member ways is not a valid extraction strategy.
- Specify handling of missing references, duplicate/conflicting records, nested relations and cycles. Reject or diagnose incomplete reconstruction rather than fabricating geometry.

## Profile contract

For each profile, document selection rules, required references, output keys and
types, geometry/CRS, units, normalization, unknown/invalid/conditional values,
relationships, diagnostics and representative queries. Specify supported source
patterns rather than claiming to understand all OSM tags.

- Allow overlapping classifications. Do not force one source object into exactly one theme or merge distinct objects merely because they share a name or location.
- Preserve original strings alongside lossy interpretation. Unknown tags or enum values must not become invented defaults; absent access is not confirmed permission. Conditional restrictions need explicit support or a visible unresolved status.
- Keep canonical values and aliases distinguishable. Preserve multilingual text and full address additions. Normalized search keys must not overwrite source spellings.
- Design built-in profiles through a clear description that can later support external configuration. Use named, tested operations for complex reconstruction; do not create an unrestricted scripting framework prematurely.

## Geometry and region semantics

- A closed way is not automatically an area. Interpret tags and relation semantics. Multipolygon reconstruction must account for outer/inner rings and member roles; see the [multipolygon documentation](https://wiki.openstreetmap.org/wiki/Relation:multipolygon).
- State coordinate order, CRS, precision and any transformation. Keep source geometry separate from derived centroids, points on surface, simplified geometry and clipped output.
- Give every region selection an identifiable boundary/extract definition. Specify intersects/contains behavior and whether crossing features are retained whole or clipped. Record incomplete features at extract edges.
- Record geometry repairs and their effects; do not silently replace invalid source geometry. Spatial containment or proximity is derived evidence, not an OSM-tagged relationship.
- Administrative level numbers and hierarchies need regional interpretation. A roads profile does not imply routing topology, legal access or turn restrictions.

## Provenance, quality and updates

- Record source URL, hash and available data date; the boundary, profile/schema and extension identities; counts and diagnostics. Keep software licensing separate from [OSM data licensing and attribution](https://www.openstreetmap.org/copyright). Do not choose a software license as a side effect of data ingestion.
- Account for inputs, recognized features, exclusions, failures and unresolved references with documented counting units. Counts alone do not prove completeness; retained lineage must explain an output field or rejection.
- Require deterministic logical results for identical declared inputs and versions. Define tie-breaking and feature keys independently of hash iteration, worker scheduling and wall-clock timestamps. SQL order still requires ORDER BY.
- When implementing updates, track changed nodes through affected ways/relations and projected features; account for deletions and changes of classification or geometry. Compare an updated logical result with a clean rebuild of the same final snapshot. Do not add update scaffolding during an unrelated profile task.

## Evidence

Use small hand-written source fixtures with documented expected fields, geometry
and lineage. Include the relevant awkward cases, such as a relation with a hole,
missing member, overlapping themes, an unsupported unit or a crossing boundary.
Keep these separate from versioned real-extract integration runs.

For scale claims, record exact extract/profile versions, output equivalence,
machine, DuckDB/build configuration, duration, peak process memory and temporary
disk use. Include Rust allocations and dependency-index costs. Compare indexes
and layouts on the same required fields and query workload; report tradeoffs.
