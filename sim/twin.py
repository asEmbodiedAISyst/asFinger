"""Digital twin of the data-collection scene, second version: the arm with its real meshes, the photo box, the lights,
both cameras and a list of loose objects (the whiteboard, the cube, ...) that a recorded episode can set.

    uv run python sim/twin.py render --out /tmp/twin                       # both cameras, default object poses
    uv run python sim/twin.py render --episode <name> --out /tmp/twin      # ... with an episode's measured start state
    uv run python sim/twin.py view                                         # interactive viewer (needs a display)

From code (the same control library as the real arm, as in sim/scene.py):

    import sys; sys.path.insert(0, "sim")
    import twin
    cfg = twin.load_config(state=twin.load_state("<episode>"))   # state optional
    with twin.make_arm(cfg) as arm:
        arm.backend.set_q(q)                           # or arm.enable(); arm.move_home(); ...
        image = twin.render(arm, "top")                # RGB as the overhead phone would see it; "wrist" for the tool's

Files: sim/twin.yaml (the scene: what is measured, what estimated; it also holds where the cameras and the tags of
the whiteboard are in one reference setup), the tool file it names (calibration/tool_*.yaml: the tool's kinematics and
its `sim:` block with mesh, collision shapes and camera frames) and, per episode, a start state. A local file
sim/twin_registration.yaml (not in git) overrides the camera poses and the board geometry of twin.yaml when it exists.
That file and the start states are written by tools that are not part of this repository yet (twin_register.py,
episode_state.py); the twin runs without them. sim/scene.py (the first version) is left as it was.

Recorded data is looked for in the repository's data/ folder, as robot/episode.py writes it (data/episodes); the
start states in data/derived/twin. Set ASFINGER_DATA to use another folder.

What is modelled and what not:
- arm: the control library's kinematics and dynamics; Seeed's official, undecimated meshes on top (drawn only).
  The tool collides with the parts listed in its file (rod, mounting disc, phone); the arm's links do not.
- objects: free bodies. The whiteboard rests on the floor with its own mass and friction, the cube on the board.
  Friction of a contact is set by the surface: the floor, the board's white top and the tool have priority, so
  cube-on-board is the board's surface_friction, tool-on-cube the base's tool_friction, board-on-floor the floor's.
  An object's own friction counts only against other loose objects.
- box: the 80 cm photo box closed on all six sides (silver foil, the backdrop, a cloth with an opening behind the arm,
  a glowing diffusion cloth under the light strips). Only the floor collides; each face has its own viewer group.
- cameras: real intrinsics (focal length and principal point), no lens distortion; a fixed tone per phone (exposure,
  white balance, gamma) fitted to real frames, applied by render().
- lights: two light strips (a few spot lights each), fill lights for the light the silver walls bounce, ambient light;
  their strengths were fitted to real frames together with the tones.
"""

from __future__ import annotations

import argparse
import copy
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
TWIN_FILE = Path(__file__).with_name('twin.yaml')
REGISTRATION_FILE = Path(__file__).with_name('twin_registration.yaml')
DATA = Path(os.environ.get('ASFINGER_DATA') or ROOT / 'data')  # robot/episode.py records into data/episodes
DERIVED = DATA / 'derived' / 'twin'  # per-episode start states (their tool is not in this repository yet)
EPISODES = DATA / 'episodes'
ASSETS = Path(__file__).with_name('assets')
GEOM = mujoco.mjtGeom
HIDDEN_GROUP = 5  # not drawn by default


# ------------------------------------------------------------------------------------------------- geometry helpers
def quat_of(R) -> list[float]:
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, np.asarray(R, dtype=float).reshape(9))
    return q.tolist()


def mat_of(quat) -> np.ndarray:
    R = np.zeros(9)
    mujoco.mju_quat2Mat(R, np.asarray(quat, dtype=float))
    return R.reshape(3, 3)


def rot_z(yaw_rad: float) -> np.ndarray:
    c, s = np.cos(yaw_rad), np.sin(yaw_rad)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def mj_camera_quat(R_cv) -> list[float]:
    """MuJoCo camera orientation (x right, y up, looking along -z) from OpenCV axes as columns (right, down, forward)."""
    R = np.asarray(R_cv, dtype=float)
    return quat_of(np.column_stack([R[:, 0], -R[:, 1], -R[:, 2]]))


def intrinsics_matrix(intr: dict, scale: float = 1.0) -> np.ndarray:
    return np.array(
        [[intr['fx'] * scale, 0, intr['cx'] * scale], [0, intr['fy'] * scale, intr['cy'] * scale], [0, 0, 1.0]]
    )


def tag_png(tag_id: int) -> Path:
    """AprilTag 36h11 picture with a one-cell white margin (the printed tags have one), written once."""
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / f'tag36h11_{tag_id}.png'
    if not path.exists():
        d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        cell = 32
        img = np.full((10 * cell, 10 * cell), 255, np.uint8)
        img[cell:-cell, cell:-cell] = cv2.aruco.generateImageMarker(d, tag_id, 8 * cell)
        cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    return path


