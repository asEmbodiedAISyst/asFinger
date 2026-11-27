"""Check a dataset written by robot/to_lerobot.py with lerobot itself. Run it with a Python that has lerobot.

    python robot/check_lerobot.py data/lerobot/push-line              # in an environment that has lerobot
    python robot/check_lerobot.py data/lerobot/push-line --every 1    # decode every frame (slow), not every 10th

Loads the dataset from the folder (nothing is downloaded), decodes pictures of every episode, and builds one
batch with a 16-step action chunk, the way a data loader asks for it. lerobot itself refuses a dataset
whose timestamps do not fit its fps, and a picture that is not at the time asked for.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault('HF_HUB_OFFLINE', '1')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('dataset')
    ap.add_argument('--every', type=int, default=10, help='decode every n-th frame')
    ap.add_argument('--video-backend', help="torchcodec, pyav or video_reader (default: lerobot's choice)")
    args = ap.parse_args()
    import torch

    try:
        from lerobot.common.datasets.lerobot_dataset import (
            CODEBASE_VERSION,
            LeRobotDataset,
        )  # lerobot at dataset format v2.1
    except ImportError:
        from lerobot.datasets.lerobot_dataset import CODEBASE_VERSION, LeRobotDataset
    root = Path(args.dataset).resolve()
    kw = {'video_backend': args.video_backend} if args.video_backend else {}
    ds = LeRobotDataset(f'local/{root.name}', root=root, **kw)
    print(
        f'lerobot reads format {CODEBASE_VERSION}; the dataset: {ds.num_episodes} episodes, {ds.num_frames} frames, {ds.fps} fps, '
        f'cameras {ds.meta.camera_keys}, tasks {list(ds.meta.tasks.values())}'
    )
    first = ds[0]
    for key, value in first.items():
        print(f'  {key}: {tuple(value.shape) if hasattr(value, "shape") else repr(value)}')
    ends = set(ds.episode_data_index['from'].tolist()) | {i - 1 for i in ds.episode_data_index['to'].tolist()}
    n = 0
    for i in sorted(set(range(0, len(ds), args.every)) | ends):
        item = ds[i]
        for key in ds.meta.camera_keys:
            assert item[key].shape[0] == 3 and float(item[key].max()) <= 1.0, key
        n += 1
    print(f'decoded {n} frames, the first and last of every episode among them')
    chunk = LeRobotDataset(
        f'local/{root.name}', root=root, delta_timestamps={'action': [k / ds.fps for k in range(16)]}, **kw
    )
    batch = next(iter(torch.utils.data.DataLoader(chunk, batch_size=8, shuffle=True)))
    print(
        'a batch: ' + ', '.join(f'{k} {tuple(v.shape)}' for k, v in batch.items() if hasattr(v, 'shape') and v.ndim > 1)
    )
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
