"""Checks of the default config and of the config without the flange adapter. Run: uv run pytest"""

import math
import os
import tempfile

from asfinger import Model
from asfinger import geom as G

# The folder that holds configs/ and assets/: asset paths in a config are relative to it.
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'hardware')
CFG = os.path.join(ROOT, 'configs', 'iphone17pro_default.json')
DIRECT = os.path.join(ROOT, 'configs', 'rebot_rs_flange.json')  # same pusher without the flange adapter


def in_mount(w):
    """Frames relative to F_mount (the pusher's own base face), whatever sits between it and the robot flange."""
    Ti = w['F_mount'].inv()
    return {k: Ti * T for k, T in w.items()}


def close(a, b, tol):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_frames_match_fusion():
    w, _, info = Model.load(CFG).frames()
    w = in_mount(w)
    # measured in Fusion (iphone17supporter+tool sketches), converted to the pusher's mount face
    assert close(w['T_tip'].p, [96.33, 0, 163.18], 0.1), w['T_tip'].p
    assert close(G.col(w['R_rod'].R, 2), [0.5, 0, 0.866], 1e-3)
    # optical axis coplanar with the rod and the flange axis, and 55.14 deg from the flange axis
    a = G.mul(G.col(w['C_main'].R, 2), -1)
    assert abs(a[1]) < 1e-9 and abs(w['C_main'].p[1]) < 1e-9
    assert abs(math.degrees(math.acos(a[2])) - 55.14) < 1e-6
    # MagSafe centre: lateral offset vs measured -42.0; in-plane residual is reported, not asserted tightly
    s = w['S_mount'].p
    assert abs(s[1] - (-42.0)) < 1.0, s
    print(
        'S_mount offset vs the current physical connector (mm):',
        [round(x - y, 2) for x, y in zip(s, [-27.27, -42.0, 56.98])],
    )
    assert not info['P_phone']['stale']


def test_param_edit_keeps_camera_on_tcp():
    m = Model.load(CFG).set(rod_L=140, rod_tilt=15, v_n=-0.4)
    w, _, _ = m.frames(resolve=True)
    C, T = w['C_main'], w['T_tcp']
    pc = C.inv().pt(T.p)
    tanY = math.tan(math.radians(56.82) / 2)
    assert abs(pc[0]) < 1e-9
    assert abs(pc[1] / -pc[2] / tanY - (-0.4)) < 2e-3
    assert abs(G.norm(pc) - 163.3) < 1e-6


def test_flange_chain():
    """F_robot (robot flange) -> adapter -> F_mount (pusher base face): height adapter_h, turned by mount_rot."""
    m = Model.load(CFG)
    w, _, _ = m.frames()
    P = m.params()
    assert close(w['F_mount'].p, [0, 0, 9.0], 1e-9) and P['adapter_h'] == 9.0
    assert close(G.col(w['F_mount'].R, 0), [-1, 0, 0], 1e-9)  # mount_rot = 180
    # the reBot sim mounts the tool on link6 at z = 9 mm turned 180 deg about Z: TCP in the link6 frame
    assert close(w['T_tcp'].p, [-100.09, 0, 178.70], 0.01), w['T_tcp'].p
    # mount_rot turns the whole pusher about the flange axis and nothing else
    w2, _, _ = Model.load(CFG).set(mount_rot=30).frames()
    a, b = in_mount(w), in_mount(w2)
    assert all(close(a[k].p, b[k].p, 1e-9) for k in a if k not in ('F_robot', 'F_adapter'))
    r = math.hypot(*w['T_tcp'].p[:2])
    assert close(w2['T_tcp'].p, [r * math.cos(math.radians(30)), r * math.sin(math.radians(30)), w['T_tcp'].p[2]], 1e-9)


