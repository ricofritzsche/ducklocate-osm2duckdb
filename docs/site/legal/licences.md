---
title: Licences & attribution
description: Apache 2.0 terms, third-party notices and OpenStreetMap data licensing.
prev: false
next: false
---

## DuckLocate software, documentation and website

Copyright 2026 Rico Fritzsche and DuckLocate contributors.

Unless otherwise indicated, original DuckLocate source code, documentation,
website code and artwork are licensed under the **Apache License, Version 2.0**
(`Apache-2.0`). This includes the native DuckDB extension and the shared Rust
implementation intended for the future `osm2duckdb` CLI.

Read the [complete Apache 2.0 licence](../../../LICENSE) and
[project NOTICE](../../../NOTICE). The same files are included below as part
of the website's [distributed licence notices](#third-party-software).

Apache 2.0 permits use, modification and redistribution, including commercial
use, subject to its conditions. Redistribution requires preserving the licence
and applicable notices, identifying modified files, and carrying relevant NOTICE
attributions. The licence includes a patent grant and patent-litigation terms.
It does not generally grant trademark rights. The project's non-commercial
operation does not restrict the uses permitted by the licence.

The software and documentation are provided under the licence's warranty
disclaimer and limitation of liability, subject to mandatory law. The full
licence controls over this summary.

## Third-party software

Third-party software retains its own licences and copyright notices.
[Repository third-party notices](../../../THIRD_PARTY_NOTICES.md) describe the
native dependencies and build tooling. The website includes a downloadable
copy of the project licence and notices plus the licence texts supplied with
its installed npm dependencies:

<!-- legal-downloads -->

The website notices include build tools as well as browser code; listing a
package does not mean it is delivered to the browser. Native binary packages
must carry the notices required by their actual linked and bundled dependencies.

## OpenStreetMap data

**© OpenStreetMap contributors.** OpenStreetMap data is available under the
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
See [OpenStreetMap copyright and attribution](https://www.openstreetmap.org/copyright)
and the [OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines).

DuckLocate's Apache 2.0 licence covers the project's own materials. It does not
relicense OSM input data, extracted databases or maps made from that data.
Publicly distributing or using OSM-derived databases and produced works may
require attribution, licence information and, for derivative databases, sharing
under ODbL. Check the terms for the specific output and its use.

The repository's hand-written synthetic fixtures contain no real OSM data.
The real-input [Bremen evaluation](../../bremen-roads-evaluation.md) documents
the separate source and data attribution for its local extract.

## Names and marks

DuckLocate is the project name. DuckDB, OpenStreetMap and other third-party
names and marks belong to their respective owners. References describe
compatibility and data sources and do not imply endorsement.
