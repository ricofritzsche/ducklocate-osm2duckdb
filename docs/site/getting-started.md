---
title: Your first query
description: Build the local extension and query the synthetic roads fixture.
---

This walkthrough uses the repository's small, synthetic roads fixture. Run the
commands from the **repository root**, rather than the website directory.

## Build and load

The recorded native environment is **macOS arm64 and DuckDB 2.0.0**. Follow the
[build instructions](../../README.md#build-and-test) to obtain the pinned tools and
create the release artifact. Setup explicitly downloads development dependencies.
Reading a local PBF does not download data.

There is no community installation or packaged CLI yet. The `-unsigned` flag in
the example is for the locally built development extension.

## Query the fixture

<!-- readme:first-query -->

## Understand the result

The sample selects one known way from the fixture. Its `road_class` preserves
the original highway value, `max_speed_kmh` is an interpreted speed, and
`oneway` describes an explicit tag relative to the original way direction.
Missing values do not imply permission or two-way travel.

- [SQL & usage reference](../../README.md#public-sql-interface): arguments, defaults, errors, and prerequisites.
- [Roads 1.0.0](../roads-v1.md): selection rules, the ordered schema, and diagnostic codes.
- [Roads verification](../roads-verification.md): recorded checks and their limits.

Use a small existing local extract when moving beyond the fixture. The current
512 MiB source limit and other [resource limits](../roads-v1.md#execution-security-and-resource-limits)
apply to each scan.
