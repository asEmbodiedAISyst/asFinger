"""Filament rendering of the twin (MuJoCo 4.0's physically based renderer, mujoco.mjrf), as an alternative to MuJoCo's
classic OpenGL renderer. sim/twin.py uses it when twin.yaml says `base.renderer: filament` (or render(..., renderer=
"filament")); the classic renderer stays the default.

What it adds to the scene (only when the twin is built for Filament; see twin.yaml base.filament):
- physically based materials (metallic, roughness) for the box's cloth, the floor, the whiteboard and the arm;
- photometric lights: the strips' spot lights in candela with a bulb radius (soft PCSS shadows), the fill lights, and an
  image light (a two-colour environment cube) for the light the box bounces around: white from the cloth and the walls,
  backdrop-coloured from below;
- Filament's screen-space ambient occlusion, tone mapping and colour grading (custom `filament.*` flags).
The cameras are the same MuJoCo cameras (same intrinsics); segmentation pictures still come from the classic renderer,
which draws the same geometry.

Notes from the MuJoCo docs (doc/programming/rendering.rst of the installed package): `mujoco.studio.window` must be
imported before the context is created (it registers Filament's material files); if any light has a positive
intensity, all lights are photometric, the headlight is off and there is no ambient light except an image light.
"""

from __future__ import annotations

import mujoco
import numpy as np

_CTX = None  # one Filament context per process (it starts a render thread)


def require_filament() -> None:
    """Filament came with MuJoCo 4.0: say so, instead of failing somewhere inside an older version."""
    if int(mujoco.__version__.split('.')[0]) < 4:
        raise RuntimeError(
            f'the Filament renderer needs mujoco >= 4.0 (installed: {mujoco.__version__}); '
            'use `base.renderer: classic` in sim/twin.yaml'
        )


def context():
    global _CTX
    require_filament()
    if _CTX is None:
        import mujoco.studio.window  # noqa: F401  (registers the Filament asset providers: pbr.filamat, ...)
        from mujoco import mjrf

        _CTX = mjrf.Context(mjrf.ContextConfig())  # headless (Vulkan on a Linux computer with a GPU)
    return _CTX


def add_to_spec(spec, base: dict) -> None:
    """Materials, light intensities, the environment light and the Filament flags (called after the scene is built)."""
    require_filament()
    fl = base['filament']
    mats = fl.get('materials', {})

    def pbr(name, rgba, look):
        m = spec.material(name) or spec.add_material(name=name, rgba=rgba)
        m.metallic, m.roughness = float(look['metallic']), float(look['roughness'])
        if 'albedo_scale' in look:  # this renderer's own brightness of the colour (tuned)
            m.rgba = [min(1.0, c * look['albedo_scale']) for c in m.rgba[:3]] + [m.rgba[3]]
        return m.name

    # the box's cloth (silver_foil material), the arm's materials and the cloth panel
    if 'cloth' in mats and spec.material('silver_foil') is not None:
        pbr('silver_foil', None, mats['cloth'])
    for mname in base['arm_meshes']['materials']:
        key = 'arm_silver' if mname == 'silver' else 'arm_black' if 'black' in mname else 'arm_plastic'
        if key in mats:
            pbr(f'arm_{mname}', None, mats[key])
    # geoms coloured by rgba only: give them a material so they are shaded physically
    by_geom = {
        'floor': 'floor',
        'whiteboard_white': 'board',
        'whiteboard_top': 'board',
        'whiteboard_body': 'board_frame',
        'wall_back': 'backdrop',
        'cube': 'cube',
    }
    for g in spec.geoms:
        key = by_geom.get(g.name)
        if key and key in mats and not g.material:
            g.material = pbr(f'pbr_{g.name}', list(g.rgba), mats[key])
            g.rgba = [0.5, 0.5, 0.5, 1]  # MuJoCo's default: the material's colour is used

    # lights: photometric intensities (candela)
    lt = fl['lights']
    for light in spec.lights:
        if light.name.startswith('strip'):
            light.intensity = lt['strip_cd']
            light.bulbradius = lt.get('bulb_radius', 0.1)
        elif light.name.startswith('fill'):
            light.intensity = lt['fill_cd']
    env = fl['environment']
    tex = spec.add_texture(
        name='env',
        type=mujoco.mjtTexture.mjTEXTURE_CUBE,
        builtin=mujoco.mjtBuiltin.mjBUILTIN_FLAT,
        rgb1=env['around'],
        rgb2=env['below'],
        width=64,
        height=64,
    )
    spec.worldbody.add_light(
        name='environment',
        type=mujoco.mjtLightType.mjLIGHT_IMAGE,
        texture=tex.name,
        intensity=env['intensity'],
        castshadow=False,
        pos=[0, 0, 1],
        dir=[0, 0, -1],
    )

    # renderer flags (doc: "Rendering options")
    for key, val in (fl.get('flags') or {}).items():
        if isinstance(val, str):
            spec.add_text(name=f'filament.{key}', data=val)
        else:
            spec.add_numeric(name=f'filament.{key}', data=np.atleast_1d(np.asarray(val, dtype=float)).tolist())


class FilamentRenderer:
    """Renders an arm's MuJoCo model with Filament from its cameras; keeps the retained scene between calls."""

    def __init__(self, model: mujoco.MjModel, groups):
        from mujoco import mjrf
        from mujoco.rendering.filament import model_scene, renderer

        self.mjrf, self.view = mjrf, renderer.View
        self.r = renderer.Renderer(context())
        self.scene = model_scene.ModelScene(self.r.context, model, self.r.scene('twin'))
        self.groups = tuple(groups)
        self.buffers: dict = {}
        self.model = model

    def render(
        self, data: mujoco.MjData, camera: str | mujoco.MjvCamera, width: int, height: int, groups=None
    ) -> np.ndarray:
        """RGB picture from a named model camera (its calibrated intrinsics) or a free MjvCamera; ``groups``: geom groups to
        draw (default: those given at construction)."""
        opt = mujoco.MjvOption()
        opt.geomgroup[:] = self.groups if groups is None else groups
        self.scene._renderables.set_options(opt)
        self.scene.update(data)
        key = (width, height)
        if key not in self.buffers:
            self.buffers[key] = np.zeros((height, width, 3), np.uint8)
            self.r.target(f't{width}x{height}', self.buffers[key])
        if isinstance(camera, str):
            cam = mujoco.MjvCamera()
            cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
            cam.fixedcamid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, camera)
        else:
            cam = camera
        gl = mujoco.mjv_camera2GLCamera(self.model, data, cam)
        # all frustum fields, including the horizontal centre and width (the principal point and focal length of the
        # calibrated cameras); renderer.View's own conversion leaves those two out
        c = self.mjrf.Camera(
            pos=gl.pos,
            forward=gl.forward,
            up=gl.up,
            frustum_center=gl.frustum_center,
            frustum_width=gl.frustum_width,
            frustum_bottom=gl.frustum_bottom,
            frustum_top=gl.frustum_top,
            frustum_near=gl.frustum_near,
            frustum_far=gl.frustum_far,
        )
        self.r.render([self.view(scene='twin', target=f't{width}x{height}', camera=c, skybox=False, headlight=False)])
        return self.buffers[key].copy()
