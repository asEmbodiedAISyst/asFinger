"""Record an episode: the arm's servo log and both phones' streams, all on the PC's clock.

As a module (inside the program that moves the arm; only one program may hold the arm):

    from episode import EpisodeRecorder
    with EpisodeRecorder(arm, label="push", cams=("top", "wrist")) as rec:
        ...
        rec.add("tcp_target", np.r_[pos, rot.ravel()])     # optional extra streams, one row per call
    print(rec.path)

From the command line:

    uv run python robot/episode.py record --seconds 10             # phones + the arm, read only: nothing moves
    uv run python robot/episode.py record --seconds 10 --no-arm    # phones only
    uv run python robot/episode.py list                            # all episodes, one line each
    uv run python robot/episode.py info data/episodes/<name>       # what is in it, rates, gaps, clock offsets
    uv run python robot/episode.py sync data/episodes/<name>       # video against arm log, from the motion in it
    uv run python robot/episode.py frames data/episodes/<name> --cam top --every 1.0 -o /some/dir
    uv run python robot/episode.py video data/episodes/<name>                  # top.mp4 / wrist.mp4 next to the .mcap

An episode is a folder under data/episodes/:

    meta.yaml     label, task, index, instruction (the task in words), success (false: marked failed), start and end
                  time, tool, calibration, table height, per-camera device and clock offset, notes
    config/       copies of the tool model, the arm calibration and the table height as they were when recording
    arm.npz       the 150 Hz servo log: t (unix seconds, PC clock), t_arm (the arm's own clock), q, dq, tau, temp,
                  q_cmd, dq_cmd, kp, kd, tau_ff; and every extra stream `name` with its times `name_t`
    top.mcap      what the overhead phone sent, in iMuninn's own format (H.264 video and IMU, not re-encoded);
    wrist.mcap    message log time = capture time on the PC clock (device time + the measured clock offset)

Times: phone samples carry the phone's monotonic time; iMuninn measures the offset to the PC clock when it connects,
and it is measured again when the recording stops (both are in meta.yaml: their difference is the drift). The arm's
servo log uses time.perf_counter on the real arm, converted with an offset taken at start and at stop. In the
simulator the arm's clock is simulated time and no cameras are recorded.

The phones' configuration is not changed. If a phone's capture session is off it is started, and stopped again at
the end. Video can only be decoded from a keyframe on, so every file starts with the last keyframe before the
recording began (up to about a second earlier).
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
import threading
import time
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'episodes'
FIELD = {
    'ImuSample': 'imu',
    'PoseSample': 'pose',
    'VideoFrame': 'video',
    'DepthFrame': 'depth',
    'Gap': 'gap',
    'DeviceHealth': 'health',
}


class Phone:
    """One phone, connected for as long as the program collects data; begin() / end() bracket one episode's file.

    The video of an episode has to start at a keyframe. The phone sends one every second or so, so the messages
    since the last keyframe are kept in memory and written first when an episode begins: the recording starts at
    once (a little before, in fact) instead of waiting for the next keyframe.
    """

    def __init__(self, cam: str) -> None:
        import imuninn
        from snapshot import camera, config_mismatches

        self.cam = cam
        self.host, device_id, self.label = camera(cam)
        self.dev = imuninn.connect(self.host, timeout=10)
        self.warnings: list[str] = []
        if self.dev.info.device_id != device_id:
            self.warnings.append(f'{self.host} is device {self.dev.info.device_id}, not {self.label}')
        mismatches = config_mismatches(self.dev, cam)
        if mismatches:
            self.warnings.append(f'configuration differs from robot/{cam}_camera.yaml: {"; ".join(mismatches)}')
        self._lock = threading.Lock()
        self._gop: list = []  # (field, sample) since the last keyframe, keyframe first
        self._rec = None
        self._closing = None
        self.started_session = False
        self.frames = 0
        self.first_ns: int | None = None
        self.last_ns: int | None = None
        self.path: Path | None = None
        self.offset_start: int | None = None
        self.dev.on('*', self._on_sample)

    def _write(self, field: str, sample) -> None:
        from imuninn.proto import imuninn_pb2 as pb

        if field == 'video':
            t = self.dev.to_pc_time_ns(sample.header.device_time_ns)
            self.first_ns = self.first_ns or t
            self.last_ns = t
            self.frames += 1
        self._rec.write(pb.DataMessage(**{field: sample}))

    def _on_sample(self, stream: str, sample) -> None:
        field = FIELD.get(type(sample).__name__)
        if field is None:
            return
        with self._lock:
            if field == 'video' and sample.keyframe:
                self._gop = []
            if self._gop or field == 'video':
                self._gop.append((field, sample))
                if len(self._gop) > 4000:  # no keyframe for a long time: do not grow for ever
                    self._gop = []
            if self._rec is not None:
                self._write(field, sample)

    def ready(self, timeout: float) -> bool:
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end:
            with self._lock:
                if self._gop:
                    return True
            time.sleep(0.02)
        return False

    def start(self) -> None:
        """Returns once video that can be decoded is arriving (starts the phone's capture session if it is off)."""
        if not self.ready(2.5):
            self.dev.start()
            self.started_session = True
            if not self.ready(8.0):
                raise RuntimeError(
                    f'{self.cam} camera ({self.label}, {self.host}): no video arrives (is the rgb stream enabled?)'
                )

    def begin(self, path: Path) -> None:
        from imuninn.mcap_io import McapRecorder

        if not self.ready(3.0):
            raise RuntimeError(f'{self.cam} camera ({self.label}, {self.host}): the video has stopped')
        # no clock sync here: it takes a few tenths of a second per phone. The offset in use is the one measured
        # when the phone was connected or when the previous episode ended.
        self.offset_start = self.dev.clock_offset_ns
        rec = McapRecorder(path, self.dev.info, self.dev.capabilities, self.dev.clock_offset_ns)
        rec.write_config(self.dev.config)
        with self._lock:
            self.path, self.frames, self.first_ns, self.last_ns = path, 0, None, None
            self._rec = rec
            for field, sample in self._gop:
                self._write(field, sample)

    def detach(self) -> None:
        """Stop writing now; end() finishes the file."""
        with self._lock:
            self._closing, self._rec = self._rec, None

    def end(self) -> dict:
        if self._rec is not None:
            self.detach()
        rec, self._closing = self._closing, None
        offset_end = None
        try:
            offset_end = self.dev.time_sync()
        except Exception as e:  # noqa: BLE001 - the recording is still good without the second offset
            self.warnings.append(f'clock sync at the end failed: {e}')
        if rec is not None:
            rec.close()
        info = {
            'device': self.label,
            'host': self.host,
            'device_id': self.dev.info.device_id,
            'file': self.path.name if self.path else None,
            'video_frames': self.frames,
            'messages': rec.count if rec else 0,
            'first_frame_unix': round(self.first_ns / 1e9, 6) if self.first_ns else None,
            'last_frame_unix': round(self.last_ns / 1e9, 6) if self.last_ns else None,
            'clock_offset_ns_start': int(self.offset_start) if self.offset_start is not None else None,
            'clock_offset_ns_end': int(offset_end) if offset_end is not None else None,
            'session_started_by_recorder': self.started_session,
            'warnings': list(self.warnings),
        }
        return info

    def shutdown(self) -> None:
        if self._rec is not None:
            self.end()
        try:
            if self.started_session:
                self.dev.stop()
        finally:
            self.dev.close()


class Cameras:
    """The phones of a data-collection run: connected once, used by every episode. Close with shutdown()."""

    def __init__(self, names: tuple[str, ...] = ('top', 'wrist')) -> None:
        self.phones: list[Phone] = []
        try:
            for name in names:
                self.phones.append(Phone(name))
            for ph in self.phones:
                ph.start()
        except BaseException:
            self.shutdown()
            raise

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(ph.cam for ph in self.phones)

    def warnings(self) -> list[str]:
        return [f'{ph.cam}: {w}' for ph in self.phones for w in ph.warnings]

    def begin(self, folder: Path) -> None:
        for ph in self.phones:
            ph.begin(folder / f'{ph.cam}.mcap')

    def end(self) -> dict:
        out = {}
        for ph in self.phones:
            ph.detach()  # all phones stop at the same moment; the clock syncs come after
        for ph in self.phones:
            try:
                out[ph.cam] = ph.end()
            except Exception as e:  # noqa: BLE001 - keep what the other phone and the arm recorded
                out[ph.cam] = {'error': str(e)}
        return out

    def shutdown(self) -> None:
        for ph in self.phones:
            try:
                ph.shutdown()
            except Exception:  # noqa: BLE001, S110 - closing: nothing more to do with this phone
                pass
        self.phones = []


class EpisodeRecorder:
    """Servo log of ``arm`` (may be None) and the streams of ``cams``, in one folder. See the module docstring.

    ``cams`` is a tuple of camera names (the phones are connected for this one episode) or a :class:`Cameras`
    that stays connected between episodes.
    """

    def __init__(
        self,
        arm=None,
        label: str = '',
        cams: tuple[str, ...] | Cameras = ('top', 'wrist'),
        root: Path = DATA,
        meta: dict | None = None,
        config_files: tuple[Path, ...] = (),
    ) -> None:
        self.arm, self.label = arm, label
        self.config_files = tuple(Path(f) for f in config_files)
        self.pool = cams if isinstance(cams, Cameras) else None
        self.cams = self.pool.names if self.pool is not None else tuple(cams)
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        sim = bool(arm is not None and arm.is_sim)
        name = stamp + (f'-{label}' if label else '') + ('-sim' if sim else '')
        self.path, n = Path(root) / name, 1
        while self.path.exists():  # a second episode within the same second
            n += 1
            self.path = Path(root) / f'{name}-{n}'
        self.meta = {
            'label': label,
            'created': dt.datetime.now().isoformat(timespec='seconds'),
            'sim': sim,
            'complete': False,
            **(meta or {}),
        }
        self._own_pool = False
        self.extra: dict[str, tuple[list, list]] = {}
        self._clock0: tuple[float, float] | None = None
        self.running = False

    # -- lifecycle
    def start(self) -> EpisodeRecorder:
        if self.pool is None:
            self.pool, self._own_pool = Cameras(self.cams), True
        self.path.mkdir(parents=True, exist_ok=False)
        if self.config_files:  # the models the episode was recorded with, as they were then
            (self.path / 'config').mkdir()
            for f in self.config_files:
                if f.is_file():
                    shutil.copy2(f, self.path / 'config' / f.name)
            self.meta['config'] = sorted(p.name for p in (self.path / 'config').iterdir())
        try:
            self.pool.begin(self.path)
        except BaseException:
            self._close_phones()
            raise
        if self.arm is not None:
            self._clock0 = (time.time(), time.perf_counter())
            self.arm.start_recording()
        self.meta['start_unix'] = round(time.time(), 6)
        self._write_meta()
        self.running = True
        return self

    def add(self, name: str, value, t: float | None = None) -> None:
        """One row of an extra stream (e.g. the commanded tool pose), stamped with the arm's clock."""
        ts, vs = self.extra.setdefault(name, ([], []))
        ts.append(self.arm.now() if t is None and self.arm is not None else (time.perf_counter() if t is None else t))
        vs.append(np.asarray(value, dtype=float).copy())

    def note(self, **kv) -> None:
        self.meta.update(kv)

    def stop(self, complete: bool = True) -> Path:
        if not self.running:
            return self.path
        self.running = False
        self.meta['end_unix'] = round(time.time(), 6)
        if self.arm is not None:
            log = self.arm.stop_recording()
            arm = self.arm
            sim = arm.is_sim
            out = {'t_arm': log.pop('t'), **log}
            if sim:
                out['t'] = out['t_arm'].copy()
                self.meta['arm_clock'] = 'simulated time: t is not unix time'
            else:
                w0, p0 = self._clock0
                w1, p1 = time.time(), time.perf_counter()
                out['t'] = out['t_arm'] + 0.5 * ((w0 - p0) + (w1 - p1))
                self.meta['arm_clock'] = {
                    'offset_start_s': w0 - p0,
                    'offset_end_s': w1 - p1,
                    'drift_ms': round(((w1 - p1) - (w0 - p0)) * 1e3, 3),
                }
            off = out['t'][0] - out['t_arm'][0] if len(out['t']) else 0.0
            for name, (ts, vs) in self.extra.items():
                out[name] = np.array(vs)
                out[name + '_t'] = np.array(ts) + off
            np.savez(self.path / 'arm.npz', **out)
            self.meta['arm'] = {
                'file': 'arm.npz',
                'samples': int(len(out['t'])),
                'tool': str(arm.tool.source or arm.tool.name),
                'tool_name': arm.tool.name,
                'streams': sorted(self.extra),
            }
        self.meta['cameras'] = self._close_phones()
        self.meta['complete'] = bool(complete)
        self._write_meta()
        return self.path

    def _close_phones(self) -> dict:
        if self.pool is None:
            return {}
        out = self.pool.end()
        if self._own_pool:
            self.pool.shutdown()
            self.pool, self._own_pool = None, False
        return out

    def _write_meta(self) -> None:
        (self.path / 'meta.yaml').write_text(yaml.safe_dump(self.meta, sort_keys=False, allow_unicode=True, width=140))

    def __enter__(self) -> EpisodeRecorder:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop(complete=exc_type is None)


# ------------------------------------------------------------------------------------------------- reading
def load(path: Path) -> tuple[dict, dict]:
    """(meta, arm arrays) of an episode; the arm dict is empty when the arm was not recorded."""
    path = Path(path)
    meta = yaml.safe_load((path / 'meta.yaml').read_text())
    arm = dict(np.load(path / 'arm.npz')) if (path / 'arm.npz').is_file() else {}
    return meta, arm


def video_times(path: Path, cam: str) -> np.ndarray:
    """Capture times (unix seconds) of the video frames of one camera."""
    from imuninn.mcap_io import replay_timed

    return np.array([t / 1e9 for _, _, t in replay_timed(Path(path) / f'{cam}.mcap', topics=['/rgb'])])


def frames(path: Path, cam: str, gray: bool = False):
    """Yield (capture time in unix seconds, image in sensor orientation) for every video frame of one camera.

    RGB (H, W, 3), or the luma plane (H, W) with ``gray``. A decoder hands a picture out several frames after it
    was fed (frame threading: about one frame per CPU core), so the times are queued and each picture takes the
    oldest one: pairing a picture with the message that was being fed mislabels it by up to 0.3 s.
    """
    import av
    from imuninn.mcap_io import replay_timed
    from imuninn.proto import imuninn_pb2 as pb

    codec = av.CodecContext.create('h264', 'r')
    times: list[float] = []
    started = False

    def pictures(packet):
        for f in codec.decode(packet):
            if times:
                yield times.pop(0), f.to_ndarray(format='gray' if gray else 'rgb24')

    for _, sample, t in replay_timed(Path(path) / f'{cam}.mcap', topics=['/rgb']):
        if sample.format != pb.PIXEL_FORMAT_H264_NAL or not (started or sample.keyframe):
            continue
        started = True
        times.append(t / 1e9)  # one message carries one picture
        for packet in codec.parse(bytes(sample.data)):
            yield from pictures(packet)
    yield from pictures(None)  # the pictures still inside the decoder


def sync_check(path: Path, tool: str | None = None, calibration: str | None = None) -> dict[str, dict]:
    """Time offset of each camera's video against the arm log, from an episode in which the arm moves.

    The arm's tool speed (from the joint angles) is compared with how fast the picture changes: the mean absolute
    difference between consecutive frames, which rises and falls with the motion in both views. Returned per camera:
    ``offset_ms`` (positive: a frame stamped t shows the arm as it was at t - offset), the correlation there and
    at zero. Needs starts and stops in the episode; a steady periodic motion alone would be ambiguous.
    """
    import cv2
    from rebot_control import ArmConfig, RobotModel, ToolConfig
    from rebot_control.config import Calibration

    meta, arm = load(path)
    tool = tool or meta['arm']['tool']
    cal = calibration or meta.get('calibration') or str(ROOT / 'calibration' / 'b601_rs.yaml')
    model = RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(tool), Calibration.load(cal))
    data = model.new_data()
    t = arm['t'][::3]
    tip = np.array([model.fk(q, data)[0] for q in arm['q'][::3]])
    speed = np.convolve(np.linalg.norm(np.gradient(tip, t, axis=0), axis=1), np.ones(9) / 9, mode='same')
    grid = np.arange(t[0] + 1.0, t[-1] - 1.0, 1 / 60)
    v_arm = np.interp(grid, t, speed)
    out = {}
    for cam in meta.get('cameras') or {}:
        ts, energy, prev = [], [], None
        for tf, img in frames(path, cam, gray=True):
            small = cv2.resize(img, (160, 120), interpolation=cv2.INTER_AREA).astype(np.float32)
            if prev is not None:
                ts.append(tf - 0.5 / 60)  # the change happened between the two frames
                energy.append(float(np.abs(small - prev).mean()))
            prev = small
        e = np.interp(grid, np.array(ts), np.convolve(energy, np.ones(3) / 3, mode='same'))
        lags = np.arange(-30, 31)
        cs = np.array([np.corrcoef(e[40:-40], np.roll(v_arm, int(k))[40:-40])[0, 1] for k in lags])
        i = int(cs.argmax())
        frac = 0.5 * (cs[i - 1] - cs[i + 1]) / (cs[i - 1] - 2 * cs[i] + cs[i + 1]) if 0 < i < len(cs) - 1 else 0.0
        out[cam] = {
            'offset_ms': round(float((lags[i] + frac) / 60 * 1000), 1),
            'correlation': round(float(cs[i]), 3),
            'correlation_at_zero': round(float(cs[30]), 3),
        }
    return out


