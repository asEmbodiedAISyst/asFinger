"""The one place that knows where the phones are: robot/snapshot.py camera()."""

import os
import sys

import pytest

pytest.importorskip('imuninn')
pytest.importorskip('PIL')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXAMPLE = os.path.join(ROOT, 'robot', 'cameras.example.yaml')


@pytest.fixture
def snapshot(monkeypatch):
    monkeypatch.syspath_prepend(os.path.join(ROOT, 'robot'))
    for name in ('ASFINGER_TOP_CAM', 'ASFINGER_WRIST_CAM', 'IPUSH_TOP_CAM', 'IPUSH_WRIST_CAM'):
        monkeypatch.delenv(name, raising=False)
    sys.modules.pop('snapshot', None)
    import snapshot

    yield snapshot
    sys.modules.pop('snapshot', None)


def test_camera_reads_the_local_file(snapshot, monkeypatch, tmp_path):
    local = tmp_path / 'cameras.local.yaml'
    local.write_text(
        'top: {address: 192.0.2.21, device_id: AAAA-1, label: phone A}\n'
        'wrist: {address: wrist-phone.local, device_id: BBBB-2, label: phone B}\n'
    )
    monkeypatch.setattr(snapshot, 'CAMERAS_FILE', local)
    assert snapshot.camera('top') == ('192.0.2.21', 'AAAA-1', 'phone A')
    assert snapshot.camera('wrist') == ('wrist-phone.local', 'BBBB-2', 'phone B')
    assert snapshot.CAMERA_NAMES == ('top', 'wrist')


def test_environment_overrides_the_address_only(snapshot, monkeypatch, tmp_path):
    local = tmp_path / 'cameras.local.yaml'
    local.write_text('top: {address: 192.0.2.21, device_id: AAAA-1, label: phone A}\n')
    monkeypatch.setattr(snapshot, 'CAMERAS_FILE', local)
    monkeypatch.setenv('IPUSH_TOP_CAM', '192.0.2.50')  # the earlier name still works
    assert snapshot.camera('top') == ('192.0.2.50', 'AAAA-1', 'phone A')
    monkeypatch.setenv('ASFINGER_TOP_CAM', '192.0.2.60')  # the new name wins
    assert snapshot.camera('top') == ('192.0.2.60', 'AAAA-1', 'phone A')


def test_missing_file_or_entry_names_the_example(snapshot, monkeypatch, tmp_path):
    monkeypatch.setattr(snapshot, 'CAMERAS_FILE', tmp_path / 'cameras.local.yaml')
    with pytest.raises(snapshot.CameraConfigError, match='cameras.example.yaml'):
        snapshot.camera('top')
    (tmp_path / 'cameras.local.yaml').write_text('top: {address: 192.0.2.21, device_id: AAAA-1, label: phone A}\n')
    with pytest.raises(snapshot.CameraConfigError, match="no entry for the camera 'wrist'"):
        snapshot.camera('wrist')
    # the environment variable does not replace the file: the tools also check which phone answers
    monkeypatch.setenv('ASFINGER_WRIST_CAM', '192.0.2.70')
    with pytest.raises(snapshot.CameraConfigError):
        snapshot.camera('wrist')


def test_the_example_file_has_both_cameras_and_no_real_address(snapshot, monkeypatch):
    monkeypatch.setattr(snapshot, 'CAMERAS_FILE', snapshot.Path(EXAMPLE))
    for cam in snapshot.CAMERA_NAMES:
        host, device_id, label = snapshot.camera(cam)
        assert host.startswith('192.0.2.')  # the documentation range of RFC 5737
        assert set(device_id) <= set('0-') and label
