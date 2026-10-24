"""Exercise the real Node server in a disposable directory."""
import http.client
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time


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
