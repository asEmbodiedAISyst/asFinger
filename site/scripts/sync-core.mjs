// Copies what the browser needs from the rest of the repo into public/ (run before dev/build).
//   src/asfinger/*.py       -> public/py/asfinger/   (pure-Python parts only; Pyodide runs them)
//   hardware/configs/*.json -> public/configs/
//   mesh assets used by the configs (hardware/assets/...) -> public/assets/...
//   Pyodide runtime         -> public/pyodide/        (self-hosted, no CDN at runtime)
// A config names its meshes as "assets/<...>", relative to the folder that holds configs/ and assets/
// (hardware/ in the repo). The site keeps the same two names under its root, so the paths in a config are
// valid in both places.
import { cpSync, mkdirSync, readdirSync, existsSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const site = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(process.env.ASFINGER_ROOT || join(site, '..'));
const pub = join(site, 'public');
const PACKAGE = 'asfinger';
const pySrc = join(repo, 'src', PACKAGE);
const hardware = join(repo, 'hardware');

const PURE = ['__init__.py', 'geom.py', 'expr.py', 'frames.py', 'csg.py', 'mjcf.py', 'options.py', 'interference.py'];
const pyDir = join(pub, 'py', PACKAGE);
rmSync(join(pub, 'py'), { recursive: true, force: true });
mkdirSync(pyDir, { recursive: true });
for (const f of PURE) cpSync(join(pySrc, f), join(pyDir, f));
writeFileSync(join(pub, 'py', 'manifest.json'), JSON.stringify({ package: PACKAGE, files: PURE }));

const cfgDir = join(pub, 'configs');
rmSync(cfgDir, { recursive: true, force: true });
mkdirSync(cfgDir, { recursive: true });
const assets = new Set();
for (const f of readdirSync(join(hardware, 'configs')).filter((f) => f.endsWith('.json'))) {
  cpSync(join(hardware, 'configs', f), join(cfgDir, f));
  const txt = readFileSync(join(hardware, 'configs', f), 'utf8');
  for (const m of txt.matchAll(/"file"\s*:\s*"([^"]+)"/g)) assets.add(m[1]);
}
rmSync(join(pub, 'assets'), { recursive: true, force: true });
for (const a of assets) {
  const src = join(hardware, a);
  if (!existsSync(src)) { console.warn('[sync-core] missing asset', a); continue; }
  mkdirSync(dirname(join(pub, a)), { recursive: true });
  cpSync(src, join(pub, a));
}

const pyo = join(site, 'node_modules', 'pyodide');
const pyoOut = join(pub, 'pyodide');
mkdirSync(pyoOut, { recursive: true });
for (const f of ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  if (existsSync(join(pyo, f))) cpSync(join(pyo, f), join(pyoOut, f));
}
console.log(`[sync-core] ${PACKAGE} (${PURE.length} files), ${assets.size} assets, pyodide -> public/`);
