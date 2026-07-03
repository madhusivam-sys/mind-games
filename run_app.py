from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Final


ROOT_DIR: Final[Path] = Path(__file__).resolve().parent
SRC_DIR: Final[Path] = ROOT_DIR / "src"
DEFAULT_API_HOST: Final[str] = "127.0.0.1"
DEFAULT_API_PORT: Final[int] = 8000
DEFAULT_DASHBOARD_PORT: Final[int] = 8501


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_DIR) if not existing else f"{SRC_DIR}{os.pathsep}{existing}"
    return env


def _spawn(command: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(command, cwd=ROOT_DIR, env=_base_env())


def start_fastapi(host: str = DEFAULT_API_HOST, port: int = DEFAULT_API_PORT, reload_enabled: bool = True) -> subprocess.Popen[bytes]:
    print("Starting FastAPI server...")
    command = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", host, "--port", str(port)]
    if reload_enabled:
        command.append("--reload")
    return _spawn(command)



def start_streamlit(port: int = DEFAULT_DASHBOARD_PORT) -> subprocess.Popen[bytes]:
    print("Starting Streamlit dashboard...")
    command = [sys.executable, "-m", "streamlit", "run", str(SRC_DIR / "dashboard" / "app.py"), "--server.port", str(port)]
    return _spawn(command)



def run_tests() -> int:
    command = [sys.executable, "-m", "pytest"]
    return subprocess.call(command, cwd=ROOT_DIR, env=_base_env())



def run_all(host: str, api_port: int, dashboard_port: int, reload_enabled: bool) -> int:
    api_process = start_fastapi(host=host, port=api_port, reload_enabled=reload_enabled)
    dashboard_process = start_streamlit(port=dashboard_port)

    print("\nSystem started successfully")
    print(f"Dashboard: http://localhost:{dashboard_port}")
    print(f"API Docs: http://{host}:{api_port}/docs")

    try:
        input("\nPress ENTER to stop servers...")
    finally:
        for process in (api_process, dashboard_process):
            if process.poll() is None:
                process.terminate()
        for process in (api_process, dashboard_process):
            if process.poll() is None:
                process.wait(timeout=10)
    return 0



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launcher for Bazaar Mind Games MVP.")
    parser.add_argument("mode", nargs="?", default="all", choices=["all", "dashboard", "api", "test"], help="Which app surface to run.")
    parser.add_argument("--host", default=DEFAULT_API_HOST, help="API host when mode=api or mode=all.")
    parser.add_argument("--port", type=int, default=DEFAULT_API_PORT, help="API port when mode=api or mode=all.")
    parser.add_argument("--dashboard-port", type=int, default=DEFAULT_DASHBOARD_PORT, help="Streamlit port when mode=dashboard or mode=all.")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn reload when mode=api or mode=all.")
    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "all":
        return run_all(host=args.host, api_port=args.port, dashboard_port=args.dashboard_port, reload_enabled=not args.no_reload)
    if args.mode == "dashboard":
        process = start_streamlit(port=args.dashboard_port)
        return process.wait()
    if args.mode == "api":
        process = start_fastapi(host=args.host, port=args.port, reload_enabled=not args.no_reload)
        return process.wait()
    return run_tests()


if __name__ == "__main__":
    raise SystemExit(main())
