"""CSG trees: five element types bound to frames.

Leaves (all centred on their own origin):
    {"box":      {"size": [x, y, z]}}
    {"box":      {"size": [x, y], "from": PT, "to": PT, "up": [vx, vy, vz]}}   # bar between two points
    {"box":      {"corners": [PT, PT]}}                                       # axis-aligned box spanning two points
    {"sphere":   {"r": e}}
    {"cylinder": {"r": e, "h": e}}                                            # along local Z
    {"cylinder": {"r": e, "from": PT, "to": PT}}
    {"mesh":     {"file": "assets/x.stl", "scale": 1}}                        # an imported solid, placed as-is
Operations:
    {"union": [node, ...]}        {"difference": [base, cut, cut, ...]}
Shared shapes: a config may hold named sub-trees under "shapes"; {"use": "name"} places one (with its own
"name", "pos", "rot", "frame", "enabled" applied on top), so the same solid can appear in several parts.
Common keys on every node: "name", "pos", "rot", "frame" (evaluate this node in another frame), "enabled" (expr),
"sim": "collide" | "none" (leaf only; whether it becomes a MuJoCo collision primitive), "color".
PT is [x, y, z] in the node's frame, or {"frame": "S_mount", "pos": [x, y, z]} anywhere in the tree.

`resolve_tree` turns a node into the same tree with every leaf given its pose in the root frame (mm),
which is what all backends (mesh, MJCF, preview, Fusion) consume.
"""

import copy

from . import geom as G
from .expr import ev_vec, evaluate
from .frames import rot_from_spec

LEAVES = ('box', 'sphere', 'cylinder', 'mesh')
OPS = ('union', 'difference')


def node_type(node):
    ks = [k for k in LEAVES + OPS if k in node]
    if len(ks) != 1:
        raise ValueError(f'CSG node must have exactly one of {LEAVES + OPS}: {list(node)}')
    return ks[0]


def _point(pt, T_frame, world, P):
    """Point spec -> coordinates in the root frame."""
    if isinstance(pt, dict):
        return world[pt['frame']].pt(ev_vec(pt.get('pos', [0, 0, 0]), P))
    return T_frame.pt(ev_vec(pt, P))


def _segment_tf(a, b, up):
    """Frame whose Z runs from a to b, origin at the midpoint, Y as close to `up` as possible."""
    z = G.unit(G.sub(b, a))
    upv = up if abs(G.dot(G.unit(up), z)) < 0.999 else ([1, 0, 0] if abs(z[0]) < 0.9 else [0, 1, 0])
    y = G.unit(G.sub(upv, G.mul(z, G.dot(upv, z))))
    x = G.cross(y, z)
    return G.Tf(G.cols(x, y, z), G.mul(G.add(a, b), 0.5)), G.norm(G.sub(b, a))


def _extend_ends(a, b, spec, P):
    """Optional `extend_from` / `extend_to`: lengthen a from/to element past either end (mm)."""
    d = G.unit(G.sub(b, a))
    ea = evaluate(spec.get('extend_from', 0), P)
    eb = evaluate(spec.get('extend_to', 0), P)
    return G.sub(a, G.mul(d, ea)), G.add(b, G.mul(d, eb))


