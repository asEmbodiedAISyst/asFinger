"""The test scene in MuJoCo: the arm in its photo box with the whiteboard, the tags, a cube and both cameras.

    uv run python sim/scene.py render --out /tmp/asfinger-sim        # both camera views at the registration pose
    uv run python sim/scene.py render --compare                   # ... and compare the tags with the real pictures
    uv run python sim/scene.py push                               # push the cube 10 cm and report where it ends up
    uv run python sim/scene.py view                               # interactive viewer (needs a display)

From code, the scene runs under the same control library as the real arm:

    from scene import make_arm, render
    with make_arm() as arm:                 # rebot_control.Arm on the simulator, scene included
        arm.enable(); arm.move_home()
        image = render(arm, "top")          # RGB array as the overhead phone would see it

The scene is described in sim/scene.yaml (measured and estimated values, with a note on each) and
sim/registration.yaml (where the cameras, the whiteboard and the tags are, written by sim/register.py), both in
the arm's base frame. What is and is not modelled:
- the arm: joints, masses and centres of mass from calibration/b601_rs.yaml; drawn as capsules between the joints.
  Its links do not collide with anything. Only the pusher rod does.
- contact and friction parameters are MuJoCo defaults or estimates, not identified from the real setup.
- the cameras have the real intrinsics and estimated poses, but no lens distortion and no exposure model.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault('MUJOCO_GL', 'egl')  # offscreen rendering without a display

import cv2  # noqa: E402
import mujoco  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from rebot_control import Arm, ArmConfig, RobotModel, ToolConfig  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCENE_FILE = Path(__file__).with_name('scene.yaml')
ASSETS = Path(__file__).with_name('assets')
TOOL = str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml')  # the pusher that is on the arm
CALIBRATION = ROOT / 'calibration' / 'b601_rs.yaml'

GEOM = mujoco.mjtGeom
PVC = [0.93, 0.76, 0.58, 1.0]  # the pink-yellow backdrop
SILVER = [0.72, 0.72, 0.70, 1.0]


def load_scene(path: Path = SCENE_FILE) -> dict:
    """scene.yaml (measured and estimated values) with registration.yaml (camera, board and tag poses) merged in."""
    scene = yaml.safe_load(Path(path).read_text())
    reg_file = Path(path).with_name('registration.yaml')
    if not reg_file.is_file():
        raise FileNotFoundError(f'{reg_file} is missing: run sim/register.py --write')

    def merge(a: dict, b: dict) -> dict:
        for k, v in b.items():
            a[k] = merge(a.get(k, {}), v) if isinstance(v, dict) else v
        return a

    return merge(scene, yaml.safe_load(reg_file.read_text()))


# ---------------------------------------------------------------------------------------------------- helpers
def _quat(R: np.ndarray) -> list[float]:
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(R, dtype=float).reshape(9))
    return q.tolist()


def _camera_quat(R_cv: np.ndarray) -> list[float]:
    """MuJoCo camera orientation (x right, y up, looking along -z) from OpenCV axes as columns (right, down, forward)."""
    R = np.asarray(R_cv, dtype=float)
    return _quat(np.column_stack([R[:, 0], -R[:, 1], -R[:, 2]]))


def _fovy(intr: dict) -> float:
    return float(np.degrees(2 * np.arctan(intr['height'] / 2 / intr['fy'])))


def _tag_png(tag_id: int) -> Path:
    """AprilTag 36h11 image with a one-cell white margin (the printed tags have one), written once."""
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / f'tag36h11_{tag_id}.png'
    if not path.exists():
        d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        cell = 32
        tag = cv2.aruco.generateImageMarker(d, tag_id, 8 * cell)
        img = np.full((10 * cell, 10 * cell), 255, np.uint8)
        img[cell:-cell, cell:-cell] = tag
        cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    return path


def _add_fixed_body_mass(body, mass: float, half: np.ndarray) -> None:
    """Explicit inertia of a solid box (the arm's spec does not take inertias from geoms)."""
    a, b, c = 2 * np.asarray(half)
    body.mass = mass
    body.ipos = [0, 0, 0]
    body.inertia = [mass * (b * b + c * c) / 12, mass * (a * a + c * c) / 12, mass * (a * a + b * b) / 12]
    body.explicitinertial = True


# ------------------------------------------------------------------------------------------------------ scene
def make_scene_hook(params: dict, model: RobotModel):
    """A function for ``SimBackend(scene=...)`` that adds the surroundings of the arm to its MuJoCo spec."""

    def add(spec) -> None:
        world = spec.worldbody
        spec.visual.global_.offwidth, spec.visual.global_.offheight = 1920, 1440
        spec.visual.headlight.ambient = [0.45, 0.45, 0.45]
        spec.visual.headlight.diffuse = [0.5, 0.5, 0.5]
        box, fz = params['box'], params['floor_z']
        (x0, x1), (y0, y1), top = box['x'], box['y'], box['height']

        # light from the top of the box, floor, back and side walls (drawn only; the arm's links do not collide)
        world.add_light(pos=[(x0 + x1) / 2, 0, top], dir=[0, 0, -1], diffuse=[0.6, 0.6, 0.6])
        world.add_geom(
            name='floor', type=GEOM.mjGEOM_PLANE, size=[1.0, 1.0, 0.05], pos=[(x0 + x1) / 2, 0, fz], rgba=PVC
        )
        wall = dict(type=GEOM.mjGEOM_BOX, contype=0, conaffinity=0)
        h = (top - fz) / 2
        world.add_geom(
            name='wall_back', size=[0.004, (y1 - y0) / 2, h], pos=[x1, (y0 + y1) / 2, fz + h], rgba=PVC, **wall
        )
        for name, y in (('wall_left', y1), ('wall_right', y0)):
            world.add_geom(
                name=name, size=[(x1 - x0) / 2, 0.004, h], pos=[(x0 + x1) / 2, y, fz + h], rgba=SILVER, **wall
            )
        world.add_geom(
            name='base_plate', size=[0.09, 0.07, -fz / 2], pos=[0.02, 0, fz / 2], rgba=[0.1, 0.1, 0.1, 1], **wall
        )

        # whiteboard: a fixed plate the objects slide on
        wb = params['whiteboard']
        yaw = np.radians(wb['yaw_deg'])
        Rb = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
        t = wb['thickness']
        board = world.add_body(name='whiteboard', pos=[*wb['centre'], fz + t / 2], quat=_quat(Rb))
        board.add_geom(
            name='whiteboard',
            type=GEOM.mjGEOM_BOX,
            size=[wb['size'][0] / 2, wb['size'][1] / 2, t / 2],
            rgba=[0.97, 0.97, 0.97, 1],
            friction=[wb['friction'], 0.005, 0.0001],
        )
        surface = fz + t

        # tags: thin textured tiles on the board, placed from their four measured corners
        for tag_id, corners in params['tags']['corners'].items():
            c = np.asarray(corners, dtype=float)  # detector order: marker top-left, then clockwise
            ex = (c[1] - c[0] + c[2] - c[3]) / 2  # marker "right"
            ey = (c[0] - c[3] + c[1] - c[2]) / 2  # marker "up"
            side = (np.linalg.norm(ex) + np.linalg.norm(ey)) / 2
            ex = ex / np.linalg.norm(ex)
            R = np.column_stack([[*ex, 0], np.cross([0, 0, 1], [*ex, 0]), [0, 0, 1]])
            if np.dot(R[:2, 1], ey) < 0:  # seen from above the marker must not be mirrored
                raise ValueError(f"tag {tag_id}: corners are not in the detector's clockwise order")
            name = f'tag{tag_id}'
            spec.add_texture(name=name, type=mujoco.mjtTexture.mjTEXTURE_2D, file=str(_tag_png(int(tag_id))))
            mat = spec.add_material(name=name)
            mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = name
            half = side * 10 / 8 / 2  # the tile includes the white margin
            world.add_geom(
                name=name,
                type=GEOM.mjGEOM_BOX,
                size=[half, half, 0.0004],
                pos=[*c.mean(0), surface + 0.0004],
                quat=_quat(R),
                material=name,
                contype=0,
                conaffinity=0,
            )

        # objects
        for name, o in params['objects'].items():
            hs = o['size'] / 2
            body = world.add_body(name=name, pos=[*o['pos'], surface + hs + 0.001])
            body.add_freejoint()
            body.add_geom(
                name=name,
                type=GEOM.mjGEOM_BOX,
                size=[hs, hs, hs],
                rgba=o['rgba'],
                friction=[o['friction'], 0.005, 0.0001],
            )
            _add_fixed_body_mass(body, o['mass'], np.full(3, hs))

        # the tool on the last link: the rod (the only part of the arm that collides), the phone and the wrist camera
        import pinocchio as pin

        joint = model.flange_joint
        link = spec.body(model.link_name(joint))
        T_joint_flange = model.model.frames[model.flange_frame_id].placement
        T_joint_tcp = model.model.frames[model.tcp_frame_id].placement
        tool = params['tool']
        tip = T_joint_tcp.translation  # the rod: from the flange centre towards the tool tip
        axis = (tip - T_joint_flange.translation) / np.linalg.norm(tip - T_joint_flange.translation)
        for g in link.geoms:  # the library draws a grey capsule there: hide it
            g.rgba = [0, 0, 0, 0]
        link.add_geom(
            name='rod',
            type=GEOM.mjGEOM_CAPSULE,
            size=[tool['rod_radius'], 0, 0],
            rgba=[0.05, 0.05, 0.05, 1],
            fromto=[*(T_joint_flange.translation + tool['rod_start'] * axis), *(tip - tool['rod_radius'] * axis)],
            friction=[0.4, 0.005, 0.0001],
        )
        wc = params['cameras']['wrist']
        T_cam = T_joint_flange * pin.SE3(np.asarray(wc['R'], dtype=float), np.asarray(wc['pos'], dtype=float))
        link.add_camera(
            name='wrist',
            pos=T_cam.translation.tolist(),
            quat=_camera_quat(T_cam.rotation),
            fovy=_fovy(wc['intrinsics']),
        )
        ps = np.asarray(tool['phone_size']) / 2  # the phone: screen normal along the optical axis
        phone_pos = T_cam.translation - T_cam.rotation[:, 2] * (ps[2] + 0.002)
        link.add_geom(
            name='phone',
            type=GEOM.mjGEOM_BOX,
            size=ps.tolist(),
            pos=phone_pos.tolist(),
            quat=_quat(T_cam.rotation),
            rgba=[0.15, 0.15, 0.17, 1],
            contype=0,
            conaffinity=0,
        )

        tc = params['cameras']['top']
        world.add_camera(
            name='top', pos=tc['pos'], quat=_camera_quat(np.asarray(tc['R'], dtype=float)), fovy=_fovy(tc['intrinsics'])
        )

    return add


def make_arm(scene_file: Path = SCENE_FILE, calibration: Path | None = CALIBRATION, **backend_kwargs) -> Arm:
    """The arm on the simulator with the scene around it. Use it like the real one (``with make_arm() as arm: ...``)."""
    params = load_scene(scene_file)
    cal = str(calibration) if calibration and Path(calibration).is_file() else None
    model = RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(TOOL))
    arm = Arm.from_config(
        'b601_rs', tool=TOOL, calibration=cal, backend='sim', scene=make_scene_hook(params, model), **backend_kwargs
    )
    arm.scene_params = params
    return arm


