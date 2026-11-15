---
name: ducklocate-conventions
description: Use for repository changes and implementation prompts in Ducklocate; covers focused Rust code, architecture, independent verification, documentation and Git.
---

# Ducklocate conventions

Read [Concept.md](../../../Concept.md). Use the extension and OSM skills when the
task touches their contracts. Documentation tasks do not start a build milestone.

## Structure and processing

- Organize by responsibility: OSM decoding/reference resolution, profile rules, geometry, output construction and DuckDB integration. These are responsibilities, not mandatory top-level folders or separate crates.
- Start with the smallest layout supported by the verified extension tooling. Add crates when dependency direction, testing or native entrypoint requirements justify them. Do not copy the geocoding application's single-package restriction or a reference project's stage-per-crate layout.
- Keep each processing path visible. DuckDB callbacks translate SQL inputs and outputs; projection semantics live with their profile or operation. Keep I/O at the edges where pure rule functions make independent testing useful.
- Streaming algorithms may borrow buffers and maintain local state. Do not require whole-input copies or a command/outcome framework for ordinary scalar or table-function callbacks.
- Split files when responsibilities or tests obscure the processing path. Roughly 200 lines is a review signal, not a hard limit. Avoid catch-all services, managers, helpers and speculative plugin frameworks.

## Rust

- Use edition 2024 and pin a compatible stable toolchain during bootstrap. Record binding, native engine and build-tool versions actually verified; commit Cargo.lock once Cargo files exist.
- Prefer safe Rust. Keep necessary unsafe code at narrow native boundaries, with ownership, lifetime and threading invariants documented next to it. Do not impose a blanket unsafe ban that prevents required extension entrypoints.
- No unwrap, expect or panic for recoverable input, I/O or extension failures in production code. Return meaningful typed errors and translate them into DuckDB errors at the boundary.
- Keep invalid input, unsupported semantics, valid empty output and technical failure distinguishable. Define whether a malformed feature fails a build or becomes a reported rejection; never drop it silently.
- Use distinct types where they prevent mixing element identities, coordinate systems or units. Preserve source precision unless a documented output contract explicitly chooses otherwise.
- Keep visibility narrow. Document public behavior, NULL handling, side effects and important limitations. Explain new dependencies in the manifest or relevant development note.

## Verification

- Write expected profile results from small source fixtures and a written derivation. Never regenerate acceptance answers from the implementation under test. Investigate disagreements before changing an expectation.
- Test meaningful rules and risks: missing references, overlapping profiles, relation geometry, normalization failures, provenance, cancellation and SQL translation as applicable. Skip trivial getter tests and tests of file/module shape.
- Once a Cargo workspace exists, run cargo fmt --all --check, cargo test --workspace --locked and cargo clippy --workspace --all-targets --locked -- -D warnings for Rust changes. Add the applicable native build and SQL tests from the extension skill; Cargo success alone does not prove a loadable extension.
- For documentation-only changes, validate skill frontmatter, relative links and the diff. Do not claim native or Cargo checks ran when there is no implementation.
- Report exact commands and their results, including unavailable prerequisites or skipped cases. A missing input is not a passing integration test.

## Documentation and Git

- Record durable product choices in Concept.md; put substantial contracts, decisions and evidence under focused docs/ files when needed. Mark proposals and unresolved choices explicitly.
- Keep reusable instructions out of progress logs, and changing measurements out of AGENTS.md. Reference official sources and identify the version or source revision used.
- Reuse cached tools and extracts. Ignore local caches, databases, extension binaries and build results before producing them. Track only small fixtures with documented origin and permitted reuse.
- Inspect the working tree before editing and preserve unrelated changes. Before committing, verify the repository-local identity against Fritzsche, Rico <rico@bluvolve.dev>; do not change global Git settings.
- When committing is part of the task, use one logical change per commit, an imperative subject and verification in the body. Instruction maintenance does not itself authorize remote publication, a release or a community submission.
