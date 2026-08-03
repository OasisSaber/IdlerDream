"""Regression smoke test for the packaged Sidecar executable (CR-24 / issue #13).

The PyInstaller output is only built by ``scripts/build-sidecar.ps1`` (or the
``sidecar-packaging`` CI job), so this test is skipped when the executable is
absent. When present it launches the exe with an isolated data directory and
asserts the two readiness signals the desktop app depends on:

1. the read API answers ``/health`` with ``status: ok``; and
2. the private Windows control named pipe answers a ``ping`` command.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

SIDECAR_EXE = Path(__file__).resolve().parents[1] / "dist" / "idlerdream-sidecar.exe"

_READY_DEADLINE_SECONDS = 60
_POLL_INTERVAL_SECONDS = 0.5


def _packaged_exe_available() -> bool:
    return os.name == "nt" and SIDECAR_EXE.exists()


pytestmark = pytest.mark.skipif(
    not _packaged_exe_available(),
    reason="packaged Windows sidecar executable not present; run scripts/build-sidecar.ps1",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _control_ping(profile: str, token: str) -> dict:
    """Send one authenticated ``ping`` over the named control pipe."""
    import pywintypes
    import win32file
    import win32pipe

    pipe_name = rf"\\.\pipe\IdlerDream-{profile}"
    last_error: BaseException | None = None
    deadline = time.monotonic() + _READY_DEADLINE_SECONDS
    handle = None
    while time.monotonic() < deadline:
        try:
            handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            break
        except pywintypes.error as exc:
            last_error = exc
            if exc.winerror == 231:  # ERROR_PIPE_BUSY
                try:
                    win32pipe.WaitNamedPipe(pipe_name, 1000)
                except pywintypes.error:
                    pass
            time.sleep(_POLL_INTERVAL_SECONDS)
    if handle is None:
        raise AssertionError(f"control pipe {pipe_name} never became available: {last_error}")
    try:
        request = json.dumps({"token": token, "command": "ping"}).encode("utf-8") + b"\n"
        win32file.WriteFile(handle, request)
        _, data = win32file.ReadFile(handle, 65536)
        return json.loads(data.decode("utf-8"))
    finally:
        win32file.CloseHandle(handle)


def _kill_process_tree(pid: int) -> None:
    """Kill a process and all descendants (Windows taskkill /T).

    PyInstaller onefile boots the app in a child process, so terminating only
    the bootloader leaves the real sidecar alive, holding the port and locking
    the exe file. /T ensures the whole tree is reaped.
    """
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)


def test_packaged_sidecar_becomes_ready(tmp_path: Path) -> None:
    api_port = _free_port()
    read_token = "smoke-read-token"
    control_token = "smoke-control-token"
    profile = f"smoke-{os.getpid()}"
    env = os.environ.copy()
    env.update(
        {
            "IDLERDREAM_DATA_DIR": str(tmp_path),
            "IDLERDREAM_PROFILE": profile,
            "IDLERDREAM_MOCK_INSPECTOR": "1",
            "IDLERDREAM_API_PORT": str(api_port),
            "IDLERDREAM_READ_TOKEN": read_token,
            "IDLERDREAM_CONTROL_TOKEN": control_token,
        }
    )

    process = subprocess.Popen(
        [str(SIDECAR_EXE)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        base_url = f"http://127.0.0.1:{api_port}"
        deadline = time.monotonic() + _READY_DEADLINE_SECONDS
        last_error: BaseException | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = b""
                if process.stdout is not None:
                    output = process.stdout.read()
                pytest.fail(
                    f"packaged sidecar exited early with code {process.returncode}\n{output.decode('utf-8', errors='replace')}"
                )
            try:
                response = httpx.get(
                    f"{base_url}/health",
                    headers={"X-IdlerDream-Read-Token": read_token},
                    timeout=2,
                )
                if response.status_code == 200:
                    assert response.json()["status"] == "ok"
                    break
            except httpx.HTTPError as exc:
                last_error = exc
            time.sleep(_POLL_INTERVAL_SECONDS)
        else:
            output = b""
            if process.stdout is not None:
                output = process.stdout.read()
            pytest.fail(
                f"packaged sidecar never became ready: {last_error}\n{output.decode('utf-8', errors='replace')}"
            )

        response = _control_ping(profile, control_token)
        assert response == {"ok": True, "result": {"status": "ok"}}, response
    finally:
        if process.poll() is None:
            _kill_process_tree(process.pid)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
