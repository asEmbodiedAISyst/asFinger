"""Set a camera to manual exposure and white balance using the colour card.

    uv run python robot/calibrate_color.py --cam top            # search, leave the phone on the result
    uv run python robot/calibrate_color.py --cam top --check    # only read the card, change nothing

The card (docs/en/user/robot-calibration.md) must be fully visible to the camera, under the
light the experiments will use. The script switches the phone to manual exposure and
manual white balance and searches for:
  - ISO, at a fixed shutter time, so that the unprinted white patch reads --white;
  - colour temperature and tint, so that the white and 75 % grey patches are neutral.
It prints the values to copy into the camera's profile (robot/top_camera.yaml): the
phone forgets its configuration when the iMuninn app restarts.

The phone does not report the values auto mode picked, hence the search.
"""

from __future__ import annotations

import argparse
import math
import sys
import time

import cv2
import imuninn
import numpy as np
from imuninn.video import H264Decoder

from make_tags import card_layout
from snapshot import CAMERA_NAMES, CameraConfigError, camera
from tags import detect

GAMMA = 2.2  # rough display gamma, to predict how pixel values follow exposure


def read_card(dev, settle_s: float = 0.9, frames: int = 6) -> dict[str, np.ndarray] | None:
    """Mean RGB of every card patch, averaged over a few frames taken after `settle_s`."""
    card = card_layout()
    decoder, images, start = H264Decoder(), [], time.monotonic()
    for frame in dev.iter('rgb', timeout=5):
        for img in decoder.decode(frame, upright=False):
            if time.monotonic() - start >= settle_s:
                images.append(img.astype(np.float32))
        if len(images) >= frames:
            break
    if not images:
        return None
    mean = np.mean(images, axis=0)
    tags = detect(cv2.cvtColor(np.clip(mean, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY))
    if not all(i in tags for i in card['tags']):
        return None
    src, dst = [], []
    for tag_id, (x, y, s) in card['tags'].items():
        src += [[x, y], [x + s, y], [x + s, y + s], [x, y + s]]
        dst += list(tags[tag_id])
    H, _ = cv2.findHomography(np.array(src, np.float32), np.array(dst, np.float32))
    out = {}
    for name, (x, y, s) in card['patches'].items():  # sample the middle 40 % of each patch
        q = np.array(
            [
                [x + 0.3 * s, y + 0.3 * s],
                [x + 0.7 * s, y + 0.3 * s],
                [x + 0.7 * s, y + 0.7 * s],
                [x + 0.3 * s, y + 0.7 * s],
            ],
            np.float32,
        )
        mask = np.zeros(mean.shape[:2], np.uint8)
        cv2.fillConvexPoly(mask, np.round(cv2.perspectiveTransform(q[None], H)[0]).astype(np.int32), 1)
        out[name] = mean[mask > 0].mean(0)
    return out


def neutral(p: dict[str, np.ndarray]) -> np.ndarray:
    return (p['white'] + p['grey75']) / 2


def set_param(dev, key: str, value) -> None:
    r = dev.set(key, value)
    f = r.fields[0]
    if f.status != f.STATUS_APPLIED:
        print(f'  note: {key}={value}: {f.Status.Name(f.status)} {f.reason}', file=sys.stderr)


def report(p: dict[str, np.ndarray]) -> None:
    for name, m in p.items():
        print(f'  {name:8s} {m[0]:4.0f} {m[1]:4.0f} {m[2]:4.0f}   R/G {m[0] / m[1]:.3f}  B/G {m[2] / m[1]:.3f}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--cam', choices=sorted(CAMERA_NAMES), default='top')
    ap.add_argument('--check', action='store_true', help='read the card with the current settings and exit')
    ap.add_argument('--white', type=float, default=215.0, help='target value of the white patch (0-255)')
    ap.add_argument(
        '--shutter-ms',
        type=float,
        default=10.0,
        help='shutter time; 10 ms spans one flicker period of 50 Hz mains lighting',
    )
    args = ap.parse_args()

    try:
        host = camera(args.cam)[0]
    except CameraConfigError as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    with imuninn.connect(host, timeout=10) as dev:
        if read_card(dev, settle_s=0.3, frames=1) is None:
            dev.start()
        before = read_card(dev)
        if before is None:
            print('error: colour card not found (both of its tags must be visible)', file=sys.stderr)
            return 1
        print('card with the current settings:')
        report(before)
        if args.check:
            return 0

        iso, temp, tint = 100.0, 5000.0, 0.0
        set_param(dev, 'rgb.exposure_mode', 'manual')
        set_param(dev, 'rgb.exposure_ms', args.shutter_ms)
        set_param(dev, 'rgb.iso', iso)
        set_param(dev, 'rgb.white_balance_mode', 'manual')
        set_param(dev, 'rgb.wb_temperature_k', temp)
        set_param(dev, 'rgb.wb_tint', tint)

        def measure() -> dict[str, np.ndarray]:
            p = read_card(dev)
            if p is None:
                raise RuntimeError('lost the colour card during the search')
            return p

        def fit_exposure() -> None:
            nonlocal iso
            for _ in range(5):
                g = measure()['white'][1]
                if abs(g - args.white) < 3:
                    break
                # pixel value ~ exposure^(1/gamma); a clipped patch says nothing, so halve instead
                factor = 0.5 if g >= 250 else (args.white / max(g, 1.0)) ** GAMMA
                iso = float(np.clip(iso * factor, 54, 5184))
                set_param(dev, 'rgb.iso', iso)

        def secant(key: str, value: float, step: float, lo: float, hi: float, error) -> float:
            """Drive error(patches) to zero by changing one phone parameter."""
            x0, e0 = value, error(measure())
            x1 = float(np.clip(value + step, lo, hi))
            for _ in range(6):
                set_param(dev, key, x1)
                e1 = error(measure())
                if abs(e1) < 0.004 or e1 == e0:
                    break
                x0, e0, x1 = x1, e1, float(np.clip(x1 - e1 * (x1 - x0) / (e1 - e0), lo, hi))
            return x1

        red_blue = lambda p: math.log(neutral(p)[0] / neutral(p)[2])  # temperature axis
        green = lambda p: math.log(neutral(p)[1] ** 2 / (neutral(p)[0] * neutral(p)[2])) / 2  # tint axis

        fit_exposure()
        for _ in range(2):  # the two axes interact a little
            temp = secant('rgb.wb_temperature_k', temp, 500.0, 2000, 10000, red_blue)
            tint = secant('rgb.wb_tint', tint, 15.0, -150, 150, green)
        fit_exposure()

        print('card after calibration:')
        report(measure())
        print('\nprofile values (streams.rgb):')
        print(
            f'    exposure_mode: manual\n    exposure_ms: {args.shutter_ms:g}\n    iso: {iso:.0f}\n'
            f'    white_balance_mode: manual\n    wb_temperature_k: {temp:.0f}\n    wb_tint: {tint:.1f}'
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
