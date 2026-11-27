"""Checks of the robot-side files that need nothing installed beyond the dev group."""

import os
import py_compile
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def tracked(*folders):
    out = subprocess.run(['git', 'ls-files', *folders], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f]


def test_scripts_compile():
    scripts = [f for f in tracked('robot', 'sim') if f.endswith('.py')]
    assert len(scripts) >= 20
    for f in scripts:
        py_compile.compile(os.path.join(ROOT, f), doraise=True)


def test_no_address_and_no_phone_identity_in_tracked_files():
    """Addresses and phone identities belong in robot/cameras.local.yaml, which git ignores."""
    private_net = re.compile(r'\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b')
    uuid = re.compile(r'\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b')
    for f in tracked('robot', 'sim', 'calibration', 'data'):
        if f.endswith(('.png', '.stl', '.npz', '.jpg', '.pdf')):
            continue
        with open(os.path.join(ROOT, f), encoding='utf-8') as fh:
            text = fh.read()
        assert not private_net.search(text), f
        assert all(set(m) <= set('0-') for m in uuid.findall(text)), f
        assert '/home/' not in text and '/Users/' not in text, f
    assert 'robot/cameras.local.yaml' not in tracked('robot')
    assert not tracked('calibration/data')


def test_calibration_files_that_the_tools_read_are_there():
    names = {os.path.basename(f) for f in tracked('calibration')}
    assert names == {'b601_rs.yaml', 'tool_ip17pro_print.yaml', 'table.yaml', 'workspace.yaml', 'star_leader.yaml'}
    with open(os.path.join(ROOT, 'robot', 'arm'), encoding='utf-8') as fh:
        wrapper = fh.read()
    assert os.access(os.path.join(ROOT, 'robot', 'arm'), os.X_OK)
    assert '--tool calibration/tool_ip17pro_print.yaml --calibration calibration/b601_rs.yaml' in wrapper
