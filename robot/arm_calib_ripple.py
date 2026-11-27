"""Calibrate the motors' angle-periodic torque ripple (shoulder and elbow) and check the feedforward against it.

    uv run python robot/arm_calib_ripple.py                    # real arm: print the plan only, nothing moves
    uv run python robot/arm_calib_ripple.py --yes              # real arm: sweep, fit, write calibration/b601_rs.yaml
    uv run python robot/arm_calib_ripple.py --yes --ripple-ff 1   # same sweeps with the feedforward on: compare only
    uv run python robot/arm_calib_ripple.py --from-data calibration/data/ripple-*.npz    # refit, no arm
    uv run python robot/arm_calib_ripple.py --sim --sim-ripple    # the whole procedure in the simulator

Why: at low speed the RS-06 motors of the shoulder and elbow need a torque that varies with the joint angle, one
period every 2.86 deg (126 per turn). The position loop cannot reject it, so slow straight lines of the tool tip
come out bumpy (found with robot/arm_line_test.py on 2026-11-17). The control library can feed this torque
forward (`ripple` in the calibration file); this tool measures it.

What it does: unfolds to home, goes to --center, and moves one joint at a time back and forth by +-amplitude at
each of --speeds while the others hold. From the motor torques it fits, per joint, the number of periods per turn
and the sine and cosine of the ripple (mean of the two directions, see rebot_control/calib/ripple.py), and writes
them to the `ripple` section of the calibration file, keeping everything else. Then home, fold, torque off.
The raw sweeps go to calibration/data/ripple-<time>.npz.

Reported for every joint and speed is also the unevenness of the motion: how far the measured angle strays from
uniform motion during the constant-speed part of a pass (RMS, deg). With --ripple-ff the sweeps run with the
feedforward at that scale and nothing is written: compare the unevenness with a run at 0.

The model belongs to the joints' zero positions: after re-zeroing a motor, run this again.

Real arm: only with the operator at the motor power switch, after telling them what will happen
(docs/en/user/robot-arm-tools.md). Every sweep is checked against calibration/workspace.yaml first.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm_move import go_home, load_workspace, start_pose, violation  # noqa: E402
from rebot_control import Arm, ArmConfig, RobotModel, ToolConfig  # noqa: E402
from rebot_control.calib.friction import collect_sweeps  # noqa: E402
from rebot_control.calib.ripple import fit_joint_ripple, to_ripple_params  # noqa: E402
from rebot_control.config import Calibration, FrictionParams, RippleParams  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CENTER_DEG = '0,84,89,-65,0,0'  # rod vertical, tip at about (0.28, 0, 0.16) m
SIM_RIPPLE = {
    'cycles': [126, 126, 126, 0, 0, 0],
    'a1': [0.25, 0.30, -0.25, 0, 0, 0],
    'b1': [0.20, -0.20, 0.40, 0, 0, 0],
}
MAX_SHARE = 0.72  # of kp: the library refuses a model above 0.75


def limited(rp: RippleParams, kp: np.ndarray) -> tuple[RippleParams, np.ndarray]:
    """The model with every joint scaled down so that N x amplitude stays within MAX_SHARE of its kp, and the factors.

    The feedforward acts like a position feedback of N x amplitude; with the phase wrong it would cancel that much
    of kp. On a joint with a low kp the measured ripple can be too strong to compensate in full.
    """
    stiff = rp.stiffness()
    factor = np.where(stiff > MAX_SHARE * kp, MAX_SHARE * kp / np.maximum(stiff, 1e-9), 1.0)
    return RippleParams(rp.cycles.copy(), rp.a1 * factor, rp.b1 * factor, rp.a2 * factor, rp.b2 * factor), factor


def unevenness(data: dict[str, np.ndarray]) -> dict[float, float]:
    """RMS distance (deg) of the measured angle from uniform motion in the constant-speed part of each pass, per speed."""
    j = int(data['joint'])
    t, q, v = data['t'], np.degrees(data['q'][:, j]), data['v_nom']
    out: dict[float, list] = {}
    edges = np.flatnonzero(np.abs(np.diff(v)) > 1e-9) + 1
    for a, b in zip(np.r_[0, edges], np.r_[edges, len(v)], strict=True):
        if abs(v[a]) < 1e-9 or b - a < 150 or np.any(np.diff(t[a:b]) > 0.1):
            continue
        a2, b2 = a + 45, b - 15  # the joint filter lets the speed settle
        r = q[a2:b2] - np.polyval(np.polyfit(t[a2:b2], q[a2:b2], 1), t[a2:b2])
        out.setdefault(round(math.degrees(abs(v[a])), 3), []).append(float(np.mean(r**2)))
    return {s: math.sqrt(float(np.mean(m))) for s, m in sorted(out.items())}


def coulomb(model: RobotModel, data: dict[str, np.ndarray]) -> dict[float, float]:
    """Dry friction of the swept joint (N*m) per speed (deg/s): half the difference of the mean of
    (motor torque - gravity model) between the two directions, which cover the same angles."""
    j = int(data['joint'])
    q, v = data['q'], data['v_nom']
    d = model.new_data()
    out = {}
    for s in np.unique(np.round(np.abs(v[np.abs(v) > 0]), 6)):
        means = []
        for sign in (1.0, -1.0):
            k = np.flatnonzero(np.isclose(v, sign * s))
            k = k[
                (q[k, j] > q[:, j].min() + math.radians(2.0)) & (q[k, j] < q[:, j].max() - math.radians(2.0))
            ]  # away from the turns
            means.append(float(np.mean(data['tau'][k, j] - np.array([model.gravity(q[i], d)[j] for i in k]))))
        out[round(math.degrees(s), 3)] = 0.5 * (means[0] - means[1])
    return out


def save_calibration(path: Path, cal: Calibration) -> None:
    """Write the calibration file, keeping the comment lines at its top."""
    head = []
    if path.is_file():
        for line in path.read_text().splitlines():
            if not line.startswith('#'):
                break
            head.append(line)
    cal.save(path)
    if head:
        path.write_text('\n'.join(head) + '\n' + path.read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        '--joints', default='2,3', help='joints to calibrate, numbered from 1 (default: shoulder and elbow)'
    )
    ap.add_argument('--center', default=CENTER_DEG, help="pose the sweeps are centred on, 'deg,...' (6 values)")
    ap.add_argument('--amplitude', type=float, default=15.0, help='each joint moves by +- this (deg)')
    ap.add_argument('--speeds', default='3,6', help='sweep speeds (deg/s): slow, the ripple fades at speed')
    ap.add_argument('--cycles', type=int, help='periods per turn (default: found from the data)')
    ap.add_argument(
        '--ripple-ff',
        type=float,
        default=0.0,
        help='run the sweeps with the ripple feedforward at this scale (0..1) '
        'and write nothing: to see what the calibration achieves',
    )
    ap.add_argument(
        '--friction-scale',
        type=float,
        help='share of the measured dry friction that is fed forward (0..1); '
        'default: what the calibration file says, 0.7 if it says nothing',
    )
    ap.add_argument(
        '--end', choices=('fold', 'hold'), default='fold', help='fold and torque off, or keep holding at home'
    )
    ap.add_argument('--sim', action='store_true')
    ap.add_argument(
        '--sim-ripple', action='store_true', help='simulator: give the simulated shoulder and elbow a known ripple'
    )
    ap.add_argument('--yes', action='store_true', help='real arm: actually move (default: print the plan only)')
    ap.add_argument('--tool', default=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'))
    ap.add_argument('--calibration', default=str(ROOT / 'calibration' / 'b601_rs.yaml'))
    ap.add_argument('--workspace', default=str(ROOT / 'calibration' / 'workspace.yaml'))
    ap.add_argument('--from-data', help='refit a saved ripple-*.npz, no arm')
    ap.add_argument('--no-save', action='store_true')
    args = ap.parse_args()

    cal_path = Path(args.calibration)
    joints = [int(j) - 1 for j in args.joints.split(',')]
    speeds = tuple(math.radians(float(v)) for v in args.speeds.split(','))
    amplitude = math.radians(args.amplitude)
    center = np.radians([float(v) for v in args.center.split(',')])
    if max(speeds) > math.radians(15.0) or not 0.0 <= args.ripple_ff <= 1.0 or args.amplitude > 25.0:
        print('REFUSED: speeds up to 15 deg/s, amplitude up to 25 deg, --ripple-ff between 0 and 1')
        return 2
    cal = Calibration.load(cal_path) if cal_path.is_file() else Calibration()
    if args.friction_scale is not None and not 0.0 <= args.friction_scale <= 1.0:
        print('REFUSED: --friction-scale must be between 0 and 1')
        return 2

    if args.from_data:
        raw = np.load(args.from_data)
        names = ArmConfig.load('b601_rs').joints
        data = {
            j: {k: raw[f'{names[j]}_{k}'] for k in ('t', 'q', 'dq', 'tau', 'v_nom', 'joint')}
            for j in joints
            if f'{names[j]}_q' in raw
        }
        model = RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(args.tool), cal)
        sim = False
    else:
        if args.ripple_ff > 0 and cal.ripple is None and not args.sim_ripple:
            print('REFUSED: --ripple-ff needs a ripple model in the calibration file (run without it first)')
            return 2
        if args.sim:
            sys.path.insert(0, str(ROOT / 'sim'))
            from scene import make_arm

            kw = {'truth_ripple': SIM_RIPPLE} if args.sim_ripple else {}
            arm_cm = make_arm(calibration=cal_path, **kw)
            if args.sim_ripple and args.ripple_ff > 0 and cal.ripple is None:
                # the simulator's own ripple as the model, limited like a calibrated one
                arm_cm.cfg.ripple = limited(RippleParams.from_dict(SIM_RIPPLE, arm_cm.n), arm_cm.cfg.gains.kp)[0]
        else:
            arm_cm = Arm.from_config('b601_rs', tool=args.tool, calibration=args.calibration, backend='real')
        arm_cm.cfg.feedforward.ripple_scale = args.ripple_ff  # 0 while calibrating: measure the whole ripple
        if args.ripple_ff == 0:
            arm_cm.cfg.feedforward.friction_scale = 0.0  # and the whole friction
        lo, hi = load_workspace(Path(args.workspace))
        sim = args.sim
        with arm_cm as arm:
            model = arm.model
            folded, at_home, roll = start_pose(arm)
            print(
                f'start: q {np.round(np.degrees(arm.q()), 1).tolist()} deg'
                + ('  (motors already enabled: taking the hold over)' if arm.taken_over else '')
            )
            if not (folded or at_home):
                print(
                    "REFUSED: the arm is neither folded nor at the tool's home pose. Bring it there first (robot/arm_move.py) or release it (robot/arm release)."
                )
                return 2
            problems, mdata = [], model.new_data()
            for j in joints:
                for s in np.linspace(-1.0, 1.0, 41):
                    q = center.copy()
                    q[j] += s * amplitude
                    why = violation(model, q, lo, hi, mdata)
                    if why:
                        problems.append(f'{arm.cfg.joints[j]} at {math.degrees(q[j]):.0f} deg: {why}')
                        break
            seconds = sum(4 * amplitude / v + 3 for v in speeds) * len(joints) + 40
            print(
                f'sweeps centred on {np.round(np.degrees(center), 1).tolist()} deg (tip {np.round(model.fk(center)[0], 3).tolist()} m): '
                f'joints {[j + 1 for j in joints]} one at a time, +-{args.amplitude:g} deg at {args.speeds} deg/s, about {seconds:.0f} s in all'
            )
            for j in joints:
                ends = [np.round(model.fk(center + np.eye(6)[j] * s * amplitude)[0], 2).tolist() for s in (-1, 1)]
                print(
                    f'  {arm.cfg.joints[j]}: {math.degrees(center[j] - amplitude):.0f}..{math.degrees(center[j] + amplitude):.0f} deg, tip between {ends[0]} and {ends[1]} m'
                )
            print(
                f'  ripple feedforward during the sweeps: scale {args.ripple_ff:g}'
                + ('' if args.ripple_ff == 0 else ' (comparison run: nothing is written)')
                + f'; then: {"fold, torque off" if args.end == "fold" else "keep holding at home, enabled"}'
            )
            if abs(roll) > math.radians(5.0) and folded and not at_home:
                print(f'  the tool hangs rolled by {math.degrees(roll):+.0f} deg: joint 6 is levelled first, in place')
            if problems:
                print('REFUSED:\n  ' + '\n  '.join(problems))
                return 2
            if not args.sim and not args.yes:
                print('plan only: nothing moved (add --yes to move the real arm)')
                return 0
            arm.enable()
            go_home(arm)
            arm.move_to_joint(center, speed=math.radians(15.0))
            data = {}
            for j in joints:
                print(f'{arm.cfg.joints[j]}:', flush=True)
                data[j] = collect_sweeps(arm, j, center, amplitude, speeds, progress=lambda s: print(s, flush=True))
                arm.move_to_joint(center, speed=math.radians(15.0))
            arm.move_to_joint(np.asarray(arm.tool.home, dtype=float), speed=math.radians(15.0))
            names = arm.cfg.joints
            if args.end == 'hold':
                arm.detach()
            else:
                print('folding to the zero pose, then torque off', flush=True)
        if not sim:
            stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
            out = (
                ROOT
                / 'calibration'
                / 'data'
                / f'ripple-{stamp}{"-ff" + format(args.ripple_ff, "g") if args.ripple_ff else ""}.npz'
            )
            np.savez(out, **{f'{names[j]}_{k}': v for j, d in data.items() for k, v in d.items()})
            print(f'raw data: {out}')

    print()
    fits, dry = [], {}
    for j, d in data.items():
        fc = coulomb(model, d)
        dry[j] = float(np.mean(list(fc.values())))
        print(f'joint {j + 1}: dry friction ' + ', '.join(f'{f:.2f} N*m at {s:g} deg/s' for s, f in fc.items()))
        une = unevenness(d)
        print(
            f'joint {j + 1}: unevenness of the motion '
            + ', '.join(f'{u:.3f} deg at {s:g} deg/s' for s, u in une.items())
        )
        f = fit_joint_ripple(model, d, cycles=args.cycles)
        fits.append(f)
        print(
            f'  ripple: {f.cycles} periods per turn ({360 / f.cycles:.2f} deg), amplitude {f.amplitude:.2f} N*m '
            f'(forward {f.amplitude_dir[0]:.2f} at {f.phase_dir[0]:+.0f} deg, backward {f.amplitude_dir[1]:.2f} at {f.phase_dir[1]:+.0f} deg); '
            f'second harmonic {math.hypot(f.a2, f.b2):.2f} N*m'
        )
        print(
            f'  the model explains {f.explained * 100:.0f} % of the torque variation ({f.rms_before:.2f} -> {f.rms_after:.2f} N*m RMS; '
            f'{f.explained_dir * 100:.0f} % with a separate fit per direction), {f.samples} samples'
        )
    if args.ripple_ff > 0:
        print(
            'comparison run with the feedforward on: the torque above is what the motors still had to deliver in total; nothing written'
        )
        return 0
    kp = np.asarray(cal.gains.get('kp', ArmConfig.load('b601_rs').gains.kp), dtype=float)
    measured = to_ripple_params(fits, 6)
    new, factor = limited(measured, kp)
    print(
        f'position-feedback strength of the measured ripple, N x amplitude: {np.round(measured.stiffness(), 1).tolist()} N*m/rad (kp {kp.tolist()})'
    )
    for f in fits:
        if factor[f.joint] < 1.0:
            print(
                f'  joint {f.joint + 1}: too strong for kp = {kp[f.joint]:g} to be compensated in full; the model is saved at {factor[f.joint] * 100:.0f} % '
                f'({f.amplitude * factor[f.joint]:.2f} of {f.amplitude:.2f} N*m)'
            )
    rp = cal.ripple if cal.ripple is not None else RippleParams.zeros(6)
    for f in fits:
        for k in ('cycles', 'a1', 'b1', 'a2', 'b2'):
            getattr(rp, k)[f.joint] = getattr(new, k)[f.joint]
    rp.check(kp)
    fr = cal.friction if cal.friction is not None else FrictionParams.zeros(6)
    for j, f in dry.items():
        fr.fc_pos[j] = fr.fc_neg[j] = max(f, 0.0)
    scale = args.friction_scale if args.friction_scale is not None else cal.feedforward.get('friction_scale', 0.7)
    print(
        f'dry friction model {np.round(fr.fc_pos, 2).tolist()} N*m, fed forward at {scale:g} of it along the commanded direction of motion'
    )
    if args.no_save or (sim and not args.from_data):
        print('calibration file not written')
        return 0
    meta = {
        'ripple_date': dt.datetime.now().isoformat(timespec='seconds'),
        'ripple_joints': [j + 1 for j in data],
        'ripple_amplitude': [round(f.amplitude, 3) for f in fits],
        'ripple_explained': [round(f.explained, 3) for f in fits],
        'ripple_saved_share': [round(float(factor[f.joint]), 3) for f in fits],
        'ripple_note': "torque ripple per joint angle from slow single-joint sweeps (robot/arm_calib_ripple.py); belongs to the joints' zeros",
    }
    meta['friction_note'] = (
        'dry friction per joint from the same sweeps (half the torque difference between directions)'
    )
    save_calibration(
        cal_path,
        cal.merge(Calibration(ripple=rp, friction=fr, feedforward={'friction_scale': float(scale)}, meta=meta)),
    )
    print(f'saved {cal_path} (ripple, friction and feedforward sections)')
    print(yaml.safe_dump({'ripple': rp.to_dict()}, default_flow_style=None).strip())
    return 0


if __name__ == '__main__':
    sys.exit(main())
