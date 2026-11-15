# Ducklocate OSM to DuckDB

## Purpose

Ducklocate is an open-source native DuckDB extension written in Rust. It turns
OpenStreetMap data into structured tables with typed attributes, geometries and
source references. Users work through SQL inside DuckDB and select the region
and datasets they need.

The value is the documented interpretation of OSM into useful datasets: which
objects are selected, how tags become fields, how geometries are reconstructed,
and which limitations remain. Performance claims require measurements.

This is independent of the geocoding-api-duckdb experiment. Its official-address
source restrictions, GridPin integration and HTTP architecture do not apply here.

## Established direction

- Native, open-source DuckDB extension, implemented in Rust and targeting DuckDB 2.0. Pin an exact compatible release when bootstrapping the build.
- SQL is the user interface. A separate server or REST API is not part of the product.
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

## Open choices

Resolve these as concrete tasks need them, with a short rationale and evidence:

- First profile and regional acceptance fixture; first measured real extract.
- SQL names and signatures, catalogue discovery and materialization workflow.
- Input acquisition interface and region definitions.
- Geometry representation, spatial-extension integration and index strategy.
- Table keys, shared source storage and dependency indexes.
- External profile format and schema/profile compatibility policy.
- Incremental updates, deletion handling and publication semantics.
- Rust binding and exact toolchain pins, crate layout and tested platforms.
- Software license and community-distribution route. Software and OSM data licensing are separate.

No SQL interface, supported-platform matrix or performance target has been fixed
by this document. Public descriptions state the product's purpose; verified
support and current limitations belong in development and release documentation.