# ------------------------------------------------------------------------------------------------------ config
def _merge(a: dict, b: dict) -> dict:
    for k, v in b.items():
        a[k] = _merge(dict(a.get(k) or {}), v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return a


def load_state(episode: str | Path) -> dict:
    """The start state of an episode (yaml), by episode name or path. The tool that measures it from the episode's
    top video is not part of this repository yet."""
    p = Path(episode)
    path = p if p.suffix == '.yaml' else DERIVED / p.name / 'state.yaml'
    if not path.is_file():
        raise FileNotFoundError(
            f"no start state of {p.name} at {path} (the tool that measures it from the episode's video is not "
            'part of this repository yet)'
        )
    return yaml.safe_load(path.read_text())


def load_config(
    path: Path = TWIN_FILE,
    registration: Path | None = REGISTRATION_FILE,
    state: dict | None = None,
    session: str | None = None,
) -> dict:
    """twin.yaml with the tool, the table height, a local registration if there is one, and (optionally) an episode's
    state merged in.

    ``registration``: a local file that overrides twin.yaml's camera poses and board geometry (not in the repository;
    skipped when it does not exist). ``session``: which of its overhead-camera poses to use (default: the episode's,
    else its default).
    """
    cfg = yaml.safe_load(Path(path).read_text())
    base = cfg['base']
    tool_file = ROOT / base['tool']
    tool = ToolConfig.load(tool_file)
    if 'sim' not in tool.extra:
        raise ValueError(f'{tool_file} has no `sim:` block (mesh, collision, cameras): the twin cannot draw this tool')
    mesh_dir = ROOT / base['arm_meshes']['dir']
    for parts in base['arm_meshes']['links'].values():  # fail early, before MuJoCo compiles anything
        for mesh, _ in parts:
            _mesh_file(mesh_dir, mesh)
    base['tool_file'] = str(tool_file)
    base['tool_sim'] = copy.deepcopy(tool.extra['sim'])
    base['table_z'] = float(yaml.safe_load((ROOT / base['table']).read_text())['table']['z'])
    cfg['objects'] = {o['name']: o for o in cfg['objects']}
    board = next((o for o in cfg['objects'].values() if o['type'] == 'board'), None)
    base['floor_z'] = float(base['floor'].get('z', 0.0))
    if board is not None and board.get('thickness', 'auto') == 'auto':  # the board's top is the touched table
        board['thickness'] = base['table_z'] - base['floor_z']
    wrist = copy.deepcopy(base['tool_sim']['cameras']['wrist'])  # the as-built camera frame of the tool file ...
    wrist.update(base['cameras'].get('wrist') or {})  # ... unless twin.yaml gives a measured one
    base['cameras']['wrist'] = wrist

    if registration is not None and Path(registration).is_file():  # a local registration overrides twin.yaml's values
        reg = yaml.safe_load(Path(registration).read_text())
        cfg['registration'] = reg
        sessions = reg.get('top_camera', {})
        key = session or (state or {}).get('session') or reg.get('default_session')
        if key in sessions:
            base['cameras']['top'].update({'pos': sessions[key]['pos'], 'R': sessions[key]['R']})
            base['cameras']['top']['session'] = key
        if 'wrist_camera' in reg:  # a measured wrist camera replaces the as-built one
            base['cameras']['wrist'].update(reg['wrist_camera'])
        if board is not None and 'board_tags' in reg:
            board['tags'] = _merge(board.get('tags', {}), reg['board_tags'])
        if board is not None and 'board_white' in reg:
            board['white'] = reg['board_white']
            board['frame'] = reg.get('board_frame', board['frame'])
    handeye = ROOT / 'calibration' / 'handeye_wrist.yaml'  # a ChArUco hand-eye calibration wins, when the file is
    # there (its tool is not part of this repository yet)
    if handeye.is_file():
        he = yaml.safe_load(handeye.read_text())
        base['cameras']['wrist'].update(
            {
                'frame': 'flange',
                'pos': he['pos'],
                'R': he['R'],
                'intrinsics': he['intrinsics'],
                'dist_k1k2': he['dist_k1_k2_p1_p2_k3'][:2],
                'dist': he['dist_k1_k2_p1_p2_k3'],
                'source': str(handeye),
            }
        )
        if he.get('joint_offsets_deg'):  # fitted with the camera: the joint angles the twin poses the arm at
            base['joint_offsets'] = np.radians(he['joint_offsets_deg']).tolist()
    if 'pos' not in base['cameras']['top']:
        raise FileNotFoundError(
            f'no overhead camera pose: give base.cameras.top `pos` and `R` in {path} (a local {registration} '
            'would override them)'
        )

    for name, s in ((state or {}).get('objects') or {}).items():
        if name in cfg['objects']:
            _merge(cfg['objects'][name], s)
    cfg['state'] = state
    return cfg


# ------------------------------------------------------------------------------------------------------- scene
def _surface_z(cfg: dict, xy) -> float:
    """Height of whatever an object at ``xy`` rests on: the top of a board under it, else the floor."""
    z = cfg['base']['floor_z']
    for o in cfg['objects'].values():
        if o['type'] != 'board':
            continue
        p = o['pose']
        local = rot_z(np.radians(p['yaw_deg'])).T @ np.array([xy[0] - p['x'], xy[1] - p['y'], 0.0])
        half = np.asarray(o['white']) / 2 + o['frame']
        if abs(local[0]) <= half[0] and abs(local[1]) <= half[1]:
            z = max(z, cfg['base']['floor_z'] + o['thickness'])
    return z


def _inertia(body, mass: float, half) -> None:
    """Explicit inertia of a solid box (the arm's spec does not take inertias from geoms)."""
    a, b, c = 2 * np.asarray(half, dtype=float)
    body.mass = mass
    body.ipos = [0, 0, 0]
    body.inertia = [mass * (b * b + c * c) / 12, mass * (a * a + c * c) / 12, mass * (a * a + b * b) / 12]
    body.explicitinertial = True


def _add_board(spec, cfg: dict, o: dict) -> None:
    world, fz = spec.worldbody, cfg['base']['floor_z']
    p, t = o['pose'], o['thickness']
    half = np.asarray(o['white']) / 2 + o['frame']
    body = world.add_body(
        name=o['name'], pos=[p['x'], p['y'], fz + t / 2 + 1e-4], quat=quat_of(rot_z(np.radians(p['yaw_deg'])))
    )
    body.add_freejoint()
    _inertia(body, o['mass'], [*half, t / 2])
    # the body (grey frame colour) touches the floor; a thin white top carries the surface friction for objects on it
    body.add_geom(
        name=f'{o["name"]}_body',
        type=GEOM.mjGEOM_BOX,
        size=[*half, t / 2 - 0.0005],
        pos=[0, 0, -0.0005],
        rgba=[0.80, 0.81, 0.82, 1],
        friction=[o['friction'], 0.005, 0.0001],
    )
    body.add_geom(
        name=f'{o["name"]}_top',
        type=GEOM.mjGEOM_BOX,
        size=[*half, 0.0005],
        pos=[0, 0, t / 2 - 0.0005],
        rgba=[0.86, 0.87, 0.88, 1],
        friction=[o['surface_friction'], 0.005, 0.0001],
        priority=1,
    )
    vis = dict(contype=0, conaffinity=0)
    body.add_geom(
        name=f'{o["name"]}_white',
        type=GEOM.mjGEOM_BOX,
        size=[*(np.asarray(o['white']) / 2), 0.0002],
        pos=[0, 0, t / 2 + 0.0002],
        rgba=[0.97, 0.97, 0.97, 1],
        **vis,
    )
    cap = o.get('corner_cap', 0.025)  # the grey plastic corner pieces (drawn only)
    for sx in (-1, 1):
        for sy in (-1, 1):
            body.add_geom(
                name=f'{o["name"]}_cap{sx}{sy}',
                type=GEOM.mjGEOM_BOX,
                size=[cap / 2, cap / 2, t / 2 + 0.001],
                pos=[sx * (half[0] - cap / 2), sy * (half[1] - cap / 2), 0.001],
                rgba=[0.42, 0.43, 0.45, 1],
                **vis,
            )
    top = t / 2 + 0.0004
    tags = o.get('tags') or {}
    side = tags.get('size', 0.05)
    for tag_id, tg in tags.items():
        if tag_id == 'size':
            continue
        name = f'{o["name"]}_tag{tag_id}'
        spec.add_texture(name=name, type=mujoco.mjtTexture.mjTEXTURE_2D, file=str(tag_png(int(tag_id))))
        mat = spec.add_material(name=name)
        mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = name
        h = side * 10 / 8 / 2  # the tile includes the white margin
        body.add_geom(
            name=name,
            type=GEOM.mjGEOM_BOX,
            size=[h, h, 0.0002],
            pos=[*tg['pos'], top + 0.0002],
            quat=quat_of(rot_z(np.radians(tg['yaw_deg']))),
            material=name,
            **vis,
        )
    line = o.get('line') or {}
    pts = np.asarray(line.get('points') or [], dtype=float)
    r = line.get('width', 0.003) / 2
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if np.linalg.norm(b - a) < 1e-4:
            continue
        body.add_geom(
            name=f'{o["name"]}_line{i}',
            type=GEOM.mjGEOM_CAPSULE,
            size=[r, 0, 0],
            rgba=line.get('rgba', [0.03, 0.03, 0.03, 1]),
            fromto=[*a, top + 0.0006, *b, top + 0.0006],
            **vis,
        )


def _add_box_object(spec, cfg: dict, o: dict) -> None:
    p, hs = o['pose'], o['size'] / 2
    z = _surface_z(cfg, (p['x'], p['y'])) + hs + 1e-4
    body = spec.worldbody.add_body(
        name=o['name'], pos=[p['x'], p['y'], z], quat=quat_of(rot_z(np.radians(p['yaw_deg'])))
    )
    body.add_freejoint()
    body.add_geom(
        name=o['name'], type=GEOM.mjGEOM_BOX, size=[hs, hs, hs], rgba=o['rgba'], friction=[o['friction'], 0.005, 0.0001]
    )
    _inertia(body, o['mass'], [hs, hs, hs])


def _add_sheet(spec, cfg: dict, o: dict) -> None:
    """A printed sheet (e.g. a calibration board) lying on whatever is under it: a thin textured plate.
    o: size [x, y] (m), image (file of the print, its top edge along +y), pose, optional thickness."""
    p, t = o['pose'], o.get('thickness', 0.0004)
    z = _surface_z(cfg, (p['x'], p['y'])) + 0.001 + t / 2  # above the board's drawn layers (tags, line)
    body = spec.worldbody.add_body(
        name=o['name'], pos=[p['x'], p['y'], z], quat=quat_of(rot_z(np.radians(p['yaw_deg'])))
    )
    body.add_freejoint()
    _inertia(body, o.get('mass', 0.005), [o['size'][0] / 2, o['size'][1] / 2, t / 2])
    spec.add_texture(name=o['name'], type=mujoco.mjtTexture.mjTEXTURE_2D, file=str(o['image']))
    mat = spec.add_material(name=o['name'])
    mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = o['name']
    body.add_geom(
        name=o['name'],
        type=GEOM.mjGEOM_BOX,
        size=[o['size'][0] / 2, o['size'][1] / 2, t / 2],
        material=o['name'],
        contype=0,
        conaffinity=0,
    )


OBJECT_TYPES = {'board': _add_board, 'box': _add_box_object, 'sheet': _add_sheet}


def make_scene_hook(cfg: dict, model: RobotModel):
    """A function for ``SimBackend(scene=...)`` that adds the base and the objects to the arm's MuJoCo spec."""

    def add(spec) -> None:
        import pinocchio as pin

        base = cfg['base']
        world = spec.worldbody
        for b in spec.bodies:  # the library's capsules and tcp marker: hidden
            for g in b.geoms:
                g.group, g.rgba, g.castshadow = HIDDEN_GROUP, [0, 0, 0, 0], 0
            for site in b.sites:
                site.group, site.rgba = HIDDEN_GROUP, [0, 0, 0, 0]
        spec.visual.global_.offwidth, spec.visual.global_.offheight = 1920, 1440
        spec.visual.quality.shadowsize = 4096
        _add_box(spec, base)
        _add_lights(spec, base)

        # ---- arm: the library's capsules are hidden above; add the official meshes
        am = base['arm_meshes']
        mats = {}
        for mname, rgba in am['materials'].items():
            mats[mname] = spec.add_material(name=f'arm_{mname}', rgba=rgba, specular=0.3, shininess=0.3).name
        for bname, parts in am['links'].items():
            body = world if bname == 'world' else spec.body(bname)
            for mesh, mat in parts:
                if spec.mesh(f'arm_{mesh}') is None:
                    spec.add_mesh(name=f'arm_{mesh}', file=str(_mesh_file(ROOT / am['dir'], mesh)))
                body.add_geom(
                    name=f'arm_{bname}_{mesh}',
                    type=GEOM.mjGEOM_MESH,
                    meshname=f'arm_{mesh}',
                    material=mats[mat],
                    contype=0,
                    conaffinity=0,
                )

        # ---- tool: everything is given in the tool's own frame F_robot, placed on the flange by `mount`
        ts = base['tool_sim']
        flange = spec.body(model.link_name(model.flange_joint))
        T_flange = model.model.frames[model.flange_frame_id].placement  # flange frame in its joint's body frame
        T_mount = T_flange * pin.SE3(mat_of(ts['mount']['quat']), np.asarray(ts['mount']['pos'], dtype=float))

        def place(pos, quat=(1, 0, 0, 0)):
            T = T_mount * pin.SE3(mat_of(quat), np.asarray(pos, dtype=float))
            return T.translation.tolist(), quat_of(T.rotation)

        mesh_file = (Path(base['tool_file']).parent / ts['mesh']['file']).resolve()
        spec.add_mesh(name='tool_mesh', file=str(mesh_file), scale=[ts['mesh']['scale']] * 3)
        pos, quat = place([0, 0, 0])
        flange.add_geom(
            name='tool_mesh',
            type=GEOM.mjGEOM_MESH,
            meshname='tool_mesh',
            pos=pos,
            quat=quat,
            rgba=ts['mesh']['rgba'],
            contype=0,
            conaffinity=0,
        )
        tf = [base.get('tool_friction', 0.4), 0.005, 0.0001]
        hidden = dict(group=HIDDEN_GROUP, rgba=[0.9, 0.4, 0.2, 0.0], castshadow=0, friction=tf, priority=1)
        for c in ts.get('collision', []):
            if c['type'] == 'capsule':
                a, _ = place(c['fromto'][:3])
                b, _ = place(c['fromto'][3:])
                flange.add_geom(
                    name=f'tool_{c["name"]}',
                    type=GEOM.mjGEOM_CAPSULE,
                    size=[c['radius'], 0, 0],
                    fromto=[*a, *b],
                    **hidden,
                )
            else:
                pos, quat = place(c['pos'], c.get('quat', [1, 0, 0, 0]))
                gtype = {'cylinder': GEOM.mjGEOM_CYLINDER, 'box': GEOM.mjGEOM_BOX, 'sphere': GEOM.mjGEOM_SPHERE}[
                    c['type']
                ]
                flange.add_geom(
                    name=f'tool_{c["name"]}',
                    type=gtype,
                    size=list(c['size']) + [0] * (3 - len(c['size'])),
                    pos=pos,
                    quat=quat,
                    **hidden,
                )
        ph = ts.get('phone')
        if ph:
            zc = (ph['z'][0] + ph['z'][1]) / 2
            R_ph = mat_of(ph['quat'])
            pos, quat = place(np.asarray(ph['pos']) + R_ph[:, 2] * zc, ph['quat'])
            flange.add_geom(
                name='tool_phone',
                type=GEOM.mjGEOM_BOX,
                size=[*ph['half'], (ph['z'][1] - ph['z'][0]) / 2],
                pos=pos,
                quat=quat,
                rgba=ph['rgba'],
                friction=tf,
                priority=1,
                **({} if ph.get('collide', True) else dict(contype=0, conaffinity=0)),
            )

        # ---- cameras: the wrist camera rides on the flange; the overhead camera is fixed
        cams = base['cameras']
        wc = cams['wrist']
        if 'frame' in wc and wc['frame'] == 'flange':  # a measured pose given in the flange frame
            T = T_flange * pin.SE3(np.asarray(wc['R'], dtype=float), np.asarray(wc['pos'], dtype=float))
            wpos, wR = T.translation.tolist(), T.rotation
        else:
            wpos, wq = place(wc['pos'], wc['quat'])
            wR = mat_of(wq)
        _add_camera(flange, 'wrist', wpos, wR, wc['intrinsics'])
        tc = cams['top']
        _add_camera(world, 'top', tc['pos'], np.asarray(tc['R'], dtype=float), tc['intrinsics'])

        # ---- objects
        for o in cfg['objects'].values():
            OBJECT_TYPES[o['type']](spec, cfg, o)

        if base.get('renderer', 'classic') == 'filament':  # materials, photometric lights, renderer flags
            import twin_filament

            twin_filament.add_to_spec(spec, base)

    return add


# ------------------------------------------------------------------------------------------- box and lights
# Viewer groups: every face of the box has its own group, so the interactive viewer (sim/twin_view.py) can hide it
# with the number keys or the "Group enable" panel. Hiding only changes the viewer's picture: the walls do not collide
# and cast no shadows anyway, and render() (the two calibrated cameras, all offline pictures) always draws all of them.
BOX_GROUPS = {'front': 1, 'top': 2, 'left': 3, 'right': 3, 'back': 4}  # left and right share key 3
RENDER_GROUPS = (1, 1, 1, 1, 1, 0)  # what render() draws: all but hidden


def _mesh_file(folder: Path, name: str) -> Path:
    for ext in ('.STL', '.stl', '.obj'):
        if (folder / f'{name}{ext}').is_file():
            return folder / f'{name}{ext}'
    raise FileNotFoundError(f'arm mesh {name} missing in {folder}: run uv run python sim/fetch_arm_meshes.py')


def foil_png(contrast: float, cell_px: int = 6, size: int = 512) -> Path:
    """Grey crinkled-foil picture: mean FOIL_MEAN, relative spread ``contrast``, facets of about ``cell_px`` pixels,
    tiling seamlessly. Written once per setting."""
    ASSETS.mkdir(exist_ok=True)
    path = ASSETS / f'foil_{size}_{cell_px}_{contrast:.3f}.png'
    if not path.exists():
        rng = np.random.default_rng(7)
        img = np.zeros((size, size), np.float32)
        for scale, w in ((cell_px, 1.0), (3 * cell_px, 0.7), (12 * cell_px, 0.5)):  # facets, crinkles, folds
            n = max(2, size // scale)
            small = rng.normal(0, 1, (n, n)).astype(np.float32)
            big = cv2.resize(np.tile(small, (3, 3)), (3 * size, 3 * size), interpolation=cv2.INTER_CUBIC)
            img += w * big[size : 2 * size, size : 2 * size]
        img = (img - img.mean()) / img.std()
        cv2.imwrite(str(path), np.clip(255 * FOIL_MEAN * (1 + contrast * img), 0, 255).astype(np.uint8))
    return path


FOIL_MEAN = 0.84  # mean of the foil texture; the material colour is divided by it


def _add_box(spec, base: dict) -> None:
    """The photo box: the floor (collides) and six drawn-only faces, each in its viewer group (BOX_GROUPS)."""
    world = spec.worldbody
    box, fz, fl = base['box'], base['floor_z'], base['floor']
    (x0, x1), (y0, y1), top = box['x'], box['y'], box['top']
    # the floor plane collides everywhere; it is drawn only inside the box
    world.add_geom(
        name='floor',
        type=GEOM.mjGEOM_PLANE,
        size=[(x1 - x0) / 2, (y1 - y0) / 2, 0.05],
        pos=[(x0 + x1) / 2, (y0 + y1) / 2, fz],
        rgba=fl['rgba'],
        friction=[fl['friction'], 0.005, 0.0001],
        priority=1,
    )
    sv = box['silver']
    spec.add_material(name='silver_foil', rgba=sv['rgba'], specular=sv['specular'], shininess=sv['shininess'])
    if sv.get('crinkle', 0) > 0:  # MuJoCo multiplies the texture with the material colour
        cell = 6
        spec.add_texture(name='foil', type=mujoco.mjtTexture.mjTEXTURE_2D, file=str(foil_png(sv['crinkle'], cell)))
        mat = spec.material('silver_foil')
        mat.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = 'foil'
        mat.texuniform = True
        mat.texrepeat = [2 / (512 / cell * sv['crinkle_cell'])] * 2  # uniform 2-D mapping: texrepeat / 2 per metre
        rgba = np.asarray(sv['rgba'][:3], dtype=float) / FOIL_MEAN
        mat.rgba = (rgba / max(1.0, rgba.max())).tolist() + [1.0]  # keeps the hue if it would exceed 1
    spec.material('silver_foil').emission = sv.get('emission', 0.0)
    t = box.get('wall_thickness', 0.004)
    vis = dict(type=GEOM.mjGEOM_BOX, contype=0, conaffinity=0, castshadow=0)
    # each face is a thin box whose own z axis is the face's normal, so a 2-D texture lies flat on its large side
    turn = {
        'x': quat_of([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]),
        'y': quat_of([[1, 0, 0], [0, 0, 1], [0, -1, 0]]),
        'z': [1, 0, 0, 0],
    }

    def panel(name, normal, pos, half_u, half_v, face, **look):
        """A face across ``normal`` (x, y or z) at ``pos``; half_u, half_v: half sizes along the face's own x and y,
        which are (z, y) for a face across x, (x, z) across y and (x, y) across z (in the base frame)."""
        world.add_geom(
            name=name,
            size=[half_u, half_v, t / 2],
            pos=list(pos),
            quat=turn[normal],
            group=BOX_GROUPS[face],
            **look,
            **vis,
        )

    h = (top - fz) / 2
    xc, yc, zc = (x0 + x1) / 2, (y0 + y1) / 2, fz + h
    foil = dict(material='silver_foil')
    back = foil if box.get('back', 'backdrop') == 'silver' else dict(rgba=fl['rgba'])
    panel('wall_back', 'x', [x1 + t / 2, yc, zc], h, (y1 - y0) / 2 + t, 'back', **back)
    panel('wall_left', 'y', [xc, y1 + t / 2, zc], (x1 - x0) / 2, h, 'left', **foil)
    panel('wall_right', 'y', [xc, y0 - t / 2, zc], (x1 - x0) / 2, h, 'right', **foil)
    panel('wall_top', 'z', [xc, yc, top + t / 2], (x1 - x0) / 2 + t, (y1 - y0) / 2 + t, 'top', **foil)
    # operator-side face: silver cloth around a rectangular opening (four panels), or closed
    fr = box.get('front') or {}
    op = fr.get('opening', 'closed')
    fx = x0 - t / 2
    if op in ('closed', None):
        rects = [((y0, y1), (fz, top))]
    else:
        (oy0, oy1), (oz0, oz1) = op['y'], op['z']
        rects = [((y0, y1), (fz, oz0)), ((y0, y1), (oz1, top)), ((y0, oy0), (oz0, oz1)), ((oy1, y1), (oz0, oz1))]
        if fr.get('outside_rgba'):  # the room seen through the opening, as a flat colour
            spec.add_material(name='outside', rgba=fr['outside_rgba'], emission=1.0, specular=0.0)  # not lit by the box
            panel(
                'wall_front_outside',
                'x',
                [x0 - 0.40, (oy0 + oy1) / 2, (fz - 0.6 + oz1 + 0.2) / 2],
                (oz1 + 0.8 - fz) / 2,
                (oy1 - oy0) / 2 + 0.2,
                'front',
                material='outside',
            )
    for k, ((a, b), (c, d)) in enumerate(rects):
        if b - a > 1e-4 and d - c > 1e-4:
            panel(f'wall_front{k}', 'x', [fx, (a + b) / 2, (c + d) / 2], (d - c) / 2, (b - a) / 2, 'front', **foil)
    # diffusion cloth under the light strips: a softly glowing white panel
    cl = box['cloth']
    spec.add_material(name='cloth', rgba=cl['rgba'], emission=cl['emission'], specular=0.0)
    panel('wall_top_cloth', 'z', [xc, yc, cl['z']], (x1 - x0) / 2, (y1 - y0) / 2, 'top', material='cloth')


def _add_lights(spec, base: dict) -> None:
    """LED strips behind the cloth: a few wide spot lights each (one casts a shadow), fill light from the silver walls, and
    ambient light. MuJoCo has no bounced light, so the fill and ambient lights stand in for it (8 lights at most)."""
    world, lt, box, fz = spec.worldbody, base['lights'], base['box'], base['floor_z']
    spec.visual.headlight.ambient = [lt['ambient']] * 3
    spec.visual.headlight.diffuse = [0.0] * 3
    spec.visual.headlight.specular = [0.0] * 3
    spec.add_material(name='strip', rgba=[1, 1, 1, 1], emission=1.0)
    for k, x in enumerate(lt['strips_x']):
        world.add_geom(
            name=f'wall_top_strip{k}',
            type=GEOM.mjGEOM_BOX,
            size=[0.012, lt['length'] / 2, 0.003],
            pos=[x, 0, lt['z']],
            material='strip',
            contype=0,
            conaffinity=0,
            castshadow=0,
            group=BOX_GROUPS['top'],
        )
        ys = np.linspace(-lt['length'] / 2, lt['length'] / 2, lt['per_strip'] + 2)[1:-1]
        for j, y in enumerate(ys):
            world.add_light(
                name=f'strip{k}_{j}',
                pos=[x, float(y), lt['z'] - 0.01],
                dir=[0, 0, -1],
                diffuse=[lt['diffuse']] * 3,
                specular=[0.1] * 3,
                cutoff=lt.get('cutoff', 85),
                exponent=lt.get('exponent', 2),
                castshadow=bool(lt['shadows']) and j == 0,
            )
    (x0, x1), (y0, y1), top = box['x'], box['y'], box['top']
    xc, zc = (x0 + x1) / 2, fz + 0.45 * (top - fz)
    f = lt.get('fill', 0.0)
    if f > 0:  # from the left, right and back walls towards the middle of the floor
        for name, pos in (
            ('fill_left', [xc, y1 - 0.02, zc]),
            ('fill_right', [xc, y0 + 0.02, zc]),
            ('fill_back', [x1 - 0.02, 0, zc]),
        ):
            d = np.array([xc - 0.05, 0.0, fz]) - np.array(pos)
            world.add_light(
                name=name,
                pos=pos,
                dir=(d / np.linalg.norm(d)).tolist(),
                diffuse=[f] * 3,
                specular=[0.0] * 3,
                cutoff=88,
                exponent=1,
                castshadow=False,
            )


def _add_camera(body, name: str, pos, R_cv, intr: dict) -> None:
    """A camera with the given pinhole intrinsics (focal length and principal point in pixels)."""
    cam = body.add_camera(name=name, pos=list(pos), quat=mj_camera_quat(R_cv))
    w, h = intr['width'], intr['height']
    cam.resolution = [w, h]
    cam.sensor_size = [w * 1e-3, h * 1e-3]  # any size: with it MuJoCo uses focal_pixel / principal_pixel
    cam.focal_pixel = [intr['fx'], intr['fy']]
    # MuJoCo draws the principal point at (w/2 - 0.5 - px, h/2 - 0.5 - py) in pixel-centre coordinates (checked by
    # rendering points of known position), so this puts it at (cx, cy) like the pinhole model of project()
    cam.principal_pixel = [w / 2 - 0.5 - intr['cx'], h / 2 - 0.5 - intr['cy']]


def make_arm(cfg: dict | None = None, **backend_kwargs) -> Arm:
    """The arm on the simulator with the twin around it. Use it like the real one (``with make_arm() as arm: ...``)."""
    cfg = cfg or load_config()
    base = cfg['base']
    cal = ROOT / base['calibration']
    model = RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(base['tool_file']))
    arm = Arm.from_config(
        'b601_rs',
        tool=base['tool_file'],
        calibration=str(cal) if cal.is_file() else None,
        backend='sim',
        scene=make_scene_hook(cfg, model),
        **backend_kwargs,
    )
    arm.twin = cfg
    return arm


# ------------------------------------------------------------------------------------------------------ queries
def render(arm: Arm, camera: str, scale: float = 1.0, segmentation: bool = False, raw: bool = False) -> np.ndarray:
    """RGB image (or geom-id image with ``segmentation``) from "top" or "wrist" at the arm's current simulated state.

    ``scale`` < 1 renders a smaller picture with the same field of view (cheaper). The whole closed box is always drawn
    (whatever a viewer hides). The camera's tone (base.camera_tone: exposure, white balance and gamma of the phone,
    fitted to real frames) is applied unless ``raw``. The renderer is the one the twin was built for
    (base.renderer: classic, or filament, see sim/twin_filament.py); segmentation always comes from the classic one."""
    m, d = arm.backend.mj_model, arm.backend.mj_data
    intr = arm.twin['base']['cameras'][camera]['intrinsics']
    w, h = int(round(intr['width'] * scale)), int(round(intr['height'] * scale))
    base = arm.twin['base']
    if base.get('renderer', 'classic') == 'filament' and not segmentation:
        fr = arm.__dict__.get('_filament')
        if fr is None:
            import twin_filament

            fr = arm.__dict__['_filament'] = twin_filament.FilamentRenderer(m, RENDER_GROUPS)
        img = fr.render(d, camera, w, h)
        tone = (base['filament'].get('camera_tone') or {}).get(camera)
        return img if raw or not tone else apply_tone(img, tone)
    key = (camera, w, h)
    renderers = arm.__dict__.setdefault('_renderers', {})
    if key not in renderers:
        renderers[key] = mujoco.Renderer(m, h, w)
    opt = arm.__dict__.get('_render_opt')
    if opt is None:
        opt = arm.__dict__['_render_opt'] = mujoco.MjvOption()
        opt.geomgroup[:] = RENDER_GROUPS
    r = renderers[key]
    if segmentation:
        r.enable_segmentation_rendering()
    r.update_scene(d, camera=camera, scene_option=opt)
    img = r.render().copy()
    if segmentation:
        r.disable_segmentation_rendering()
        return img[..., 0]
    tone = (arm.twin['base'].get('camera_tone') or {}).get(camera)
    return img if raw or not tone else apply_tone(img, tone)


_TONE_LUTS: dict = {}


def apply_tone(img: np.ndarray, tone: dict) -> np.ndarray:
    """A phone camera's response on a rendered picture: the renderer's output is taken as linear light (or decoded from
    sRGB with ``input: srgb``), scaled by the exposure and the white balance (``gain``, per channel R, G, B) and encoded
    with ``gamma``."""
    k = (tuple(tone['gain']), tone['gamma'], tone.get('input', 'linear'))
    lut = _TONE_LUTS.get(k)
    if lut is None:  # one lookup table per channel
        x = np.arange(256) / 255.0
        if tone.get('input') == 'srgb':  # a picture already encoded as sRGB (Filament): back to linear light
            x = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
        lut = _TONE_LUTS[k] = (
            np.stack(
                [np.clip(255 * np.clip(g * x, 0, 1) ** (1 / tone['gamma']) + 0.5, 0, 255) for g in tone['gain']],
                axis=-1,
            )
            .astype(np.uint8)
            .reshape(256, 1, 3)
        )
    return cv2.LUT(np.ascontiguousarray(img), lut)


def camera_pose(arm: Arm, camera: str) -> tuple[np.ndarray, np.ndarray]:
    """Position and OpenCV axes (columns: right, down, forward) of a camera in the arm's base frame."""
    m, d = arm.backend.mj_model, arm.backend.mj_data
    i = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_CAMERA, camera)
    R = d.cam_xmat[i].reshape(3, 3)
    return d.cam_xpos[i].copy(), np.column_stack([R[:, 0], -R[:, 1], -R[:, 2]])