def resolve_tree(node, T_frame, world, P, path='root', shapes=None):
    """Return a resolved copy: leaves carry 'T' (pose in root, Tf) and numeric dims; disabled nodes are dropped."""
    if 'enabled' in node and not evaluate(node['enabled'], P):
        return None
    if 'frame' in node:
        T_frame = world[node['frame']]
    T_node = T_frame * G.Tf(rot_from_spec(node.get('rot'), P), ev_vec(node.get('pos', [0, 0, 0]), P))
    name = node.get('name', path)
    if 'use' in node:  # a shared shape, placed at this node's pose
        if not shapes or node['use'] not in shapes:
            raise ValueError(f'unknown shape {node["use"]!r} (see "shapes" in the config)')
        out = resolve_tree(shapes[node['use']], T_node, world, P, name, shapes)
        if out is not None and 'name' in node:
            out['name'] = name
        return out
    t = node_type(node)
    out = {'type': t, 'name': name}
    if 'color' in node:
        out['color'] = node['color']
    if t in OPS:
        kids = [resolve_tree(c, T_node, world, P, f'{name}/{i}', shapes) for i, c in enumerate(node[t])]
        kids = [k for k in kids if k is not None]
        if t == 'difference' and (not kids or kids[0] is None):
            return None
        out['children'] = kids
        return out
    spec = node[t]
    out['sim'] = node.get('sim', 'collide')
    if t == 'box' and 'corners' in spec:
        # axis-aligned in the node frame, spanning two points (each may live in any frame)
        Ti = T_node.inv()
        a = Ti.pt(_point(spec['corners'][0], T_node, world, P))
        b = Ti.pt(_point(spec['corners'][1], T_node, world, P))
        lo = [min(a[i], b[i]) for i in range(3)]
        hi = [max(a[i], b[i]) for i in range(3)]
        out.update(
            T=T_node * G.Tf(None, [(lo[i] + hi[i]) / 2 for i in range(3)]), size=[hi[i] - lo[i] for i in range(3)]
        )
    elif t == 'box':
        size = [evaluate(v, P) for v in spec['size']]
        if 'from' in spec:
            a = _point(spec['from'], T_node, world, P)
            b = _point(spec['to'], T_node, world, P)
            a, b = _extend_ends(a, b, spec, P)
            up = T_node.vec(ev_vec(spec.get('up', [0, 1, 0]), P))
            T_seg, L = _segment_tf(a, b, up)
            out.update(T=T_seg, size=[size[0], size[1], L + evaluate(spec.get('extend', 0), P)])
        else:
            out.update(T=T_node, size=size)
    elif t == 'sphere':
        out.update(T=T_node, r=evaluate(spec['r'], P))
    elif t == 'cylinder':
        r = evaluate(spec['r'], P)
        if 'from' in spec:
            a = _point(spec['from'], T_node, world, P)
            b = _point(spec['to'], T_node, world, P)
            T_seg, L = _segment_tf(a, b, [0, 0, 1])
            out.update(T=T_seg, r=r, h=L + evaluate(spec.get('extend', 0), P))
        else:
            out.update(T=T_node, r=r, h=evaluate(spec['h'], P))
    elif t == 'mesh':
        out.update(T=T_node, file=spec['file'], scale=evaluate(spec.get('scale', 1), P))
        out['sim'] = node.get('sim', 'none')
    return out


def collision_leaves(rnode):
    """MuJoCo has no booleans: keep the positive side of every difference, drop what is subtracted."""
    if rnode is None:
        return []
    t = rnode['type']
    if t == 'union':
        return [l for c in rnode['children'] for l in collision_leaves(c)]
    if t == 'difference':
        return collision_leaves(rnode['children'][0]) if rnode['children'] else []
    return [rnode] if rnode.get('sim') == 'collide' and t != 'mesh' else []


def leaves(rnode):
    if rnode is None:
        return []
    if rnode['type'] in OPS:
        return [l for c in rnode['children'] for l in leaves(c)]
    return [rnode]


def to_json(rnode):
    """Resolved tree -> plain JSON (poses as pos + quat)."""
    if rnode is None:
        return None
    o = {k: v for k, v in rnode.items() if k not in ('T', 'children')}
    if 'T' in rnode:
        o.update(rnode['T'].to_json(10, 12))  # full precision: CAD kernels need faces that touch to coincide
    if 'children' in rnode:
        o['children'] = [to_json(c) for c in rnode['children']]
    return o


def resolve_parts(cfg, P, world):
    parts = []
    shapes = cfg.get('shapes')
    for part in cfg['parts']:
        if 'enabled' in part and not evaluate(part['enabled'], P):
            continue
        T = world[part['frame']]
        tree = resolve_tree(part['csg'], T, world, P, part['name'], shapes)
        if tree is None:
            continue
        coll = None
        if 'collision' in part:
            coll = [
                resolve_tree(n, T, world, P, f'{part["name"]}/collision{i}', shapes)
                for i, n in enumerate(part['collision'])
            ]
            coll = [l for c in coll for l in leaves(c)]
        p = {k: copy.deepcopy(v) for k, v in part.items() if k not in ('csg', 'collision')}
        p['tree'] = tree
        p['collision_leaves'] = coll if coll is not None else collision_leaves(tree)
        parts.append(p)
    return parts
