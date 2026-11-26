"""Interference checks: solids that must not overlap, and a camera line of sight that must stay free.

Config:
    "interference": [
      {"id": "phone_body", "a": "phone", "b": "tool_body", "msg": "...", "msg_en": "..."},
      {"id": "holder_rod", "a": "holder", "b": {"part": "tool_body", "only": ["rod", "tip"]}, ...},
      {"id": "sight", "a": {"sight": {"from": "C_main", "to": "T_tip", "stop_before": "rod_D/2 + 1", "r": 0.5}},
       "b": [{"part": "tool_body", "only": ["adapter", "beam_mitred", "spine_mitred"]}, "holder", "phone"], ...}
    ]
Optional per rule: "enabled" (expression; the rule is skipped when it is 0) and "level": "error" (default) or
"warn". Errors block export in the web editor; warnings are only shown.
A side is a part name, {"part", "only": [node names], "skip": [node names]}, a line of sight {"sight": ...}
(a thin cylinder between two frame origins, shortened by `stop_before` at the far end and 1 mm at the near end),
a check-only solid {"csg": node, "frame": F} (e.g. screw heads, a driver's access column),
or a list of these (their union). A rule fails when the overlap volume exceeds `tol_mm3` (default 1 mm³).
Rules whose parts or frames are switched off (see options.py) are skipped.

This module is pure Python: `jobs` only selects resolved CSG trees. Any backend that can build a resolved tree
(mesh.py with manifold3d, or manifold-3d in the browser) intersects them; `run` does it with mesh.py.
"""

from . import geom as G
from .expr import evaluate


def _find(rnode, name):
    if rnode is None:
        return None
    if rnode.get('name') == name:
        return rnode
    for c in rnode.get('children', []):
        f = _find(c, name)
        if f is not None:
            return f
    return None


def _skip(rnode, names):
    if rnode is None or rnode.get('name') in names:
        return None
    if 'children' not in rnode:
        return rnode
    kids = [_skip(c, names) for c in rnode['children']]
    if rnode['type'] == 'difference' and kids and kids[0] is None:
        return None
    kids = [k for k in kids if k is not None]
    return {**rnode, 'children': kids} if kids else None


def _union(nodes, name):
    nodes = [n for n in nodes if n is not None]
    if not nodes:
        return None
    return nodes[0] if len(nodes) == 1 else {'type': 'union', 'name': name, 'children': nodes}


def _side(spec, R, name):
    if isinstance(spec, list):
        sides = [_side(s, R, f'{name}/{i}') for i, s in enumerate(spec)]
        return None if any(s is False for s in sides) else _union(sides, name)
    if isinstance(spec, str):
        spec = {'part': spec}
    if 'csg' in spec:  # a check-only solid, e.g. a screw head or a driver's access column
        from .csg import resolve_tree

        fr = spec.get('frame', R['cfg'].get('root'))
        if fr not in R['world']:
            return False
        return resolve_tree(spec['csg'], R['world'][fr], R['world'], R['P'], name, R['cfg'].get('shapes'))
    if 'sight' in spec:
        s = spec['sight']
        if s['from'] not in R['world'] or s['to'] not in R['world']:
            return False
        a, b = R['world'][s['from']].p, R['world'][s['to']].p
        d = G.unit(G.sub(b, a))
        a = G.add(a, G.mul(d, evaluate(s.get('start_after', 1), R['P'])))
        b = G.sub(b, G.mul(d, evaluate(s.get('stop_before', 0), R['P'])))
        z = G.unit(G.sub(b, a))
        up = [1, 0, 0] if abs(z[0]) < 0.9 else [0, 1, 0]
        y = G.unit(G.cross(z, up))
        x = G.cross(y, z)
        T = G.Tf(G.cols(x, y, z), G.mul(G.add(a, b), 0.5))
        return {
            'type': 'cylinder',
            'name': name,
            'sim': 'none',
            'T': T,
            'r': evaluate(s.get('r', 0.5), R['P']),
            'h': G.norm(G.sub(b, a)),
        }
    part = next((p for p in R['parts'] if p['name'] == spec['part']), None)
    if part is None:
        return False  # part switched off: the rule does not apply
    tree = part['tree']
    if 'only' in spec:
        tree = _union([_find(tree, n) for n in spec['only']], name)
    if 'skip' in spec:
        tree = _skip(tree, set(spec['skip']))
    return tree


def jobs(R):
    """The rules that apply, with both sides as resolved trees: [{id, a, b, tol, level, msg, msg_en}]."""
    out = []
    for i, rule in enumerate(R['cfg'].get('interference', [])):
        rid = rule.get('id', f'rule{i}')
        if 'enabled' in rule and not evaluate(rule['enabled'], R['P']):
            continue
        a, b = _side(rule['a'], R, f'{rid}/a'), _side(rule['b'], R, f'{rid}/b')
        if a is False or b is False or a is None or b is None:
            continue
        out.append(
            {
                'id': rid,
                'a': a,
                'b': b,
                'tol': float(rule.get('tol_mm3', 1.0)),
                'level': rule.get('level', 'error'),
                'msg': rule.get('msg', f'{rid}: overlap'),
                'msg_en': rule.get('msg_en'),
            }
        )
    return out


def message(job, vol, lang=None):
    msg = (lang and job.get(f'msg_{lang}')) or job['msg']
    return f'{msg} ({job["id"]}: {vol:.1f} mm³)'


def run(model, R, lang=None):
    """Evaluate the rules with manifold3d. Returns [(job, overlap_mm3)] for the rules that fail."""
    from . import mesh as MS

    bad = []
    for j in jobs(R):
        a, b = MS.build(j['a'], model.base_dir), MS.build(j['b'], model.base_dir)
        v = MS.mf.Manifold.batch_boolean([a, b], MS.mf.OpType.Intersect).volume()
        if v > j['tol']:
            bad.append((j, v))
    return bad
