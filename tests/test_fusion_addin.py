"""Checks of the Fusion add-in that run without Fusion: the `adsk` modules are replaced by stand-ins, so only the
code that does not touch a Fusion design is exercised (paths, the config payload of the palette, the HTTP bridge,
and the pure-Python helpers of asfinger_fusion). Building or updating a design is not tested here.
Run: uv run pytest"""

import importlib.util
import json
import os
import socket
import struct
import sys
import threading
import types
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUSION = os.path.join(ROOT, 'hardware', 'cad', 'fusion')
ADDIN = os.path.join(FUSION, 'asFingerAddIn', 'asFingerAddIn.py')
LIB = os.path.join(FUSION, 'asfinger_fusion', 'asfinger_fusion.py')
CFG = os.path.join(ROOT, 'hardware', 'configs', 'iphone17pro_default.json')


class _Adsk(types.ModuleType):
    """A stand-in for adsk.core / adsk.fusion: event handler base classes are plain classes (the add-in derives
    from them), everything else is a MagicMock."""

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        value = type(name, (), {}) if name.endswith('Handler') else mock.MagicMock(name=name)
        setattr(self, name, value)
        return value


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def addin(tmp_path):
    """The add-in module, imported with stand-in adsk modules. sys.path and sys.modules are restored afterwards."""
    saved_path = list(sys.path)
    saved_modules = dict(sys.modules)
    adsk = types.ModuleType('adsk')
    adsk.core, adsk.fusion = _Adsk('adsk.core'), _Adsk('adsk.fusion')
    sys.modules.update({'adsk': adsk, 'adsk.core': adsk.core, 'adsk.fusion': adsk.fusion})
    try:
        mod = _load(ADDIN, 'asFingerAddIn_under_test')
        mod.SETTINGS = str(tmp_path / 'settings.json')  # never read or write a settings file beside the add-in
        yield mod
    finally:
        sys.path[:] = saved_path
        for k in list(sys.modules):
            if k not in saved_modules:
                del sys.modules[k]
        sys.modules.update(saved_modules)


def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _serve(addin):
    srv = ThreadingHTTPServer(('127.0.0.1', 0), addin.Bridge)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def test_addin_finds_the_package_and_the_default_config(addin):
    assert addin.REPO == ROOT
    assert os.path.join(ROOT, 'src') in sys.path
    assert os.path.join(FUSION, 'asfinger_fusion') in sys.path
    assert addin._settings()['config'] == CFG and os.path.isfile(CFG)
    Model, lib = addin._reload()
    assert Model.__module__ == 'asfinger' and os.path.samefile(lib.__file__, LIB)
    # a config that arrives as a dict gets the base folder that Model.load gives a config file in hardware/configs
    with open(CFG, encoding='utf-8') as f:
        cfg = json.load(f)
    assert addin._model(cfg, None).base_dir == addin._model(CFG, None).base_dir == os.path.join(ROOT, 'hardware')


def test_names_that_other_programs_and_stored_designs_depend_on(addin):
    # new ids, so the add-in does not collide with the earlier add-in
    assert (addin.CMD_ID, addin.PALETTE_ID, addin.EVENT_ID) == (
        'asfinger_palette_cmd',
        'asfinger_palette',
        'asfinger_apply_event',
    )
    # kept names: the port, and the attribute group that existing Fusion designs carry
    assert addin.PORT == 47910
    _, lib = addin._reload()
    assert lib.ATTR == 'ipush'
    design = mock.MagicMock()
    addin._is_asfinger_design(design)
    design.rootComponent.attributes.itemByName.assert_called_with('ipush', 'signature')
    # the manifest, the folder and the .py file must have the same base name, or Fusion does not load the add-in
    for folder in ('asFingerAddIn', 'asFingerFromJSON'):
        assert os.path.isfile(os.path.join(FUSION, folder, folder + '.py'))
        with open(os.path.join(FUSION, folder, folder + '.manifest'), encoding='utf-8') as f:
            assert json.load(f)['autodeskProduct'] == 'Fusion'


def test_palette_payload_lists_the_parameters(addin):
    p = addin.config_payload()
    assert p['config'] == CFG and p['name'] == 'iphone17pro_default' and p['port'] == 47910
    assert p['server'] is False  # the HTTP server was not started in this test
    rows = {r['name']: r for r in p['params']}
    assert rows['rod_L']['src'] == rows['rod_L']['value']
    # a parameter that is an expression is listed with its source text and its value
    exprs = [r for r in p['params'] if isinstance(r['src'], str)]
    assert exprs and all(isinstance(r['value'], (int, float)) for r in exprs)
    json.dumps(p)  # the palette receives it as JSON
    # edits arrive from the palette as strings
    assert addin._model(CFG, {'rod_L': '150'}).params()['rod_L'] == 150.0
    with pytest.raises(KeyError):
        addin._model(CFG, {'no_such_parameter': '1'})


