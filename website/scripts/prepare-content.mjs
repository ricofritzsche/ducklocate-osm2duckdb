import { readdir, readFile, mkdir, writeFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, extname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const website = fileURLToPath(new URL('../', import.meta.url));
const root = resolve(website, '..');
const output = resolve(website, '.generated/docs');
const repository = 'https://github.com/ricofritzsche/ducklocate-osm2duckdb';
export const sourcePaths = [resolve(root, 'docs'), resolve(root, 'README.md'), resolve(root, 'Concept.md')];

const referencePages = [
  ['README.md', 'reference', 'SQL & usage reference'],
  ['Concept.md', 'project/concept', 'Concept & scope'],
  ['docs/roads-v1.md', 'profiles/roads', 'Roads 1.0.0'],
  ['docs/roads-verification.md', 'development/roads-verification', 'Roads verification'],
  ['docs/native-foundation.md', 'development/native-foundation', 'Native foundation'],
  ['docs/bremen-roads-evaluation.md', 'development/bremen-roads-evaluation', 'Bremen real-input evaluation'],
];

export function pageUrl(slug) {
  const base = `/${(process.env.DOCS_BASE || '').replace(/^\/+|\/+$/g, '')}`.replace(/\/$/, '');
  return `${base}/${slug ? `${slug}/` : ''}`;
}

async function authoredPages(directory = resolve(root, 'docs/site')) {
  const pages = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) pages.push(...await authoredPages(path));
    else if (/\.mdx?$/.test(entry.name)) {
      const slug = relative(resolve(root, 'docs/site'), path).replace(/\.mdx?$/, '').replace(/(^|\/)index$/, '');
      pages.push([relative(root, path), slug]);
    }
  }
  return pages;
}

function rewriteLinks(markdown, source, routes) {
  return markdown.replace(/\]\(([^\s)]+)(\s+"[^"]*")?\)/g, (match, href, title = '') => {
    if (/^(?:[a-z][a-z\d+.-]*:|#)/i.test(href)) return match;
    const [path, fragment = ''] = href.split('#');
    const target = resolve(dirname(resolve(root, source)), path);
    if (!existsSync(target)) throw new Error(`Missing source link: ${source}: ${href}`);
    const route = routes.get(target);
    if (route !== undefined) return `](${pageUrl(route)}${fragment ? `#${fragment}` : ''}${title})`;
    const repoPath = relative(root, target);
    if (repoPath.startsWith('..')) throw new Error(`Link outside repository: ${source}: ${href}`);
    return `](${repository}/blob/main/${repoPath}${fragment ? `#${fragment}` : ''}${title})`;
  });
}

async function generateContent() {
  const pages = [...referencePages, ...await authoredPages()];
  const routes = new Map(pages.map(([source, slug]) => [resolve(root, source), slug]));
  const expected = new Set();
  for (const [source, slug, title] of pages) {
    let body = await readFile(resolve(root, source), 'utf8');
    if (title) {
      body = body.replace(/^# .+\r?\n/m, '');
      body = `---\ntitle: ${JSON.stringify(title)}\neditUrl: ${repository}/edit/main/${source}\n---\n${body}`;
    }
    body = rewriteLinks(body, source, routes);
    body = body.replace('<!-- legal-downloads -->', [
      `- [Apache 2.0 licence text](${pageUrl('legal')}LICENSE)`,
      `- [Project NOTICE](${pageUrl('legal')}NOTICE)`,
      `- [Third-party notices and licence texts](${pageUrl('legal')}licenses.txt)`,
    ].join('\n'));
    // Reuse the README's runnable example without maintaining a second copy.
    body = await replaceIncludes(body, routes);
    const file = resolve(output, `${slug || 'index'}${extname(source)}`);
    expected.add(file);
    await mkdir(dirname(file), { recursive: true });
    const current = await readFile(file, 'utf8').catch(() => null);
    if (current !== body) await writeFile(file, body);
  }
  // Remove pages whose source was deleted, including during development.
  for (const entry of await readdir(output, { recursive: true, withFileTypes: true })) {
    const path = resolve(entry.parentPath, entry.name);
    if (entry.isFile() && !expected.has(path)) await rm(path);
  }
}

async function replaceIncludes(body, routes) {
  const marker = '<!-- readme:first-query -->';
  if (!body.includes(marker)) return body;
  const readme = await readFile(resolve(root, 'README.md'), 'utf8');
  const section = readme.match(/^## Read a local file\r?\n([\s\S]*?)(?=^## |$(?![\s\S]))/m)?.[1];
  if (!section) throw new Error('README is missing the Read a local file section.');
  return body.replace(marker, rewriteLinks(section.trim(), 'README.md', routes));
}

// Serialize watcher events so a burst of file saves cannot race generation.
let pending = Promise.resolve();
export function prepareContent() {
  pending = pending.catch(() => {}).then(generateContent);
  return pending;
}
