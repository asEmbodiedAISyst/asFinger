"""asfinger: one parametric description (params + frame tree + CSG trees bound to frames) -> preview, STL, MJCF.

from asfinger import Model
m = Model.load('hardware/configs/iphone17pro_default.json')
m.set(rod_L=150, rod_tilt=20)          # programmatic edits
m.set_options(phone=False)             # optional modules (see options.py): the rod without phone and holder
m.build('out/my_tool')                 # resolved.json, print/*.stl, meshes/*.stl, ipush_tool.xml, preview.html
"""

import copy
import json
import os

from . import geom
from . import interference as _interf
from .csg import resolve_parts, to_json
from .expr import resolve_params
from .frames import resolve_frames
from .options import effective_cfg, option_values

__all__ = ['Model', 'PRODUCT_NAME', 'geom']

# The name shown to people (preview title, command line). File and frame names inside the outputs do not use it.
PRODUCT_NAME = 'asFinger'


class Model:
    def __init__(self, cfg, base_dir='.'):
        self.cfg = cfg
        self.base_dir = base_dir
        self.log = print

    @classmethod
    def load(cls, path):
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
        # asset paths ("file": "assets/...") are relative to the parent of the config's folder: the folder that
        # holds configs/ and assets/ side by side (hardware/ in this repository)
        base = os.path.dirname(os.path.dirname(os.path.abspath(path)))
        return cls(cfg, base)

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.cfg, f, indent=2, ensure_ascii=False)

    def copy(self):
        return Model(copy.deepcopy(self.cfg), self.base_dir)

    def set(self, **params):
        for k, v in params.items():
            if k not in self.cfg['params']:
                raise KeyError(f'unknown parameter {k}')
            self.cfg['params'][k] = v
        return self

    def set_options(self, **values):
        """Switch optional modules on/off, e.g. set_options(phone=False). The full config is kept."""
        for k, v in values.items():
            if k not in self.cfg.get('options', {}):
                raise KeyError(f'unknown option {k}')
            self.cfg['options'][k]['value'] = bool(v)
        return self

    def root_to(self, frame, R=None):
        """Pose of `frame` in the root frame (F_robot), e.g. root_to('T_tcp') = the TCP offset to enter on the robot."""
        return (R or self.resolve())['world'][frame]

    def options(self):
        return option_values(self.cfg)

    def view(self):
        """The config as evaluated: with switched-off modules pruned (shares frame dicts with self.cfg)."""
        return effective_cfg(self.cfg)

    # ------------------------------------------------------------ evaluation
    def params(self):
        return resolve_params(self.cfg['params'])

    def frames(self, resolve=False):
        P = self.params()
        return resolve_frames(self.view(), P, resolve=resolve, log=self.log)

    def resolve(self, resolve=False):
        """Evaluate everything. Returns a dict with params, frames (world+local), parts (resolved trees)."""
        P = self.params()
        v = self.view()
        world, local, info = resolve_frames(v, P, resolve=resolve, log=self.log)
        parts = resolve_parts(v, P, world)
        return {'P': P, 'world': world, 'local': local, 'info': info, 'parts': parts, 'cfg': v}

    def resolved_json(self, R=None):
        R = R or self.resolve()
        fr = {}
        for n, T in R['world'].items():
            f = self.cfg['frames'][n]
            fr[n] = {
                'parent': f.get('parent'),
                'module': f.get('module'),
                'desc': f.get('desc', ''),
                'world': T.to_json(10, 12),
                'local': R['local'][n].to_json(10, 12),
                **R['info'].get(n, {}),
            }
        parts = []
        for p in R['parts']:
            q = {k: v for k, v in p.items() if k not in ('tree', 'collision_leaves')}
            q['tree'] = to_json(p['tree'])
            q['collision'] = [to_json(l) for l in p['collision_leaves']]
            parts.append(q)
        cams = {}
        for c, spec in R['cfg'].get('cameras', {}).items():
            from .expr import evaluate

            cams[c] = {
                'fovy_deg': evaluate(spec['fovy_deg'], R['P']),
                'aspect': evaluate(spec.get('aspect', 4 / 3), R['P']),
                'resolution': spec.get('resolution', [640, 480]),
            }
        whole = {id(p['tree']): p['name'] for p in R['parts']}  # a side that is a whole part is sent by name

        def side(t):
            if id(t) in whole:
                return {'ref': whole[id(t)]}
            if t.get('type') == 'union' and any(id(c) in whole for c in t['children']):
                return {'type': 'union', 'name': t['name'], 'children': [side(c) for c in t['children']]}
            return to_json(t)

        interf = [
            {
                'id': j['id'],
                'a': side(j['a']),
                'b': side(j['b']),
                'tol': j['tol'],
                'level': j['level'],
                'msg': j['msg'],
                'msg_en': j['msg_en'],
            }
            for j in _interf.jobs(R)
        ]
        return {
            'name': self.cfg.get('name'),
            'units': 'mm',
            'base_dir': os.path.abspath(self.base_dir),
            'root': self.cfg.get('root'),
            'params': R['P'],
            'param_exprs': {k: v for k, v in self.cfg.get('params', {}).items() if isinstance(v, str)},
            'options': self.options(),
            'dropped_frames': R['cfg'].get('dropped_frames', []),
            'frames': fr,
            'cameras': cams,
            'parts': parts,
            'interference': interf,
        }

    def check(self, R=None, lang=None):
        """Evaluate the config's "checks" (geometric sanity limits). Returns a list of messages; empty = OK.
            "checks": [{"frame": "J_foot", "axis": "z", "min": "plate_t", "msg": "...", "msg_en": "..."}]
        `lang` picks "msg_<lang>" when the check has one (the web editor passes "en" or "zh"); default is "msg"."""
        from .expr import evaluate

        R = R or self.resolve()
        out = []
        for c in R['cfg'].get('checks', []):
            T = R['world'][c['frame']]
            v = T.p['xyz'.index(c.get('axis', 'z'))]
            lo = evaluate(c['min'], R['P']) if 'min' in c else None
            hi = evaluate(c['max'], R['P']) if 'max' in c else None
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                rng = f'{"" if lo is None else round(lo, 2)} .. {"" if hi is None else round(hi, 2)}'
                msg = (lang and c.get(f'msg_{lang}')) or c.get('msg', 'check failed')
                out.append(f'{msg} ({c["frame"]}.{c.get("axis", "z")} = {v:.2f}, allowed {rng})')
        return out

    def interference(self, R=None, lang=None, level='error'):
        """Overlaps between solids that must stay apart (config "interference"; needs manifold3d). Messages; empty = OK.
        `level` picks the rules: 'error' (default: things that cannot be built), 'warn' (inconvenient, e.g. a flange
        screw that needs a short key instead of a straight driver) or None for both."""
        R = R or self.resolve()
        return [_interf.message(j, v, lang) for j, v in _interf.run(self, R) if level is None or j['level'] == level]

    def build(self, out_dir, resolve=False, stl=True, mjcf=True, preview=True):
        from .build import build_all

        return build_all(self, out_dir, resolve=resolve, stl=stl, mjcf=mjcf, preview=preview)
