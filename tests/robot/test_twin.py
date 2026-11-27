"""The twin scene (sim/twin.py): what can be checked without the arm meshes and without a GL context, and, where the
meshes were fetched, that the scene compiles. Rendering is checked in test_local_data.py."""

import hashlib
import importlib.util
import os
import re
import sys

import pytest

pytest.importorskip('rebot_control')
pytest.importorskip('mujoco')
yaml = pytest.importorskip('yaml')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIM = os.path.join(ROOT, 'sim')
MESHES = os.path.join(SIM, 'assets', 'meshes', 'b601_rs_official')
HAVE_MESHES = os.path.isfile(os.path.join(MESHES, 'base_link.STL'))


def module(name):
    spec = importlib.util.spec_from_file_location(f'{name}_under_test', os.path.join(SIM, f'{name}.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def twin(monkeypatch):
    monkeypatch.setenv('MUJOCO_GL', 'disable')  # the module would ask for EGL otherwise; nothing is rendered here
    monkeypatch.delenv('ASFINGER_DATA', raising=False)
    monkeypatch.syspath_prepend(SIM)
    return module('twin')


def test_checksum_list_and_the_scene_agree():
    with open(os.path.join(MESHES, 'SHA256SUMS'), encoding='utf-8') as f:
        lines = [line.split() for line in f if line.strip()]
    assert len(lines) == 19 and all(len(parts) == 2 and re.fullmatch(r'[0-9a-f]{64}', parts[0]) for parts in lines)
    names = {name for _, name in lines}
    assert 'LICENSE' in names and len(names) == 19
    with open(os.path.join(SIM, 'twin.yaml'), encoding='utf-8') as f:
        arm = yaml.safe_load(f)['base']['arm_meshes']
    used = {mesh for parts in arm['links'].values() for mesh, _ in parts}
    assert {f'{m}.STL' for m in used} == names - {'LICENSE'}  # every mesh of the scene is fetched, and nothing else
    assert {material for parts in arm['links'].values() for _, material in parts} <= set(arm['materials'])
    assert arm['dir'] == 'sim/assets/meshes/b601_rs_official'


def test_fetch_knows_where_each_file_is_upstream():
    fetch = module('fetch_arm_meshes')
    assert re.fullmatch(r'[0-9a-f]{40}', fetch.COMMIT) and fetch.REPO == 'Seeed-Projects/reBot-DevArm'
    assert fetch.upstream_path('LICENSE') == 'LICENSE'
    assert fetch.upstream_path('link6.STL') == 'Rebot_Arm_description/RS/meshes/shared/link6.STL'
    assert fetch.upstream_path('cnc2.STL') == 'Rebot_Arm_description/RS/meshes/visual/cnc2.STL'
    assert set(fetch.expected()) == {n for n in fetch.expected() if n == 'LICENSE' or n.endswith('.STL')}


def test_fetch_check_and_a_source_with_wrong_content(tool, tmp_path):
    r = tool('sim/fetch_arm_meshes.py', '--out', str(tmp_path / 'none'), '--check')
    assert r.returncode == 1 and '0 of 19 files match SHA256SUMS' in r.stdout
    # a local "clone" whose files are not the pinned ones: nothing is kept
    clone = tmp_path / 'clone' / 'Rebot_Arm_description' / 'RS' / 'meshes' / 'shared'
    clone.mkdir(parents=True)
    (clone / 'base_link.STL').write_bytes(b'not the mesh')
    out = tmp_path / 'out'
    r = tool('sim/fetch_arm_meshes.py', '--from', str(tmp_path / 'clone'), '--out', str(out))
    assert r.returncode == 1 and 'checksum differs from SHA256SUMS' in r.stderr
    assert os.listdir(out) == []


@pytest.mark.skipif(not HAVE_MESHES, reason='the arm meshes are not fetched (sim/fetch_arm_meshes.py)')
def test_fetched_meshes_match_the_list():
    with open(os.path.join(MESHES, 'SHA256SUMS'), encoding='utf-8') as f:
        for digest, name in (line.split() for line in f if line.strip()):
            with open(os.path.join(MESHES, name), 'rb') as mesh:
                assert hashlib.sha256(mesh.read()).hexdigest() == digest, name


def test_data_folder_is_the_repository_one_unless_the_variable_says_otherwise(twin, monkeypatch, tmp_path):
    assert str(twin.EPISODES) == os.path.join(ROOT, 'data', 'episodes')  # where robot/episode.py records
    assert str(twin.DERIVED) == os.path.join(ROOT, 'data', 'derived', 'twin')
    monkeypatch.setenv('ASFINGER_DATA', str(tmp_path))
    other = module('twin')
    assert str(other.EPISODES) == str(tmp_path / 'episodes') and str(other.DERIVED) == str(
        tmp_path / 'derived' / 'twin'
    )
    sys.path.insert(0, os.path.join(ROOT, 'robot'))
    try:
        import episode

        assert str(episode.DATA) == str(twin.EPISODES)
    finally:
        sys.path.remove(os.path.join(ROOT, 'robot'))
        sys.modules.pop('episode', None)


def test_messages_when_something_is_not_there(twin, tmp_path):
    with pytest.raises(FileNotFoundError, match='run uv run python sim/fetch_arm_meshes.py'):
        twin._mesh_file(tmp_path, 'base_link')
    with pytest.raises(FileNotFoundError, match='not part of this repository yet'):
        twin.load_state('20000101-000000-none')
    if not HAVE_MESHES:
        with pytest.raises(FileNotFoundError, match='arm mesh base_link missing'):
            twin.load_config()


def test_filament_needs_mujoco_4(twin, monkeypatch):
    filament = module('twin_filament')
    filament.require_filament()  # the locked mujoco is 4.x
    monkeypatch.setattr(filament.mujoco, '__version__', '3.2.6')
    with pytest.raises(RuntimeError, match=r'needs mujoco >= 4\.0 \(installed: 3\.2\.6\)'):
        filament.require_filament()
    with pytest.raises(RuntimeError, match='base.renderer: classic'):
        filament.context()


@pytest.mark.skipif(not HAVE_MESHES, reason='the arm meshes are not fetched (sim/fetch_arm_meshes.py)')
def test_scene_compiles_with_the_cameras_and_the_objects(twin):
    cfg = twin.load_config()
    base = cfg['base']
    assert base['cameras']['top']['intrinsics'] == {
        'width': 1920,
        'height': 1440,
        'fx': 766.0,
        'fy': 766.0,
        'cx': 956.6,
        'cy': 720.2,
    }
    assert base['cameras']['wrist']['intrinsics']['width'] == 640 and 'pos' in base['cameras']['top']
    assert base['table_z'] == pytest.approx(0.0197) and cfg['objects']['whiteboard']['thickness'] == pytest.approx(
        0.0197
    )
    with twin.make_arm(cfg) as arm:
        m = arm.backend.mj_model
        assert m.nmesh >= 18  # the arm's parts, drawn only
        position, _ = twin.object_pose(arm, 'cube')
        assert position[0] == pytest.approx(0.30, abs=0.01) and position[2] == pytest.approx(0.0197 + 0.02, abs=0.003)
        twin.set_object_pose(arm, 'cube', 0.35, 0.05, 30.0)
        position, rotation = twin.object_pose(arm, 'cube')
        assert position[:2] == pytest.approx([0.35, 0.05], abs=1e-6) and twin.yaw_of(rotation) == pytest.approx(
            30.0, abs=1e-6
        )
        K = twin.intrinsics_matrix(base['cameras']['top']['intrinsics'], 0.5)
        assert K[0, 0] == pytest.approx(383.0) and K[0, 2] == pytest.approx(478.3)


def test_camera_poses_and_board_geometry_come_from_the_scene_file(twin, monkeypatch, tmp_path):
    """They are parameters of one reference setup in sim/twin.yaml. A local registration file overrides them."""
    monkeypatch.setattr(twin, '_mesh_file', lambda folder, name: folder / name)  # no meshes needed for the config
    assert not [f for f in os.listdir(SIM) if f == 'twin_registration.yaml' and _tracked(f'sim/{f}')]
    cfg = twin.load_config(registration=None)
    cams, board = cfg['base']['cameras'], cfg['objects']['whiteboard']
    assert cams['top']['pos'] == [0.54162, -0.1436, 0.78305] and len(cams['top']['R']) == 3
    assert cams['wrist']['frame'] == 'flange' and cams['wrist']['pos'] == [0.03837, -0.02582, 0.10714]
    assert cams['wrist']['intrinsics']['width'] == 640  # the intrinsics still come from the tool file
    assert board['white'] == [0.26932, 0.36888] and board['frame'] == 0.015
    assert board['tags'][1] == {'pos': [0.0984, 0.1451], 'yaw_deg': -88.75} and board['tags']['size'] == 0.05
    assert 'registration' not in cfg
    assert (
        twin.load_config(registration=tmp_path / 'absent.yaml')['base']['cameras']['top']['pos'] == cams['top']['pos']
    )

    local = tmp_path / 'twin_registration.yaml'
    local.write_text(
        'default_session: a\n'
        'top_camera:\n'
        '  a: {pos: [0.5, 0.0, 0.8], R: [[1, 0, 0], [0, -1, 0], [0, 0, -1]]}\n'
        '  b: {pos: [0.6, 0.1, 0.7], R: [[1, 0, 0], [0, -1, 0], [0, 0, -1]]}\n'
        'board_white: [0.2, 0.3]\n'
        'board_tags: {1: {pos: [0.05, 0.1], yaw_deg: 0.0}}\n'
        'wrist_camera: {pos: [0.01, 0.02, 0.03]}\n'
    )
    over = twin.load_config(registration=local)
    assert over['base']['cameras']['top']['pos'] == [0.5, 0.0, 0.8] and over['base']['cameras']['top']['session'] == 'a'
    assert twin.load_config(registration=local, session='b')['base']['cameras']['top']['pos'] == [0.6, 0.1, 0.7]
    assert (
        over['base']['cameras']['wrist']['pos'] == [0.01, 0.02, 0.03]
        and over['base']['cameras']['wrist']['frame'] == 'flange'
    )
    assert over['objects']['whiteboard']['white'] == [0.2, 0.3]
    assert over['objects']['whiteboard']['tags'][1]['pos'] == [0.05, 0.1]
    assert over['objects']['whiteboard']['tags'][2]['pos'] == [
        -0.093,
        -0.1482,
    ]  # what the local file does not give stays


def _tracked(path):
    import subprocess

    return subprocess.run(['git', 'ls-files', '--error-unmatch', path], cwd=ROOT, capture_output=True).returncode == 0
