"""Detect AprilTag 36h11 markers in an image.

    uv run python robot/snapshot.py -o view.png
    uv run python robot/tags.py view.png                      # one line per tag
    uv run python robot/tags.py view.png --annotate out.jpg   # also draw them

Corners are in image pixels, in OpenCV's order (clockwise from the tag's own
top-left corner). Tag ids and sizes are listed in docs/en/user/robot-calibration.md.
"""

from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
_PARAMS = cv2.aruco.DetectorParameters()
_PARAMS.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
_DETECTOR = cv2.aruco.ArucoDetector(_DICT, _PARAMS)


def tag_size_mm(tag_id: int) -> float:
    """Edge of the black square; the id range fixes the size (docs/en/user/robot-calibration.md)."""
    return 50.0 if tag_id < 10 else 40.0 if tag_id < 20 else 70.0 if tag_id < 30 else 30.0


def detect(image: np.ndarray) -> dict[int, np.ndarray]:
    """Tags in a grayscale or 3-channel image as {id: 4x2 corner array}."""
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _DETECTOR.detectMarkers(gray)
    return {} if ids is None else {int(i): c[0] for c, i in zip(corners, ids.ravel())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('image')
    ap.add_argument('--annotate', help='write a copy of the image with the tags drawn')
    args = ap.parse_args()

    img = cv2.imread(args.image)
    if img is None:
        print(f'error: cannot read {args.image}', file=sys.stderr)
        return 1
    tags = detect(img)
    for tag_id in sorted(tags):
        c = tags[tag_id]
        sides = [np.linalg.norm(c[k] - c[(k + 1) % 4]) for k in range(4)]
        print(
            f'id {tag_id:3d}  {tag_size_mm(tag_id):g} mm  centre ({c[:, 0].mean():7.1f}, {c[:, 1].mean():7.1f})  '
            f'sides {min(sides):.0f}-{max(sides):.0f} px  corners ' + ' '.join(f'({x:.1f},{y:.1f})' for x, y in c)
        )
    if not tags:
        print('no tags found')
    if args.annotate:
        for tag_id, c in tags.items():
            cv2.polylines(img, [np.round(c).astype(np.int32)], True, (0, 255, 0), 2)
            cv2.putText(
                img,
                str(tag_id),
                tuple(np.round(c[0]).astype(int) - (0, 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2,
            )
        cv2.imwrite(args.annotate, img)
    return 0


if __name__ == '__main__':
    sys.exit(main())
