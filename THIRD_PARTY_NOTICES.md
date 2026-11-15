# DuckLocate third-party notices

DuckLocate's original code, documentation and website assets are licensed under
[Apache 2.0](LICENSE). Third-party materials keep their own licenses. This file
does not replace those licenses or extend DuckLocate's license to external data.

## Native extension

The exact Rust dependency graph is recorded in [Cargo.lock](Cargo.lock).
Current direct dependencies are:

| Dependency | Version | Upstream license |
| --- | --- | --- |
| [duckdb-neo](https://crates.io/crates/duckdb-neo/0.20000.2) | 0.20000.2 | MIT |
| [flate2](https://crates.io/crates/flate2/1.1.11) | 1.1.11 | MIT OR Apache-2.0 |
| [sha2](https://crates.io/crates/sha2/0.10.9) | 0.10.9 | MIT OR Apache-2.0 |
| [tempfile](https://crates.io/crates/tempfile/3.27.0) | 3.27.0 | MIT OR Apache-2.0 |
| [rusqlite](https://crates.io/crates/rusqlite/0.32.1) | 0.32.1 | MIT |
| [serde](https://crates.io/crates/serde/1.0.229) | 1.0.229 | MIT OR Apache-2.0 |
| [serde_json](https://crates.io/crates/serde_json/1.0.154) | 1.0.154 | MIT OR Apache-2.0 |

The bundled SQLite source is public domain; the Rust SQLite bindings have their
own MIT license. DuckDB and its binding/tooling components retain their upstream
terms. See the licenses supplied with the resolved crates and the selected
DuckDB artifact, including separately loaded extensions such as Spatial.

Build integration follows the [official Rust extension template at the recorded
revision](https://github.com/duckdb/extension-template-rs/tree/a679601f8e133db7546777c6637bc7a6c2d2780e).
The `extension-ci-tools` Git submodule retains its own upstream notices and
licenses; it is not relicensed by DuckLocate.

This repository does not distribute a supported native binary release. A binary
distribution must include the actual transitive, linked and bundled dependency
license texts and notices for its platform and features. This direct-dependency
summary is not a substitute for that distribution inventory.

## Documentation website

Astro, Starlight, Pagefind, Expressive Code, Shiki and their dependencies retain
their respective licenses. Installed versions are fixed by
[website/package-lock.json](website/package-lock.json).

The website preparation step generates `website/public/legal/licenses.txt` from
the project LICENSE and NOTICE, this file, and license/notice files supplied in
the installed npm packages. It also includes the upstream Pagefind 1.6.0 license
for the default UI package, which omits that file from its npm archive, and the
Svelte 4.2.20 runtime license for code bundled into that UI (version recorded in
Pagefind's upstream `pagefind_ui/default/package-lock.json` at tag `v1.6.0`). The
result is served with the static website and linked from its license page.
The inventory includes build tools as well as client assets; it does not assert
that every installed package is shipped to visitors. Metadata-only entries are
identified when an installed package does not supply a license text.

Original third-party copyright and license notices in generated assets must
also be preserved. Update the installed dependencies and regenerate the notices
when changing the website lockfile. Build-tool binaries in `node_modules` are
not distributed as part of the static site.

## OpenStreetMap data

© OpenStreetMap contributors. OpenStreetMap data is licensed under
[ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), with
[attribution and copyright information](https://www.openstreetmap.org/copyright).
DuckLocate's software license does not change the license of input or derived
data. Local real-data evaluation extracts are not distributed in this repository.
