import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const android = process.argv.includes('--android');
const apiUrl = new URL(process.env.BANK_API_URL || (android
  ? 'http://10.0.2.2:8000'
  : 'http://127.0.0.1:8000'));
if (!['http:', 'https:'].includes(apiUrl.protocol) || apiUrl.username || apiUrl.password) {
  throw new Error('BANK_API_URL must be an HTTP(S) URL without credentials.');
}

await mkdir(path.join(root, 'dist'), { recursive: true });
let html = await readFile(path.join(root, 'index.html'), 'utf8');
html = html.replace('<script src="https://cdn.tailwindcss.com"></script>',
  '<link rel="stylesheet" href="./styles.css">');
html = html.replace('const API_URL = "http://127.0.0.1:8000";',
  `const API_URL = ${JSON.stringify(apiUrl.href.replace(/\/$/, '')).replaceAll('<', '\\u003c')};`);
await writeFile(path.join(root, 'dist/index.html'), html);
execFileSync(process.execPath, [
  path.join(root, 'node_modules/tailwindcss/lib/cli.js'),
  '--input', path.join(root, 'scripts/styles.css'),
  '--content', path.join(root, 'index.html'),
  '--output', path.join(root, 'dist/styles.css'), '--minify',
], { cwd: root, stdio: 'inherit' });
console.log(`Built ${android ? 'Android' : 'web'} client. API: ${apiUrl.origin}`);