def test_adapter_modes():
    """mount_screws: 0 = part B printed with the pusher, 1 = separate part B screwed from below; option off = direct."""
    from asfinger import mesh as MS

    vol = lambda R, n: MS.build(next(p for p in R['parts'] if p['name'] == n)['tree'], ROOT).volume()
    m = Model.load(CFG)
    R = m.resolve()
    assert [p['name'] for p in R['parts']] == ['tool_body', 'holder', 'phone', 'adapter_a']
    m1 = Model.load(CFG).set(mount_screws=1)
    R1 = m1.resolve()
    assert [p['name'] for p in R1['parts']] == ['tool_body', 'holder', 'phone', 'adapter_a', 'adapter_b']
    cup = vol(R, 'tool_body') - vol(R1, 'tool_body')
    assert 15000 < cup < 18000, cup  # the cup of part B, mm^3
    assert abs(vol(R1, 'adapter_b') - cup) < 1500  # the same solid minus 4 screw holes
    assert m.interference(R) == [] and m1.interference(R1) == []
    # the four holes of the base stay on part B's pattern (PCD 38 at 45 deg in F_robot) for any mount_rot
    for rot in (180, 30):
        mm = Model.load(CFG).set(mount_screws=1, mount_rot=rot)
        RR = mm.resolve()
        body = next(p for p in RR['parts'] if p['name'] == 'tool_body')['tree']

        def find(n, name):
            if n.get('name') == name:
                return n
            for c in n.get('children', []):
                f = find(c, name)
                if f:
                    return f

        for k in range(4):
            a = math.radians(45 + 90 * k)
            assert close(find(body, f'hole{k + 1}')['T'].p[:2], [19 * math.cos(a), 19 * math.sin(a)], 1e-9)
    d = Model.load(DIRECT)
    Rd = d.resolve()
    assert [p['name'] for p in Rd['parts']] == ['tool_body', 'holder', 'phone']
    assert 'F_adapter' not in Rd['world'] and close(Rd['world']['F_mount'].p, [0, 0, 0], 1e-12)
    assert d.interference(Rd) == [], d.interference(Rd)  # all four rotor screws reachable
    assert len(d.interference(Rd, level='warn')) == 1  # one of them only with a short key
    bad = Model.load(DIRECT).set(mount_rot=180, beam_x=0)  # the default layout straight on the rotor
    ids = [x.split('(')[-1].split(':')[0] for x in bad.interference(bad.resolve(resolve=True))]
    assert 'screw_access' in ids, ids


def test_direct_config_is_the_default_plus_listed_changes():
    import json

    a, b = json.load(open(CFG, encoding='utf-8')), json.load(open(DIRECT, encoding='utf-8'))
    changed = {k for k in a['params'] if a['params'][k] != b['params'][k]}
    assert changed == {
        'mount_rot',
        'adapter_h',
        'mount_screws',
        'hole_pcd',
        'hole_rot',
        'hole_ang2',
        'hole_d',
        'cbore_depth',
        'relief_h',
        'beam_x',
    }, changed
    assert b['options']['adapter']['value'] is False
    for k in a:
        if k not in ('name', 'description', 'params', 'options', 'mjcf', 'frames'):
            assert a[k] == b[k], k
    strip = lambda F: {n: {k: v for k, v in f.items() if k != 'result'} for n, f in F.items()}
    assert strip(a['frames']) == strip(b['frames'])


def test_beam_clears_counterbores():
    # The beam centre line (in the base plane) keeps clear of the four hole positions of the base.
    m = Model.load(CFG)
    w, _, _ = m.frames()
    P = m.params()
    a = [P['beam_x'], P['beam_y_in']]
    b = [P['beam_x'], w['J_foot'].p[1]]
    for k in range(4):
        ang = math.radians(P['hole_rot'] + 90 * k)
        h = [P['hole_pcd'] / 2 * math.cos(ang), P['hole_pcd'] / 2 * math.sin(ang)]
        d = [b[0] - a[0], b[1] - a[1]]
        t = max(0, min(1, ((h[0] - a[0]) * d[0] + (h[1] - a[1]) * d[1]) / (d[0] ** 2 + d[1] ** 2)))
        dist = math.hypot(a[0] + t * d[0] - h[0], a[1] + t * d[1] - h[1])
        assert dist > P['beam_w'] / 2 + P['cbore_d'] / 2, (k, dist)


