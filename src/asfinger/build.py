"""Build all outputs for a model: resolved.json, STL per part, MJCF, HTML preview."""

import json
import os

import numpy as np

from . import PRODUCT_NAME
from . import geom as G
from . import mesh as MS
from .expr import ev_vec
from .frames import rot_from_spec
from .mjcf import body_frame, write_mjcf
from .preview import write_preview


def build_all(model, out_dir, resolve=False, stl=True, mjcf=True, preview=True):
    os.makedirs(out_dir, exist_ok=True)
    R = model.resolve(resolve=resolve)
    rj = model.resolved_json(R)
    report = {'parts': {}}

    meshes, manis = {}, {}
    for p in R['parts']:
        raw = MS.build(p['tree'], model.base_dir)
        manis[p['name']] = raw
        m = MS.clean(raw)
        V, F = MS.to_arrays(m)
        meshes[p['name']] = (V, F)
        report['parts'][p['name']] = {
            'volume_cm3': round(m.volume() / 1000, 3),
            'mass_g': round(m.volume() / 1000 * float(p.get('density', 1.0)), 1),
            'triangles': int(len(F)),
            'role': p.get('role'),
        }
    with open(os.path.join(out_dir, 'resolved.json'), 'w', encoding='utf-8') as f:
        json.dump(rj, f, indent=1, ensure_ascii=False)

    files = {}
    if stl:
        for p in R['parts']:
            V, F = meshes[p['name']]
            # printable STL in the part's own frame; mesh used by MJCF/preview stays in the root frame
            T = R['world'][p['frame']]
            if p.get('role') == 'printed':
                MS.write_stl(
                    os.path.join(out_dir, 'print', f'{p["name"]}.stl'), MS.transform_arrays(V, T), F, p['name']
                )
            # meshes/ feeds the MJCF: in the MJCF body frame (the root frame unless "mjcf": {"frame": ...})
            Tb = body_frame(R)[1]
            MS.write_stl(os.path.join(out_dir, 'meshes', f'{p["name"]}.stl'), MS.transform_arrays(V, Tb), F, p['name'])
            files[p['name']] = f'meshes/{p["name"]}.stl'
        # print sets: several printed parts fused into one body, written in the frame of the first member
        # (the pusher's mount face on z = 0, whatever adapter sits under it)
        for name, members in R['cfg'].get('print_sets', {}).items():
            u = MS.clean(MS.mf.Manifold.batch_boolean([manis[n] for n in members], MS.mf.OpType.Add))
            V, F = MS.to_arrays(u)
            Tm = R['world'][next(p['frame'] for p in R['parts'] if p['name'] == members[0])]
            MS.write_stl(os.path.join(out_dir, 'print', f'{name}.stl'), MS.transform_arrays(V, Tm), F, name)
            report.setdefault('print_sets', {})[name] = {
                'members': members,
                'volume_cm3': round(u.volume() / 1000, 3),
                'bodies': len(u.decompose()),
                'triangles': int(len(F)),
            }
    if mjcf:
        fname, Tb = body_frame(R)
        inc = [p for p in R['parts'] if p.get('mjcf') is not False]
        props = [
            MS.mass_properties(
                MS.transform_arrays(meshes[p['name']][0], Tb), meshes[p['name']][1], float(p.get('density', 1.0))
            )
            for p in inc
        ]
        M, com, I = MS.combine_mass(props)
        report['total'] = {
            'mass_g': round(M * 1000, 1),
            'com_mm': [round(x, 2) for x in com],
            'frame': fname,
            'parts': [p['name'] for p in inc],
        }
        write_mjcf(
            model,
            R,
            os.path.join(out_dir, 'ipush_tool.xml'),
            {p['name']: files.get(p['name']) for p in inc},
            inertial=(M, com, I.tolist()),
        )
    if preview:
        refs = []
        for r in R['cfg'].get('references', []):
            V, F = MS.read_stl(os.path.join(model.base_dir, r['file']))
            T = R['world'][r['frame']] * G.Tf(
                rot_from_spec(r.get('rot'), R['P']), ev_vec(r.get('pos', [0, 0, 0]), R['P'])
            )
            V = V @ np.array(T.R).T + np.array(T.p)
            refs.append((r['name'], V, F))
        write_preview(
            os.path.join(out_dir, 'preview.html'), rj, meshes, refs, title=f'{PRODUCT_NAME} · {model.cfg.get("name")}'
        )
    report['interference'] = model.interference(R)
    report['warnings'] = model.interference(R, level='warn')
    with open(os.path.join(out_dir, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=1)
    return R, report
