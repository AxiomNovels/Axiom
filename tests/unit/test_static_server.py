"""Exercise the real Node server in a disposable directory."""
import http.client
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


def test_malformed_urls_and_sibling_traversal_do_not_crash_or_escape(tmp_path):
    root = Path(__file__).resolve().parents[2]
    shutil.copyfile(root / 'frontend/server.js', tmp_path / 'server.js')
    (tmp_path / 'public').mkdir()
    (tmp_path / 'public/index.html').write_text('healthy')
    (tmp_path / 'public-private').mkdir()
    (tmp_path / 'public-private/sentinel.txt').write_text('must stay private')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(['node', 'server.js'], cwd=tmp_path, env={**os.environ, 'PORT': str(port)}, stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1): break
            except OSError: time.sleep(.1)
        for path, expected in [('/%',400),('/%2e%2e%2fpublic-private/sentinel.txt',400),('/%00',400),('/',200)]:
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            connection.request('GET', path)
            response = connection.getresponse()
            body = response.read()
            connection.close()
            assert response.status == expected, path
            assert b'must stay private' not in body
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_local_runtime_follows_backend_without_sharing_secrets(tmp_path):
    root = Path(__file__).resolve().parents[2]
    shutil.copyfile(root / 'frontend/server.js', tmp_path / 'server.js')
    (tmp_path / 'public').mkdir()
    state = {"enabled": True, "status": 200}

    class Backend(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == '/api/analytics/config'
            body = json.dumps({"enabled": state["enabled"], "secret": "must-not-reach-browser"}).encode()
            self.send_response(state["status"])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    backend = ThreadingHTTPServer(('127.0.0.1', 0), Backend)
    thread = Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'PORT': str(port), 'API_BASE': f'http://127.0.0.1:{backend.server_port}'}
    env.pop('ANALYTICS_ENABLED', None)
    process = subprocess.Popen(['node', 'server.js'], cwd=tmp_path, env=env, stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1): break
            except OSError: time.sleep(.1)

        def config():
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            connection.request('GET', '/runtime-config.js')
            response = connection.getresponse()
            body = response.read().decode()
            assert response.status == 200
            assert response.getheader('Cache-Control') == 'no-store'
            assert 'must-not-reach-browser' not in body
            assert f'http://127.0.0.1:{backend.server_port}/api/analytics/events' in body
            connection.close()
            return body

        assert 'analyticsEnabled: true' in config()
        state['enabled'] = False
        assert 'analyticsEnabled: false' in config()
        state['enabled'] = 'true'  # A malformed response must not enable collection.
        assert 'analyticsEnabled: false' in config()
        state['enabled'] = True
        state['status'] = 503
        assert 'analyticsEnabled: false' in config()
    finally:
        process.terminate()
        process.wait(timeout=5)
        backend.shutdown(); backend.server_close(); thread.join()
