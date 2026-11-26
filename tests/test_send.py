"""Checks of `asfinger send` against a local HTTP server that stands in for the Fusion add-in. Run: uv run pytest"""

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from asfinger.__main__ import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, 'hardware', 'configs', 'iphone17pro_default.json')


origins = []  # the Origin header of each request: the add-in refuses a request that has one


def serve(seen):
    class Fake(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get('Content-Length', 0))
            seen.append((self.path, self.headers.get('Content-Type'), json.loads(self.rfile.read(n))))
            origins.append(self.headers.get('Origin'))
            body = json.dumps({'ok': True, 'queued': True}).encode()
            self.send_response(202)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(('127.0.0.1', 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, 'argv', ['asfinger', 'send', *args])
    main()


def test_send_posts_the_config_path_and_the_edits(monkeypatch, capsys):
    seen = []
    srv = serve(seen)
    port = str(srv.server_address[1])
    try:
        rel = os.path.relpath(CFG)
        run(monkeypatch, rel, '--port', port)
        run(monkeypatch, rel, '--set', 'rod_L=150', '--set', 'rod_tilt=25', '--rebuild', '--save', '--port', port)
    finally:
        srv.shutdown()
        srv.server_close()
    out = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line) for line in out] == [{'ok': True, 'queued': True}] * 2
    assert [(p, t) for p, t, _ in seen] == [('/ipush/apply', 'application/json')] * 2
    assert origins[-2:] == [None, None]
    # the path is absolute (Fusion has another working directory); values of --set are sent as text
    assert seen[0][2] == {'config': CFG, 'params': {}, 'mode': 'update', 'save': False}
    assert seen[1][2] == {
        'config': CFG,
        'params': {'rod_L': '150', 'rod_tilt': '25'},
        'mode': 'rebuild',
        'save': True,
    }


def test_send_without_the_addin_prints_a_message(monkeypatch, capsys):
    with socket.socket() as s:  # a port that nothing listens on
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    run(monkeypatch, CFG, '--port', str(port))
    assert f'Fusion add-in not reachable on port {port}' in capsys.readouterr().out
