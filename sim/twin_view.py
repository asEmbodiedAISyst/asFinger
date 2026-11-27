"""Look at the twin in MuJoCo's interactive viewer (needs a desktop: a screen, a remote desktop, or ssh -X).

    uv run python sim/twin_view.py                                          # default scene, arm at the tool's home pose
    uv run python sim/twin_view.py --episode <episode>      # that episode's whiteboard and cube start
    uv run python sim/twin_view.py --episode <episode> --replay      # ... and play it back in a loop

    uv run python sim/twin_view.py --hide none                              # the closed box (from inside)
    uv run python sim/twin_view.py --hide front,left                        # hide any faces: front back left right top

--replay poses the arm at the recorded joint angles and the cube where the overhead video saw it (kinematic, no physics),
in real time (--speed to change). Close the window to end. Mouse: left drag turns, right drag moves, wheel zooms;
double-click selects a body. Ctrl+Tab (or the "Camera" menu on the left) switches to the twin's top / wrist cameras.

Hiding the box's faces (only this window's picture; nothing else changes: the walls never collide, cast no shadows, and
the twin's cameras and all offline pictures always draw the whole closed box). By default the operator-side face (with
the opening, behind the arm) and the ceiling are hidden so you can look in from the usual side.
    F8 front (operator side)   F9 back   F10 left (+y)   F11 right (-y)   F12 top (ceiling, cloth, light strips)
    number keys 1-4, or "Group enable" > Geom on the left panel: 1 front, 2 top, 3 both side walls, 4 back
This window always draws with MuJoCo's classic renderer, whatever base.renderer says: MuJoCo 4.0.0's Filament viewer
(MuJoCo Studio) did not open a window when it was tried (its Python wrapper fails with "Target not found", also
with `python -m mujoco.studio.viewer`).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import twin  # noqa: E402  (first: it sets up MuJoCo for off-screen pictures; the viewer window works alongside)
import mujoco  # noqa: E402
import mujoco.viewer  # noqa: E402
import numpy as np  # noqa: E402
from rebot_control import ToolConfig  # noqa: E402


class JointLog:
    """The recorded joint angles of an episode (its arm.npz), at any time, plus the twin's joint offsets if any."""

    def __init__(self, episode: str, offsets=None):
        sys.path.insert(0, str(twin.ROOT / 'robot'))
        from episode import load

        path = Path(episode) if Path(episode).is_dir() else twin.EPISODES / Path(episode).name
        if not (path / 'arm.npz').is_file():
            raise FileNotFoundError(f'no joint log {path / "arm.npz"}')
        self.log = load(path)[1]
        self.offsets = np.zeros(self.log['q'].shape[1]) if offsets is None else np.asarray(offsets, dtype=float)

    def q(self, t) -> np.ndarray:
        t = np.atleast_1d(t)
        return (
            np.column_stack([np.interp(t, self.log['t'], self.log['q'][:, j]) for j in range(self.log['q'].shape[1])])
            + self.offsets
        )


VIEWER_AMBIENT = 0.4  # this window only; the twin's cameras use base.lights.ambient and their tone
FACE_KEYS = {297: 'front', 298: 'back', 299: 'left', 300: 'right', 301: 'top'}  # GLFW key codes of F8-F12


def face_geoms(m) -> dict[str, list[int]]:
    """Geom ids of each face of the box (names wall_<face>...; see twin._add_box), for hiding them in this viewer."""
    names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) or '' for i in range(m.ngeom)]
    return {f: [i for i, n in enumerate(names) if n.startswith(f'wall_{f}')] for f in FACE_KEYS.values()}


