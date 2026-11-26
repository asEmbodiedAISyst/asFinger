"""Fusion script: pick a resolved.json written by `asfinger build` and build it as a parametric design in a new
document. Install: Utilities > Add-Ins > Scripts and Add-Ins > + > choose this folder."""

import os
import sys
import traceback

import adsk.core

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(os.path.dirname(HERE), 'asfinger_fusion')
if LIB not in sys.path:
    sys.path.insert(0, LIB)


def run(context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        import importlib

        import asfinger_fusion

        importlib.reload(asfinger_fusion)
        dlg = ui.createFileDialog()
        dlg.title = 'Choose an asFinger resolved.json'
        dlg.filter = 'resolved.json (*.json)'
        if dlg.showOpen() != adsk.core.DialogResults.DialogOK:
            return
        logs = []
        s = asfinger_fusion.build(app, dlg.filename, new_document=True, log=logs.append)
        msg = f'Built {len(s["parts"])} parts and {s["joint_origins"]} joint origins.'
        if logs:
            msg += '\n\n' + '\n'.join(logs)
        ui.messageBox(msg, 'asFinger')
    except Exception:
        ui.messageBox(traceback.format_exc(), 'asFinger: failed')
