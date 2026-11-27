"""Bake the robot arm models shown in the editor into one small GLB per arm, posed and in mm.

    python scripts/bake-arms.py --menagerie /path/to/mujoco_menagerie --rebot /path/to/rebot.xml

Each arm is loaded with MuJoCo, put in a fixed pose, and its visual meshes are transformed into the base frame,
merged by material, reduced to the arm's triangle budget (`tris`; the Menagerie arms are kept whole) and written to
public/arms/<id>.glb. With --gltf-transform the GLB is then quantized and meshopt-compressed (about 1/5 of the
size; the editor's loader has the decoder). The flange pose (the robot's own flange frame,
which is the config's F_robot frame) goes to src/data/arms.json together with the pose and the source/licence of the
model. All arms are posed with the flange pitched 30 degrees below horizontal (the "push" pose), so that a tool
mounted with the carrier's default mount_rot looks the same on each of them, and with the pusher base face at the
same height above the arm base (265.4 mm, where the reBot holds it in the pose HOME_QPOS; flange 0.5 m out), so
that the editor can keep the pusher and the ground in place and swap only the arm. The reBot is baked without its gripper connector (link6.STL): the editor draws that as the flange adapter.
The editor then only loads a static GLB; no MuJoCo or URDF parsing happens in the browser.

Needs: mujoco, trimesh, fast-simplification, scipy (or networkx); optionally `npm i @gltf-transform/cli`.
"""

import argparse
import json
import pathlib
import subprocess

import fast_simplification
import mujoco
import numpy as np
import trimesh

ROOT = pathlib.Path(__file__).resolve().parent.parent

ARMS = {
    'franka_fr3': dict(
        xml='franka_fr3/fr3.xml',
        pose='push',
        qpos=[0.0, 0.3764, 0.0, -2.5278, 0.0, 3.9514, 0.0],
        short='MuJoCo Menagerie franka_fr3',
        flange=('site', 'attachment_site'),
        tris=260_000,
        crease=40,
        source='MuJoCo Menagerie franka_fr3 (from Franka Robotics franka_description)',
        url='https://github.com/google-deepmind/mujoco_menagerie/tree/main/franka_fr3',
        license='Apache-2.0',
    ),
    'ur5e': dict(
        xml='universal_robots_ur5e/ur5e.xml',
        pose='push',
        qpos=[-3.1416, -1.2418, 2.2695, -3.6301, -1.3412, -0.1353],
        short='MuJoCo Menagerie universal_robots_ur5e',
        flange=('site', 'attachment_site'),
        tris=260_000,
        crease=50,  # its tubes have about 10 sides
        source='MuJoCo Menagerie universal_robots_ur5e (from Universal Robots ROS description)',
        url='https://github.com/google-deepmind/mujoco_menagerie/tree/main/universal_robots_ur5e',
        license='BSD-3-Clause',
    ),
    'rebot_rs': dict(
        xml=None,
        short='Seeed reBot-DevArm B601-RS',
        pose='HOME_QPOS',
        qpos=[0.0, 0.349, 0.5, -0.677, 0.0, 0.0],
        flange=('body', 'link6'),
        tris=320_000,
        source='Seeed reBot-DevArm, Rebot_Arm_description/RS meshes; kinematics from the Seeed URDF, pose HOME_QPOS',
        url='https://github.com/Seeed-Projects/reBot-DevArm',
        license='CERN-OHL-W-2.0',
    ),
    # A humanoid: standing (keyframe "stand"), the right arm raised so that the wrist's end face is pitched 30 deg
    # below horizontal like the arms above, with the wrist-yaw axis upward in the vertical plane (the flange x of
    # the other arms points the same way, so the same mount_rot puts the phone on top). The flange is the end
    # interface of the official URDF: right_wrist_yaw_link at x = 41.5 mm, normal +X; its x axis is the yaw axis
    # (the long side of the G1 wrist adapter). The right rubber hand is left out: the adapter and the pusher go
    # there. The arm angles come from a small least-squares fit (wrist face direction, yaw axis, hand in front of
    # the chest). The ground of the editor is the floor under the feet.
    'unitree_g1': dict(
        xml='unitree_g1/g1.xml',
        key='stand',
        joints={
            'right_shoulder_pitch_joint': -0.874,
            'right_shoulder_roll_joint': -0.2765,
            'right_shoulder_yaw_joint': -0.128,
            'right_elbow_joint': 0.9688,
            'right_wrist_roll_joint': 0.1266,
            'right_wrist_pitch_joint': 0.4454,
            'right_wrist_yaw_joint': 0.1046,
        },
        short='MuJoCo Menagerie unitree_g1',
        flange=('body', 'right_wrist_yaw_link'),
        # flange frame in the body: origin at the end interface, x = body z (yaw axis), y = -body y, z = body x
        flange_local=dict(pos=[0.0415, 0.0, 0.0], mat=[[0, 0, 1], [0, -1, 0], [1, 0, 0]]),
        hide_meshes=['right_rubber_hand'],
        tris=300_000,
        crease=40,
        source='MuJoCo Menagerie unitree_g1 (from Unitree unitree_ros g1_description, 29 DoF rev 1.0)',
        url='https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_g1',
        license='BSD-3-Clause',
    ),
}