def describe(path: Path) -> str:
    meta, arm = load(path)
    lines = [
        f"{path}: label '{meta.get('label', '')}', created {meta.get('created')}, complete {meta.get('complete')}"
        + (', SIMULATOR' if meta.get('sim') else '')
    ]
    t0 = meta.get('start_unix', 0.0)
    if arm:
        t = arm['t']
        d = np.diff(t)
        lines.append(
            f'  arm: {len(t)} samples over {t[-1] - t[0]:.2f} s ({1 / np.median(d):.0f} Hz, longest gap {d.max() * 1e3:.1f} ms), '
            f'starts {t[0] - t0:+.3f} s after the recording start'
            + ('' if not meta.get('sim') else ' (simulated time)')
        )
        for k in sorted(arm):
            if k.endswith('_t') and k[:-2] in arm:
                lines.append(
                    f'  arm stream {k[:-2]}: {arm[k[:-2]].shape}, {arm[k][0] - t[0]:+.2f} to {arm[k][-1] - t[0]:+.2f} s of the arm log'
                )
        clock = meta.get('arm_clock')
        if isinstance(clock, dict):
            lines.append(f'  arm clock: drift between start and stop {clock["drift_ms"]:+.3f} ms')
    for cam, c in (meta.get('cameras') or {}).items():
        if 'error' in c:
            lines.append(f'  {cam}: ERROR {c["error"]}')
            continue
        tv = video_times(path, cam)
        d = np.diff(tv)
        drift = (
            (c['clock_offset_ns_end'] - c['clock_offset_ns_start']) / 1e6
            if c.get('clock_offset_ns_end') is not None
            else float('nan')
        )
        lines.append(
            f'  {cam} ({c["device"]}): {len(tv)} frames over {tv[-1] - tv[0]:.2f} s ({1 / np.median(d):.1f} fps, longest gap {d.max() * 1e3:.0f} ms), '
            f'first frame {tv[0] - t0:+.3f} s, last {tv[-1] - meta.get("end_unix", tv[-1]):+.3f} s from the end; '
            f'phone clock offset changed by {drift:+.2f} ms'
        )
        for w in c.get('warnings', []):
            lines.append(f'    warning: {w}')
    return '\n'.join(lines)


