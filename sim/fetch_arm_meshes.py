"""Download Seeed's official reBot B601-RS meshes (the twin's arm, sim/twin.yaml base.arm_meshes) into
sim/assets/meshes/b601_rs_official/. They are not kept in this repository: they are fetched from Seeed's repository at
a pinned commit and checked against the SHA-256 list kept next to them (SHA256SUMS).

    uv run python sim/fetch_arm_meshes.py                          # download (about 30 MB) from github.com
    uv run python sim/fetch_arm_meshes.py --from ~/reBot-DevArm    # copy from a local clone of that repository
    uv run python sim/fetch_arm_meshes.py --check                  # only check the files in place
    uv run python sim/fetch_arm_meshes.py --out /tmp/meshes        # somewhere else

Source: https://github.com/Seeed-Projects/reBot-DevArm, Rebot_Arm_description/RS/meshes/ (base_link, link1, link6 from
shared/, the rest from visual/) and the repository's LICENSE (CERN-OHL-W-2.0). The files are used unmodified.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

REPO = 'Seeed-Projects/reBot-DevArm'
COMMIT = 'e0a06261f0c38a42e044821476b4ad664cb289ed'  # main on 2026-11-26
DEST = Path(__file__).resolve().parent / 'assets' / 'meshes' / 'b601_rs_official'
SHARED = {'base_link', 'link1', 'link6'}


def upstream_path(name: str) -> str:
    if name == 'LICENSE':
        return 'LICENSE'
    stem = name.rsplit('.', 1)[0]
    return f'Rebot_Arm_description/RS/meshes/{"shared" if stem in SHARED else "visual"}/{name}'


def expected() -> dict[str, str]:
    """{file name: sha256} from SHA256SUMS (kept in the repository, next to the meshes)."""
    sums = {}
    for line in (DEST / 'SHA256SUMS').read_text().splitlines():
        if line.strip():
            digest, name = line.split()
            sums[name] = digest
    return sums


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(folder: Path, sums: dict[str, str]) -> list[str]:
    """Names of the files that are missing or differ."""
    return [n for n, d in sums.items() if not (folder / n).is_file() or sha256(folder / n) != d]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', type=Path, default=DEST, help=f'where to put them (default {DEST})')
    ap.add_argument('--from', dest='src', type=Path, help='a local clone of the repository instead of downloading')
    ap.add_argument('--check', action='store_true', help='only check the files in place')
    args = ap.parse_args()
    sums = expected()
    out = args.out
    if args.check:
        bad = check(out, sums)
        print(
            f'{len(sums) - len(bad)} of {len(sums)} files match SHA256SUMS'
            + (f'; missing or different: {bad}' if bad else '')
        )
        return 1 if bad else 0
    out.mkdir(parents=True, exist_ok=True)
    for name, digest in sums.items():
        target = out / name
        if target.is_file() and sha256(target) == digest:
            continue
        rel = upstream_path(name)
        tmp = target.with_suffix(target.suffix + '.part')
        if args.src:
            shutil.copyfile(args.src / rel, tmp)
        else:
            url = f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{rel}'
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, 'wb') as f:
                shutil.copyfileobj(r, f)
        if sha256(tmp) != digest:
            tmp.unlink()
            print(f'{name}: checksum differs from SHA256SUMS ({rel}); nothing written for it', file=sys.stderr)
            return 1
        tmp.replace(target)
        print(f'{name}: ok ({target.stat().st_size / 1e6:.1f} MB)', flush=True)
    print(f'all {len(sums)} files in {out} match SHA256SUMS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
