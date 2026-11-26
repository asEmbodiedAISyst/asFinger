"""Frame tree: resolve every frame to a pose in the root frame, running solvers where a frame asks for one.

A frame entry in the config:
    "R_rod": {"parent": "F_tool", "pos": ["rod_x", 0, 0], "rot": {"axis": [0, 1, 0], "deg": "rod_tilt"},
              "module": "rod", "desc": "..."}
Rotation forms (`rot` may also be a list, applied left to right as intrinsic rotations):
    {"quat": [w, x, y, z]}  (MuJoCo order)     {"mat": [r00, r01, r02, r10, ..., r22]}  (row-major)
    {"axis": [x, y, z], "deg": e}  (handy when an angle is a parameter)     {"xyaxes": [x0, x1, x2, y0, y1, y2]}
A solved frame carries `solve` (the design intent) and, after `--resolve`, `result` (the saved pose):
    "P_phone": {"parent": "F_tool", "solve": {...}, "result": {"pos": [...], "quat": [...], "solve_hash": "..."}}
Generation always uses `result` when present. A stale result (hash mismatch) is reported, never silently replaced.
Frames with neither `solve` nor `result` are fixed offsets (source "module" or "manual").
"""

import hashlib
import json
import math

from . import geom as G
from .expr import ev_vec, evaluate


def rot_from_spec(spec, P):
    if spec is None:
        return G.I3
    if isinstance(spec, list):
        R = G.I3
        for s in spec:
            R = G.mm(R, rot_from_spec(s, P))
        return R
    if 'axis' in spec:
        return G.axang(ev_vec(spec['axis'], P), evaluate(spec['deg'], P))
    if 'xyaxes' in spec:
        v = ev_vec(spec['xyaxes'], P, 6)
        return G.from_xyaxes(v[:3], v[3:])
    if 'mat' in spec:  # 3x3 rotation matrix, row-major, columns = child axes in the parent frame
        v = ev_vec(spec['mat'], P, 9)
        return G.from_xyaxes([v[0], v[3], v[6]], [v[1], v[4], v[7]])
    if 'quat' in spec:
        return G.quat_to_R(ev_vec(spec['quat'], P, 4))
    raise ValueError(f'unknown rotation spec {spec!r}')


def local_tf(fr, P):
    return G.Tf(rot_from_spec(fr.get('rot'), P), ev_vec(fr.get('pos', [0, 0, 0]), P))


def _pos_from(fr, P, world):
    """Origin taken from a point defined in another frame (optionally slid along a direction until it reaches a
    plane z = value of some frame), expressed in this frame's parent. `use` picks which coordinates come from that
    point; the others come from `pos`.
        "pos_from": {"frame": "S_mount", "pos": [0, 0, -5], "dir": [-1, 0, 0],
                     "until": {"frame": "F_tool", "axis": "x", "value": 0}, "use": "xyz"}
    (`until` = the plane where that frame's x/y/z coordinate equals `value`; {"z": e} is shorthand for axis z.)
    """
    pf = fr['pos_from']
    Tsrc = world[pf['frame']]
    p = Tsrc.pt(ev_vec(pf.get('pos', [0, 0, 0]), P))
    if 'until' in pf:
        u = pf['until']
        Tpl = world[u['frame']]
        d = Tsrc.vec(ev_vec(pf['dir'], P))
        ax = u.get('axis', 'z')
        n = G.col(Tpl.R, 'xyz'.index(ax))
        z0 = evaluate(u[ax] if ax in u else u['value'], P)
        den = G.dot(n, d)
        if abs(den) < 1e-9:
            raise ValueError('pos_from: direction is parallel to the target plane')
        t = (z0 - G.dot(n, G.sub(p, Tpl.p))) / den
        p = G.add(p, G.mul(d, t))
    q = world[fr['parent']].inv().pt(p)
    base = ev_vec(fr.get('pos', [0, 0, 0]), P)
    use = pf.get('use', 'xyz')
    return [q[i] if 'xyz'[i] in use else base[i] for i in range(3)]


def _dir(spec, P, world, parent_inv):
    return parent_inv.vec(world[spec['frame']].vec(ev_vec(spec['dir'], P)))


