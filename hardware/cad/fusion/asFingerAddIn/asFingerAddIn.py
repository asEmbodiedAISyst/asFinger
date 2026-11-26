"""asFinger add-in for Fusion.

* A button "asFinger" (Utilities > Add-Ins panel and Solid > Create panel) opens a docked palette that lists the
  parameters of an asFinger config. "Apply" updates the active asFinger design in place (fillets and other
  features that the user added stay); if the active document is not an asFinger design, a new document is built.
* A small HTTP server on 127.0.0.1:47910 lets a script or `python -m asfinger send` push a config to Fusion:
  POST /ipush/apply  {"config": "/abs/path.json" | {...config...}, "params": {...}, "mode": "update"}
  Fusion's API is single-threaded, so the request is handed to the main thread through a custom event.

The geometry code lives in ../asfinger_fusion/asfinger_fusion.py and the model (params, frame solving, CSG) in the
repository's `asfinger` package (src/asfinger); both are pure Python, so nothing needs to be installed into Fusion.

Names kept from the earlier project name (iPush), because stored data and other programs depend on them: the
attribute group "ipush" in a Fusion design, the HTTP path /ipush/apply, the health reply "ipush-fusion" and the
port 47910. The ids of the command, the palette and the custom event are new, so this add-in and the earlier
iPush add-in do not share ids; they still share the port, so only one of them can run the HTTP server.
"""

import json
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import adsk.core
import adsk.fusion

HERE = os.path.dirname(os.path.abspath(__file__))
# <repo>/hardware/cad/fusion/asFingerAddIn -> <repo>
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
# the folder that holds configs/ and assets/: asset paths in a config are relative to it (as in Model.load)
HARDWARE = os.path.join(REPO, 'hardware')
for p in (os.path.join(REPO, 'src'), os.path.join(os.path.dirname(HERE), 'asfinger_fusion')):
    if p not in sys.path:
        sys.path.insert(0, p)

CMD_ID = 'asfinger_palette_cmd'
PALETTE_ID = 'asfinger_palette'
EVENT_ID = 'asfinger_apply_event'
PORT = 47910
SETTINGS = os.path.join(HERE, 'settings.json')
DEFAULT_CONFIG = os.path.join(HARDWARE, 'configs', 'iphone17pro_default.json')

app = adsk.core.Application.get()
ui = app.userInterface
handlers = []
state = {'server': None, 'event': None}


# ----------------------------------------------------------------- helpers
def _reload():
    import importlib

    for k in [k for k in sys.modules if k == 'asfinger' or k.startswith('asfinger.')]:
        del sys.modules[k]
    import asfinger_fusion

    importlib.reload(asfinger_fusion)
    from asfinger import Model

    return Model, asfinger_fusion


def _settings():
    try:
        return json.load(open(SETTINGS, encoding='utf-8'))
    except Exception:
        return {'config': DEFAULT_CONFIG}


def _save_settings(s):
    try:
        json.dump(s, open(SETTINGS, 'w', encoding='utf-8'), indent=1)
    except Exception:
        pass


def _model(config, params):
    Model, _ = _reload()
    if isinstance(config, dict):
        m = Model(config, HARDWARE)
    else:
        m = Model.load(config or _settings()['config'])
    for k, v in (params or {}).items():
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                pass
        m.set(**{k: v})
    return m


def _is_asfinger_design(design):
    # the attribute group keeps the earlier project name: existing designs carry it
    return design is not None and design.rootComponent.attributes.itemByName('ipush', 'signature') is not None


def apply(config=None, params=None, mode='update', save=False, force=False):
    """Main-thread entry: resolve the model and update / rebuild / create the Fusion design."""
    _, F = _reload()
    m = _model(config, params)
    RR = m.resolve(resolve=True)
    problems = m.check(RR)
    if problems and not force:
        return {'ok': False, 'action': 'a check failed: the design was not changed', 'log': problems}
    R = m.resolved_json(RR)
    design = adsk.fusion.Design.cast(app.activeProduct)
    logs = []
    if mode == 'new' or not _is_asfinger_design(design):
        s = F.build(app, R, new_document=True, log=logs.append)
        s['action'] = 'built in a new document'
    elif mode == 'rebuild':
        s = F.build(app, R, new_document=False, log=logs.append)
        s['action'] = 'rebuilt in place'
    else:
        s = F.update(app, R, log=logs.append)
        if not s.get('ok'):
            s['action'] = 'structure changed: press "Rebuild" (features you added will be lost)'
        else:
            s['action'] = 'updated in place'
    if save and not isinstance(config, dict):
        m.save(config or _settings()['config'])
        s['saved'] = config or _settings()['config']
    s['log'] = logs
    s['frames'] = {
        k: [round(v, 2) for v in R['frames'][k]['world']['pos']]
        for k in ('T_tcp', 'C_main', 'S_mount')
        if k in R['frames']
    }
    return s


def config_payload(path=None):
    path = path or _settings()['config']
    m = _model(path, None)
    P = m.params()
    rows = []
    for k, v in m.cfg['params'].items():
        rows.append({'name': k, 'src': v, 'value': P.get(k)})
    # 'server' is False when the port was taken at start-up: the palette then says that requests are not received
    return {
        'config': path,
        'name': m.cfg.get('name'),
        'params': rows,
        'port': PORT,
        'server': state['server'] is not None,
    }


