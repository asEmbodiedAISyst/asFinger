"""Command line:
    python -m asfinger build CONFIG.json -o out/default [--resolve] [--set rod_L=150 --set rod_tilt=20]
    python -m asfinger build CONFIG.json -o out/rod_only --option phone=0     # optional modules
    python -m asfinger frames CONFIG.json
    python -m asfinger send CONFIG.json [--set rod_L=150] [--rebuild] [--save]
The console script `asfinger` is the same as `python -m asfinger`.
send pushes the config to the Fusion add-in (127.0.0.1:47910), which updates the design in place.
--resolve re-runs the solvers and writes the new results back into the config file.
"""

import argparse
import json

from . import Model
from . import geom as G


def main():
    ap = argparse.ArgumentParser(prog='asfinger')
    ap.add_argument('cmd', choices=['build', 'frames', 'send'])
    ap.add_argument('config')
    ap.add_argument('-o', '--out', default='out')
    ap.add_argument('--resolve', action='store_true', help='re-solve solved frames and save results into the config')
    ap.add_argument('--set', action='append', default=[], metavar='NAME=VALUE')
    ap.add_argument(
        '--option',
        action='append',
        default=[],
        metavar='NAME=0|1',
        help='switch an optional module (see "options" in the config)',
    )
    ap.add_argument('--rebuild', action='store_true', help='send: rebuild instead of updating in place')
    ap.add_argument('--save', action='store_true', help='send: let Fusion write the parameters back into the config')
    ap.add_argument('--port', type=int, default=47910)
    a = ap.parse_args()
    if a.cmd == 'send':
        import os
        import urllib.request

        params = {}
        for s in a.set:
            k, v = s.split('=', 1)
            params[k] = v
        body = json.dumps(
            {
                'config': os.path.abspath(a.config),
                'params': params,
                'mode': 'rebuild' if a.rebuild else 'update',
                'save': a.save,
            }
        ).encode()
        req = urllib.request.Request(
            f'http://127.0.0.1:{a.port}/ipush/apply', body, {'Content-Type': 'application/json'}
        )
        try:
            print(urllib.request.urlopen(req, timeout=5).read().decode())
        except OSError as e:
            print(f'Fusion add-in not reachable on port {a.port}: {e}')
        return
    m = Model.load(a.config)
    for s in a.option:
        k, v = s.split('=', 1)
        m.set_options(**{k: v.strip().lower() not in ('0', 'false', 'off', 'no')})
    for s in a.set:
        k, v = s.split('=', 1)
        try:
            v = float(v)
        except ValueError:
            pass
        m.set(**{k: v})
    if a.cmd == 'frames':
        w, l, info = m.frames(resolve=a.resolve)
        for n, T in w.items():
            z = G.col(T.R, 2)
            print(
                f'{n:9s} pos={[round(x, 2) for x in T.p]}  z={[round(x, 3) for x in z]}  {info.get(n, {}).get("source", "")}'
            )
    else:
        R, rep = m.build(a.out, resolve=a.resolve)
        print(json.dumps(rep, indent=1))
    for msg in m.check():
        print('[check]', msg)
    if a.cmd == 'build':
        for msg in rep.get('interference', []):
            print('[interference]', msg)
        for msg in rep.get('warnings', []):
            print('[warning]', msg)
    if a.resolve and not a.set and not a.option:
        m.save(a.config)
        print(f'saved solved results into {a.config}')


if __name__ == '__main__':
    main()
