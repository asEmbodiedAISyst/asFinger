"""Checks of the Pad pusher (pad_finger.json): same TCP as the round rod, the TPU tip and the sensor switch. Run: uv run pytest"""

import os
import tempfile

from asfinger import Model

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'hardware')
PAD = os.path.join(ROOT, 'configs', 'pad_finger.json')
ROUND = os.path.join(ROOT, 'configs', 'iphone17pro_default.json')
SENSOR_PARTS = {'pcb_cover', 'pcb', 'usb_plug'}


def close(a, b, tol):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def parts(m):
    return {p['name'] for p in m.resolve(resolve=True)['parts']}


def test_tcp_and_phone_where_the_round_rod_has_them():
    pad, rnd = Model.load(PAD).resolve(), Model.load(ROUND).resolve()
    for f in ('T_tcp', 'P_phone', 'C_main', 'S_mount'):
        assert close(pad['world'][f].p, rnd['world'][f].p, 0.01), f


def test_one_piece_without_sensor_by_default():
    m = Model.load(PAD)
    names = parts(m)
    assert 'tip_tpu' not in names and not names & SENSOR_PARTS, names
    R = m.resolve()
    for f in ('S_pcb', 'K_cover', 'S_fpc', 'T_recess'):
        assert f not in R['world'], f
    assert m.check(R) == []


def test_tpu_tip_and_sensor_switch():
    tpu = Model.load(PAD).set(tip_split=1)
    assert 'tip_tpu' in parts(tpu) and not parts(tpu) & SENSOR_PARTS
    full = Model.load(PAD).set(tip_split=1).set_options(tactile=True)
    assert {'tip_tpu'} | SENSOR_PARTS <= parts(full)
    _, rep = full.build(tempfile.mkdtemp(), mjcf=False, preview=False)
    _, rep0 = tpu.build(tempfile.mkdtemp(), mjcf=False, preview=False)
    # the TPU tip is the same body with or without the sensor apart from the pad recess and the groove
    assert abs(rep['parts']['tip_tpu']['volume_cm3'] - rep0['parts']['tip_tpu']['volume_cm3']) < 0.5
    # the sensor cuts its groove and pocket into the bar
    assert rep['parts']['tool_body']['volume_cm3'] < rep0['parts']['tool_body']['volume_cm3']
