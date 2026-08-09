"""Control-channel authorization tests (CR-22).

The named-pipe token is strong, but the production security posture also
depends on the pipe DACL: any local process may try to open the pipe, so
token secrecy must not be the only boundary. These tests verify:

- the Windows pipe is created with a current-user-only DACL (current user +
  SYSTEM only; Everyone/Anonymous/Interactive/Users are excluded);
- unauthenticated and wrong-token requests are rejected over the real pipe;
- a valid-token request is served.

Cross-user negative tests (opening the pipe as another Windows user) require a
second logon session and are not practical inside a single pytest run. The DACL
assertion below provably denies other users at the kernel level, which is the
mechanism those tests would exercise.

Blocking win32 pipe calls run in a worker thread (``asyncio.to_thread``) so the
event loop stays free to serve ``run_coroutine_threadsafe`` dispatch callbacks,
mirroring how the real Electron client connects from a separate process.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import pytest

from idlerdream.control import ControlServer


async def _handler(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("command") == "ping":
        return {"status": "ok"}
    if request.get("command") == "echo":
        return {"echo": request.get("payload")}
    raise ValueError(f"Unknown command: {request.get('command')}")


def _run_scenario(profile: str, token: str, scenario) -> None:
    async def main() -> None:
        server = ControlServer(_handler, token, profile=profile)
        await server.start()
        try:
            # Blocking win32 client calls run off the event loop.
            await asyncio.to_thread(scenario, server.pipe_name)
        finally:
            await server.stop()

    asyncio.run(main())


def _open_pipe(pipe_name: str, timeout_seconds: float = 15.0):
    """Open a named pipe as a client, retrying ERROR_PIPE_BUSY."""
    import pywintypes
    import win32file
    import win32pipe

    deadline = time.monotonic() + timeout_seconds
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            return win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
        except pywintypes.error as exc:
            last_error = exc
            if exc.winerror == 231:  # ERROR_PIPE_BUSY
                try:
                    win32pipe.WaitNamedPipe(pipe_name, 1000)
                except pywintypes.error:
                    pass
            time.sleep(0.05)
    raise AssertionError(f"control pipe {pipe_name} never became available: {last_error}")


def _pipe_request(pipe_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    import win32file

    handle = _open_pipe(pipe_name)
    try:
        win32file.WriteFile(handle, json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
        _, data = win32file.ReadFile(handle, 65536)
        return json.loads(data.decode("utf-8"))
    finally:
        win32file.CloseHandle(handle)


def _pipe_raw_request(pipe_name: str, raw: bytes) -> dict[str, Any]:
    """Send raw bytes over the pipe and parse the JSON response."""
    import win32file

    handle = _open_pipe(pipe_name)
    try:
        win32file.WriteFile(handle, raw + b"\n")
        _, data = win32file.ReadFile(handle, 65536)
        return json.loads(data.decode("utf-8"))
    finally:
        win32file.CloseHandle(handle)


def _unique_profile() -> str:
    return f"test-{os.getpid()}-{time.monotonic_ns()}"


@pytest.mark.skipif(os.name != "nt", reason="named pipe ACL test requires Windows")
def test_control_pipe_dacl_grants_current_user_only() -> None:
    import win32api
    import win32con
    import win32file
    import win32security

    token = "acl-test-token"
    profile = _unique_profile()

    def scenario(pipe_name: str) -> None:
        handle = _open_pipe(pipe_name)
        try:
            descriptor = win32security.GetSecurityInfo(
                handle,
                win32security.SE_KERNEL_OBJECT,
                win32security.DACL_SECURITY_INFORMATION,
            )
            dacl = descriptor.GetSecurityDescriptorDacl()
        finally:
            win32file.CloseHandle(handle)

        assert dacl is not None, "pipe must have an explicit DACL"
        process_token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
        )
        user_sid = win32security.GetTokenInformation(process_token, win32security.TokenUser)[0]
        system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
        excluded_sids = [
            win32security.CreateWellKnownSid(win32security.WinWorldSid, None),
            win32security.CreateWellKnownSid(win32security.WinAnonymousSid, None),
            win32security.CreateWellKnownSid(win32security.WinInteractiveSid, None),
            win32security.CreateWellKnownSid(win32security.WinBuiltinUsersSid, None),
        ]

        found_user = found_system = False
        for index in range(dacl.GetAceCount()):
            (ace_type, _ace_flags), mask, sid = dacl.GetAce(index)
            assert ace_type == win32con.ACCESS_ALLOWED_ACE_TYPE, (
                f"unexpected ACE type {ace_type} on control pipe"
            )
            if sid == user_sid:
                assert mask & win32file.FILE_GENERIC_READ, "current user must be able to read the pipe"
                assert mask & win32file.FILE_GENERIC_WRITE, "current user must be able to write the pipe"
                found_user = True
            if sid == system_sid:
                found_system = True
            assert not any(sid == excluded for excluded in excluded_sids), (
                f"pipe DACL must exclude SID {sid}"
            )

        assert found_user, "current user SID must be present in the pipe DACL"
        assert found_system, "SYSTEM SID must be present in the pipe DACL"

    _run_scenario(profile, token, scenario)


@pytest.mark.skipif(os.name != "nt", reason="named pipe negative test requires Windows")
def test_control_pipe_rejects_wrong_token() -> None:
    profile = _unique_profile()

    def scenario(pipe_name: str) -> None:
        response = _pipe_request(
            pipe_name,
            {"token": "wrong-token", "command": "ping", "payload": {}},
        )
        assert response == {"ok": False, "error": "Unauthorized control request"}

    _run_scenario(profile, "real-token", scenario)


@pytest.mark.skipif(os.name != "nt", reason="named pipe negative test requires Windows")
def test_control_pipe_rejects_missing_token() -> None:
    profile = _unique_profile()

    def scenario(pipe_name: str) -> None:
        response = _pipe_request(
            pipe_name,
            {"command": "ping", "payload": {}},
        )
        assert response == {"ok": False, "error": "Unauthorized control request"}

    _run_scenario(profile, "real-token", scenario)


@pytest.mark.skipif(os.name != "nt", reason="named pipe round-trip test requires Windows")
def test_control_pipe_serves_valid_token() -> None:
    token = "valid-token-123"
    profile = _unique_profile()

    def scenario(pipe_name: str) -> None:
        response = _pipe_request(pipe_name, {"token": token, "command": "ping", "payload": {}})
        assert response == {"ok": True, "result": {"status": "ok"}}
        echo = _pipe_request(pipe_name, {"token": token, "command": "echo", "payload": {"a": 1}})
        assert echo == {"ok": True, "result": {"echo": {"a": 1}}}

    _run_scenario(profile, token, scenario)


@pytest.mark.skipif(os.name != "nt", reason="named pipe negative test requires Windows")
def test_control_pipe_rejects_malformed_json() -> None:
    profile = _unique_profile()

    def scenario(pipe_name: str) -> None:
        response = _pipe_raw_request(pipe_name, b"not-json{{{")
        assert response["ok"] is False
        assert "Invalid control request" in response["error"]

    _run_scenario(profile, "real-token", scenario)


@pytest.mark.skipif(os.name != "nt", reason="named pipe negative test requires Windows")
def test_control_pipe_rejects_non_dict_payload() -> None:
    profile = _unique_profile()

    def scenario(pipe_name: str) -> None:
        # A JSON array is not a command object; it must be rejected without
        # crashing the server (regression for CR-22 type-shape validation).
        response = _pipe_raw_request(pipe_name, b'["not", "an", "object"]')
        assert response["ok"] is False
        assert "Invalid control request" in response["error"]
        # The server must still serve a valid request afterwards.
        ok = _pipe_request(pipe_name, {"token": "real-token", "command": "ping", "payload": {}})
        assert ok == {"ok": True, "result": {"status": "ok"}}

    _run_scenario(profile, "real-token", scenario)


@pytest.mark.skipif(os.name != "nt", reason="named pipe negative test requires Windows")
def test_control_pipe_rejects_unknown_command() -> None:
    profile = _unique_profile()

    def scenario(pipe_name: str) -> None:
        response = _pipe_request(
            pipe_name,
            {"token": "real-token", "command": "definitely-not-a-command", "payload": {}},
        )
        assert response["ok"] is False
        assert "Unknown command" in response["error"]

    _run_scenario(profile, "real-token", scenario)


@pytest.mark.skipif(os.name == "nt", reason="TCP fallback exists only off-Windows")
def test_control_tcp_rejects_wrong_token_and_serves_valid() -> None:
    """The non-Windows loopback fallback must enforce the same token check."""

    async def scenario() -> None:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])

        server = ControlServer(_handler, "real-token", profile=_unique_profile(), port=port)
        await server.start()
        try:
            async def exchange(payload: dict[str, Any]) -> dict[str, Any]:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                try:
                    writer.write(json.dumps(payload).encode("utf-8") + b"\n")
                    await writer.drain()
                    line = await asyncio.wait_for(reader.readline(), timeout=5)
                    return json.loads(line.decode("utf-8"))
                finally:
                    writer.close()
                    await writer.wait_closed()

            denied = await exchange({"token": "bad", "command": "ping", "payload": {}})
            assert denied == {"ok": False, "error": "Unauthorized control request"}
            granted = await exchange({"token": "real-token", "command": "ping", "payload": {}})
            assert granted == {"ok": True, "result": {"status": "ok"}}
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_dispatch_line_rejects_bad_json_with_clear_error() -> None:
    async def check() -> None:
        server = ControlServer(_handler, "tok", profile="unit")
        response = await server._dispatch_line(b"not json at all\n")
        assert response["ok"] is False
        assert "Invalid control request" in response["error"]

    asyncio.run(check())