def test_bridge_health_apply_and_unknown_path(addin):
    srv, port = _serve(addin)
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=5) as r:
            assert json.loads(r.read()) == {'ok': True, 'app': 'ipush-fusion', 'port': 47910}
        body = {'config': CFG, 'params': {'rod_L': '150'}, 'mode': 'update', 'save': False}
        req = urllib.request.Request(f'http://127.0.0.1:{port}/ipush/apply', json.dumps(body).encode())
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.status == 202 and json.loads(r.read()) == {'ok': True, 'queued': True}
        # the request is handed to Fusion's main thread through the custom event, unchanged
        (event_id, info), _ = addin.app.fireCustomEvent.call_args
        assert event_id == 'asfinger_apply_event' and json.loads(info) == body
        for path, data, code in (('/other', b'{}', 404), ('/ipush/apply', b'not json', 400)):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}{path}', data), timeout=5)
            assert e.value.code == code
        assert addin.app.fireCustomEvent.call_count == 1
    finally:
        srv.shutdown()
        srv.server_close()


def test_asfinger_send_reaches_the_bridge(addin, monkeypatch, capsys):
    """The command line and the add-in agree on the path and on the shape of the request."""
    from asfinger.__main__ import main

    srv, port = _serve(addin)
    try:
        argv = ['asfinger', 'send', CFG, '--set', 'rod_L=150', '--rebuild', '--save', '--port', str(port)]
        monkeypatch.setattr(sys, 'argv', argv)
        main()
        assert json.loads(capsys.readouterr().out) == {'ok': True, 'queued': True}
        (_, info), _ = addin.app.fireCustomEvent.call_args
        assert json.loads(info) == {'config': CFG, 'params': {'rod_L': '150'}, 'mode': 'rebuild', 'save': True}
    finally:
        srv.shutdown()
        srv.server_close()


def test_port_in_use_is_reported_not_raised(addin):
    with socket.socket() as busy:
        busy.bind(('127.0.0.1', 0))
        busy.listen(1)
        addin.PORT = busy.getsockname()[1]
        assert addin.start_server() is None
        # run() stores None, logs this message, and the palette payload says that the server is off
        assert str(addin.PORT) in addin.port_taken_message() and 'in use' in addin.port_taken_message()
        addin.state['server'] = None
        addin.run(None)
        assert addin.state['server'] is None
        addin.app.log.assert_called_with(addin.port_taken_message())
        addin.ui.messageBox.assert_not_called()
        assert addin.config_payload()['server'] is False
    addin.PORT = _free_port()
    srv = addin.start_server()
    try:
        assert srv is not None
    finally:
        srv.shutdown()
        srv.server_close()


def test_pure_helpers_of_asfinger_fusion(addin, tmp_path):
    Model, lib = addin._reload()
    m = Model.load(CFG)
    R = m.resolved_json(m.resolve())
    # the signature holds the structure, not the values: a parameter change keeps it, a removed frame changes it
    m2 = Model.load(CFG).set(rod_L=150)
    assert lib.signature(m2.resolved_json(m2.resolve(resolve=True))) == lib.signature(R)
    fewer = dict(R, frames={k: v for k, v in R['frames'].items() if k != 'T_tcp'})
    assert lib.signature(fewer) != lib.signature(R)
    assert lib.param_unit('rod_tilt') == 'deg' and lib.param_unit('v_n') == '' and lib.param_unit('rod_L') == 'mm'
    # a binary STL moved by a pose: same triangle count, vertices shifted
    src = os.path.join(ROOT, 'hardware', 'assets', 'fusion_ref', 'SlideLock_Connector_local.stl')
    out = lib.transformed_stl(src, [10.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0])
    try:
        with open(src, 'rb') as f:
            a = f.read()
        with open(out, 'rb') as f:
            b = f.read()
        assert len(a) == len(b) and a[80:84] == b[80:84]
        va, vb = struct.unpack('<3f', a[96:108]), struct.unpack('<3f', b[96:108])
        assert vb == pytest.approx((va[0] + 10.0, va[1], va[2]), abs=1e-4)
    finally:
        os.remove(out)
    # resolved.json without a usable base_dir: assets are looked for in <repo>/hardware
    out_dir = tmp_path / 'repo' / 'out' / 'x'
    out_dir.mkdir(parents=True)
    (tmp_path / 'repo' / 'hardware' / 'assets').mkdir(parents=True)
    path = out_dir / 'resolved.json'
    path.write_text(json.dumps(dict(R, base_dir='/no/such/folder')), encoding='utf-8')
    assert lib._load(str(path))[1] == str(tmp_path / 'repo' / 'hardware')
    assert lib._load(R)[1] == os.path.join(ROOT, 'hardware')


def test_model_resolves_with_the_standard_library_only():
    """Fusion's Python has no numpy and no manifold3d: the calls that the add-in makes must not need them."""
    import subprocess

    code = (
        'import sys\n'
        "sys.modules['numpy'] = None\n"
        "sys.modules['manifold3d'] = None\n"
        f'sys.path.insert(0, {os.path.join(ROOT, "src")!r})\n'
        'from asfinger import Model\n'
        f'm = Model.load({CFG!r})\n'
        'RR = m.resolve(resolve=True)\n'
        'assert m.check(RR) == []\n'
        "print(len(m.resolved_json(RR)['parts']))\n"
    )
    r = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True)
    assert r.returncode == 0 and int(r.stdout) > 0, r.stderr
