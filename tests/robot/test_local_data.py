"""Checks that need files which are not in the repository: the raw calibration measurements and the pictures of the
real scene in calibration/data, and a GL context for rendering. They run where those files exist and are skipped
elsewhere (for example in CI)."""

import os

import pytest

pytest.importorskip('rebot_control')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, 'calibration', 'data')


def need(*names):
    missing = [n for n in names if not os.path.isfile(os.path.join(DATA, n))]
    if missing:
        pytest.skip(f'not in the repository: calibration/data/{missing[0]}')


def test_refit_gravity_from_saved_poses(tool):
    need('gravity-wide-20261116-163218.npz', 'gravity-board-20261116-165455.npz')
    r = tool(
        'robot/arm_calib_gravity.py',
        '--from-data',
        'calibration/data/gravity-wide-20261116-163218.npz',
        'calibration/data/gravity-board-20261116-165455.npz',
        '--no-save',
    )
    assert r.returncode == 0, r.stderr
    assert 'fitting 39 poses from 2 file(s)' in r.stdout


def test_refit_ripple_and_table_from_saved_data(tool):
    need('ripple-20261117-012200.npz', 'table-20261116-235858.npz')
    r = tool('robot/arm_calib_ripple.py', '--from-data', 'calibration/data/ripple-20261117-012200.npz', '--no-save')
    assert r.returncode == 0, r.stderr
    r = tool('robot/arm_touch_table.py', '--from-data', 'calibration/data/table-20261116-235858.npz', '--no-save')
    assert r.returncode == 0, r.stderr
    assert 'mean +19.7 mm, from +19.2 to +20.6 mm over 3 touches' in r.stdout


def test_registration_and_render_against_the_real_pictures(tool, tmp_path):
    need('scene-top-20261116.jpg', 'scene-wrist-20261116.png')
    r = tool('sim/register.py')
    assert r.returncode == 0, r.stderr
    assert 'nothing written (add --write)' in r.stdout
    gl = os.environ.get('ASFINGER_TEST_GL')  # e.g. glfw on macOS, egl on a Linux computer with a GPU
    if not gl:
        pytest.skip('set ASFINGER_TEST_GL to a MuJoCo GL backend to render')
    r = tool('sim/scene.py', 'render', '--out', str(tmp_path), '--compare', env={'MUJOCO_GL': gl})
    assert r.returncode == 0, r.stderr
    assert r.stdout.count('simulated vs real corner positions differ by') == 8
    assert os.path.isfile(tmp_path / 'sim-top.png') and os.path.isfile(tmp_path / 'sim-wrist.png')
