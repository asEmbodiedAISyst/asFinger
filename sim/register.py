"""Place the cameras, the whiteboard and the tags of the simulated scene in the arm's frame from two pictures.

    uv run python sim/register.py            # recompute from the pictures named in scene.yaml and print the result
    uv run python sim/register.py --write    # ... and write sim/registration.yaml

A rough, single-pose registration, good to about 1 cm. It is not a camera calibration:

1. Overhead camera. Its tilt comes from the phone's gravity reading and its height from the tags on the whiteboard,
   so a pixel can be turned into a point on the whiteboard plane, in a frame under the camera. The arm frame is
   tied to that frame by the pusher rod: the arm stands still at a known pose, forward kinematics gives the rod's
   tip and direction, and the tip and the rod's line are picked in the picture (--top-tip, --top-rod).
2. Whiteboard and tags: their corners in the overhead picture, put on the plane.
3. Wrist camera: PnP on the tags it sees, whose positions are known from step 2, at the same arm pose. PnP from a
   flat, distant target is weak in position, so the camera is then moved sideways until the rod tip appears where
   the wrist picture shows it (--wrist-tip).

The rod is taken to run from the flange centre to the tool tip (30 deg to the flange axis). The wrist picture
confirms this: a rod point 8 cm behind the tip lands 7 px from the rod seen there, against 100 px for a rod along
the tool config's z axis.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import cv2
import numpy as np
import pinocchio as pin
import yaml
from rebot_control import ArmConfig, RobotModel, ToolConfig

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'robot'))
from tags import detect  # noqa: E402

SCENE_FILE = Path(__file__).with_name('scene.yaml')
REGISTRATION_FILE = Path(__file__).with_name('registration.yaml')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--write', action='store_true', help='write the result to sim/registration.yaml')
    ap.add_argument(
        '--gravity',
        type=float,
        nargs=3,
        default=[0.0636, -0.6565, -0.7516],
        help="gravity direction in the overhead phone's device frame (from its accelerometer, at rest)",
    )
    ap.add_argument(
        '--height', type=float, default=0.762, help='overhead camera above the whiteboard surface (m), from the tags'
    )
    ap.add_argument(
        '--top-tip', type=float, nargs=2, default=[1276.0, 494.4], help='rod tip in the overhead picture (px)'
    )
    ap.add_argument(
        '--top-rod', type=float, nargs=2, default=[1180.0, 496.4], help="another point on the rod's centre line (px)"
    )
    ap.add_argument(
        '--wrist-tip', type=float, nargs=2, default=[351.0, 256.0], help='rod tip in the wrist picture (px)'
    )
    ap.add_argument(
        '--board',
        type=float,
        nargs=8,
        default=[1167, 368, 1500, 258, 1478, 727, 1188, 725],
        help="corners of the whiteboard's white area in the overhead picture (px), going round",
    )
    args = ap.parse_args()

    scene = yaml.safe_load(SCENE_FILE.read_text())
    reg = scene['registration']
    # the two pictures of the real scene are not in the repository (calibration/data is local)
    absent = [reg[k] for k in ('top_image', 'wrist_image') if not (ROOT / reg[k]).is_file()]
    if absent:
        sys.exit(
            f'picture(s) not found: {", ".join(absent)}. They are not part of the repository: take them with '
            'robot/snapshot.py while the arm stands at registration.q_deg of sim/scene.yaml, and save them there.'
        )
    it, iw = scene['cameras']['top']['intrinsics'], scene['cameras']['wrist']['intrinsics']
    model = RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load('pusher_ip17'))
    q = np.radians(reg['q_deg'])
    data = model.new_data()
    pin.forwardKinematics(model.model, data, q)
    pin.updateFramePlacements(model.model, data)
    flange = data.oMf[model.flange_frame_id]
    tip = model.fk(q)[0]
    rod = (tip - flange.translation) / np.linalg.norm(tip - flange.translation)

    # ---- overhead camera: a ground frame under the camera (x: where it looks, z: up) from gravity
    g = np.asarray(args.gravity) / np.linalg.norm(args.gravity)
    up = -np.array([-g[1], -g[0], -g[2]])  # in camera axes (x right, y down, z forward)
    look = np.array([0, 0, 1.0]) - up[2] * up
    look /= np.linalg.norm(look)
    R_gc = np.array([look, np.cross(up, look), up])  # camera axes -> ground frame
    f, cx, cy, H = it['fx'], it['cx'], it['cy'], args.height

    def ground_to_px(P):
        c = R_gc.T @ (P - np.array([0, 0, H]))
        return np.array([cx + f * c[0] / c[2], cy + f * c[1] / c[2]])

    def px_to_ground(u, v, z=0.0):
        r = R_gc @ np.array([(u - cx) / f, (v - cy) / f, 1.0])
        s = (z - H) / r[2]
        return np.array([s * r[0], s * r[1], z])

    # the arm frame in the ground frame: a rotation about the vertical and a shift, from the rod
    tip_px, rod_px = np.asarray(args.top_tip), np.asarray(args.top_rod)
    n = np.array([-(tip_px - rod_px)[1], (tip_px - rod_px)[0]])
    n /= np.linalg.norm(n)  # normal of the rod's line in the picture
    behind = tip - 0.08 * rod

    def arm_to_ground(P, x):
        c, s = np.cos(x[0]), np.sin(x[0])
        return np.array([c * P[0] - s * P[1] + x[1], s * P[0] + c * P[1] + x[2], P[2]])

    def residual(x):
        a = ground_to_px(arm_to_ground(tip, x)) - tip_px
        return np.array([a[0], a[1], n @ (ground_to_px(arm_to_ground(behind, x)) - tip_px)])

    x = np.array([np.pi, 0.5, -0.15])  # the camera faces the arm from about half a metre
    for _ in range(60):
        r = residual(x)
        J = np.array([(residual(x + e) - r) / 1e-6 for e in np.eye(3) * 1e-6]).T
        x = x - np.linalg.solve(J.T @ J + 1e-12 * np.eye(3), J.T @ r)
    c, s = np.cos(x[0]), np.sin(x[0])
    Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    def ground_to_arm(P):
        return Rz.T @ (np.asarray(P, dtype=float) - np.array([x[1], x[2], 0.0]))

    cam_pos = ground_to_arm([0, 0, H])
    R_top = Rz.T @ R_gc  # columns: image right, down, optical axis
    print(
        f'overhead camera in the arm frame: {np.round(cam_pos, 3).tolist()} m, looking {np.degrees(np.arccos(-R_top[2, 2])):.1f} deg from '
        f'straight down, towards {np.round(R_top[:2, 2] / np.linalg.norm(R_top[:2, 2]), 2).tolist()}'
    )

    # ---- whiteboard and tags on the plane
    board = np.array([ground_to_arm(px_to_ground(u, v))[:2] for u, v in np.asarray(args.board).reshape(4, 2)])
    sides = [np.linalg.norm(board[i] - board[(i + 1) % 4]) for i in range(4)]
    yaw = np.degrees(np.mean([np.arctan2(*(board[1] - board[0])[::-1]), np.arctan2(*(board[2] - board[3])[::-1])]))
    print(
        f'whiteboard: white area {np.round(sides, 3).tolist()} m, centre {np.round(board.mean(0), 3).tolist()}, turned {yaw:.1f} deg'
    )
    top_tags = detect(cv2.imread(str(ROOT / reg['top_image'])))
    tags = {i: np.array([ground_to_arm(px_to_ground(u, v)) for u, v in cs]) for i, cs in sorted(top_tags.items())}
    for i, P in tags.items():
        side = np.mean([np.linalg.norm(P[k] - P[(k + 1) % 4]) for k in range(4)]) * 1000
        print(f'  tag {i}: centre {np.round(P.mean(0)[:2], 3).tolist()}, side {side:.1f} mm')

    # ---- wrist camera
    wrist_tags = detect(cv2.imread(str(ROOT / reg['wrist_image'])))
    common = sorted(set(tags) & set(wrist_tags))
    K = np.array([[iw['fx'], 0, iw['cx']], [0, iw['fy'], iw['cy']], [0, 0, 1.0]])
    obj = np.concatenate([tags[i] for i in common])
    img = np.concatenate([wrist_tags[i] for i in common]).astype(float)
    _, rvec, tvec = cv2.solvePnP(obj, img, K, None)
    R_ca, _ = cv2.Rodrigues(rvec)
    err = np.linalg.norm(cv2.projectPoints(obj, rvec, tvec, K, None)[0][:, 0] - img, axis=1)
    R_w = flange.rotation.T @ R_ca.T  # camera axes in the flange frame
    p_w = flange.rotation.T @ (-R_ca.T @ tvec.ravel() - flange.translation)
    tip_f = flange.rotation.T @ (tip - flange.translation)

    def wrist_px(P, pos):
        cc = R_w.T @ (P - pos)
        return np.array([K[0, 0] * cc[0] / cc[2] + K[0, 2], K[1, 1] * cc[1] / cc[2] + K[1, 2]]), cc[2]

    before, depth = wrist_px(tip_f, p_w)
    shift = (np.asarray(args.wrist_tip) - before) * depth / K[0, 0]
    p_w2 = p_w - R_w[:, 0] * shift[0] - R_w[:, 1] * shift[1]
    print(
        f'wrist camera: PnP on tags {common}, reprojection error {err.mean():.1f} px; rod tip predicted at {np.round(before, 0).tolist()}, '
        f'seen at {list(args.wrist_tip)}: camera moved {np.linalg.norm(p_w2 - p_w) * 1000:.0f} mm sideways'
    )
    print(
        f'  in the flange frame: position {np.round(p_w2, 3).tolist()}, optical axis {np.round(R_w[:, 2], 3).tolist()}'
    )

    if not args.write:
        print('nothing written (add --write)')
        return 0
    r4 = lambda a: np.round(np.asarray(a, dtype=float), 4).tolist()
    out = {
        'whiteboard': {'centre': r4(board.mean(0)), 'yaw_deg': round(float(yaw), 1)},
        'tags': {'corners': {int(i): r4(P[:, :2]) for i, P in tags.items()}},
        'cameras': {'top': {'pos': r4(cam_pos), 'R': r4(R_top)}, 'wrist': {'pos': r4(p_w2), 'R': r4(R_w)}},
    }
    header = f"""# Written by sim/register.py on {datetime.date.today().isoformat()}: do not edit, run the script again.
# Arm base frame, metres. Good to about 1 cm; see the script for how it is obtained.
#   whiteboard: centre of the white area and rotation of the board about the vertical
#   tags.corners: corner positions on the whiteboard surface, in the order the detector returns them
#   cameras: position and axes (columns: image right, image down, optical axis); top in the arm frame, wrist in the
#     flange frame. The wrist camera: PnP reprojection error {err.mean():.1f} px, then moved
#     {np.linalg.norm(p_w2 - p_w) * 1000:.0f} mm sideways to put the rod tip where the wrist picture shows it.
# Inputs: gravity {np.round(g, 4).tolist()}, camera height {H} m, rod tip {list(args.top_tip)} and rod point
#   {list(args.top_rod)} px in the overhead picture, rod tip {list(args.wrist_tip)} px in the wrist picture.
"""
    REGISTRATION_FILE.write_text(header + yaml.safe_dump(out, sort_keys=False, default_flow_style=None, width=200))
    print(f'wrote {REGISTRATION_FILE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