def _rot_from_dirs(fr, P, world):
    """Orientation from directions defined in other frames (expressed in this frame's parent):
        "z_from": [{"frame": "F_tool", "dir": [0, 0, 1]}, {"frame": "S_mount", "dir": [1, 0, 0]}],   # z = unit(sum)
        "x_hint": {"frame": "F_tool", "dir": [0, 1, 0]}                                              # x as close as possible
    Two unit directions summed give the bisector, e.g. the normal of a mitre plane between two members."""
    Pi = world[fr['parent']].inv()
    z = [0.0, 0.0, 0.0]
    for d in fr['z_from']:
        z = G.add(z, G.unit(_dir(d, P, world, Pi)))
    z = G.unit(z)
    xh = _dir(fr['x_hint'], P, world, Pi) if 'x_hint' in fr else [1.0, 0.0, 0.0]
    if abs(G.dot(G.unit(xh), z)) > 0.999:
        xh = [0.0, 1.0, 0.0] if abs(z[1]) < 0.9 else [1.0, 0.0, 0.0]
    x = G.unit(G.sub(xh, G.mul(z, G.dot(xh, z))))
    return G.cols(x, G.cross(z, x), z)


def topo_order(frames):
    order, seen = [], set()

    def visit(n, stack=()):
        if n in seen:
            return
        if n in stack:
            raise ValueError(f'frame cycle at {n}')
        fr = frames[n]
        deps = [fr['parent']] if fr.get('parent') else []
        sv = fr.get('solve')
        if sv:
            deps += [sv.get('target'), sv.get('axis_frame')]
        pf = fr.get('pos_from')
        if pf:
            deps += [pf.get('frame'), (pf.get('until') or {}).get('frame')]
        deps += [d.get('frame') for d in fr.get('z_from', [])] + [(fr.get('x_hint') or {}).get('frame')]
        for d in deps:
            if d:
                if d not in frames:
                    raise ValueError(f'frame {n} refers to unknown frame {d}')
                visit(d, stack + (n,))
        seen.add(n)
        order.append(n)

    for n in frames:
        visit(n)
    return order


def children_of(frames, name):
    return [k for k, v in frames.items() if v.get('parent') == name]


# ---------------------------------------------------------------- solvers
def _camera_intrinsics(cfg, cam, P):
    c = cfg.get('cameras', {}).get(cam)
    if c is None:
        raise ValueError(f'camera {cam} has no entry in "cameras"')
    fovy = evaluate(c['fovy_deg'], P)
    return {
        'fovy_deg': fovy,
        'tanY': math.tan(math.radians(fovy) / 2),
        'aspect': evaluate(c.get('aspect', 4 / 3), P),
        'min_focus_mm': None if c.get('min_focus_mm') is None else evaluate(c['min_focus_mm'], P),
    }