def render(arm: Arm, camera: str) -> np.ndarray:
    """RGB image from the named camera ("top" or "wrist") at the arm's current simulated state."""
    intr = arm.scene_params['cameras'][camera]['intrinsics']
    renderers = arm.__dict__.setdefault('_renderers', {})
    if camera not in renderers:
        renderers[camera] = mujoco.Renderer(arm.backend.mj_model, intr['height'], intr['width'])
    r = renderers[camera]
    r.update_scene(arm.backend.mj_data, camera=camera)
    return r.render().copy()


def object_pose(arm: Arm, name: str) -> tuple[np.ndarray, np.ndarray]:
    """Position and rotation matrix of a scene object."""
    d, m = arm.backend.mj_data, arm.backend.mj_model
    i = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, name)
    return d.xpos[i].copy(), d.xmat[i].reshape(3, 3).copy()


# -------------------------------------------------------------------------------------------------------- CLI
def cmd_render(args) -> int:
    sys.path.insert(0, str(ROOT / 'robot'))
    from tags import detect

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    arm = make_arm(q0=None)
    reg = arm.scene_params['registration']
    with arm:
        arm.backend.set_q(np.radians(reg['q_deg']))  # the pose of the real pictures (torque stays off)
        for cam in ('top', 'wrist'):
            img = render(arm, cam)
            path = out / f'sim-{cam}.png'
            cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            sim_tags = detect(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            print(f'{cam}: {path}  tags seen: {sorted(sim_tags)}')
            if args.compare:
                if not (ROOT / reg[f'{cam}_image']).is_file():
                    # the pictures of the real scene are not in the repository (calibration/data is local)
                    print(f'   no real picture to compare with: {reg[f"{cam}_image"]} not found')
                    continue
                real = cv2.imread(str(ROOT / reg[f'{cam}_image']))
                real_tags = detect(real)
                for i in sorted(set(sim_tags) & set(real_tags)):
                    d = np.linalg.norm(sim_tags[i] - real_tags[i], axis=1)
                    print(
                        f'   tag {i:2d}: simulated vs real corner positions differ by {d.mean():.1f} px (worst {d.max():.1f})'
                    )
                missing = sorted(set(real_tags) - set(sim_tags))
                if missing:
                    print(f'   in the real picture but not found in the simulated one: {missing}')
    return 0


def cmd_push(args) -> int:
    with make_arm() as arm:
        arm.enable()
        arm.move_home()
        p0, R0 = arm.tcp_pose()
        cube0, _ = object_pose(arm, 'cube')
        z = cube0[2]  # push at the cube's mid height
        start = np.array([cube0[0] - 0.06, cube0[1], z])
        arm.move_to_pose(np.array([start[0], start[1], p0[2]]), R0, speed=0.10)
        arm.move_to_pose(start, R0, speed=0.05)
        arm.move_to_pose(start + [0.06 + args.distance, 0, 0], R0, speed=0.03)
        arm.wait(0.5)
        cube1, _ = object_pose(arm, 'cube')
        tip = arm.tcp_pose()[0]
        print(
            f'cube moved from {np.round(cube0, 3).tolist()} to {np.round(cube1, 3).tolist()}: {np.round((cube1 - cube0)[:2] * 1000, 1).tolist()} mm '
            f'(asked for {args.distance * 1000:.0f} mm along x); tool tip at {np.round(tip, 3).tolist()}'
        )
        if args.out:
            Path(args.out).mkdir(parents=True, exist_ok=True)
            for cam in ('top', 'wrist'):
                cv2.imwrite(str(Path(args.out) / f'push-{cam}.png'), cv2.cvtColor(render(arm, cam), cv2.COLOR_RGB2BGR))
        arm.move_to_pose(np.array([tip[0], tip[1], p0[2]]), R0, speed=0.10)
        arm.move_home()
    return 0


def cmd_view(args) -> int:
    os.environ['MUJOCO_GL'] = 'glfw'
    with make_arm(viewer=True) as arm:
        arm.enable()
        arm.move_home()
        print('viewer open; close its window to end')
        while arm.backend.viewer is not None and arm.backend.viewer.is_running():
            arm.wait(0.5)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('render', help='render both cameras at the pose of the real reference pictures')
    s.add_argument('--out', default='/tmp/asfinger-sim')
    s.add_argument('--compare', action='store_true', help='compare the tag positions with the real pictures')
    s.set_defaults(func=cmd_render)
    s = sub.add_parser('push', help='push the cube along x with the rod and report where it ends up')
    s.add_argument('--distance', type=float, default=0.10, help='m')
    s.add_argument('--out', help='directory for pictures of the end state')
    s.set_defaults(func=cmd_push)
    s = sub.add_parser('view', help='interactive viewer')
    s.set_defaults(func=cmd_view)
    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