def pbr(m, g):
    """Colour, metallic and roughness of a geom. MuJoCo materials without metallic/roughness (-1) get a plain
    plastic: not metallic, the rougher the lower their shininess."""
    i = m.geom_matid[g]
    if i < 0:
        return tuple(np.round(m.geom_rgba[g], 3)), 0.0, 0.6
    me, ro = float(m.mat_metallic[i]), float(m.mat_roughness[i])
    if me < 0:
        me = 0.0
    if ro < 0:
        ro = round(0.75 - 0.5 * float(m.mat_shininess[i]), 2)
    return tuple(np.round(m.mat_rgba[i], 3)), round(me, 2), round(ro, 2)


def bake(arm_id, cfg, xml_path, out_dir, gltf_transform=None):
    m = mujoco.MjModel.from_xml_path(str(xml_path))
    d = mujoco.MjData(m)
    if cfg.get('key'):
        mujoco.mj_resetDataKeyframe(m, d, mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_KEY, cfg['key']))
        for name, q in cfg.get('joints', {}).items():
            d.qpos[m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, name)]] = q
    else:
        d.qpos[: len(cfg['qpos'])] = cfg['qpos']
    mujoco.mj_forward(m, d)

    by_colour: dict[tuple, list[trimesh.Trimesh]] = {}
    for g in range(m.ngeom):
        if m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH or m.geom_group[g] != 2:
            continue
        if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_MESH, m.geom_dataid[g]) in cfg.get('hide_meshes', ()):
            continue
        mid = m.geom_dataid[g]
        v0, nv = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
        f0, nf = m.mesh_faceadr[mid], m.mesh_facenum[mid]
        V = m.mesh_vert[v0 : v0 + nv].astype(np.float64)
        F = m.mesh_face[f0 : f0 + nf].astype(np.int64)
        R = d.geom_xmat[g].reshape(3, 3)
        V = (V @ R.T + d.geom_xpos[g]) * 1000.0  # base frame, mm
        by_colour.setdefault(pbr(m, g), []).append(trimesh.Trimesh(V, F, process=False))

    total = sum(sum(len(t.faces) for t in ts) for ts in by_colour.values())
    keep = min(1.0, cfg['tris'] / total)
    scene = trimesh.Scene()
    n_out = 0
    for i, ((rgba, metallic, roughness), ts) in enumerate(sorted(by_colour.items())):
        mesh = trimesh.util.concatenate(ts)
        mesh.merge_vertices()
        if keep < 1.0 and len(mesh.faces) > 500:
            V, F = fast_simplification.simplify(mesh.vertices, mesh.faces, target_reduction=1.0 - keep)
            mesh = trimesh.Trimesh(V, F, process=True)
        mesh = trimesh.graph.smooth_shade(
            mesh, angle=np.radians(cfg.get('crease', 30))
        )  # edges sharper than this stay hard
        mesh.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                baseColorFactor=[float(c) for c in rgba], metallicFactor=metallic, roughnessFactor=roughness
            )
        )
        scene.add_geometry(mesh, node_name=f'{arm_id}_{i}')
        n_out += len(mesh.faces)
    out = out_dir / f'{arm_id}.glb'
    out.write_bytes(scene.export(file_type='glb'))
    raw = out.stat().st_size
    if gltf_transform:
        # positions to 14 bits of the arm's size (well under 0.1 mm), normals to 10 bits, then meshopt compression
        subprocess.run(
            [
                gltf_transform,
                'meshopt',
                str(out),
                str(out),
                '--level',
                'medium',
                '--quantize-position',
                '14',
                '--quantize-normal',
                '10',
            ],
            check=True,
            capture_output=True,
        )

    kind, name = cfg['flange']
    if kind == 'site':
        i = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_SITE, name)
        pos, mat = d.site_xpos[i], d.site_xmat[i]
    else:
        i = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, name)
        pos, mat = d.xpos[i], d.xmat[i]
    if cfg.get('flange_local'):
        Rb = mat.reshape(3, 3)
        pos = pos + Rb @ np.array(cfg['flange_local']['pos'])
        mat = (Rb @ np.array(cfg['flange_local']['mat'], dtype=float)).ravel()
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, mat)
    print(
        f'{arm_id}: {total} -> {n_out} triangles, {raw / 1e6:.2f} MB -> {out.stat().st_size / 1e6:.2f} MB, '
        f'flange at {np.round(pos * 1000, 1)} mm, flange Z = {np.round(mat.reshape(3, 3)[:, 2], 3)}'
    )
    return {
        'file': f'arms/{arm_id}.glb',
        'flange': {'pos': [round(float(x) * 1000, 3) for x in pos], 'quat': [round(float(x), 6) for x in quat]},
        'qpos': [round(float(x), 5) for x in d.qpos[: m.njnt]] if not cfg.get('key') else {
            k: round(float(v), 5) for k, v in cfg.get('joints', {}).items()
        },
        'short': cfg['short'],
        'pose': cfg.get('key') or cfg.get('pose'),
        'source': cfg['source'],
        'url': cfg['url'],
        'license': cfg['license'],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--menagerie', type=pathlib.Path, default=pathlib.Path('.'))
    ap.add_argument(
        '--rebot',
        type=pathlib.Path,
        help='rebot MJCF without tool and gripper connector (body "link6" = flange); needed unless --only leaves rebot_rs out',
    )
    ap.add_argument(
        '--gltf-transform', help='path of the gltf-transform CLI (node_modules/.bin/gltf-transform): compress the GLBs'
    )
    ap.add_argument('--only', nargs='*', help='bake only these arms and keep the other entries of arms.json')
    a = ap.parse_args()
    out_dir = ROOT / 'public' / 'arms'
    out_dir.mkdir(parents=True, exist_ok=True)
    path = ROOT / 'src' / 'data' / 'arms.json'
    manifest = json.loads(path.read_text()) if a.only and path.exists() else {}
    for arm_id, cfg in ARMS.items():
        if a.only and arm_id not in a.only:
            continue
        if cfg['xml'] is None and a.rebot is None:
            ap.error(f'--rebot is needed for {arm_id} (or leave it out with --only)')
        xml = a.rebot if cfg['xml'] is None else a.menagerie / cfg['xml']
        manifest[arm_id] = bake(arm_id, cfg, xml, out_dir, a.gltf_transform)
    path.write_text(json.dumps(manifest, indent=1) + '\n')


if __name__ == '__main__':
    main()
