"""Convert recorded episodes (robot/episode.py) into one LeRobot dataset, format v2.1.

    uv run python robot/to_lerobot.py --task push-line                     # -> data/lerobot/push-line
    uv run python robot/to_lerobot.py --task push-line --plan              # only list what would be converted
    uv run python robot/to_lerobot.py --task push-line --instruction "push the black cube along the black line to the other end"
    uv run python robot/to_lerobot.py --task push-line -o /data/push-line --overwrite --height 224
    uv run python robot/to_lerobot.py --task push-line --crop top=1000,170,640,640 --plan    # + a picture of the cut

v2.1 is an earlier LeRobot format that some code bases still pin: one parquet file and one mp4 per camera for
every episode, and the tables in meta/ (info.json, episodes.jsonl, tasks.jsonl, episodes_stats.jsonl). The files are
written here directly, in the layout that lerobot's own `LeRobotDataset.save_episode` produces, so lerobot is not
needed to convert. Needed: numpy, pyarrow, av, opencv, pyyaml, imuninn (reads the phones' recordings), and
rebot_control for the tool pose columns (left out with a warning when it is missing).

Which episodes: all of --task under --root that are complete, not simulated and not marked failed (`success:
false`, key f while recording); --include-failed takes those too. The order is the order of recording.

What a frame is: the episode is sampled on a fixed grid of --fps (30) from its first to its last moment that
everything covers. At each grid time t:

    observation.images.<cam>  the camera frame captured nearest to t (the phones send 60 a second), cut to --crop
                              (if given for that camera), then scaled to --height
    observation.state         the six joint angles at t [rad], from the 150 Hz servo log
    action                    the joint target the teleoperation commanded at t [rad] (stream `q_target`): the first
                              one at or after t. With --action next-state: the joint angles one step later.
    observation.tcp_pose      tool tip: x y z [m] and the first two columns of its rotation matrix (9 numbers)
    action.tcp_pose           the commanded tool pose in the same form (stream `tcp_target`)
    timestamp                 frame number / fps

The task text of an episode is its `instruction` (--instruction replaces it for all episodes; the episode's task name
is used when there is none). With teleoperation the frames before the first and after the last engaged moment are cut
off (--keep-idle keeps them); pauses in between stay in. meta/source_episodes.jsonl says which recording each
episode came from and what was cut, meta/conversion.json the options of this run.

--crop CAM=x,y,w,h cuts a rectangle out of a camera's pictures (pixels of the recorded picture, x to the right and y
down from the top left corner) before scaling. A learner usually sees pictures of about 224 x 224: what it has to see must
still be a few pixels wide there. With --plan, the first picture of the first, middle and last episode is saved
with the rectangle drawn in, next to the dataset folder, to check that the cut holds everything in all of them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import episode as ep  # noqa: E402

CODEBASE_VERSION = 'v2.1'
CHUNK = 1000  # episodes per chunk folder
DATA_PATH = 'data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet'
VIDEO_PATH = 'videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4'
JOINTS = [f'joint{i}' for i in range(1, 7)]
POSE = ['x', 'y', 'z', 'r11', 'r21', 'r31', 'r12', 'r22', 'r32']
MAX_FRAME_GAP = 0.05  # s: a grid time further than this from any camera frame fails the episode


class Skip(Exception):
    """This episode cannot be converted; the message says why."""


# ------------------------------------------------------------------------------------------------ selection
def select(root: Path, task: str, include_failed: bool, include_sim: bool) -> tuple[list[tuple[Path, dict]], list[str]]:
    chosen, left_out = [], []
    for meta_file in sorted(Path(root).glob('*/meta.yaml')):
        m = yaml.safe_load(meta_file.read_text()) or {}
        if m.get('task') != task:
            continue
        name = meta_file.parent.name
        if not m.get('complete'):
            left_out.append(f'{name}: not complete')
        elif m.get('sim') and not include_sim:
            left_out.append(f'{name}: simulator')
        elif m.get('success') is False and not include_failed:
            left_out.append(f'{name}: marked failed')
        elif not (meta_file.parent / 'arm.npz').is_file():
            left_out.append(f'{name}: no arm log')
        else:
            chosen.append((meta_file.parent, m))
    return chosen, left_out


# ------------------------------------------------------------------------------------------------ one episode
def pose9(pos: np.ndarray, rot: np.ndarray) -> np.ndarray:
    """Position and the first two columns of the rotation matrix (the third is their cross product)."""
    rot = np.asarray(rot, dtype=float).reshape(3, 3)
    return np.r_[pos, rot[:, 0], rot[:, 1]]


def tool_model(path: Path, meta: dict):
    """The arm model with the tool the episode was recorded with (its config/ copies first), or None."""
    try:
        from rebot_control import ArmConfig, RobotModel, ToolConfig
        from rebot_control.config import Calibration
    except ImportError:
        return None
    arm = meta.get('arm') or {}
    cfg = path / 'config'
    tool = next((p for p in sorted(cfg.glob('tool_*.yaml'))), None) if cfg.is_dir() else None
    tool = str(tool) if tool else arm.get('tool')
    cal = (
        cfg / 'b601_rs.yaml'
        if (cfg / 'b601_rs.yaml').is_file()
        else Path(meta.get('calibration') or ep.ROOT / 'calibration' / 'b601_rs.yaml')
    )
    if not tool or not Path(tool).is_file() or not cal.is_file():
        raise Skip('the tool model or the calibration the episode names is not there')
    return RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(tool), Calibration.load(str(cal)))


def at_or_after(t_grid: np.ndarray, t_src: np.ndarray, values: np.ndarray) -> np.ndarray:
    """For every grid time the first sample at or after it (the last one past the end)."""
    return values[np.minimum(np.searchsorted(t_src, t_grid - 1e-9, side='left'), len(t_src) - 1)]


def plan_episode(
    path: Path, meta: dict, cams: tuple[str, ...], fps: int, action: str, keep_idle: bool, with_tcp: bool
) -> dict:
    """The time grid and every column of an episode except the pictures."""
    _, arm = ep.load(path)
    t = arm['t']
    if len(t) < 2:
        raise Skip('empty arm log')
    for cam in cams:
        c = (meta.get('cameras') or {}).get(cam)
        if not c or 'error' in c or not (path / f'{cam}.mcap').is_file():
            raise Skip(f'no {cam} camera recording')
    vt = {cam: ep.video_times(path, cam) for cam in cams}
    start = max([t[0]] + [v[0] for v in vt.values()])
    end = min([t[-1]] + [v[-1] for v in vt.values()])
    if action == 'target':
        if 'q_target' not in arm:
            raise Skip('no q_target stream (not a teleoperation recording: use --action next-state)')
        start, end = max(start, arm['q_target_t'][0]), min(end, arm['q_target_t'][-1])
    cut = [0.0, 0.0]
    engaged_share = None
    if 'engaged' in arm:
        on = arm['engaged'][:, 0] > 0.5
        te = arm['engaged_t']
        if not keep_idle:
            if not on.any():
                raise Skip('never engaged')
            a, b = te[on][0], te[on][-1]
            cut = [max(0.0, a - start), max(0.0, end - b)]
            start, end = max(start, a), min(end, b)
    if action == 'next-state':
        end -= 1.0 / fps
    n = int(np.floor((end - start) * fps + 1e-6)) + 1
    if n < 2:
        raise Skip(f'too short ({end - start:.2f} s)')
    grid = start + np.arange(n) / fps
    for cam, v in vt.items():
        i = np.clip(np.searchsorted(v, grid), 1, len(v) - 1)
        gap = np.minimum(np.abs(v[i] - grid), np.abs(v[i - 1] - grid)).max()
        if gap > MAX_FRAME_GAP:
            raise Skip(f'{cam} camera: no frame within {gap * 1000:.0f} ms of a grid time')
    if 'engaged' in arm:
        engaged_share = float(at_or_after(grid, arm['engaged_t'], arm['engaged'][:, 0] > 0.5).mean())

    q = np.stack([np.interp(grid, t, arm['q'][:, j]) for j in range(6)], axis=1)
    cols = {'observation.state': q}
    if action == 'target':
        cols['action'] = at_or_after(grid, arm['q_target_t'], arm['q_target'])
    else:
        cols['action'] = np.stack([np.interp(grid + 1.0 / fps, t, arm['q'][:, j]) for j in range(6)], axis=1)
    if with_tcp:
        model = tool_model(path, meta)
        data = model.new_data()
        cols['observation.tcp_pose'] = np.array([pose9(*model.fk(row, data)[:2]) for row in q])
        if action == 'target' and 'tcp_target' in arm:
            tt = at_or_after(grid, arm['tcp_target_t'], arm['tcp_target'])
            cols['action.tcp_pose'] = np.array([pose9(row[:3], row[3:12]) for row in tt])
        else:
            cols['action.tcp_pose'] = np.array([pose9(*model.fk(row, data)[:2]) for row in cols['action']])
    return {
        'grid': grid,
        'cols': {k: v.astype(np.float32) for k, v in cols.items()},
        'cut': cut,
        'engaged_share': engaged_share,
        'span': float(t[-1] - t[0]),
    }


def stat_indices(n: int) -> np.ndarray:
    """The frames lerobot samples for the picture statistics of an episode of n frames."""
    k = max(min(n, 100), min(int(n**0.75), 10_000))
    return np.unique(np.round(np.linspace(0, n - 1, k)).astype(int))


def picture_stats(samples: list[np.ndarray]) -> dict:
    x = np.stack(samples).transpose(0, 3, 1, 2)  # (n, 3, h, w), uint8
    f = int(x.shape[3] / 150) if x.shape[3] > x.shape[2] else int(x.shape[2] / 150)
    if max(x.shape[2:]) >= 300:
        x = x[:, :, ::f, ::f]
    return {
        'min': x.min(axis=(0, 2, 3), keepdims=True)[0] / 255.0,
        'max': x.max(axis=(0, 2, 3), keepdims=True)[0] / 255.0,
        'mean': x.mean(axis=(0, 2, 3), keepdims=True)[0] / 255.0,
        'std': x.std(axis=(0, 2, 3), keepdims=True)[0] / 255.0,
        'count': np.array([len(x)]),
    }


def parse_crops(items: list[str]) -> dict[str, tuple[int, int, int, int]]:
    """["top=1000,170,640,640", ...] -> {"top": (x, y, w, h)}"""
    crops = {}
    for item in items:
        cam, _, box = item.partition('=')
        try:
            x, y, w, h = (int(v) for v in box.split(','))
        except ValueError:
            raise ValueError(f'--crop {item}: expected CAM=x,y,w,h in pixels') from None
        if min(x, y) < 0 or min(w, h) < 2:
            raise ValueError(f'--crop {item}: x and y must not be negative, w and h at least 2')
        crops[cam.strip()] = (x, y, w, h)
    return crops


def cut_picture(img: np.ndarray, crop: tuple[int, int, int, int] | None, cam: str) -> np.ndarray:
    if crop is None:
        return img
    x, y, w, h = crop
    if x + w > img.shape[1] or y + h > img.shape[0]:
        raise Skip(f'{cam} camera: the crop {x},{y},{w},{h} does not fit its {img.shape[1]}x{img.shape[0]} pictures')
    return img[y : y + h, x : x + w]


def crop_preview(episodes: list[tuple[Path, dict]], cam: str, crop: tuple[int, int, int, int], file: Path) -> None:
    """First picture of the first, middle and last episode, side by side, with the crop rectangle drawn in."""
    import cv2

    x, y, w, h = crop
    tiles = []
    for path, meta in [episodes[0], episodes[len(episodes) // 2], episodes[-1]]:
        for _, img in ep.frames(path, cam):
            img = np.ascontiguousarray(img[:, :, ::-1])
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 6)
            cv2.putText(img, f'#{meta.get("index")}', (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 255), 4)
            tiles.append(img)
            break
    file.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(file), np.concatenate(tiles, axis=1))


def write_video(
    path: Path,
    cam: str,
    grid: np.ndarray,
    out: Path,
    fps: int,
    height: int,
    vcodec: str,
    crf: int,
    crop: tuple[int, int, int, int] | None = None,
) -> tuple[tuple[int, int], dict]:
    """The camera frame nearest to every grid time, as an mp4 with one picture per grid step. -> ((h, w), statistics)"""
    import av
    import cv2

    out.parent.mkdir(parents=True, exist_ok=True)
    want = set(stat_indices(len(grid)).tolist())
    samples: list[np.ndarray] = []
    state = {'k': 0, 'stream': None, 'size': None}
    with av.open(str(out), 'w') as container:

        def emit(img: np.ndarray) -> None:
            img = cut_picture(img, crop, cam)
            h0, w0 = img.shape[:2]
            h = height or h0
            w = int(round(w0 * h / h0 / 2)) * 2
            h -= h % 2
            if (h, w) != (h0, w0):
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA if h < h0 else cv2.INTER_LINEAR)
            if state['stream'] is None:
                s = container.add_stream(vcodec, rate=fps, options={'g': '2', 'crf': str(crf)})
                s.pix_fmt, s.width, s.height = 'yuv420p', w, h
                s.time_base = Fraction(1, fps)
                state['stream'], state['size'] = s, (h, w)
            if state['k'] in want:
                samples.append(img)
            frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format='rgb24')
            frame.pts, frame.time_base = state['k'], Fraction(1, fps)
            for packet in state['stream'].encode(frame):
                container.mux(packet)
            state['k'] += 1

        prev = None
        for tf, img in ep.frames(path, cam):
            if prev is not None:
                while state['k'] < len(grid) and grid[state['k']] <= 0.5 * (prev[0] + tf):
                    emit(prev[1])
            prev = (tf, img)
            if state['k'] >= len(grid):
                break
        while prev is not None and state['k'] < len(grid):
            emit(prev[1])
        if state['stream'] is None:
            raise Skip(f'{cam} camera: nothing could be decoded')
        for packet in state['stream'].encode():
            container.mux(packet)
    return state['size'], picture_stats(samples)


def column_stats(x: np.ndarray) -> dict:
    keep = x.ndim == 1
    return {
        'min': np.min(x, axis=0, keepdims=keep),
        'max': np.max(x, axis=0, keepdims=keep),
        'mean': np.mean(x, axis=0, keepdims=keep),
        'std': np.std(x, axis=0, keepdims=keep),
        'count': np.array([len(x)]),
    }


def to_lists(d):
    return {k: to_lists(v) if isinstance(v, dict) else np.asarray(v).tolist() for k, v in d.items()}


# ------------------------------------------------------------------------------------------------ the dataset
def hf_feature(ft: dict) -> dict:
    if tuple(ft['shape']) == (1,):
        return {'dtype': ft['dtype'], '_type': 'Value'}
    return {'feature': {'dtype': ft['dtype'], '_type': 'Value'}, 'length': ft['shape'][0], '_type': 'Sequence'}


def write_table(file: Path, cols: dict[str, np.ndarray], features: dict) -> None:
    """One episode's parquet file, with the column types and the schema note that the `datasets` library writes."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    arrays, fields = [], []
    for key, ft in features.items():
        if ft['dtype'] == 'video':
            continue
        x = np.asarray(cols[key])
        kind = pa.from_numpy_dtype(np.dtype(ft['dtype']))
        if tuple(ft['shape']) == (1,):
            arrays.append(pa.array(x.reshape(-1).astype(ft['dtype']), type=kind))
            fields.append(pa.field(key, kind))
        else:
            width = ft['shape'][0]
            arrays.append(
                pa.FixedSizeListArray.from_arrays(pa.array(x.astype(ft['dtype']).reshape(-1), type=kind), width)
            )
            fields.append(pa.field(key, pa.list_(kind, width)))
    note = {'info': {'features': {k: hf_feature(ft) for k, ft in features.items() if ft['dtype'] != 'video'}}}
    schema = pa.schema(fields, metadata={'huggingface': json.dumps(note)})
    file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), file)


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def convert(
    episodes: list[tuple[Path, dict]],
    out: Path,
    cams: tuple[str, ...],
    fps: int,
    height: int,
    action: str,
    keep_idle: bool,
    instruction: str | None,
    robot_type: str,
    vcodec: str,
    crf: int,
    say=print,
    crops: dict[str, tuple[int, int, int, int]] | None = None,
) -> dict:
    crops = crops or {}
    with_tcp = True
    try:
        import rebot_control  # noqa: F401
    except ImportError:
        with_tcp = False
        say('WARNING: rebot_control is not installed: the tool pose columns are left out')
    features: dict[str, dict] = {
        'observation.state': {'dtype': 'float32', 'shape': [6], 'names': JOINTS},
        'action': {'dtype': 'float32', 'shape': [6], 'names': JOINTS},
    }
    if with_tcp:
        features['observation.tcp_pose'] = {'dtype': 'float32', 'shape': [9], 'names': POSE}
        features['action.tcp_pose'] = {'dtype': 'float32', 'shape': [9], 'names': POSE}
    for cam in cams:
        features[f'observation.images.{cam}'] = {
            'dtype': 'video',
            'shape': None,
            'names': ['height', 'width', 'channels'],
        }
    for key, kind in (
        ('timestamp', 'float32'),
        ('frame_index', 'int64'),
        ('episode_index', 'int64'),
        ('index', 'int64'),
        ('task_index', 'int64'),
    ):
        features[key] = {'dtype': kind, 'shape': [1], 'names': None}

    (out / 'meta').mkdir(parents=True)
    tasks: dict[str, int] = {}
    rows_episodes, rows_stats, rows_source, skipped = [], [], [], []
    total = 0
    for path, meta in episodes:
        i = len(rows_episodes)
        try:
            plan = plan_episode(path, meta, cams, fps, action, keep_idle, with_tcp)
            n = len(plan['grid'])
            stats, sizes = {}, {}
            for cam in cams:
                key = f'observation.images.{cam}'
                file = out / VIDEO_PATH.format(episode_chunk=i // CHUNK, video_key=key, episode_index=i)
                sizes[cam], stats[key] = write_video(
                    path, cam, plan['grid'], file, fps, height, vcodec, crf, crops.get(cam)
                )
                shape = [sizes[cam][0], sizes[cam][1], 3]
                if features[key]['shape'] not in (None, shape):
                    raise Skip(
                        f"{cam} pictures are {shape[1]}x{shape[0]}, the earlier episodes' {features[key]['shape'][1]}x{features[key]['shape'][0]}"
                    )
                features[key]['shape'] = shape
        except Skip as e:
            for cam in cams:  # a video of this episode may already be written
                out.joinpath(
                    VIDEO_PATH.format(episode_chunk=i // CHUNK, video_key=f'observation.images.{cam}', episode_index=i)
                ).unlink(missing_ok=True)
            skipped.append(f'{path.name}: {e}')
            say(f'  SKIPPED {path.name}: {e}')
            continue
        text = instruction or meta.get('instruction') or meta.get('task') or meta.get('label') or 'task'
        task_index = tasks.setdefault(text, len(tasks))
        cols = dict(plan['cols'])
        cols['timestamp'] = (np.arange(n) / fps).astype(np.float32)
        cols['frame_index'] = np.arange(n, dtype=np.int64)
        cols['episode_index'] = np.full(n, i, dtype=np.int64)
        cols['index'] = np.arange(total, total + n, dtype=np.int64)
        cols['task_index'] = np.full(n, task_index, dtype=np.int64)
        write_table(out / DATA_PATH.format(episode_chunk=i // CHUNK, episode_index=i), cols, features)
        for key, ft in features.items():
            if ft['dtype'] != 'video':
                stats[key] = column_stats(cols[key])
        rows_episodes.append({'episode_index': i, 'tasks': [text], 'length': n})
        rows_stats.append({'episode_index': i, 'stats': to_lists({k: stats[k] for k in features})})
        rows_source.append(
            {
                'episode_index': i,
                'source': path.name,
                'source_index': meta.get('index'),
                'operator': meta.get('operator', ''),
                'success': meta.get('success'),
                'start_unix': round(float(plan['grid'][0]), 4),
                'cut_start_s': round(plan['cut'][0], 3),
                'cut_end_s': round(plan['cut'][1], 3),
                'engaged_share': None if plan['engaged_share'] is None else round(plan['engaged_share'], 3),
            }
        )
        total += n
        share = (
            ''
            if plan['engaged_share'] is None or plan['engaged_share'] > 0.999
            else f', engaged {plan["engaged_share"] * 100:.0f}% of it'
        )
        say(
            f'  {i:4d}  {path.name}: {n} frames ({n / fps:.1f} s of {plan["span"]:.1f} s; cut {plan["cut"][0]:.1f} s before, {plan["cut"][1]:.1f} s after{share})'
        )

    if not rows_episodes:
        shutil.rmtree(out)
        return {'episodes': 0, 'frames': 0, 'skipped': skipped}
    for cam in cams:
        ft = features[f'observation.images.{cam}']
        ft['info'] = {
            'video.height': ft['shape'][0],
            'video.width': ft['shape'][1],
            'video.codec': 'av1' if vcodec == 'libsvtav1' else vcodec,
            'video.pix_fmt': 'yuv420p',
            'video.is_depth_map': False,
            'video.fps': fps,
            'video.channels': 3,
            'has_audio': False,
        }
    n_ep = len(rows_episodes)
    info = {
        'codebase_version': CODEBASE_VERSION,
        'robot_type': robot_type,
        'total_episodes': n_ep,
        'total_frames': total,
        'total_tasks': len(tasks),
        'total_videos': n_ep * len(cams),
        'total_chunks': (n_ep - 1) // CHUNK + 1,
        'chunks_size': CHUNK,
        'fps': fps,
        'splits': {'train': f'0:{n_ep}'},
        'data_path': DATA_PATH,
        'video_path': VIDEO_PATH if cams else None,
        'features': features,
    }
    meta_dir = out / 'meta'
    (meta_dir / 'info.json').write_text(json.dumps(info, indent=4, ensure_ascii=False))
    (meta_dir / 'tasks.jsonl').write_text(
        ''.join(dump({'task_index': k, 'task': text}) + '\n' for text, k in tasks.items())
    )
    (meta_dir / 'episodes.jsonl').write_text(''.join(dump(r) + '\n' for r in rows_episodes))
    (meta_dir / 'episodes_stats.jsonl').write_text(''.join(dump(r) + '\n' for r in rows_stats))
    (meta_dir / 'source_episodes.jsonl').write_text(''.join(dump(r) + '\n' for r in rows_source))
    (meta_dir / 'conversion.json').write_text(
        json.dumps(
            {
                'fps': fps,
                'height': height,
                'action': action,
                'keep_idle': keep_idle,
                'crop_xywh': {cam: list(crops[cam]) for cam in cams if cam in crops},
            },
            indent=4,
        )
    )
    return {'episodes': n_ep, 'frames': total, 'skipped': skipped, 'tasks': list(tasks)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--task', required=True, help='the task name the episodes were recorded with')
    ap.add_argument('--root', default=str(ep.DATA), help='where the recorded episodes are')
    ap.add_argument('-o', '--out', help='dataset folder (default data/lerobot/<task>)')
    ap.add_argument('--overwrite', action='store_true', help='replace an existing dataset folder')
    ap.add_argument('--plan', action='store_true', help='list the episodes and stop')
    ap.add_argument('--cams', default='top,wrist', help="'top,wrist', one of them, or 'none'")
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument(
        '--height', type=int, default=480, help='picture height in pixels, the width follows (0: as recorded)'
    )
    ap.add_argument(
        '--crop',
        action='append',
        default=[],
        metavar='CAM=x,y,w,h',
        help="cut this rectangle out of a camera's pictures before scaling (pixels as recorded); once per camera",
    )
    ap.add_argument('--action', choices=('target', 'next-state'), default='target')
    ap.add_argument(
        '--keep-idle', action='store_true', help='keep the frames before the first and after the last engaged moment'
    )
    ap.add_argument('--include-failed', action='store_true', help='also take episodes marked failed')
    ap.add_argument(
        '--include-sim',
        action='store_true',
        help='also take simulator episodes (they have no cameras: use --cams none)',
    )
    ap.add_argument('--instruction', help='task text for all episodes, instead of the one recorded with them')
    ap.add_argument('--robot-type', default='rebot_b601_rs')
    ap.add_argument('--vcodec', choices=('h264', 'libsvtav1'), default='h264')
    ap.add_argument('--crf', type=int, default=23, help='video quality (lower is better and larger)')
    args = ap.parse_args()

    cams = () if args.cams == 'none' else tuple(c.strip() for c in args.cams.split(','))
    out = Path(args.out) if args.out else ep.ROOT / 'data' / 'lerobot' / args.task
    try:
        crops = parse_crops(args.crop)
    except ValueError as e:
        print(f'REFUSED: {e}')
        return 2
    if set(crops) - set(cams):
        print(f'REFUSED: --crop names {sorted(set(crops) - set(cams))}, the cameras are {list(cams)}')
        return 2
    chosen, left_out = select(Path(args.root), args.task, args.include_failed, args.include_sim)
    print(f"task '{args.task}' in {args.root}: {len(chosen)} episodes to convert, {len(left_out)} left out")
    for line in left_out:
        print(f'  left out  {line}')
    texts = sorted({args.instruction or m.get('instruction') or '' for _, m in chosen})
    print(
        '  task text: '
        + '; '.join(f'"{t}"' if t else f"(none recorded: the task name '{args.task}' is used)" for t in texts)
    )
    if not chosen:
        return 1
    if args.plan:
        for path, m in chosen:
            print(f'  {path.name}  #{m.get("index")}  {m.get("end_unix", 0) - m.get("start_unix", 0):.1f} s')
        for cam, crop in crops.items():
            file = out.with_name(f'{out.name}-crop-{cam}.jpg')
            crop_preview(chosen, cam, crop, file)
            print(f'  crop of {cam}: see {file}')
        return 0
    if out.exists():
        if not args.overwrite:
            print(f'REFUSED: {out} exists (--overwrite replaces it)')
            return 2
        if not (out / 'meta' / 'info.json').is_file():
            print(f'REFUSED: {out} exists and is not a LeRobot dataset: not deleting it')
            return 2
        shutil.rmtree(out)
    print(
        f'writing {out}: {args.fps} fps, cameras {", ".join(c + (" cut to %d,%d,%d,%d" % crops[c] if c in crops else "") for c in cams) or "none"}, action = '
        + ('commanded joint target' if args.action == 'target' else 'joint angles one step later')
    )
    r = convert(
        chosen,
        out,
        cams,
        args.fps,
        args.height,
        args.action,
        args.keep_idle,
        args.instruction,
        args.robot_type,
        args.vcodec,
        args.crf,
        crops=crops,
    )
    if not r['episodes']:
        print('nothing converted')
        return 1
    size = sum(f.stat().st_size for f in out.rglob('*') if f.is_file()) / 1e6
    print(
        f'{r["episodes"]} episodes, {r["frames"]} frames ({r["frames"] / args.fps / 60:.1f} min), {len(r["skipped"])} skipped, {size:.0f} MB in {out}'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