def solve_coplanar_look_at(name, fr, cfg, P, world):
    """Pose of a phone frame such that
      * the camera optical axis lies in the plane spanned by the parent's Z axis (flange axis) and the rod axis
        (Z of `axis_frame`), through the rod axis;
      * the phone plane makes `plane_angle_deg` with the parent's XY plane (flange face),
        i.e. the optical axis makes that angle with the flange axis, tilted toward the rod side when positive;
      * the image is landscape-or-portrait as fixed by the camera's pose in the phone frame,
        with image-up in that plane (`image_up`: toward_flange | away_from_flange);
      * the target frame origin projects to normalized image coordinate (0, v_n);
      * the lens is `distance_mm` from the target.
    Returns the frame's pose relative to its parent and the inputs used (for hashing / reporting).
    """
    sv = fr['solve']
    frames = cfg['frames']
    parent = fr['parent']
    T_wpar = world[parent]
    T_par_w = T_wpar.inv()
    tgt = T_par_w * world[sv['target']]
    axf = T_par_w * world[sv.get('axis_frame', 'R_rod')]
    cam = sv['camera']
    if frames.get(cam, {}).get('parent') != name:
        raise ValueError(f'solve of {name}: camera {cam} must be a direct child of {name}')
    T_PC = local_tf(frames[cam], P)
    K = _camera_intrinsics(cfg, cam, P)
    beta = evaluate(sv['plane_angle_deg'], P)
    v_n = evaluate(sv.get('v_n', 0), P)
    dist = evaluate(sv['distance_mm'], P)
    up_rule = sv.get('image_up', 'toward_flange')

    z = [0.0, 0.0, 1.0]
    r = G.col(axf.R, 2)  # rod direction, pointing to the tip
    n = G.cross(z, r)
    if G.norm(n) < 1e-9:  # rod parallel to the flange axis: plane from an azimuth
        az = math.radians(evaluate(sv.get('plane_azimuth_deg', 0), P))
        n = [-math.sin(az), math.cos(az), 0.0]
    n = G.unit(n)
    a = G.mv(G.axang(n, beta), z)  # viewing direction
    h = G.mul(r, -1) if up_rule == 'toward_flange' else r
    yc = G.sub(h, G.mul(a, G.dot(h, a)))
    if G.norm(yc) < 1e-9:
        raise ValueError(f'solve of {name}: viewing direction is parallel to the rod, image up undefined')
    yc = G.unit(yc)
    zc = G.mul(a, -1)
    xc = G.cross(yc, zc)
    R_C = G.cols(xc, yc, zc)
    d_cam = G.unit([0.0, v_n * K['tanY'], -1.0])
    d = G.mv(R_C, d_cam)
    c = G.sub(tgt.p, G.mul(d, dist))
    T_parC = G.Tf(R_C, c)
    T_parP = T_parC * T_PC.inv()
    inputs = {
        'type': 'coplanar_look_at',
        'target': sv['target'],
        'camera': cam,
        'plane_angle_deg': beta,
        'v_n': v_n,
        'distance_mm': dist,
        'image_up': up_rule,
        'target_pose': tgt.to_json(4),
        'axis_pose': axf.to_json(4),
        'T_PC': T_PC.to_json(4),
        'fovy_deg': round(K['fovy_deg'], 6),
    }
    report = {
        'axis_to_rod_deg': math.degrees(math.acos(max(-1, min(1, G.dot(a, r))))),
        'min_focus_ok': None if K['min_focus_mm'] is None else dist >= K['min_focus_mm'],
    }
    return T_parP, inputs, report


SOLVERS = {'coplanar_look_at': solve_coplanar_look_at}


def solve_hash(inputs):
    return hashlib.sha1(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:12]


def resolve_frames(cfg, P, resolve=False, log=print):
    """Return (world, local, info). world/local: name -> Tf (world = root frame = the frame with no parent).
    If resolve=True, solved frames are re-solved and their `result` written back into cfg."""
    frames = cfg['frames']
    world, local, info = {}, {}, {}
    for name in topo_order(frames):
        fr = frames[name]
        src = 'module' if fr.get('source') != 'manual' else 'manual'
        if fr.get('parent') is None:
            T = G.Tf()
        elif 'solve' in fr:
            kind = fr['solve']['type']
            T_new, inputs, rep = SOLVERS[kind](name, fr, cfg, P, world)
            h = solve_hash(inputs)
            res = fr.get('result')
            stale = res is not None and res.get('solve_hash') != h
            if res is None or resolve:
                T = T_new
                fr['result'] = dict(T.to_json(), solve_hash=h)
            else:
                T = G.Tf.from_json(res)
                if stale:
                    log(f'[warn] {name}: saved result is stale (inputs changed); run with --resolve to update')
            src = 'solved'
            info[name] = {'solve_hash': h, 'stale': bool(stale and not resolve), **rep}
            if rep.get('min_focus_ok') is False:
                log(f'[warn] {name}: distance is below the camera minimum focus distance')
        else:
            T = local_tf(fr, P)
            if 'pos_from' in fr:
                T = G.Tf(T.R, _pos_from(fr, P, world))
            if 'z_from' in fr:
                T = G.Tf(_rot_from_dirs(fr, P, world), T.p)
        local[name] = T
        world[name] = T if fr.get('parent') is None else world[fr['parent']] * T
        info.setdefault(name, {})['source'] = src
    return world, local, info
