import { cp, mkdir, readdir, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { build } from 'esbuild';

const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, 'dist');

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });
await cp(path.join(root, 'public'), dist, { recursive: true });

await build({
  absWorkingDir: root,
  entryPoints: {
    runner: 'src/runner.ts',
    popup: 'src/popup.ts',
    content: 'src/content.ts',
  },
  outdir: dist,
  bundle: true,
  format: 'iife',
  platform: 'browser',
  target: 'chrome120',
  minify: true,
  sourcemap: false,
  legalComments: 'none',
});

const expected = ['manifest.json', 'runner.html', 'runner.css', 'runner.js',
  'popup.html', 'popup.css', 'popup.js', 'content.js'];
const files = new Set(await readdir(dist));
for (const name of expected) {
  if (!files.has(name)) throw new Error(`Build output missing ${name}`);
}