def show_face(m, faces: dict, face: str, visible: bool) -> None:
    """Draw a face in its own viewer group, or move it to the group no picture draws. Only the drawing changes."""
    for i in faces[face]:
        m.geom_group[i] = twin.BOX_GROUPS[face] if visible else twin.HIDDEN_GROUP


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--episode', help='episode whose start state to show (data/derived/twin/<episode>/state.yaml)')
    ap.add_argument('--replay', action='store_true', help="play the episode's joint angles and cube track in a loop")
    ap.add_argument('--speed', type=float, default=1.0, help='replay speed')
    ap.add_argument(
        '--seconds', type=float, default=0.0, help='close by itself after this long (0: when the window is closed)'
    )
    ap.add_argument(
        '--hide',
        default='front,top',
        help='box faces to hide at the start, comma separated: front back left right top, or none (default: front,top)',
    )
    args = ap.parse_args()
    if args.replay and not args.episode:
        ap.error('--replay needs --episode')
    hide = set() if args.hide in ('', 'none') else set(args.hide.split(','))
    if hide - set(FACE_KEYS.values()):
        ap.error(
            f'--hide: unknown face(s) {sorted(hide - set(FACE_KEYS.values()))}; use {", ".join(FACE_KEYS.values())}'
        )
    try:
        state = twin.load_state(args.episode) if args.episode else None
    except FileNotFoundError as e:
        ap.error(str(e))
    cfg = twin.load_config(state=state)
    cfg['base']['renderer'] = 'classic'  # see the note at the top
    track = at = None
    if args.replay:
        try:
            at = JointLog(args.episode, cfg['base'].get('joint_offsets'))
        except FileNotFoundError as e:
            ap.error(str(e))
        tf = twin.DERIVED / Path(args.episode).name / 'track.npz'
        track = np.load(tf) if tf.is_file() else None
    q0 = (
        at.q(at.log['t'][0])[0]
        if at is not None
        else np.asarray(ToolConfig.load(cfg['base']['tool_file']).home, dtype=float)
    )
    arm = twin.make_arm(cfg, q0=q0)
    arm.backend.connect()
    m, d = arm.backend.mj_model, arm.backend.mj_data
    arm.backend.set_q(q0)
    zc = cfg['base']['table_z'] + cfg['objects']['cube']['size'] / 2 if 'cube' in cfg['objects'] else None
    t_log = at.log['t'] if at is not None else None
    faces = face_geoms(m)
    # the viewer cannot apply the cameras' tone (twin.render does, after rendering), so brighten this window's copy of
    # the scene instead: more ambient light gives about the look of the toned pictures (fitted on three views)
    m.vis.headlight.ambient[:] = VIEWER_AMBIENT
    toggles: list[str] = []  # F-keys pressed (the viewer's thread), applied in the loop below
    t_start = time.monotonic()
    with mujoco.viewer.launch_passive(
        m, d, key_callback=lambda key: toggles.append(FACE_KEYS[key]) if key in FACE_KEYS else None
    ) as v:
        with v.lock():  # start looking at the arm and the whiteboard from the side
            v.cam.azimuth, v.cam.elevation, v.cam.distance = 30.0, -35.0, 1.0
            v.cam.lookat[:] = (0.22, 0.0, 0.08)
            v.opt.geomgroup[:5] = 1  # all box groups on (the viewer shows 0-2 only by default)
            for f in hide:
                show_face(m, faces, f, False)
        while v.is_running():
            while toggles:
                f = toggles.pop(0)
                with v.lock():
                    show_face(m, faces, f, m.geom_group[faces[f][0]] == twin.HIDDEN_GROUP)
            now = time.monotonic() - t_start
            if args.seconds and now > args.seconds:
                v.close()
                time.sleep(1.0)  # let the viewer's thread shut its window down before the interpreter exits
                break
            if at is not None:
                t = t_log[0] + (now * args.speed) % (t_log[-1] - t_log[0])
                arm.backend.set_q(at.q(t)[0])
                if track is not None and zc is not None:
                    k = int(np.argmin(np.abs(track['t'] - t)))
                    if track['valid'][k]:
                        twin.set_object_pose(
                            arm, 'cube', track['x'][k], track['y'][k], np.degrees(track['yaw'][k]), z=zc
                        )
            v.sync()
            time.sleep(1 / 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
