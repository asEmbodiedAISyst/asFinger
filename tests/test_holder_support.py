"""The holder support of all three pushers: a 14 mm beam behind the flange screws, tied to the rod root by a web,
and the spine continued up the back of the holder. The web goes with the beam when the phone is off.
Run: uv run pytest"""

import os

import pytest

from asfinger import Model

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'hardware', 'configs')
PUSHERS = ['iphone17pro_default.json', 'square_rod.json', 'pad_finger.json']


def names(node, out=None):
    out = set() if out is None else out
    if isinstance(node, dict):
        if 'name' in node:
            out.add(node['name'])
        for v in node.values():
            names(v, out)
    elif isinstance(node, list):
        for v in node:
            names(v, out)
    return out


@pytest.mark.parametrize('cfg', PUSHERS)
def test_support_values(cfg):
    P = Model.load(os.path.join(ROOT, cfg)).params()
    assert (P['beam_w'], P['beam_y_in'], P['beam_x']) == (14, -15.5, 0)
    assert (P['beam_web_t'], P['beam_web_h']) == (6, 20)
    assert P['spine_back'] == 1


@pytest.mark.parametrize('cfg', PUSHERS)
def test_web_goes_with_the_beam(cfg):
    m = Model.load(os.path.join(ROOT, cfg))
    on = names(m.view()['parts'])
    assert {'beam', 'beam_web', 'spine_back'} <= on
    off = names(m.set_options(phone=False).view()['parts'])
    assert not {'beam', 'beam_web'} & off
