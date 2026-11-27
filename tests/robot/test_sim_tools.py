"""The arm tools in the simulator (--sim): the same code paths as on the arm, with rebot-control's simulated motors.
No arm, no phone, no GL context. What a test asserts are the messages and exit codes of the tools; the numbers of a
simulated run say nothing about the real arm."""

import os
import sys

import pytest

pytest.importorskip('rebot_control')
pytest.importorskip('mujoco')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, 'robot')) if f.endswith('.py'))
# Not started here: two scripts that take no options and connect to the arm at once, and two modules that are only
# imported.
NO_HELP = {'arm_listen_ab', 'arm_sign_check', 'log', 'teleop'}


@pytest.mark.parametrize('name', [s for s in SCRIPTS if s not in NO_HELP])
def test_help(tool, name):
    r = tool(f'robot/{name}.py', '--help')
    assert r.returncode == 0, r.stderr
    assert 'usage:' in r.stdout and 'agent/' not in r.stdout and '.venv/bin' not in r.stdout


def test_arm_move_follows_waypoints_and_keeps_holding(tool):
    r = tool('robot/arm_move.py', '--waypoints', '0,=,=,=,0,0; 0,15,20,=,0,0; 0,s,s,=,0,0', '--sim')
    assert r.returncode == 0, r.stderr
    assert r.stdout.count('at waypoint') == 3
    assert 'holding the last waypoint with torque ON; end it with `rebot-control release`' in r.stdout


def test_arm_move_refuses_a_plan_outside_the_box(tool):
    r = tool('robot/arm_move.py', '--waypoints', '0,90,0,=,0,0', '--sim')
    assert r.returncode == 2
    assert 'REFUSED' in r.stdout


def test_arm_hold_and_step_check(tool):
    r = tool('robot/arm_hold.py', '--sim', '--seconds', '3')
    assert r.returncode == 0, r.stderr
    r = tool('robot/arm_step_check.py', '--joints', '1', '--sim')
    assert r.returncode == 0, r.stderr
    assert 'joint1' in r.stdout and 'overshoot' in r.stdout


def test_line_test_runs_and_its_abort_path_stops_the_arm(tool):
    r = tool('robot/arm_line_test.py', '--sim')
    assert r.returncode == 0, r.stderr
    for name in ('ASFINGER_TEST_ABORT', 'IPUSH_TEST_ABORT'):  # the earlier name of the variable still works
        r = tool('robot/arm_line_test.py', '--sim', env={name: '2'})
        assert r.returncode == 1, (name, r.stdout[-400:])
        assert 'test of the abort path (ASFINGER_TEST_ABORT)' in r.stdout + r.stderr


def test_touch_table_finds_the_simulated_table(tool):
    r = tool('robot/arm_touch_table.py', '--sim', '--auto')
    assert r.returncode == 0, r.stderr
    assert 'table height: mean' in r.stdout and r.stdout.count('contact') >= 5


def test_ripple_calibration_recovers_the_simulated_ripple(tool):
    r = tool('robot/arm_calib_ripple.py', '--sim', '--sim-ripple', '--no-save')
    assert r.returncode == 0, r.stderr
    assert 'calibration file not written' in r.stdout


def test_teleoperation_with_a_scripted_leader_records_an_episode(tool, tmp_path):
    root = str(tmp_path / 'episodes')
    r = tool('robot/teleop_star.py', '--sim', '--fake', '--keys', '1:space,3:r,12:r,13:q', '--root', root)
    assert r.returncode == 0, r.stderr
    episodes = sorted(os.listdir(root))
    assert len(episodes) == 1 and episodes[0].endswith('-teleop-sim')
    assert {'arm.npz', 'meta.yaml'} <= set(os.listdir(os.path.join(root, episodes[0])))

    r = tool('robot/episode.py', 'list', '--root', root)
    assert r.returncode == 0 and '1 episodes in' in r.stdout
    r = tool('robot/episode.py', 'info', os.path.join(root, episodes[0]))
    assert r.returncode == 0, r.stderr

    out = str(tmp_path / 'lerobot')
    r = tool('robot/to_lerobot.py', '--task', 'teleop', '--root', root, '--include-sim', '--cams', 'none', '-o', out)
    assert r.returncode == 0, r.stderr
    assert '1 episodes' in r.stdout
    assert os.path.isfile(os.path.join(out, 'meta', 'info.json'))
    assert os.path.isfile(os.path.join(out, 'data', 'chunk-000', 'episode_000000.parquet'))


def test_iphone_teleoperation_with_a_scripted_hand(tool, tmp_path):
    r = tool('robot/teleop_iphone.py', '--sim', '--keys', '1:space,3:r,14:r,15:q', '--root', str(tmp_path / 'ep'))
    assert r.returncode == 0, r.stderr
    assert len(os.listdir(tmp_path / 'ep')) == 1


def test_scene_push_moves_the_cube(tool):
    r = tool('sim/scene.py', 'push')
    assert r.returncode == 0, r.stderr
    assert 'cube moved from' in r.stdout


def test_tags_pdf_is_written(tool, tmp_path):
    r = tool('robot/make_tags.py', '-o', str(tmp_path / 'tags.pdf'))
    assert r.returncode == 0, r.stderr
    with open(tmp_path / 'tags.pdf', 'rb') as f:
        assert f.read(5) == b'%PDF-'


def test_register_says_when_the_pictures_are_not_there(tool):
    pictures = [
        os.path.join(ROOT, 'calibration', 'data', n) for n in ('scene-top-20261116.jpg', 'scene-wrist-20261116.png')
    ]
    if all(os.path.isfile(p) for p in pictures):
        pytest.skip('the pictures of the real scene are on this computer')
    r = tool('sim/register.py')
    assert r.returncode != 0
    assert 'not part of the repository' in r.stderr


@pytest.mark.skipif(sys.platform != 'linux', reason='the real-arm backend needs SocketCAN')
def test_the_real_arm_backend_is_installed_on_linux():
    import importlib.util

    assert importlib.util.find_spec('motorbridge') is not None
