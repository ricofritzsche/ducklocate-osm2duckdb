import { readdir, readFile, stat } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const output = fileURLToPath(new URL('../dist/', import.meta.url));
const base = `/${(process.env.DOCS_BASE || '').replace(/^\/+|\/+$/g, '')}`.replace(/\/$/, '');
const entries = await readdir(output, { recursive: true, withFileTypes: true });
const pages = entries.filter((entry) => entry.isFile() && entry.name.endsWith('.html'));
const failures = [];
const cache = new Map();
for (const page of pages) {
  const file = resolve(page.parentPath, page.name);
  const html = await readFile(file, 'utf8');
  for (const [, raw] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(raw)) continue;
    const url = new URL(raw.replaceAll('&amp;', '&'), `https://docs.invalid${base}/${file.slice(output.length).replace(/index\.html$/, '')}`);
    if (base && url.pathname !== base && !url.pathname.startsWith(`${base}/`)) {
      failures.push(`${file}: URL escapes configured base: ${raw}`);
      continue;
    }
    const path = decodeURIComponent(url.pathname.slice(base.length));
    let target = resolve(output, `.${path}`);
    const info = await stat(target).catch(() => null);
    if (info?.isDirectory()) target = resolve(target, 'index.html');
    const exists = await stat(target).catch(() => null);
    if (!exists?.isFile()) {
      failures.push(`${file}: missing target: ${raw}`);
      continue;
    }
    if (url.hash && target.endsWith('.html')) {
      if (!cache.has(target)) cache.set(target, await readFile(target, 'utf8'));
      const anchor = decodeURIComponent(url.hash.slice(1));
      if (!cache.get(target).includes(`id="${anchor}"`)) failures.push(`${file}: missing anchor: ${raw}`);
    }
  }
}
if (!pages.length) failures.push('No built HTML pages found. Run npm run build first.');
if (failures.length) {
  console.error(failures.join('\n'));
  process.exitCode = 1;
} else {
  console.log(`Checked local links, assets, and anchors across ${pages.length} HTML pages${base ? ` under ${base}` : ''}.`);
}
