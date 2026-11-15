import { readdir, readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const website = fileURLToPath(new URL('../', import.meta.url));
const root = resolve(website, '..');
const legal = resolve(website, 'public/legal');
const noticeName = /^(?:licen[cs]es?|copying|notice|third[-_]?party)(?:[.\-_]|$)/i;
export const licenseSourcePaths = [
  ...['LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'].map((name) => resolve(root, name)),
  resolve(website, 'package-lock.json'),
  resolve(website, 'licenses'),
];

async function noticeFiles(directory, prefix = '') {
  const files = [];
  for (const entry of await readdir(resolve(directory, prefix), { withFileTypes: true })) {
    if (!noticeName.test(entry.name)) continue;
    const path = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isFile()) files.push(path);
    else if (entry.isDirectory()) files.push(...await noticeFiles(directory, path));
  }
  return files.sort();
}

export async function prepareLicenses() {
  const lock = JSON.parse(await readFile(resolve(website, 'package-lock.json'), 'utf8'));
  const sections = ['DuckLocate website license notices\n\n'
    + 'Installed npm packages include build tools and browser code. Platform-specific\n'
    + 'packages not installed on this build host are not listed. Third-party terms\n'
    + 'are preserved below; they are not replaced by DuckLocate\'s Apache-2.0 license.'];
  await mkdir(legal, { recursive: true });
  for (const name of ['LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md']) {
    const body = await readFile(resolve(root, name), 'utf8');
    sections.push(`${name}\n\n${body}`);
    await writeFile(resolve(legal, name), body);
  }
  // The default UI archive omits LICENSE; use the license from its upstream tag.
  const pagefindLicense = await readFile(resolve(website, 'licenses/Pagefind-LICENSE.txt'), 'utf8');
  const svelteLicense = await readFile(resolve(website, 'licenses/Svelte-LICENSE.txt'), 'utf8');
  for (const [path, entry] of Object.entries(lock.packages).sort(([a], [b]) => a.localeCompare(b))) {
    if (!path) continue;
    const directory = resolve(website, path);
    let manifest;
    try {
      manifest = JSON.parse(await readFile(resolve(directory, 'package.json'), 'utf8'));
    } catch (error) {
      if (error.code === 'ENOENT' && entry.optional) continue;
      throw error;
    }
    if (manifest.version !== entry.version) throw new Error(`License inventory version mismatch: ${path}`);
    const texts = [];
    for (const file of await noticeFiles(directory)) {
      texts.push(`${file}\n\n${await readFile(resolve(directory, file), 'utf8')}`);
    }
    if (manifest.name === '@pagefind/default-ui') {
      texts.push(`Upstream Pagefind license\n\n${pagefindLicense}`);
      texts.push(`Bundled Svelte runtime license\n\n${svelteLicense}`);
    }
    sections.push(`${manifest.name} ${manifest.version}\n`
      + `Package: ${path}\nDeclared license: ${manifest.license || entry.license || 'See upstream'}\n`
      + `Source: https://www.npmjs.com/package/${manifest.name}/v/${manifest.version}\n\n`
      + (texts.length ? texts.join('\n\n') : 'No separate license text supplied in this package archive; metadata only.'));
  }
  await writeFile(resolve(legal, 'licenses.txt'), sections.join('\n\n' + '='.repeat(72) + '\n\n') + '\n');
}