def write_mp4(path: Path, cam: str, file: Path, height: int = 720) -> tuple[int, float]:
    """One camera of an episode as an H.264 mp4 that ordinary players open, every frame at its capture time.
    -> (frames, seconds)"""
    from fractions import Fraction

    import av
    import cv2

    file.parent.mkdir(parents=True, exist_ok=True)
    stream, t0, n, last = None, None, 0, -1
    with av.open(str(file), 'w') as container:
        for t, img in frames(path, cam):
            h0, w0 = img.shape[:2]
            h = (height or h0) - (height or h0) % 2
            w = int(round(w0 * h / h0 / 2)) * 2
            if (h, w) != (h0, w0):
                img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA if h < h0 else cv2.INTER_LINEAR)
            if stream is None:
                stream = container.add_stream('h264', rate=60, options={'crf': '23', 'preset': 'veryfast'})
                stream.pix_fmt, stream.width, stream.height = 'yuv420p', w, h
                stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)  # frames carry capture times
                t0 = t
            pts = max(int(round((t - t0) * 1000)), last + 1)  # milliseconds since the first frame, increasing
            last = pts
            frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format='rgb24')
            frame.pts, frame.time_base = pts, Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
            n += 1
        if stream is not None:
            for packet in stream.encode():
                container.mux(packet)
    return n, last / 1000.0 if n else 0.0


