from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import Awaitable, Callable
from typing import Any

ControlHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class ControlServer:
    """Private JSON-line control channel.

    Windows uses a named pipe so the renderer-facing HTTP service can remain read-only.
    Non-Windows development uses a loopback TCP fallback.
    """

    def __init__(
        self,
        handler: ControlHandler,
        token: str,
        *,
        profile: str,
        host: str = "127.0.0.1",
        port: int = 38174,
    ) -> None:
        self.handler = handler
        self.token = token
        self.profile = profile
        self.host = host
        self.port = port
        self.pipe_name = rf"\\.\pipe\IdlerDream-{profile}"
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: asyncio.AbstractServer | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if os.name == "nt":
            self._thread = threading.Thread(target=self._windows_loop, daemon=True)
            self._thread.start()
            return
        self._server = await asyncio.start_server(self._handle_stream, self.host, self.port)

    async def stop(self) -> None:
        self._stop.set()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_stream(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=15)
            response = await self._dispatch_line(line)
            writer.write(json.dumps(response, ensure_ascii=False).encode() + b"\n")
            await writer.drain()
        except Exception as exc:  # noqa: BLE001 - control boundary must answer the client
            writer.write(json.dumps({"ok": False, "error": str(exc)}).encode() + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def _dispatch_line(self, line: bytes) -> dict[str, Any]:
        try:
            request = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return {"ok": False, "error": f"Invalid control request: {exc}"}
        if request.get("token") != self.token:
            return {"ok": False, "error": "Unauthorized control request"}
        payload = await self.handler(request)
        return {"ok": True, "result": payload}

    def _windows_loop(self) -> None:
        try:
            import pywintypes
            import win32file
            import win32pipe
        except ImportError:
            return
        assert self._loop is not None
        security_attributes = _current_user_only_security_attributes()
        while not self._stop.is_set():
            pipe = win32pipe.CreateNamedPipe(
                self.pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                4,
                65536,
                65536,
                1000,
                security_attributes,
            )
            try:
                try:
                    win32pipe.ConnectNamedPipe(pipe, None)
                except pywintypes.error as exc:
                    if exc.winerror == 232:  # ERROR_NO_DATA: client connected then closed
                        continue
                    if exc.winerror != 535:  # ERROR_PIPE_CONNECTED
                        raise
                chunks: list[bytes] = []
                disconnected = False
                while True:
                    try:
                        _, data = win32file.ReadFile(pipe, 65536)
                    except pywintypes.error as exc:
                        if exc.winerror == 109:  # ERROR_BROKEN_PIPE
                            disconnected = True
                            break
                        raise
                    chunks.append(bytes(data))
                    if b"\n" in data:
                        break
                line = b"".join(chunks).split(b"\n", 1)[0]
                if disconnected or not line:
                    # Client disconnected before sending a complete request.
                    continue
                future = asyncio.run_coroutine_threadsafe(self._dispatch_line(line), self._loop)
                try:
                    response = future.result(timeout=30)
                except Exception as exc:  # noqa: BLE001 - pipe client must receive an error reply
                    response = {"ok": False, "error": str(exc)}
                try:
                    win32file.WriteFile(
                        pipe, json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n"
                    )
                except pywintypes.error:
                    # Client disconnected before reading the reply; the pipe is
                    # torn down in the finally block below.
                    pass
            finally:
                try:
                    win32pipe.DisconnectNamedPipe(pipe)
                except Exception:  # noqa: BLE001,S110 - best-effort pipe teardown
                    pass
                win32file.CloseHandle(pipe)


def _current_user_only_security_attributes() -> object:
    """Build SECURITY_ATTRIBUTES for the control pipe DACL.

    The named pipe is reachable by any local process that can open it, so token
    secrecy alone is not a sufficient boundary (CR-22). Grant access only to
    the current user and to SYSTEM; everyone else - including the Everyone and
    Interactive groups - is denied at the kernel level.
    """
    import win32api
    import win32con
    import win32security

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
    )
    user_sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
    dacl = win32security.ACL()
    access = win32con.GENERIC_READ | win32con.GENERIC_WRITE
    for sid in (system_sid, user_sid):
        dacl.AddAccessAllowedAce(win32security.ACL_REVISION, access, sid)
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorDacl(1, dacl, 0)
    attributes = win32security.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    return attributes