def test_tcp_is_hemisphere_apex_and_golden():
    m = Model.load(CFG)
    w, _, _ = m.frames()
    P = m.params()
    tip, tcp = w['T_tip'], w['T_tcp']
    assert abs(G.norm(G.sub(tcp.p, tip.p)) - P['tip_R']) < 1e-9
    assert abs(P['v_n'] - (1 - 2 * 0.618)) < 1e-12


def test_checks_catch_phone_below_flange():
    assert Model.load(CFG).check() == []
    m = Model.load(CFG).set(rod_L=150)
    assert m.check(m.resolve(resolve=True)), 'rod_L=150 at 55 deg puts the spine below the flange face'


def test_build_and_mujoco():
    out = tempfile.mkdtemp()
    R, rep = Model.load(CFG).build(out)
    assert rep['parts']['tool_body']['volume_cm3'] > 50
    ps = rep['print_sets']['ipush_print']  # rod body + phone holder must print as ONE solid
    assert ps['bodies'] == 1, ps
    try:
        import mujoco
    except ImportError:
        print('mujoco not installed, skipped')
        return
    m = mujoco.MjModel.from_xml_path(os.path.join(out, 'ipush_tool.xml'))
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    cid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_CAMERA, 'C_main')
    sid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, 'T_tcp')
    pc = d.cam_xmat[cid].reshape(3, 3).T @ (d.site_xpos[sid] - d.cam_xpos[cid])
    t = math.tan(math.radians(m.cam_fovy[cid]) / 2)
    u, v = pc[0] / -pc[2] / (t * 4 / 3), pc[1] / -pc[2] / t
    assert abs(u) < 1e-4 and abs(v - (1 - 2 * 0.618)) < 1e-4, (u, v)
    print('MuJoCo: TCP image coords', round(u, 5), round(v, 5), 'mass g', round(m.body_mass[1] * 1000, 1))


def test_phone_option_off_leaves_rod_only():
    m = Model.load(CFG).set_options(phone=False)
    R = m.resolve(resolve=True)
    names = [p['name'] for p in R['parts']]
    assert names == ['tool_body', 'adapter_a'], names
    for f in ('P_phone', 'C_main', 'S_mount', 'J_foot', 'J_bend'):
        assert f not in R['world'], f
    assert 'T_tcp' in R['world'] and m.check(R) == []
    full = Model.load(CFG).resolve()
    assert close(R['world']['T_tcp'].p, full['world']['T_tcp'].p, 1e-9)  # the rod itself does not move
    rj = m.resolved_json(R)
    assert rj['cameras'] == {} and rj['options'] == {'adapter': True, 'phone': False}
    out = tempfile.mkdtemp()
    _, rep = m.build(out)
    assert (
        rep['print_sets']['ipush_print']['members'] == ['tool_body'] and rep['print_sets']['ipush_print']['bodies'] == 1
    )
    _, rep_full = Model.load(CFG).build(tempfile.mkdtemp(), mjcf=False, preview=False)
    assert rep['parts']['tool_body']['volume_cm3'] < rep_full['parts']['tool_body']['volume_cm3']  # no beam/spine
    assert m.cfg['frames']['P_phone'] and 'holder' in [p['name'] for p in m.cfg['parts']]  # full config kept


def test_interference_rules():
    assert Model.load(CFG).interference() == [], 'default must be free of overlaps'

    def ids(**kw):
        m = Model.load(CFG).set(**kw)
        return [x.split('(')[-1].split(':')[0] for x in m.interference(m.resolve(resolve=True))]

    assert ids(rod_tilt=40) == ['phone_vs_body'], 'rod tilted into the phone'
    assert ids(back_to_mount=0) == ['phone_vs_holder']
    assert 'sight_to_tip' in ids(v_n=0.6)
    m = Model.load(CFG).set_options(phone=False)
    assert m.interference() == [], 'rules on switched-off parts are skipped'


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
