/// <reference lib="webworker" />
// The model engine. Runs in a Web Worker so the UI never blocks:
//   Pyodide + asfinger (the same Python as the command line)         -> params, frames, solved poses, CSG trees
//   manifold-3d (WASM)                                                      -> solids, meshes, STL
import ManifoldModule from 'manifold-3d';
import manifoldWasmUrl from 'manifold-3d/manifold.wasm?url';
import { CSGBuilder, parseSTL, toArrays, writeSTL, quatToMat4, invRigid } from './csg';
import type { PartMesh, Resolved, SolveResult } from './types';

declare const self: DedicatedWorkerGlobalScope;

const BASE = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') ?? '';
let py: any = null;
let M: any = null;
const meshFiles = new Map<string, { vert: Float32Array; tri: Uint32Array }>();
let last: { resolved: Resolved; config: any } | null = null;

const BOOT = `
import json, sys
sys.path.insert(0, '/home/pyodide')
from asfinger import Model

def asfinger_solve(cfg_json, params_json, options_json, lang=None):
    m = Model(json.loads(cfg_json), '/')
    m.log = lambda *a: None
    m.set_options(**{k: v for k, v in json.loads(options_json).items() if k in m.cfg.get('options', {})})
    for k, v in json.loads(params_json).items():
        m.set(**{k: v})
    R = m.resolve(resolve=True)
    return json.dumps({'resolved': m.resolved_json(R), 'checks': m.check(R, lang), 'config': m.cfg})

`;

async function init() {
  if (py && M) return;
  const t0 = performance.now();
  const [{ loadPyodide }, manifold] = await Promise.all([
    import(/* @vite-ignore */ `${BASE}/pyodide/pyodide.mjs`),
    ManifoldModule({ locateFile: () => manifoldWasmUrl } as any),
  ]);
  manifold.setup();
  M = manifold;
  py = await loadPyodide({ indexURL: `${BASE}/pyodide/` });
  const man = await (await fetch(`${BASE}/py/manifest.json`)).json();
  py.FS.mkdirTree(`/home/pyodide/${man.package}`);
  await Promise.all(man.files.map(async (f: string) => {
    const txt = await (await fetch(`${BASE}/py/${man.package}/${f}`)).text();
    py.FS.writeFile(`/home/pyodide/${man.package}/${f}`, txt);
  }));
  py.runPython(BOOT);
  return performance.now() - t0;
}

async function ensureMeshFiles(resolved: Resolved) {
  const files = new Set<string>();
  const walk = (n: any) => { if (n.type === 'mesh' && n.file) files.add(n.file); (n.children || []).forEach(walk); };
  resolved.parts.forEach((p) => walk(p.tree));
  await Promise.all([...files].filter((f) => !meshFiles.has(f)).map(async (f) => {
    const r = await fetch(`${BASE}/${f}`);
    if (r.ok) meshFiles.set(f, parseSTL(await r.arrayBuffer()));
  }));
}

async function solve(config: any, params: Record<string, number | string>, options: Record<string, boolean>, lang: string): Promise<SolveResult> {
  await init();
  const t0 = performance.now();
  const out = JSON.parse(py.globals.get('asfinger_solve')(JSON.stringify(config), JSON.stringify(params), JSON.stringify(options), lang));
  const t1 = performance.now();
  const resolved: Resolved = out.resolved;
  await ensureMeshFiles(resolved);
  const b = new CSGBuilder(M, meshFiles);
  const meshes: PartMesh[] = [];
  const checks: string[] = [...out.checks];
  const warnings: string[] = [];
  const overlaps: SolveResult['overlaps'] = [];
  try {
    for (const p of resolved.parts) {
      const solid = b.clean(b.build(p.tree));
      b.refs.set(p.name, solid);
      const { positions, indices } = toArrays(solid);
      meshes.push({ name: p.name, role: p.role, color: p.color, frame: p.frame, positions, indices, volume: solid.volume() });
    }
    // interference rules from the config, same as Model.interference in Python
    for (const j of resolved.interference ?? []) {
      const inter = b.keepOf(b.build(j.a).intersect(b.build(j.b)));
      const v = inter.volume();
      if (v <= j.tol) continue;
      const msg = (lang === 'en' && j.msg_en) || j.msg;
      const level = j.level === 'warn' ? 'warn' : 'error';
      (level === 'warn' ? warnings : checks).push(`${msg} (${j.id}: ${v.toFixed(1)} mm³)`);
      overlaps.push({ id: j.id, ...toArrays(inter), volume: v, level });
    }
  } finally {
    b.dispose();
  }
  last = { resolved, config: out.config };
  return { resolved, checks, warnings, config: out.config, meshes, overlaps, ms: { python: t1 - t0, geometry: performance.now() - t1 } };
}

/** STL of a print set (several printed parts fused, in the frame of its first member: the pusher base face is z = 0)
 *  or of one part in its own frame. Same as src/asfinger/build.py. */
function exportSTL(kind: 'set' | 'part', name: string): { file: string; bytes: ArrayBuffer; volume: number; bodies: number } {
  if (!last) throw new Error('nothing solved yet');
  const { resolved, config } = last;
  const b = new CSGBuilder(M, meshFiles);
  try {
    if (kind === 'set') {
      const members: string[] = config.print_sets?.[name] ?? [];
      const parts = members.map((n) => resolved.parts.find((p) => p.name === n)).filter((p) => !!p);
      if (!parts.length) throw new Error(`print set ${name} is empty`);
      const fused = b.clean(M.Manifold.union(parts.map((p) => b.build(p.tree))));
      const { positions, indices } = toArrays(fused);
      const f0 = resolved.frames[parts[0].frame].world;
      return { file: `${name}.stl`, bytes: writeSTL(positions, indices, name, invRigid(quatToMat4(f0.pos, f0.quat))), volume: fused.volume(), bodies: fused.decompose().length };
    }
    const p = resolved.parts.find((q) => q.name === name);
    if (!p) throw new Error(`no part ${name}`);
    const solid = b.clean(b.build(p.tree));
    const { positions, indices } = toArrays(solid);
    const f = resolved.frames[p.frame].world;
    return { file: `${name}.stl`, bytes: writeSTL(positions, indices, name, invRigid(quatToMat4(f.pos, f.quat))), volume: solid.volume(), bodies: 1 };
  } finally {
    b.dispose();
  }
}

self.onmessage = async (e: MessageEvent) => {
  const { id, type } = e.data;
  try {
    if (type === 'init') {
      const ms = await init();
      self.postMessage({ id, ok: true, result: { ms } });
    } else if (type === 'solve') {
      const r = await solve(e.data.config, e.data.params || {}, e.data.options || {}, e.data.lang || 'en');
      const transfer = [...r.meshes, ...r.overlaps].flatMap((m) => [m.positions.buffer, m.indices.buffer]);
      self.postMessage({ id, ok: true, result: r }, transfer as Transferable[]);
    } else if (type === 'stl') {
      const r = exportSTL(e.data.kind, e.data.name);
      self.postMessage({ id, ok: true, result: r }, [r.bytes]);
    } else {
      throw new Error(`unknown message ${type}`);
    }
  } catch (err: any) {
    self.postMessage({ id, ok: false, error: String(err?.message || err) });
  }
};