# ----------------------------------------------------------------------------------------------------- CLI
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('record', help='record for a fixed time; the arm is only read, nothing moves')
    s.add_argument('--seconds', type=float, default=10.0)
    s.add_argument('--label', default='check')
    s.add_argument('--cams', default='top,wrist', help="'top,wrist', one of them, or 'none'")
    s.add_argument('--no-arm', action='store_true')
    s.add_argument('--root', default=str(DATA))
    s = sub.add_parser('info', help='what an episode contains')
    s.add_argument('episode')
    s = sub.add_parser('list', help='one line per episode: task, number, length, cameras')
    s.add_argument('--root', default=str(DATA))
    s.add_argument('--task', help='only this task')
    s = sub.add_parser(
        'sync', help="time offset between each camera's video and the arm log (the arm must move in the episode)"
    )
    s.add_argument('episode')
    s = sub.add_parser(
        'frames', help='write video frames of an episode as JPEG files named by their time in the episode'
    )
    s.add_argument('episode')
    s.add_argument('--cam', default='top')
    s.add_argument('--every', type=float, default=1.0, help='seconds between the frames written')
    s.add_argument('-o', '--out', required=True)
    s = sub.add_parser(
        'video', help='write each camera of an episode as an mp4 that any player opens (timing as captured)'
    )
    s.add_argument('episodes', nargs='+')
    s.add_argument('--cams', default='top,wrist', help='cameras to write, those an episode does not have are skipped')
    s.add_argument(
        '--height', type=int, default=720, help='picture height in pixels, the width follows (0: as recorded)'
    )
    s.add_argument(
        '-o', '--out', help='folder for the files (default: the episode folder); names are <episode>-<cam>.mp4 then'
    )
    args = ap.parse_args()

    if args.cmd == 'video':
        for ep_dir in map(Path, args.episodes):
            for cam in (c.strip() for c in args.cams.split(',')):
                if not (ep_dir / f'{cam}.mcap').is_file():
                    continue
                file = Path(args.out) / f'{ep_dir.name}-{cam}.mp4' if args.out else ep_dir / f'{cam}.mp4'
                n, seconds = write_mp4(ep_dir, cam, file, args.height)
                print(f'{file}: {n} frames, {seconds:.1f} s')
        return 0
    if args.cmd == 'info':
        print(describe(Path(args.episode)))
        return 0
    if args.cmd == 'list':
        n = 0
        for meta_file in sorted(Path(args.root).glob('*/meta.yaml')):
            m = yaml.safe_load(meta_file.read_text()) or {}
            if args.task and m.get('task') != args.task:
                continue
            n += 1
            length = (
                f'{m["end_unix"] - m["start_unix"]:6.1f} s' if 'end_unix' in m and 'start_unix' in m else '   ?    '
            )
            cams = (
                ', '.join(f'{c} {v.get("video_frames", "?")}' for c, v in (m.get('cameras') or {}).items())
                or 'no cameras'
            )
            task = f'{m["task"]} #{m["index"]}' if 'task' in m and 'index' in m else m.get('label', '')
            print(
                f'{meta_file.parent.name:40s} {task:22s} {length}  arm {(m.get("arm") or {}).get("samples", 0):6d}  {cams}'
                + ('' if m.get('complete') else '   INCOMPLETE')
                + ('   FAILED' if m.get('success') is False else '')
                + ('  sim' if m.get('sim') else '')
            )
        print(f'{n} episodes in {args.root}')
        return 0
    if args.cmd == 'sync':
        for cam, r in sync_check(Path(args.episode)).items():
            print(
                f'{cam}: video is {r["offset_ms"]:+.0f} ms behind the arm log (speed correlation {r["correlation"]:.2f} there, '
                f'{r["correlation_at_zero"]:.2f} at zero offset)'
            )
        return 0
    if args.cmd == 'frames':
        from PIL import Image

        meta, _ = load(Path(args.episode))
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        nxt, n = -1e9, 0
        for t, img in frames(Path(args.episode), args.cam):
            if t - nxt >= args.every:
                nxt = t
                Image.fromarray(img).save(out / f'{args.cam}-{t - meta["start_unix"]:07.3f}s.jpg')
                n += 1
        print(f'{n} frames in {out}')
        return 0

    cams = () if args.cams == 'none' else tuple(c.strip() for c in args.cams.split(','))
    arm_cm = None
    if not args.no_arm:
        from rebot_control import Arm

        arm_cm = Arm.from_config(
            'b601_rs',
            tool=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'),
            calibration=str(ROOT / 'calibration' / 'b601_rs.yaml'),
            backend='real',
        )

    def run(arm) -> Path:
        # the arm is only read: motors that are off stay off, motors left holding keep holding (as `robot/arm state`)
        with EpisodeRecorder(arm, label=args.label, cams=cams, root=Path(args.root)) as rec:
            print(f'recording {args.seconds:g} s to {rec.path}', flush=True)
            t_end = time.monotonic() + args.seconds
            while time.monotonic() < t_end:
                arm.sleep() if arm is not None else time.sleep(0.05)
        return rec.path

    if arm_cm is None:
        path = run(None)
    else:
        with arm_cm as arm:
            path = run(arm)
    print(describe(path))
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
