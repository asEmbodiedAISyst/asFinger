"""MJCF backend.

* collision: the positive-side primitives of every part (or the part's `collision` override), group 3, hidden by default
* visual:    one mesh per part (full CSG result), contype=conaffinity=0, group 1
* inertial:  exact mass / COM / inertia of all parts, computed from the CSG meshes, written as one <inertial>
* sites:     one per frame;  camera: one per entry in `cameras`, at its frame (same convention as MuJoCo)
Everything sits in one body named `ipush`. Its frame is the root frame (F_robot, the robot flange) unless the config
says otherwise:
    "mjcf": {"frame": "F_mount"}      # write everything relative to this frame instead
and a part with "mjcf": false is left out (geometry and mass). Use both when the robot model already contains the
flange adapter: the reBot URDF's link6 is the gripper connector, so the default config exports the pusher alone,
relative to the connector's tool face. Attach the body with mjSpec (`spec.attach`) or by including the file;
geometry is written in metres.
"""

import os
from xml.sax.saxutils import quoteattr

M = 0.001


def _f(v, nd=6):
    return ' '.join(f'{x:.{nd}g}' for x in v)


def _pose_in(T):
    return f'pos="{_f([x * M for x in T.p])}" quat="{_f(T.quat(), 8)}"'


def _geom_attrs(leaf):
    t = leaf['type']
    if t == 'box':
        return f'type="box" size="{_f([s * M / 2 for s in leaf["size"]])}"'
    if t == 'sphere':
        return f'type="sphere" size="{leaf["r"] * M:.6g}"'
    if t == 'cylinder':
        return f'type="cylinder" size="{leaf["r"] * M:.6g} {leaf["h"] * M / 2:.6g}"'
    raise ValueError(t)


def _rgba(hexcol, a=1.0):
    h = (hexcol or '#999999').lstrip('#')
    return f'{int(h[0:2], 16) / 255:.3f} {int(h[2:4], 16) / 255:.3f} {int(h[4:6], 16) / 255:.3f} {a}'


def body_frame(R):
    """(name, Tf root -> body frame) of the frame the MJCF body is written in."""
    name = R['cfg'].get('mjcf', {}).get('frame') or R['cfg'].get('root')
    if name not in R['world']:
        name = R['cfg'].get('root')
    return name, R['world'][name]


def write_mjcf(model, R, path, mesh_files, prefix='', inertial=None):
    """mesh_files: part name -> mesh path relative to the xml (or None to skip the visual mesh); meshes must be
    in the body frame (see body_frame)."""
    cams = R['cfg'].get('cameras', {})
    from .expr import evaluate

    Ti = body_frame(R)[1].inv()
    _pose = lambda T: _pose_in(Ti * T)
    L = []
    L.append(f'<mujoco model={quoteattr(model.cfg.get("name", "ipush"))}>')
    L.append('  <compiler angle="radian" meshdir="."/>')
    L.append('  <default>')
    L.append('    <default class="ipush_col"><geom group="3" rgba="0.9 0.4 0.2 0.4" density="0"/></default>')
    L.append('    <default class="ipush_vis"><geom group="1" contype="0" conaffinity="0"/></default>')
    L.append('  </default>')
    L.append('  <asset>')
    for name, f in mesh_files.items():
        if f:
            L.append(f'    <mesh name="{prefix}{name}" file="{f}" scale="{M} {M} {M}"/>')
    L.append('  </asset>')
    L.append('  <worldbody>')
    L.append(f'    <body name="{prefix}ipush">')
    if inertial:
        m, com, I = inertial
        L.append(
            f'      <inertial pos="{_f([x * M for x in com])}" mass="{m:.6g}" '
            f'fullinertia="{I[0][0]:.6g} {I[1][1]:.6g} {I[2][2]:.6g} {I[0][1]:.6g} {I[0][2]:.6g} {I[1][2]:.6g}"/>'
        )
    for p in R['parts']:
        if p.get('mjcf') is False:
            continue
        dens = float(p.get('density', 1.0)) * 1000  # g/cm3 -> kg/m3
        for i, leaf in enumerate(p['collision_leaves']):
            L.append(
                f'      <geom name="{prefix}{p["name"]}_c{i}" class="ipush_col" {_geom_attrs(leaf)} {_pose(leaf["T"])}/>'
            )
        if mesh_files.get(p['name']):
            L.append(
                f'      <geom name="{prefix}{p["name"]}" class="ipush_vis" type="mesh" mesh="{prefix}{p["name"]}" '
                f'density="{0 if inertial else dens:.6g}" rgba="{_rgba(p.get("color"))}"/>'
            )
    for n, T in R['world'].items():
        L.append(f'      <site name="{prefix}{n}" {_pose(T)} size="0.002"/>')
    for c, spec in cams.items():
        fovy = evaluate(spec['fovy_deg'], R['P'])
        res = spec.get('resolution', [640, 480])
        L.append(
            f'      <camera name="{prefix}{c}" {_pose(R["world"][c])} fovy="{fovy:.6g}" resolution="{res[0]} {res[1]}"/>'
        )
    L.append('    </body>')
    L.append('  </worldbody>')
    L.append('</mujoco>')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    return path
