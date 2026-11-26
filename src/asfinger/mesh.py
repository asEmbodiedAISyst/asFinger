"""Mesh backend: resolved CSG tree -> triangle mesh with manifold3d (exact, robust booleans), STL I/O.

Needs numpy + manifold3d (pip install manifold3d). Not used inside Fusion.
"""

import os
import struct

import manifold3d as mf
import numpy as np

SEGMENTS = 96


def read_stl(path):
    """Binary or ASCII STL -> (V float64 Nx3, F int Mx3) with duplicate vertices merged."""
    data = open(path, 'rb').read()
    tris = None
    if len(data) >= 84:
        n = struct.unpack('<I', data[80:84])[0]
        if 84 + 50 * n == len(data):
            rec = np.frombuffer(
                data, dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), count=n, offset=84
            )
            tris = rec['v'].astype(np.float64)
    if tris is None:
        vs = [
            list(map(float, l.split()[1:4]))
            for l in data.decode(errors='ignore').splitlines()
            if l.strip().startswith('vertex')
        ]
        tris = np.array(vs, dtype=np.float64).reshape(-1, 3, 3)
    flat = tris.reshape(-1, 3)
    key = np.round(flat, 5)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    return uniq, inv.reshape(-1, 3)


def write_stl(path, V, F, name='ipush'):
    V = np.asarray(V, dtype=np.float32)
    F = np.asarray(F)
    tri = V[F]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    nrm = (nrm / ln).astype(np.float32)
    rec = np.zeros(len(F), dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    rec['n'] = nrm
    rec['v'] = tri
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(name.encode()[:80].ljust(80, b' '))
        f.write(struct.pack('<I', len(F)))
        f.write(rec.tobytes())


def _mat34(T):
    return np.array([T.R[0] + [T.p[0]], T.R[1] + [T.p[1]], T.R[2] + [T.p[2]]], dtype=np.float64)


_mesh_cache = {}


def _load_mesh(file, base_dir, scale):
    path = file if os.path.isabs(file) else os.path.join(base_dir, file)
    key = (path, scale)
    if key not in _mesh_cache:
        V, F = read_stl(path)
        m = mf.Manifold(mf.Mesh(vert_properties=(V * scale).astype(np.float32), tri_verts=F.astype(np.uint32)))
        if m.status() != mf.Error.NoError or m.is_empty():
            raise ValueError(f'{path} is not a closed (manifold) solid: {m.status()}')
        _mesh_cache[key] = m
    return _mesh_cache[key]


def build(rnode, base_dir='.'):
    """Resolved node -> manifold3d.Manifold (in root-frame mm)."""
    if rnode is None:
        return mf.Manifold()
    t = rnode['type']
    if t == 'union':
        kids = [build(c, base_dir) for c in rnode['children']]
        return mf.Manifold.batch_boolean(kids, mf.OpType.Add) if kids else mf.Manifold()
    if t == 'difference':
        kids = [build(c, base_dir) for c in rnode['children']]
        base = kids[0]
        if len(kids) > 1:
            base = base - mf.Manifold.batch_boolean(kids[1:], mf.OpType.Add)
        return base
    if t == 'box':
        m = mf.Manifold.cube(tuple(rnode['size']), True)
    elif t == 'sphere':
        m = mf.Manifold.sphere(rnode['r'], SEGMENTS)
    elif t == 'cylinder':
        m = mf.Manifold.cylinder(rnode['h'], rnode['r'], rnode['r'], SEGMENTS, True)
    elif t == 'mesh':
        m = _load_mesh(rnode['file'], base_dir, rnode.get('scale', 1.0))
    else:
        raise ValueError(t)
    return m.transform(_mat34(rnode['T']))


def clean(m, min_vol=1e-3):
    """Drop zero-volume slivers that coplanar or tangent faces leave behind (slicers flag them as extra shells).
    The mesh is first snapped to float32, the precision STL stores, so slivers created by that rounding go too."""
    me = m.to_mesh()
    V = np.asarray(me.vert_properties)[:, :3].astype(np.float32)
    key, inv = np.unique(np.round(V.astype(np.float64), 5), axis=0, return_inverse=True)
    F = inv.reshape(-1)[np.asarray(me.tri_verts)].astype(np.uint32)
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    m2 = mf.Manifold(mf.Mesh(vert_properties=key.astype(np.float32), tri_verts=F))
    if m2.status() == mf.Error.NoError and not m2.is_empty():
        m = m2
    comps = [c for c in m.decompose() if abs(c.volume()) > min_vol]
    return mf.Manifold.compose(comps) if comps else mf.Manifold()


def to_arrays(m):
    me = m.to_mesh()
    return np.asarray(me.vert_properties)[:, :3].astype(np.float64), np.asarray(me.tri_verts).astype(np.int64)


def transform_arrays(V, T):
    """Root-frame vertices -> the frame T (T is the frame's pose in root)."""
    Ti = T.inv()
    return V @ np.array(Ti.R).T + np.array(Ti.p)


def mass_properties(V, F, density_g_cm3):
    """Closed triangle mesh in mm -> (mass kg, centre of mass mm, inertia about the COM in kg*m^2, 3x3).
    Exact for polyhedra (signed tetrahedra from the origin)."""
    V = np.asarray(V, dtype=np.float64) / 1000.0  # m
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    vol6 = np.einsum('ij,ij->i', a, np.cross(b, c))  # 6 * signed volume of each tetra
    vol = vol6.sum() / 6.0
    rho = density_g_cm3 * 1000.0  # kg/m3
    mass = rho * vol
    com = (vol6[:, None] * (a + b + c)).sum(0) / (4.0 * vol6.sum())
    # second moments  int x_i x_j dV  over each tetra (0,a,b,c)
    S = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            S[i, j] = (
                vol6
                / 120.0
                * (
                    2 * (a[:, i] * a[:, j] + b[:, i] * b[:, j] + c[:, i] * c[:, j])
                    + a[:, i] * b[:, j]
                    + a[:, j] * b[:, i]
                    + a[:, i] * c[:, j]
                    + a[:, j] * c[:, i]
                    + b[:, i] * c[:, j]
                    + b[:, j] * c[:, i]
                )
            ).sum()
    S *= rho
    I_o = np.trace(S) * np.eye(3) - S  # about origin
    d = com
    I_c = I_o - mass * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return mass, com * 1000.0, I_c


def combine_mass(props):
    """[(mass, com_mm, I_com)] -> combined (mass, com_mm, I_com) via the parallel-axis theorem."""
    M = sum(p[0] for p in props)
    c = sum(p[0] * np.asarray(p[1]) for p in props) / M / 1000.0
    I = np.zeros((3, 3))
    for m, cm, Ic in props:
        d = np.asarray(cm) / 1000.0 - c
        I += Ic + m * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    return M, c * 1000.0, I
