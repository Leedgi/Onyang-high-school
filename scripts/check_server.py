"""실제 Streamlit 프로세스의 준비 상태를 확인한다. 자신이 시작한 프로세스만 종료한다."""
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    log_path = artifacts / "server-smoke.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
            "--server.address=127.0.0.1", f"--server.port={port}",
            "--server.headless=true", "--server.fileWatcherType=none",
        ], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    print(f"Server exited with {process.returncode}. See {log_path}")
                    return 1
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as response:
                        healthy = response.status == 200 and response.read().strip() == b"ok"
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                        page = response.status == 200 and b"<html" in response.read().lower()
                    if healthy and page:
                        print("Streamlit HTTP health and page checks passed. Functional checks: pytest / AppTest.")
                        return 0
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.5)
            print(f"Server startup timed out. See {log_path}")
            return 1
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
