import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
TEST_ENV = ROOT / "tests" / ".env.test"
FRONTEND_URL = "http://localhost:3100"
BACKEND_URL = "http://localhost:8100"


def run(command):
    print(f"\n> {' '.join(map(str, command))}")
    return subprocess.run(command, cwd=ROOT).returncode


def wait_for(url, process, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited before becoming ready: {url}")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {url}")


def stop(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def run_e2e():
    if not TEST_ENV.exists():
        raise RuntimeError(
            "Create tests/.env.test from tests/.env.test.example before running E2E tests."
        )

    test_values = {key: value for key, value in dotenv_values(TEST_ENV).items() if value}
    required = {"SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY"}
    missing = sorted(required - test_values.keys())
    if missing:
        raise RuntimeError(f"Missing test settings: {', '.join(missing)}")

    environment = os.environ.copy()
    environment.update(test_values)
    environment["FRONTEND_ORIGIN"] = FRONTEND_URL
    environment["TEST_FRONTEND_URL"] = FRONTEND_URL
    environment["TEST_BACKEND_URL"] = BACKEND_URL

    backend = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import truststore; truststore.inject_into_ssl(); "
                "import uvicorn; uvicorn.run('main:app', port=8100)"
            ),
        ],
        cwd=ROOT / "backend",
        env=environment,
    )
    frontend = subprocess.Popen(
        ["node", "server.js"],
        cwd=ROOT / "frontend",
        env={**environment, "PORT": "3100"},
    )

    try:
        wait_for(f"{BACKEND_URL}/api/health", backend)
        wait_for(f"{FRONTEND_URL}/", frontend)
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                "tests/pytest.ini",
                "tests/e2e",
            ],
            cwd=ROOT,
            env=environment,
        ).returncode
    finally:
        stop(frontend)
        stop(backend)


def main():
    parser = argparse.ArgumentParser(description="Run the Axiom test suites.")
    parser.add_argument("--fast", action="store_true", help="Skip browser E2E tests.")
    args = parser.parse_args()

    fast_result = run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "tests/pytest.ini",
            "tests/unit",
            "tests/integration",
        ]
    )
    if fast_result:
        return fast_result

    if args.fast:
        return 0

    return run_e2e()


if __name__ == "__main__":
    raise SystemExit(main())