def project(arm: Arm, camera: str, points, scale: float = 1.0) -> np.ndarray:
    """Pixel positions of 3-D points (base frame) in a camera, with the same pinhole model as its rendering."""
    pos, R = camera_pose(arm, camera)
    cam = arm.twin['base']['cameras'][camera]
    K = intrinsics_matrix(cam['intrinsics'], scale)
    c = (np.atleast_2d(points) - pos) @ R
    if cam.get('dist') is not None:  # a calibrated lens (the renderer itself stays a pinhole)
        uv, _ = cv2.projectPoints(
            np.asarray(c, dtype=np.float64), np.zeros(3), np.zeros(3), K, np.asarray(cam['dist'], dtype=float)
        )
        uv = uv.reshape(-1, 2)
        uv[c[:, 2] <= 0] = np.nan
        return uv
    uv = (c / c[:, 2:3]) @ K.T
    return uv[:, :2]


def robot_geoms(arm: Arm) -> np.ndarray:
    """Ids of the geoms that draw the arm and the tool (for masking them out of a picture)."""
    m = arm.backend.mj_model
    names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) or '' for i in range(m.ngeom)]
    return np.array([i for i, n in enumerate(names) if n.startswith(('arm_', 'tool_'))])


def body_id(arm: Arm, name: str) -> int:
    return mujoco.mj_name2id(arm.backend.mj_model, mujoco.mjtObj.mjOBJ_BODY, name)


