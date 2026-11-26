// Resolved CSG tree -> manifold-3d solids. Mirrors src/asfinger/mesh.py so the browser and Python agree.
import type { RNode, Quat, Vec3 } from './types';

export const SEGMENTS = 96;

export function quatToMat4(pos: Vec3 = [0, 0, 0], q: Quat = [1, 0, 0, 0]): number[] {
  const n = Math.hypot(...q) || 1;
  const [w, x, y, z] = q.map((v) => v / n);
  const R = [
    [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
    [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
    [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
  ];
  // column-major 4x4
  return [R[0][0], R[1][0], R[2][0], 0, R[0][1], R[1][1], R[2][1], 0, R[0][2], R[1][2], R[2][2], 0, pos[0], pos[1], pos[2], 1];
}

/** Parse a binary or ASCII STL into an indexed mesh with merged vertices. */
export function parseSTL(buf: ArrayBuffer): { vert: Float32Array; tri: Uint32Array } {
  const dv = new DataView(buf);
  let tris: number[] = [];
  const n = buf.byteLength >= 84 ? dv.getUint32(80, true) : 0;
  if (84 + 50 * n === buf.byteLength) {
    for (let k = 0; k < n; k++) {
      const o = 84 + 50 * k + 12;
      for (let j = 0; j < 9; j++) tris.push(dv.getFloat32(o + 4 * j, true));
    }
  } else {
    const txt = new TextDecoder().decode(buf);
    for (const m of txt.matchAll(/vertex\s+(\S+)\s+(\S+)\s+(\S+)/g)) tris.push(+m[1], +m[2], +m[3]);
  }
  const map = new Map<string, number>();
  const vert: number[] = [];
  const tri = new Uint32Array(tris.length / 3);
  for (let i = 0; i < tris.length; i += 3) {
    const key = `${tris[i].toFixed(5)},${tris[i + 1].toFixed(5)},${tris[i + 2].toFixed(5)}`;
    let id = map.get(key);
    if (id === undefined) { id = vert.length / 3; map.set(key, id); vert.push(tris[i], tris[i + 1], tris[i + 2]); }
    tri[i / 3] = id;
  }
  return { vert: new Float32Array(vert), tri };
}

export class CSGBuilder {
  /** Every Manifold created here is tracked and freed by dispose(); WASM memory is not garbage-collected. */
  private live: any[] = [];
  constructor(private M: any, private meshes: Map<string, { vert: Float32Array; tri: Uint32Array }>) {}

  private keep<T>(m: T): T { this.live.push(m); return m; }
  /** Track a Manifold made outside build() so dispose() frees it too. */
  keepOf<T>(m: T): T { return this.keep(m); }

  /** Solids already built, used for nodes {"ref": part name} (interference rules reuse the part solids). */
  refs = new Map<string, any>();

  build(n: RNode | null | undefined): any {
    const { Manifold, Mesh } = this.M;
    if (!n) return this.keep(new Manifold());
    if (n.ref) { const r = this.refs.get(n.ref); if (!r) throw new Error(`unknown part ${n.ref}`); return r; }
    let m: any;
    switch (n.type) {
      case 'union': {
        const kids = (n.children || []).map((c) => this.build(c));
        return this.keep(kids.length ? Manifold.union(kids) : new Manifold());
      }
      case 'difference': {
        const kids = (n.children || []).map((c) => this.build(c));
        if (kids.length < 2) return kids[0];
        const tools = this.keep(Manifold.union(kids.slice(1)));
        return this.keep(kids[0].subtract(tools));
      }
      case 'box': m = this.keep(Manifold.cube(n.size, true)); break;
      case 'sphere': m = this.keep(Manifold.sphere(n.r, SEGMENTS)); break;
      case 'cylinder': m = this.keep(Manifold.cylinder(n.h, n.r, n.r, SEGMENTS, true)); break;
      case 'mesh': {
        const src = this.meshes.get(n.file!);
        if (!src) return this.keep(new Manifold());
        const s = n.scale ?? 1;
        const vert = s === 1 ? src.vert : src.vert.map((v) => v * s);
        const mesh = new Mesh({ numProp: 3, vertProperties: vert, triVerts: src.tri });
        mesh.merge();
        m = this.keep(new Manifold(mesh));
        break;
      }
      default: throw new Error(`unknown CSG node ${(n as any).type}`);
    }
    return this.keep(m.transform(quatToMat4(n.pos, n.quat)));
  }

  /** Drop zero-volume slivers (coplanar cuts leave them; slicers report them as extra shells). */
  clean(m: any): any {
    const parts = m.decompose().map((p: any) => this.keep(p)).filter((p: any) => Math.abs(p.volume()) > 1e-3);
    return this.keep(parts.length ? this.M.Manifold.compose(parts) : new this.M.Manifold());
  }

  dispose() {
    for (const m of this.live) { try { m.delete(); } catch { /* already freed */ } }
    this.live = [];
  }
}

export function toArrays(m: any): { positions: Float32Array; indices: Uint32Array } {
  const mesh = m.getMesh();
  const np = mesh.numProp;
  const nv = mesh.vertProperties.length / np;
  const positions = new Float32Array(nv * 3);
  for (let i = 0; i < nv; i++) {
    positions[3 * i] = mesh.vertProperties[np * i];
    positions[3 * i + 1] = mesh.vertProperties[np * i + 1];
    positions[3 * i + 2] = mesh.vertProperties[np * i + 2];
  }
  return { positions, indices: new Uint32Array(mesh.triVerts) };
}

/** Binary STL from indexed arrays, optionally transformed into another frame by a column-major 4x4. */
export function writeSTL(positions: Float32Array, indices: Uint32Array, name = 'ipush', mat?: number[]): ArrayBuffer {
  const nt = indices.length / 3;
  const buf = new ArrayBuffer(84 + 50 * nt);
  const dv = new DataView(buf);
  const head = new TextEncoder().encode(name.slice(0, 79));
  new Uint8Array(buf, 0, head.length).set(head);
  dv.setUint32(80, nt, true);
  const P = (i: number) => {
    const x = positions[3 * i], y = positions[3 * i + 1], z = positions[3 * i + 2];
    if (!mat) return [x, y, z];
    return [mat[0] * x + mat[4] * y + mat[8] * z + mat[12], mat[1] * x + mat[5] * y + mat[9] * z + mat[13], mat[2] * x + mat[6] * y + mat[10] * z + mat[14]];
  };
  for (let t = 0; t < nt; t++) {
    const a = P(indices[3 * t]), b = P(indices[3 * t + 1]), c = P(indices[3 * t + 2]);
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const nx = u[1] * v[2] - u[2] * v[1], ny = u[2] * v[0] - u[0] * v[2], nz = u[0] * v[1] - u[1] * v[0];
    const l = Math.hypot(nx, ny, nz) || 1;
    const o = 84 + 50 * t;
    [nx / l, ny / l, nz / l, ...a, ...b, ...c].forEach((val, j) => dv.setFloat32(o + 4 * j, val, true));
  }
  return buf;
}

/** Inverse of a rigid column-major 4x4. */
export function invRigid(m: number[]): number[] {
  const R = [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]];
  const t = [m[12], m[13], m[14]];
  const Rt = [[R[0][0], R[1][0], R[2][0]], [R[0][1], R[1][1], R[2][1]], [R[0][2], R[1][2], R[2][2]]];
  const ti = [0, 1, 2].map((i) => -(Rt[i][0] * t[0] + Rt[i][1] * t[1] + Rt[i][2] * t[2]));
  return [Rt[0][0], Rt[1][0], Rt[2][0], 0, Rt[0][1], Rt[1][1], Rt[2][1], 0, Rt[0][2], Rt[1][2], Rt[2][2], 0, ti[0], ti[1], ti[2], 1];
}
