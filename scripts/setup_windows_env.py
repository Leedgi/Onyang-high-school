"""현재 Python으로 실행 환경을 준비하고, 다른 버전의 기존 환경은 삭제 없이 백업한다."""
from datetime import datetime
import json
from pathlib import Path
import struct
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (3, 14)
PROBE = "import json,sys,struct,sysconfig; print(json.dumps({'version':list(sys.version_info[:2]),'bits':struct.calcsize('P')*8,'free_threaded':bool(sysconfig.get_config_var('Py_GIL_DISABLED')),'venv':sys.prefix!=sys.base_prefix}))"


def environment_python(path: Path) -> Path:
    return path / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def compatible(path: Path) -> bool:
    try:
        result = subprocess.run([str(environment_python(path)), "-c", PROBE],
                                capture_output=True, text=True, timeout=30, check=True)
        info = json.loads(result.stdout)
        return (info["version"] == list(REQUIRED) and info["bits"] == 64
                and not info["free_threaded"] and info["venv"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return False


def ensure_environment(root: Path = ROOT) -> Path:
    if (sys.version_info[:2] != REQUIRED or struct.calcsize('P') != 8
            or sysconfig.get_config_var('Py_GIL_DISABLED')):
        raise ValueError("Run setup with standard Python 3.14 x64 (not the free-threaded build).")
    target = root / ".venv"
    if compatible(target):
        print("Using the existing Python 3.14 environment.")
        return target
    if target.exists():
        backups = root / ".venv-backups"
        backups.mkdir(exist_ok=True)
        backup = backups / datetime.now().strftime("environment-%Y%m%d-%H%M%S-%f")
        target.rename(backup)
        print(f"Previous environment preserved: {backup}")
    subprocess.run([sys.executable, "-m", "venv", str(target)], check=True)
    if not compatible(target):
        raise ValueError("The new Python 3.14 environment could not be verified.")
    print("Created a Python 3.14 x64 environment. OCR model files remain in .cache.")
    return target


if __name__ == "__main__":
    try:
        ensure_environment()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Environment preparation failed: {exc}", file=sys.stderr)
        print("Close the running app and terminals using .venv, then retry setup. Previous environments are preserved.", file=sys.stderr)
        raise SystemExit(1)
