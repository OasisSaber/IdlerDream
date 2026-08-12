"""Secret storage for Inspector provider credentials.

Windows production path: Windows Credential Manager (advapi32 ``Cred*W``)
with target ``IdlerDream/Inspector/<provider>``. The secret never touches
SQLite, settings.json, renderer state or logs.

Non-Windows fallback: DPAPI-protected file (reuses the storage KeyProtector),
kept only so the code path stays testable on CI.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from ..storage.raw_reports import KeyProtector

_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_CRED_MAX_CREDENTIAL_BLOB_SIZE = 5 * 1024 * 1024


class _CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", wintypes.LPBYTE),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("User", wintypes.LPWSTR),
    ]


def _load_advapi32() -> ctypes.WinDLL | None:
    if os.name != "nt":
        return None
    try:
        return ctypes.WinDLL("advapi32", use_last_error=True)
    except (OSError, AttributeError):
        return None


def _cred_write(advapi32: ctypes.WinDLL, target: str, secret: bytes) -> None:
    blob = ctypes.create_string_buffer(secret)
    credential = _CREDENTIAL()
    credential.Type = _CRED_TYPE_GENERIC
    credential.TargetName = target
    credential.CredentialBlobSize = len(secret)
    credential.CredentialBlob = ctypes.cast(blob, wintypes.LPBYTE)
    credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
    credential.User = None
    ok = advapi32.CredWriteW(ctypes.byref(credential), 0)
    if not ok:
        error = ctypes.get_last_error()
        raise OSError(error, f"CredWriteW failed (error {error})")


def _cred_read(advapi32: ctypes.WinDLL, target: str) -> bytes | None:
    handle = ctypes.c_void_p()
    ok = advapi32.CredReadW(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(handle))
    if not ok:
        error = ctypes.get_last_error()
        # ERROR_NOT_FOUND (1168): credential does not exist.
        if error == 1168:
            return None
        raise OSError(error, f"CredReadW failed (error {error})")
    try:
        cred = ctypes.cast(handle, ctypes.POINTER(_CREDENTIAL)).contents
        size = cred.CredentialBlobSize
        if size > _CRED_MAX_CREDENTIAL_BLOB_SIZE:
            raise OSError("credential blob exceeds size limit")
        raw = ctypes.string_at(cred.CredentialBlob, size)
        return raw
    finally:
        advapi32.CredFree(handle)


def _cred_delete(advapi32: ctypes.WinDLL, target: str) -> bool:
    ok = advapi32.CredDeleteW(target, _CRED_TYPE_GENERIC, 0)
    if ok:
        return True
    error = ctypes.get_last_error()
    if error == 1168:  # already absent
        return False
    raise OSError(error, f"CredDeleteW failed (error {error})")


class CredentialStore:
    """Stores one secret per Inspector provider.

    Only ``configured`` / ``missing`` state and never the secret itself is
    exposed to callers that do not explicitly ask for it.
    """

    def __init__(self, data_dir: Path, protector: KeyProtector | None = None) -> None:
        self.data_dir = Path(data_dir).resolve(strict=False)
        self._advapi32 = _load_advapi32()
        self._protector = protector or KeyProtector(self.data_dir)
        self._fallback_dir = self.data_dir / "credentials"

    def _target(self, provider: str) -> str:
        if not provider or "/" in provider or "\\" in provider:
            raise ValueError("provider must be a simple name without separators")
        return f"IdlerDream/Inspector/{provider}"

    def _fallback_path(self, provider: str) -> Path:
        return self._fallback_dir / f"{provider}.enc"

    def set(self, provider: str, secret: str) -> bool:
        """Store the secret; returns True once configured."""
        if not secret:
            raise ValueError("secret must not be empty")
        target = self._target(provider)  # validates provider naming
        payload = secret.encode("utf-8")
        if self._advapi32 is not None:
            _cred_write(self._advapi32, target, payload)
            return True
        self._fallback_dir.mkdir(parents=True, exist_ok=True)
        self._fallback_path(provider).write_bytes(self._protector.protect(payload))
        return True

    def get(self, provider: str) -> str | None:
        """Returns the secret or None when not configured."""
        if self._advapi32 is not None:
            raw = _cred_read(self._advapi32, self._target(provider))
            return raw.decode("utf-8") if raw is not None else None
        path = self._fallback_path(provider)
        if not path.is_file():
            return None
        return self._protector.unprotect(path.read_bytes()).decode("utf-8")

    def delete(self, provider: str) -> bool:
        """Removes the secret; returns True when a credential existed."""
        if self._advapi32 is not None:
            return _cred_delete(self._advapi32, self._target(provider))
        path = self._fallback_path(provider)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def configured(self, provider: str) -> bool:
        return self.get(provider) is not None