def object_pose(arm: Arm, name: str) -> tuple[np.ndarray, np.ndarray]:
    """Position and rotation matrix of a scene object."""
    d, i = arm.backend.mj_data, body_id(arm, name)
    return d.xpos[i].copy(), d.xmat[i].reshape(3, 3).copy()


def set_object_pose(arm: Arm, name: str, x: float, y: float, yaw_deg: float, z: float | None = None) -> None:
    """Move a free object (keeps its height unless ``z`` is given) and stop it."""
    m, d = arm.backend.mj_model, arm.backend.mj_data
    j = m.body_jntadr[body_id(arm, name)]
    a, v = m.jnt_qposadr[j], m.jnt_dofadr[j]
    d.qpos[a : a + 3] = [x, y, d.qpos[a + 2] if z is None else z]
    d.qpos[a + 3 : a + 7] = quat_of(rot_z(np.radians(yaw_deg)))
    d.qvel[v : v + 6] = 0
    mujoco.mj_forward(m, d)


def yaw_of(R) -> float:
    return float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))


# -------------------------------------------------------------------------------------------------------- CLI
def cmd_render(args) -> int:
    sys.path.insert(0, str(ROOT / 'robot'))
    from tags import detect

    state = load_state(args.episode) if args.episode else None
    cfg = load_config(state=state)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    q = np.radians(args.q_deg) if args.q_deg else np.asarray(state['q0']) if state else None
    tool = ToolConfig.load(cfg['base']['tool_file'])
    with make_arm(cfg, q0=None) as arm:
        arm.backend.set_q(q if q is not None else np.radians(tool.home))
        for cam in ('top', 'wrist'):
            img = render(arm, cam, scale=args.scale)
            path = out / f'twin-{cam}.png'
            cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            seen = detect(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            print(f'{cam}: {path}  tags seen: {sorted(seen)}')
    return 0


def cmd_view(args) -> int:
    os.environ['MUJOCO_GL'] = 'glfw'
    state = load_state(args.episode) if args.episode else None
    with make_arm(load_config(state=state), viewer=True) as arm:
        arm.enable()
        arm.move_home()
        print('viewer open; close its window to end')
        while arm.backend.viewer is not None and arm.backend.viewer.is_running():
            arm.wait(0.5)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('render', help="render both cameras (at the tool's home pose, or an episode's first pose)")
    s.add_argument('--out', default='/tmp/asfinger-twin')
    s.add_argument('--episode', help="use this episode's start state (data/derived/twin/<episode>/state.yaml)")
    s.add_argument('--q-deg', type=float, nargs=6, help='joint angles (deg)')
    s.add_argument('--scale', type=float, default=1.0, help="picture size relative to the real camera's")
    s.set_defaults(func=cmd_render)
    s = sub.add_parser('view', help="interactive viewer (sim/twin_view.py can also hide the box's faces and replay)")
    s.add_argument('--episode')
    s.set_defaults(func=cmd_view)
    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
