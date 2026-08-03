from __future__ import annotations

import base64
import ctypes
import json
import os
import threading
from ctypes import wintypes
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..database import Database


class KeyProtector:
    """Protects small data keys with DPAPI on Windows and a local dev key elsewhere.

    The AES-GCM dev key is a development convenience only. On Windows the code
    must go through DPAPI; the fallback path is intentionally unreachable there
    and must never be shipped as the Windows production path.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._fallback_key_path = data_dir / "config" / ".dev-key"

    def protect(self, plaintext: bytes) -> bytes:
        if os.name == "nt":
            self._assert_windows_production_path()
            return _dpapi_protect(plaintext)
        key = self._fallback_key()
        nonce = os.urandom(12)
        return nonce + AESGCM(key).encrypt(nonce, plaintext, b"idlerdream-raw-report-key-v1")

    def unprotect(self, ciphertext: bytes) -> bytes:
        if os.name == "nt":
            self._assert_windows_production_path()
            return _dpapi_unprotect(ciphertext)
        key = self._fallback_key()
        nonce, body = ciphertext[:12], ciphertext[12:]
        return AESGCM(key).decrypt(nonce, body, b"idlerdream-raw-report-key-v1")

    @staticmethod
    def _assert_windows_production_path() -> None:
        if not hasattr(ctypes, "windll") or not hasattr(ctypes.windll, "crypt32"):
            raise RuntimeError(
                "Windows DPAPI is unavailable; refusing to fall back to the "
                "development key on the Windows production path"
            )

    def _fallback_key(self) -> bytes:
        if self._fallback_key_path.exists():
            return self._fallback_key_path.read_bytes()
        self._fallback_key_path.parent.mkdir(parents=True, exist_ok=True)
        key = AESGCM.generate_key(bit_length=256)
        self._fallback_key_path.write_bytes(key)
        try:
            os.chmod(self._fallback_key_path, 0o600)
        except OSError:
            pass
        return key


class RawReportStore:
    def __init__(self, directory: Path, database: Database, protector: KeyProtector) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir = directory / "quarantine"
        self.database = database
        self.protector = protector
        self._lock = threading.RLock()

    def save(self, project_id: UUID | str, payload: dict, retention_days: int = 7) -> str:
        report_id = str(uuid4())
        now = datetime.now(UTC)
        expires = now + timedelta(days=retention_days)
        data_key = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, report_id.encode())
        week_file = _week_filename(now)
        record = {
            "report_id": report_id,
            "project_id": str(project_id),
            "created_at": now.isoformat(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }
        with self._lock, (self.directory / week_file).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.database.save_raw_report_key(
            report_id,
            str(project_id),
            week_file,
            self.protector.protect(data_key),
            now.isoformat(),
            expires.isoformat(),
        )
        return report_id

    def read(self, report_id: str) -> dict:
        key_row = self.database.get_raw_report_key(report_id)
        if not key_row or key_row["wrapped_key"] is None:
            raise KeyError("Report key is missing or has been destroyed")
        data_key = self.protector.unprotect(key_row["wrapped_key"])
        path = self.directory / key_row["week_file"]
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("report_id") != report_id:
                    continue
                nonce = base64.b64decode(record["nonce"])
                ciphertext = base64.b64decode(record["ciphertext"])
                plaintext = AESGCM(data_key).decrypt(nonce, ciphertext, report_id.encode())
                return json.loads(plaintext)
        raise KeyError(f"Encrypted report body not found: {report_id}")

    def destroy(self, report_id: str) -> None:
        self.database.destroy_raw_report_key(report_id, datetime.now(UTC).isoformat())

    def destroy_expired(self) -> int:
        rows = self.database.expired_raw_reports(datetime.now(UTC).isoformat())
        for row in rows:
            self.destroy(row["report_id"])
        return len(rows)

    def maintain(self) -> dict[str, int]:
        """Idle maintenance pass for the raw-report container.

        1. Quarantine bundle files whose container is corrupted (an unparseable
           JSONL line) so one damaged week cannot fail the whole store.
        2. Destroy keys that have reached their retention expiry.
        3. Compact dead ciphertext (records whose key is destroyed or expired)
           out of the remaining week bundles.

        Returns counts: ``quarantined`` files moved, ``keys_destroyed``,
        ``records_removed`` by compaction, ``bytes_freed``.
        """
        with self._lock:
            stats: dict[str, int] = {
                "quarantined": 0,
                "keys_destroyed": 0,
                "records_removed": 0,
                "bytes_freed": 0,
            }
            stats["quarantined"] += len(self.quarantine_corrupted())
            stats["keys_destroyed"] += self.destroy_expired()
            removed, freed = self.compact()
            stats["records_removed"] += removed
            stats["bytes_freed"] += freed
            return stats

    def quarantine_corrupted(self) -> list[str]:
        """Move bundle files with unparseable records into ``quarantine/``.

        A corrupted container means the ciphertext inside can no longer be
        trusted or addressed reliably, so the referencing keys are destroyed as
        well. The file itself is preserved for forensic recovery. Returns the
        names of the quarantined files.
        """
        moved: list[str] = []
        with self._lock:
            for path in sorted(self.directory.glob("*.bundle.jsonl")):
                corrupted = False
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        for line in handle:
                            if not line.strip():
                                continue
                            try:
                                record = json.loads(line)
                            except ValueError:
                                corrupted = True
                                break
                            if not isinstance(record, dict) or not record.get("report_id"):
                                corrupted = True
                                break
                except OSError:
                    corrupted = True
                if not corrupted:
                    continue
                self.quarantine_dir.mkdir(parents=True, exist_ok=True)
                target = self.quarantine_dir / path.name
                counter = 1
                while target.exists():
                    target = self.quarantine_dir / f"{path.stem}-{counter}{path.suffix}"
                    counter += 1
                path.replace(target)
                moved.append(target.name)
                for row in self.database.raw_report_keys_for_week_file(path.name):
                    if row["wrapped_key"] is not None:
                        self.database.destroy_raw_report_key(
                            row["report_id"], datetime.now(UTC).isoformat()
                        )
            return moved

    def compact(self) -> tuple[int, int]:
        """Remove dead ciphertext from week bundles.

        A record is dead when its key row is missing, destroyed or expired.
        Rewriting the bundle atomically (temp file + ``os.replace``) avoids
        leaving the store in a partial state. Returns ``(records_removed,
        bytes_freed)``.
        """
        removed = 0
        freed = 0
        with self._lock:
            for path in sorted(self.directory.glob("*.bundle.jsonl")):
                live_lines: list[str] = []
                total_records = 0
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        for line in handle:
                            if not line.strip():
                                continue
                            try:
                                record = json.loads(line)
                            except ValueError:
                                continue  # quarantine_corrupted() owns this file
                            if not isinstance(record, dict):
                                continue
                            report_id = record.get("report_id")
                            if not report_id:
                                continue
                            total_records += 1
                            if self._is_live(report_id):
                                live_lines.append(line)
                except OSError:
                    continue
                if total_records == 0:
                    continue
                if not live_lines:
                    # Everything in this bundle is dead; remove the container.
                    size = path.stat().st_size if path.exists() else 0
                    path.unlink(missing_ok=True)
                    freed += size
                    removed += total_records
                    continue
                total_size = path.stat().st_size if path.exists() else 0
                live_bytes = sum(len(line.encode("utf-8")) for line in live_lines)
                dead_bytes = total_size - live_bytes
                if dead_bytes <= 0:
                    continue
                temp = path.with_name(path.name + ".compact")
                try:
                    with temp.open("w", encoding="utf-8") as handle:
                        for line in live_lines:
                            handle.write(line)
                        handle.flush()
                        os.fsync(handle.fileno())
                    temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)
                removed += total_records - len(live_lines)
                freed += dead_bytes
        return removed, freed

    def _is_live(self, report_id: str) -> bool:
        row = self.database.get_raw_report_key(report_id)
        if row is None or row["wrapped_key"] is None or row["destroyed_at"] is not None:
            return False
        try:
            expires = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            return False
        return expires >= datetime.now(UTC)


def _week_filename(value: datetime) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}.bundle.jsonl"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _dpapi_protect(data: bytes) -> bytes:
    in_blob, in_buffer = _blob(data)
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        del in_buffer


def _dpapi_unprotect(data: bytes) -> bytes:
    in_blob, in_buffer = _blob(data)
    out_blob = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        del in_buffer
