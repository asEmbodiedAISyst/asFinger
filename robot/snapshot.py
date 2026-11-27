"""Grab one RGB frame from a workspace camera (an iPhone running iMuninn).

    uv run python robot/snapshot.py                 # overhead camera -> /tmp/asfinger-top.jpg
    uv run python robot/snapshot.py --cam wrist     # camera on the arm's end -> /tmp/asfinger-wrist.jpg
    uv run python robot/snapshot.py -o view.png
    uv run python robot/snapshot.py --keep-running  # leave the capture session on for faster repeat shots

The image is saved in sensor orientation (landscape; 1920x1440 for the overhead
camera, 640x480 for the wrist camera): the same frame the intrinsics and tag
detections use, and it stays the same across sessions. For the overhead camera that
puts the arm on the left and the back of the box on the right.
See docs/en/user/robot-setup.md.

The phone's configuration is never changed; a warning is printed when it differs from
the camera's profile (robot/top_camera.yaml, robot/wrist_camera.yaml). If the capture
session was off, it is started for the shot and stopped again afterwards unless
--keep-running is given.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from pathlib import Path

import imuninn
import yaml
from imuninn.proto import imuninn_pb2 as pb
from imuninn.video import H264Decoder
from PIL import Image

CAMERA_NAMES = ('top', 'wrist')
CAMERAS_FILE = Path(__file__).with_name('cameras.local.yaml')


class CameraConfigError(RuntimeError):
    pass


def camera(cam: str) -> tuple[str, str, str]:
    """(address, device_id, label) of a workspace camera.

    They are read from robot/cameras.local.yaml, which is not in git: copy robot/cameras.example.yaml to that name
    and fill it in (`imuninn list` finds a phone's address). ASFINGER_TOP_CAM / ASFINGER_WRIST_CAM override the
    address; the earlier names IPUSH_TOP_CAM / IPUSH_WRIST_CAM still work.
    """
    if not CAMERAS_FILE.is_file():
        raise CameraConfigError(
            f'{CAMERAS_FILE} not found: copy {CAMERAS_FILE.with_name("cameras.example.yaml")} to that '
            'name and fill in the address, device_id and label of your phones'
        )
    entry = (yaml.safe_load(CAMERAS_FILE.read_text()) or {}).get(cam)
    if not entry:
        raise CameraConfigError(f'{CAMERAS_FILE} has no entry for the camera {cam!r} (see cameras.example.yaml)')
    env = f'{cam.upper()}_CAM'
    host = os.environ.get(f'ASFINGER_{env}', os.environ.get(f'IPUSH_{env}', entry['address']))
    return host, entry['device_id'], entry['label']


def profile_path(cam: str) -> Path:
    return Path(__file__).with_name(f'{cam}_camera.yaml')


def config_mismatches(dev, cam: str) -> list[str]:
    """Settings where the phone differs from the camera's profile (mode and rgb parameters)."""
    profile = yaml.safe_load(profile_path(cam).read_text())
    out = []
    mode = {pb.SESSION_MODE_AR: 'ar', pb.SESSION_MODE_CAMERA: 'camera'}.get(dev.config.mode)
    if mode != profile['mode']:
        out.append(f'mode={mode} (profile: {profile["mode"]})')
    rgb = {s.stream_id: s for s in dev.config.streams}['rgb'].params
    for key, want in profile['streams']['rgb'].items():
        if key == 'enabled':
            continue
        have = getattr(rgb[key], rgb[key].WhichOneof('v'))
        same = abs(have - want) < 0.5 if isinstance(want, (int, float)) and not isinstance(want, bool) else have == want
        if not same:
            out.append(f'{key}={have} (profile: {want})')
    return out


def grab(dev, decoder: H264Decoder, wait_s: float, settle_s: float, upright: bool):
    """Latest decoded frame after `settle_s` of video, or None if nothing arrives in `wait_s`."""
    img = meta = None
    first = None
    for frame in dev.iter('rgb', timeout=wait_s):
        for decoded in decoder.decode(frame, upright=upright):
            img, meta = decoded, frame
            first = first or time.monotonic()
        if first and time.monotonic() - first >= settle_s:
            break
    return img, meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--cam', choices=sorted(CAMERA_NAMES), default='top', help='which camera (default: top)')
    ap.add_argument('-o', '--out', help='output image (.jpg / .png); default /tmp/asfinger-<cam>.jpg')
    ap.add_argument(
        '--host', help='phone address, overriding cameras.local.yaml (env ASFINGER_TOP_CAM / ASFINGER_WRIST_CAM)'
    )
    ap.add_argument(
        '--upright', action='store_true', help="rotate by the phone's rotation_deg instead of sensor orientation"
    )
    ap.add_argument('--keep-running', action='store_true', help='do not stop a capture session this script started')
    ap.add_argument('--settle', type=float, default=0.5, help='seconds of video to decode before taking the frame')
    args = ap.parse_args()
    try:
        host, device_id, label = camera(args.cam)
    except CameraConfigError as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    args.host = args.host or host
    args.out = args.out or f'/tmp/asfinger-{args.cam}.jpg'

    with imuninn.connect(args.host, timeout=10) as dev:
        if dev.info.device_id != device_id:
            print(f'warning: {args.host} is device {dev.info.device_id}, not {label} ({device_id})', file=sys.stderr)

        mismatches = config_mismatches(dev, args.cam)
        if mismatches:
            # the app drops back to its defaults (AR mode, main lens, auto exposure) when it restarts
            print(
                f'warning: phone configuration differs from its profile: {"; ".join(mismatches)}. To restore: '
                f'uv run imuninn profile apply robot/{args.cam}_camera.yaml {args.host}',
                file=sys.stderr,
            )

        decoder = H264Decoder()
        # A running session delivers a keyframe within keyframe_interval (1 s at the current config).
        img, meta = grab(dev, decoder, 2.5, args.settle, args.upright)
        started = False
        if img is None:
            dev.start()
            started = True
            # auto exposure needs time after a cold start: a 0.5 s shot has come out black
            img, meta = grab(dev, decoder, 8.0, max(args.settle, 1.5), args.upright)
        try:
            if img is None:
                print('error: no RGB frames received (is the rgb stream enabled on the phone?)', file=sys.stderr)
                return 1
            Image.fromarray(img).save(args.out)
            h, w = img.shape[:2]
            print(f'saved {args.out} {w}x{h} captured_at={dev.to_pc_time(meta.header.device_time_ns):.3f}')
        finally:
            if started and not args.keep_running:
                dev.stop()
        print(
            'session: '
            + (
                'was running'
                if not started
                else 'started, left running'
                if args.keep_running
                else 'started, stopped again'
            )
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
