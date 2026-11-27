"""Record episodes one after another, started and stopped from the keyboard.

    uv run python robot/record.py --task push-cube            # both phones + the arm (read only: nothing moves)
    uv run python robot/record.py --task push-cube --no-arm   # phones only
    uv run python robot/episode.py list                       # what has been recorded

Keys (no Enter needed):  r  start an episode / stop and save it      x  throw the last episode away
                         f  the episode failed: stop and save it marked `success: false` (or mark the last saved one)
                         q  quit (a running episode is saved first)

This script only watches: the arm is read as `robot/arm state` reads it (motors that are off stay off, motors left
holding keep holding), so it records whatever happens to the arm - nothing, or someone moving it by hand with the
torque off. To record while a program moves the arm, that program has to do the recording itself, because only
one program can hold the arm: the teleoperation tools (robot/teleop_iphone.py, robot/teleop_star.py) use the same
Session and the same keys.

Every episode is a folder data/episodes/<time>-<task>/ (format: robot/episode.py), with `task`, `index` (running
number within the task), `instruction` (--instruction: the task in words), `operator` and `success` in its meta.yaml, and
copies of the tool model, arm calibration and table height in config/. A thrown-away episode is moved to data/discarded/, not
deleted. A failed episode stays with the others: robot/to_lerobot.py leaves it out unless asked. The phones stay connected between episodes, so an episode starts the moment the key is pressed.
Messages go through sharklog (robot/log.py), with a live status line under them.
"""

from __future__ import annotations

import argparse
import os
import select
import shutil
import sys
import termios
import time
import tty
from pathlib import Path

import sharklog
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log  # noqa: E402
from episode import DATA, ROOT, Cameras, EpisodeRecorder  # noqa: E402


class Keys:
    """Single key presses from the terminal without waiting, or from a script ("2.5:r,10:r,11:q": time in seconds: key).

    `space` and `enter` are the names of those keys in a script. A script is for tests and the simulator; its clock
    is the one handed to :meth:`get`.
    """

    def __init__(self, script: str | None = None) -> None:
        self.script = None
        if script:
            self.script = sorted(
                (float(a), {'space': ' ', 'enter': '\n'}.get(b, b))
                for a, b in (item.split(':') for item in script.split(','))
            )
        self._old = None

    def __enter__(self) -> Keys:
        if self.script is None:
            if not sys.stdin.isatty():
                raise RuntimeError('this program is driven from the keyboard: run it in a terminal')
            self._old = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, *exc) -> None:
        if self._old is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old)

    def get(self, now: float | None = None) -> str | None:
        if self.script is not None:
            if self.script and now is not None and now >= self.script[0][0]:
                return self.script.pop(0)[1]
            return None
        if select.select([sys.stdin], [], [], 0)[0]:
            return os.read(sys.stdin.fileno(), 1).decode(errors='ignore')
        return None


