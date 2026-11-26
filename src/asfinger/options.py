"""Optional modules: switch whole groups of frames and geometry off without editing the frame tree or the CSG.

A config may declare
    "options": {
      "phone": {"value": true, "modules": ["phone", "holder", "connector"],
                "desc": "Phone camera with its holder. Off = the rod alone; the camera solve is skipped."}
    }
and `Model.set_options(phone=False)` (or the config value) turns it off. `effective_cfg` then returns a pruned view:

  * frames of those modules are dropped, then (repeatedly) every frame whose parent, `pos_from`, `z_from`,
    `x_hint` or `solve` refers to a dropped frame, so solvers of dropped frames never run;
  * CSG leaves that refer to a dropped frame (own `frame` or a point {"frame": ...}) are dropped; a union keeps what
    is left, a difference whose base is gone is dropped, a cut that is gone is simply not subtracted;
  * parts left empty, cameras, checks and references on dropped frames, and print-set members that are gone
    are dropped too.

The view shares the frame dicts with the full config, so `--resolve` still writes solved results into it.
The full config (with every module) is what gets saved and exported.
"""

LEAVES = ('box', 'sphere', 'cylinder', 'mesh')


def option_values(cfg):
    return {k: bool(v.get('value', True)) for k, v in cfg.get('options', {}).items()}


def _frame_refs(obj):
    """Every frame name referred to anywhere inside obj (dicts with a 'frame' key, solve targets)."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('frame', 'target', 'axis_frame', 'camera') and isinstance(v, str):
                out.add(v)
            else:
                out |= _frame_refs(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _frame_refs(v)
    return out


def dropped_frames(cfg):
    off = {m for k, o in cfg.get('options', {}).items() if not o.get('value', True) for m in o.get('modules', [])}
    if not off:
        return set()
    frames = cfg['frames']
    gone = {n for n, f in frames.items() if f.get('module') in off}
    changed = True
    while changed:
        changed = False
        for n, f in frames.items():
            if n in gone:
                continue
            refs = {f.get('parent')} | _frame_refs(
                {k: f[k] for k in ('pos_from', 'z_from', 'x_hint', 'solve') if k in f}
            )
            if refs & gone:
                gone.add(n)
                changed = True
    return gone


def _prune(node, gone, shapes=None):
    """The CSG node without anything that refers to a dropped frame; None if nothing is left."""
    if any(k in node for k in LEAVES):
        return None if _frame_refs(node) & gone else node
    if node.get('frame') in gone:
        return None
    if 'use' in node:  # a shared shape goes as a whole when anything in it is gone
        return None if _frame_refs((shapes or {}).get(node['use'], {})) & gone else node
    if 'union' in node:
        kids = [c for c in (_prune(c, gone, shapes) for c in node['union']) if c is not None]
        return {**node, 'union': kids} if kids else None
    if 'difference' in node:
        base, *cuts = node['difference']
        base = _prune(base, gone, shapes)
        if base is None:
            return None
        return {**node, 'difference': [base] + [c for c in (_prune(c, gone, shapes) for c in cuts) if c is not None]}
    return node


def effective_cfg(cfg):
    gone = dropped_frames(cfg)
    if not gone:
        return cfg
    v = dict(cfg)
    v['frames'] = {n: f for n, f in cfg['frames'].items() if n not in gone}  # same dicts: solve results write through
    parts = []
    for p in cfg['parts']:
        if p['frame'] in gone:
            continue
        csg = _prune(p['csg'], gone, cfg.get('shapes'))
        if csg is None:
            continue
        q = {**p, 'csg': csg}
        if 'collision' in p:
            q['collision'] = [c for c in (_prune(c, gone, cfg.get('shapes')) for c in p['collision']) if c is not None]
        parts.append(q)
    v['parts'] = parts
    names = {p['name'] for p in parts}
    v['cameras'] = {c: s for c, s in cfg.get('cameras', {}).items() if c not in gone}
    v['checks'] = [c for c in cfg.get('checks', []) if c['frame'] not in gone]
    v['references'] = [r for r in cfg.get('references', []) if r['frame'] not in gone]
    v['print_sets'] = {k: [m for m in ms if m in names] for k, ms in cfg.get('print_sets', {}).items()}
    v['print_sets'] = {k: ms for k, ms in v['print_sets'].items() if ms}
    v['dropped_frames'] = sorted(gone)
    return v