# ----------------------------------------------------------------- palette
class PaletteHTMLHandler(adsk.core.HTMLEventHandler):
    def notify(self, args):
        try:
            data = json.loads(args.data) if args.data else {}
            a = args.action
            if a == 'load':
                if data.get('config'):
                    s = _settings()
                    s['config'] = data['config']
                    _save_settings(s)
                args.returnData = json.dumps({'ok': True, **config_payload(data.get('config'))})
            elif a == 'pick':
                dlg = ui.createFileDialog()
                dlg.title = 'asFinger config'
                dlg.filter = 'asFinger config (*.json)'
                dlg.initialDirectory = os.path.dirname(_settings()['config'])
                if dlg.showOpen() == adsk.core.DialogResults.DialogOK:
                    s = _settings()
                    s['config'] = dlg.filename
                    _save_settings(s)
                    args.returnData = json.dumps({'ok': True, **config_payload(dlg.filename)})
                else:
                    args.returnData = json.dumps({'ok': False, 'cancelled': True})
            elif a == 'apply':
                r = apply(data.get('config'), data.get('params'), data.get('mode', 'update'), data.get('save', False))
                args.returnData = json.dumps({'ok': True, 'result': r})
            else:
                args.returnData = json.dumps({'ok': False, 'error': f'unknown action {a}'})
        except Exception:
            args.returnData = json.dumps({'ok': False, 'error': traceback.format_exc()})


class PaletteClosedHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def notify(self, args):
        pass


def show_palette():
    pal = ui.palettes.itemById(PALETTE_ID)
    if pal is None:
        pal = ui.palettes.add(
            PALETTE_ID, 'asFinger', os.path.join(HERE, 'palette.html'), True, True, True, 360, 640, True
        )
        pal.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        h = PaletteHTMLHandler()
        pal.incomingFromHTML.add(h)
        handlers.append(h)
        c = PaletteClosedHandler()
        pal.closed.add(c)
        handlers.append(c)
    pal.isVisible = True
    return pal


class CmdExecute(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            show_palette()
        except Exception:
            ui.messageBox(traceback.format_exc())


class CmdCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        h = CmdExecute()
        args.command.execute.add(h)
        handlers.append(h)


# ----------------------------------------------------------------- localhost bridge
class ApplyEvent(adsk.core.CustomEventHandler):
    def notify(self, args):
        req = json.loads(args.additionalInfo)
        try:
            r = apply(req.get('config'), req.get('params'), req.get('mode', 'update'), req.get('save', False))
            msg = {'ok': True, 'result': r}
        except Exception:
            msg = {'ok': False, 'error': traceback.format_exc()}
        pal = ui.palettes.itemById(PALETTE_ID)
        if pal is not None:
            pal.sendInfoToHTML('remote', json.dumps({'request': req, **msg}))


class Bridge(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        # the health reply keeps the earlier name: other programs look for it
        self._send(200, {'ok': True, 'app': 'ipush-fusion', 'port': PORT})

    def do_POST(self):
        if self.path.rstrip('/') != '/ipush/apply':
            return self._send(404, {'ok': False})
        n = int(self.headers.get('Content-Length', 0))
        try:
            req = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return self._send(400, {'ok': False, 'error': 'bad json'})
        app.fireCustomEvent(EVENT_ID, json.dumps(req))
        self._send(202, {'ok': True, 'queued': True})

    def log_message(self, *a):
        pass


def start_server():
    try:
        srv = ThreadingHTTPServer(('127.0.0.1', PORT), Bridge)
    except OSError:
        return None
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def port_taken_message():
    return (
        f'asFinger: port {PORT} is in use, so the add-in does not receive configs from `asfinger send` or other '
        'programs. The palette works. Another program holds the port; if the earlier iPush add-in is running, '
        'stop it (Utilities > Add-Ins > Scripts and Add-Ins), then stop and run the asFinger add-in again.'
    )


# ----------------------------------------------------------------- lifecycle
def run(context):
    try:
        cmd = ui.commandDefinitions.itemById(CMD_ID) or ui.commandDefinitions.addButtonDefinition(
            CMD_ID, 'asFinger', 'Edit asFinger parameters and update this design in place', ''
        )
        h = CmdCreated()
        cmd.commandCreated.add(h)
        handlers.append(h)
        for ws_id, panel_id in (
            ('FusionSolidEnvironment', 'SolidScriptsAddinsPanel'),
            ('FusionSolidEnvironment', 'SolidCreatePanel'),
        ):
            ws = ui.workspaces.itemById(ws_id)
            panel = ws.toolbarPanels.itemById(panel_id) if ws else None
            if panel and not panel.controls.itemById(CMD_ID):
                ctl = panel.controls.addCommand(cmd)
                ctl.isPromoted = panel_id == 'SolidCreatePanel'
        ev = app.registerCustomEvent(EVENT_ID)
        eh = ApplyEvent()
        ev.add(eh)
        handlers.append(eh)
        state['event'] = ev
        state['server'] = start_server()
        if state['server'] is None:
            # no message box: the add-in runs on start-up, and the palette shows the same message when it opens
            try:
                app.log(port_taken_message())
            except Exception:
                pass
    except Exception:
        ui.messageBox('asFinger add-in failed to start:\n' + traceback.format_exc())


def stop(context):
    try:
        if state['server']:
            state['server'].shutdown()
            state['server'].server_close()
        app.unregisterCustomEvent(EVENT_ID)
        pal = ui.palettes.itemById(PALETTE_ID)
        if pal:
            pal.deleteMe()
        for ws_id, panel_id in (
            ('FusionSolidEnvironment', 'SolidScriptsAddinsPanel'),
            ('FusionSolidEnvironment', 'SolidCreatePanel'),
        ):
            ws = ui.workspaces.itemById(ws_id)
            panel = ws.toolbarPanels.itemById(panel_id) if ws else None
            c = panel.controls.itemById(CMD_ID) if panel else None
            if c:
                c.deleteMe()
        d = ui.commandDefinitions.itemById(CMD_ID)
        if d:
            d.deleteMe()
    except Exception:
        pass