class Session:
    """Episodes of one task, one after another: begin() / end() / discard_last(), with the phones kept connected."""

    def __init__(
        self,
        arm=None,
        task: str = 'task',
        cams: tuple[str, ...] = ('top', 'wrist'),
        root: Path = DATA,
        operator: str = '',
        meta: dict | None = None,
        instruction: str = '',
        config_files: tuple[Path, ...] = (),
    ) -> None:
        self.arm, self.task, self.root, self.operator = arm, task, Path(root), operator
        self.instruction, self.config_files = instruction, tuple(config_files)
        self.meta = dict(meta or {})
        self.pool = Cameras(tuple(cams)) if cams else None
        self.rec: EpisodeRecorder | None = None
        self.saved: list[Path] = []
        self.failed: set[Path] = set()
        self.index = self._next_index()
        self.t_begin = 0.0

    def _next_index(self) -> int:
        n = -1
        for meta in self.root.glob('*/meta.yaml'):
            try:
                m = yaml.safe_load(meta.read_text())
            except yaml.YAMLError:
                continue
            if isinstance(m, dict) and m.get('task') == self.task and isinstance(m.get('index'), int):
                n = max(n, m['index'])
        return n + 1

    @property
    def recording(self) -> bool:
        return self.rec is not None

    def begin(self, **extra) -> Path:
        if self.rec is not None:
            raise RuntimeError('an episode is already being recorded')
        meta = {
            'task': self.task,
            'index': self.index,
            'instruction': self.instruction,
            'operator': self.operator,
            **self.meta,
            **extra,
        }
        self.rec = EpisodeRecorder(
            self.arm,
            label=self.task,
            cams=self.pool if self.pool is not None else (),
            root=self.root,
            meta=meta,
            config_files=self.config_files,
        )
        self.rec.start()
        self.t_begin = time.monotonic()
        return self.rec.path

    def add(self, name: str, value, t: float | None = None) -> None:
        """One row of an extra stream of the running episode (ignored between episodes)."""
        if self.rec is not None:
            self.rec.add(name, value, t)

    def end(self, complete: bool = True, **note) -> Path | None:
        if self.rec is None:
            return None
        rec, self.rec = self.rec, None
        rec.note(**note)
        path = rec.stop(complete=complete)
        self.saved.append(path)
        self.index += 1
        return path

    def fail_last(self) -> Path | None:
        """Mark the running episode (it is stopped and saved), or else the last one saved in this session, as failed."""
        if self.rec is not None:
            path = self.end(success=False)
        elif self.saved:
            path = self.saved[-1]
            meta = yaml.safe_load((path / 'meta.yaml').read_text())
            meta['success'] = False
            (path / 'meta.yaml').write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=140))
        else:
            return None
        self.failed.add(path)
        return path

    def discard_last(self) -> Path | None:
        """Move the running episode, or else the last one saved in this session, to data/discarded/."""
        if self.rec is not None:
            self.end(complete=False, discarded=True)
        if not self.saved:
            return None
        path = self.saved.pop()
        self.failed.discard(path)
        folder = self.root.parent / 'discarded'  # data/discarded next to data/episodes
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / path.name
        shutil.move(str(path), str(dest))
        self.index = self._next_index()
        return dest

    def close(self) -> None:
        if self.rec is not None:
            self.end(complete=False, interrupted=True)
        if self.pool is not None:
            self.pool.shutdown()
            self.pool = None

    def status(self) -> str:
        if self.rec is not None:
            return f'REC #{self.index} {time.monotonic() - self.t_begin:5.1f} s'
        failed = f' ({len(self.failed)} failed)' if self.failed else ''
        return f'idle, {len(self.saved)} saved{failed}, next #{self.index}'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        '--task', required=True, help='short name of what is being recorded, e.g. push-cube; goes into the folder names'
    )
    ap.add_argument('--instruction', default='', help='the task in words, as a language instruction (into meta.yaml)')
    ap.add_argument('--operator', default='', help='who records (free text, into meta.yaml)')
    ap.add_argument('--cams', default='top,wrist', help="'top,wrist', one of them, or 'none'")
    ap.add_argument('--no-arm', action='store_true', help='do not read the arm')
    ap.add_argument('--root', default=str(DATA))
    ap.add_argument('--keys', help="scripted keys for tests, e.g. '1:r,5:r,6:q'")
    args = ap.parse_args()
    if not args.task.replace('-', '').replace('_', '').isalnum():
        print('REFUSED: --task is used in folder names: letters, digits, - and _ only')
        return 2
    cams = () if args.cams == 'none' else tuple(c.strip() for c in args.cams.split(','))
    log.setup()

    def run(arm) -> None:
        cal = ROOT / 'calibration'
        session = Session(
            arm,
            task=args.task,
            cams=cams,
            root=Path(args.root),
            operator=args.operator,
            instruction=args.instruction,
            config_files=(cal / 'tool_ip17pro_print.yaml', cal / 'b601_rs.yaml', cal / 'table.yaml'),
        )
        t0 = time.monotonic()
        try:
            if session.pool is not None:
                for w in session.pool.warnings():
                    sharklog.warning(w)
            sharklog.info(
                f"task '{args.task}', next episode #{session.index}.   r = start / stop and save   f = failed   x = throw the last one away   q = quit"
            )
            with Keys(args.keys) as keys:
                while True:
                    key = keys.get(time.monotonic() - t0)
                    if key == 'r':
                        if session.recording:
                            sharklog.info(f'saved {session.end(success=True)}')
                        else:
                            sharklog.info(f'recording {session.begin()}')
                    elif key == 'f':
                        path = session.fail_last()
                        sharklog.warning(f'marked failed: {path}' if path else 'nothing to mark')
                    elif key == 'x':
                        dest = session.discard_last()
                        sharklog.warning(f'moved to {dest}' if dest else 'nothing to throw away')
                    elif key == 'q':
                        break
                    if arm is not None:
                        arm.sleep()
                    else:
                        time.sleep(0.02)
                    log.status('  ' + session.status())
        finally:
            if session.recording:
                sharklog.info(f'saved {session.end()}')
            session.close()
            sharklog.info(f'{len(session.saved)} episodes saved in this session')
            log.end_status()

    if args.no_arm:
        run(None)
    else:
        from rebot_control import Arm

        with Arm.from_config(
            'b601_rs',
            tool=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'),
            calibration=str(ROOT / 'calibration' / 'b601_rs.yaml'),
            backend='real',
        ) as arm:
            run(arm)
    return 0


if __name__ == '__main__':
    sys.exit(main())
