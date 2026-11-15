# Ducklocate OSM to DuckDB

## Purpose

Ducklocate is an open-source native DuckDB extension written in Rust. It turns
OpenStreetMap data into structured tables with typed attributes, geometries and
source references. Users select the region and datasets through SQL inside
DuckDB or the osm2duckdb CLI. Both interfaces share one Rust projection
implementation and output contracts.

The value is the documented interpretation of OSM into useful datasets: which
objects are selected, how tags become fields, how geometries are reconstructed,
and which limitations remain. Performance claims require measurements.

This is independent of the geocoding-api-duckdb experiment. Its official-address
source restrictions, GridPin integration and HTTP architecture do not apply here.

## Established direction

- Native, open-source DuckDB extension, implemented in Rust and targeting DuckDB 2.0. Pin an exact compatible release when bootstrapping the build.
- SQL and the osm2duckdb CLI are supported user interfaces. The CLI builds a DuckDB database from a region or local file and selected profiles. A server or REST API is not part of the product.
- Support local OSM files and explicit downloads of named regions. Projection of a local file must not implicitly acquire or refresh data.
- Support an optional output CRS consistently in SQL and CLI. Default to WGS84 longitude/latitude in XY order; explicit reprojection transforms geometry and records the output CRS, axis convention and transformation provenance. Source data and identifiers remain unchanged, and local reads stay offline.
- A catalogue of versioned projection profiles describes datasets such as roads, buildings, administrative areas and points of interest. Barriers, settlements, landmarks, water, land use and infrastructure belong to the broader design catalogue.
- Categories may overlap. One source object can contribute to several profiles; one projected object can depend on several source objects.
- Built-in profiles establish a contract that can later support external configuration. A custom configuration language is not required to start.
- Preserve access to original tags and source references alongside interpreted fields. Unknown, missing, conditional and invalid values remain distinguishable.
- Separate data preparation from map styling. Road objects and a routing graph have different contracts.

The catalogue describes the intended design space, not an instruction to implement
every profile in the first milestone.

## Projection model

Keep the following responsibilities distinguishable in code and documentation:

1. Identify the source snapshot, selected region and required input elements.
2. Resolve dependencies needed to reconstruct the selected features.
3. Apply versioned selection, geometry and attribute rules.
4. Validate results and account for unsupported, rejected or incomplete features.
5. Expose documented tables and build metadata through DuckDB.

This describes responsibilities, not a required number of passes or crates.
Choose execution and storage strategies after a small native integration proof.

Each profile defines source selection and dependencies, output keys and types,
geometry and coordinate conventions, normalization and units, missing-value
semantics, relationships, quality rules and representative SQL queries. Region
selection must state how intersecting features and references outside the region
are handled. Spatial inference must remain identifiable as an inference.

Object projection profiles and coordinate reprojection are distinct choices.
Profiles define feature semantics; the requested output CRS defines the coordinate
representation. Both interfaces share the same transformation behavior and metadata.

## Reproducibility and quality

Identify inputs by source, content hash and available data timestamp. Record the
region definition, extension/build identity, schema and profile versions, relevant
dependencies, counts and diagnostics. Track source element type and ID together;
retain element versions where the input provides them and disclose absent metadata.

For identical declared inputs and versions, require the same logical results and
documented identifiers. SQL row order requires ORDER BY. Byte-identical DuckDB
database files are a separate claim and are not assumed.

Hand-written source fixtures and independently derived expectations establish
correctness. Real extracts establish integration and scale under recorded
conditions. Counts of recognized objects do not establish geographic completeness.
Measure build time, query latency, peak memory, temporary storage and output size
separately from correctness.

Preserve source-to-output dependencies so updates can eventually identify affected
features. Incremental update support requires its own specification and evidence;
full snapshot rebuilds remain a valid initial implementation.

## SQL and CLI design

[README.md](README.md) is the user-facing SQL and CLI documentation and currently
contains the interface proposal. SQL offers profile discovery, provider catalogue
lookup, explicit downloads, local source inspection, profile reads and a convenience
import operation. The CLI builds a database containing selected profile tables and
source/profile metadata. Both interfaces use the same projection rules and snapshot
identity. DuckDB owns catalogue and transaction behavior. Native loading, the
empty catalogue, geometry/nested output and the initial CRS path are verified in
[the development note](docs/native-foundation.md). The C API callback context has
no caller-transaction SQL execution handle. The proposed CALL import stays
unimplemented; its atomicity contract must be preserved. A test-only query-pragma
SQL expansion demonstrates a possible alternative without committing to a public
interface change. Complete profile contracts remain future work.

Keep public signatures and examples in the README rather than duplicating them
here. Design work may refine the proposal; record settled scope choices here and
retain an explicit distinction between proposed behavior and implementation evidence.

## Open choices

Resolve these as concrete tasks need them, with a short rationale and evidence:

- First profile and regional acceptance fixture; first measured real extract.
- Review the proposed SQL signatures, CLI build contract, catalogue, materialization workflow and diagnostic row contract in README.md.
- Named-region provider integration and exact extract semantics; Geofabrik is the proposed first provider.
- Geometry representation, spatial-extension integration and index strategy; CRS operation selection, accuracy policy and metadata capture.
- Table keys, shared source storage and dependency indexes.
- External profile format and schema/profile compatibility policy.
- Incremental updates, deletion handling and publication semantics.
- Broader platforms and future embedded CLI packaging beyond the pinned macOS arm64 native foundation.
- Software license and community-distribution route. Software and OSM data licensing are separate.

The README distinguishes the implemented native foundation and empty profile
catalogue from the remaining proposed SQL and CLI interfaces. No supported-platform matrix or
performance target has been fixed by this document. Public descriptions state
the product's purpose; verified support and current limitations belong in
development and release documentation.
