import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { prepareContent, sourcePaths } from './scripts/prepare-content.mjs';
import { prepareLicenses, licenseSourcePaths } from './scripts/prepare-licenses.mjs';

await prepareLicenses();
await prepareContent();

export default defineConfig({
  // Set DOCS_SITE and DOCS_BASE when choosing a Pages URL or custom domain.
  site: process.env.DOCS_SITE,
  base: process.env.DOCS_BASE || '/',
  integrations: [
    starlight({
      title: 'DuckLocate',
      description: 'OpenStreetMap snapshots into typed, queryable DuckDB features.',
      logo: { src: './src/assets/ducklocate.svg' },
      favicon: '/favicon.svg',
      customCss: ['./src/styles/custom.css'],
      components: { Footer: './src/components/Footer.astro' },
      social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/ricofritzsche/ducklocate-osm2duckdb' }],
      sidebar: [
        { label: 'Overview', slug: '' },
        { label: 'Start here', items: [{ slug: 'getting-started' }] },
        { label: 'Use the extension', items: [
          { label: 'SQL & usage reference', slug: 'reference' },
          { label: 'Roads 1.0.0', slug: 'profiles/roads' },
        ] },
        { label: 'Project', items: [
          { slug: 'project/roadmap' },
          { label: 'Concept & scope', slug: 'project/concept' },
        ] },
        { label: 'Development', collapsed: true, items: [
          { label: 'Roads verification', slug: 'development/roads-verification' },
          { label: 'Bremen evaluation', slug: 'development/bremen-roads-evaluation' },
          { label: 'Native foundation', slug: 'development/native-foundation' },
        ] },
        { label: 'Legal', collapsed: true, items: [
          { slug: 'legal/legal-notice' },
          { slug: 'legal/privacy' },
          { slug: 'legal/licences' },
        ] },
      ],
    }),
    {
      name: 'ducklocate-documentation-sources',
      hooks: {
        'astro:server:setup': ({ server }) => {
          server.watcher.add([...sourcePaths, ...licenseSourcePaths]);
          for (const event of ['add', 'change', 'unlink']) {
            server.watcher.on(event, (path) => {
              if (licenseSourcePaths.some((source) => path === source || path.startsWith(`${source}/`))) {
                prepareLicenses().catch((error) => server.config.logger.error(error.message));
              }
              if (sourcePaths.some((source) => path === source || path.startsWith(`${source}/`))) {
                prepareContent().catch((error) => server.config.logger.error(error.message));
              }
            });
          }
        },
      },
    },
  ],
});
