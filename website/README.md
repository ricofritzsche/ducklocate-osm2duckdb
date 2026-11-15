# DuckLocate documentation website

Astro/Starlight documentation website, published from `main` at
<https://ricofritzsche.github.io/ducklocate-osm2duckdb/>. A custom domain is not
configured.

## Preview

Use Node.js 22.12.0 or newer. From the repository root:

```sh
npm --prefix website ci
npm --prefix website run dev
```

Open the Local URL printed by Astro. Search is indexed in the production build;
use the production preview to check it:

```sh
npm --prefix website run build
npm --prefix website run check:links
npm --prefix website run preview
```

## Content and structure

- `docs/site/`: authored overview, getting-started guide, and roadmap.
- `README.md`: canonical SQL/usage reference, rendered at `/reference/`.
- `docs/roads-v1.md`: canonical roads contract, rendered at `/profiles/roads/`.
- `Concept.md` and existing verification/evaluation notes: rendered as project/development pages.
- `website/`: configuration, styles, assets, and content preparation.
- `docs/site/legal/`: operator/contact, privacy, and licensing pages.
- `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`: canonical project licensing.

The site footer links to all legal pages. Starlight's default footer remains
available above these links. The project name is **DuckLocate**; lowercase
`ducklocate` remains the extension, SQL and repository identifier.

Configuration preparation copies project licensing and the installed npm
packages' supplied license/notice files into ignored `public/legal/`, which is
included in the static output. Do not edit these generated files. Missing
optional platform packages are omitted; installed versions must match the
lockfile. `licenses/Pagefind-LICENSE.txt` preserves the upstream
[Pagefind 1.6.0 license](https://github.com/Pagefind/pagefind/blob/v1.6.0/LICENSE)
for its default UI package, whose npm archive omits the text. Update that source
if Pagefind changes. `licenses/Svelte-LICENSE.txt` preserves the
[Svelte 4.2.20 license](https://github.com/sveltejs/svelte/blob/svelte%404.2.20/LICENSE.md)
for the runtime bundled into Pagefind's default UI; the version comes from
[Pagefind's upstream lockfile](https://github.com/Pagefind/pagefind/blob/v1.6.0/pagefind_ui/default/package-lock.json).
Packages without a separate notice file are explicitly
identified as metadata-only; the inventory includes tools that are not shipped
to visitors and is not a native binary license inventory.

The configuration prepares ignored `.generated/docs/` input before Astro reads
the content collection. It adds page metadata to existing notes, removes their
first H1 in the rendered copy, and maps repository Markdown links to site routes.
Links to repository files without a site page point to GitHub. The first-query
example is included from the README by a named marker, rather than copied.
Source changes regenerate pages during the development session.

Edit the source documents, never `.generated/`. Add authored pages under
`docs/site/`, use relative Markdown links to their source files, and add their
slugs to the sidebar in `astro.config.mjs`. The source Markdown remains readable
on GitHub. Keep full contracts in their canonical files.

## GitHub Pages deployment

The [documentation workflow](../.github/workflows/website.yml) runs on pushes to
`main`, pull requests targeting `main`, and manual dispatch. It installs the
locked npm dependencies with Node.js 22.12.0, builds the static output and checks
local links, assets and anchors. Successful `main` builds upload `website/dist/`
and deploy it to the `github-pages` environment. Pull requests only build and
check; they do not deploy. GitHub Pages must use GitHub Actions as its source.

The workflow pins action revisions and sets the public origin and repository
prefix below. Check its deployment job and then the live site after publishing.

`DOCS_SITE` sets the public origin; `DOCS_BASE` sets an optional repository prefix.
Both remain unset for local use. To reproduce the published build:

```sh
DOCS_SITE=https://ricofritzsche.github.io DOCS_BASE=/ducklocate-osm2duckdb npm --prefix website run build
DOCS_BASE=/ducklocate-osm2duckdb npm --prefix website run check:links
```

A custom subdomain uses its own origin and `/` as the base. Domain selection
and DNS configuration remain separate work. Hosting the static `website/dist/`
output requires no application server.

Framework references: [Starlight](https://starlight.astro.build/),
[Astro on GitHub Pages](https://docs.astro.build/en/guides/deploy/github/).

## Verification notes

The initial scaffold was built with Node.js 22.12.0, npm 10.9.0, Astro 7.2.10,
and Starlight 0.43.1. Production builds and local link/asset/anchor checks passed
both at `/` and with `DOCS_BASE=/ducklocate-osm2duckdb` plus
`DOCS_SITE=https://ricofritzsche.github.io`. Production search for
`ducklocate_read`, navigation, and 1440 px / 375 px layouts were checked in a browser.
No native extension build or Rust checks are part of this documentation change.

Local builds without `DOCS_SITE` intentionally skip the sitemap. The pinned
Astro bundler also emits a non-fatal `use astro:head-inject` directive warning for
the MDX overview; the rendered page, component styles, and search were checked.
In a restricted agent environment, `ASTRO_TELEMETRY_DISABLED=1` avoids writing
Astro's preferences outside the checkout; `ASTRO_DEV_BACKGROUND=1` (or
`ASTRO_PREVIEW_BACKGROUND=1`) lets a retained execution session own the server.
