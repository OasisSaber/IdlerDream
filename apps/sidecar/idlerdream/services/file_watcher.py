from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID

from ..config import DEFAULT_IGNORE_DIRS
from .projects import ProjectService

ChangeCallback = Callable[[UUID], Awaitable[None]]


class FileEventWatcher:
    """Watchdog-based file event watcher for monitored workspaces (CR-20).

    On Windows a Watchdog observer watches every enabled project workspace
    recursively. File events for relevant paths are debounced per project and
    then fire the callback with the project id, letting the monitoring service
    reconcile VCS/test facts and re-fingerprint that project immediately.

    When Watchdog is unavailable (or off Windows) the watcher reports
    ``available() == False`` and the monitoring service keeps running on the
    low-frequency recovery scans alone.
    """

    def __init__(
        self,
        projects: ProjectService,
        *,
        ignore_dirs: set[str] | None = None,
        debounce_seconds: float = 2.0,
    ) -> None:
        self.projects = projects
        self.ignore_dirs = set(ignore_dirs or DEFAULT_IGNORE_DIRS)
        self.debounce_seconds = debounce_seconds
        self._observer = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._callback: ChangeCallback | None = None
        self._workspace_to_project: dict[str, UUID] = {}
        self._timers: dict[UUID, threading.Timer] = {}
        self._lock = threading.Lock()

    def available(self) -> bool:
        if os.name != "nt":
            return False
        try:
            from watchdog.observers import Observer  # noqa: F401
        except ImportError:
            return False
        return True

    def start(self, loop: asyncio.AbstractEventLoop, callback: ChangeCallback) -> bool:
        if not self.available():
            return False
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        self._loop = loop
        self._callback = callback
        observer = Observer()

        class _Handler(FileSystemEventHandler):
            def __init__(self, watcher: FileEventWatcher) -> None:
                self._watcher = watcher

            def on_any_event(self, event) -> None:
                watcher = self._watcher
                if getattr(event, "is_directory", False):
                    return
                path = Path(getattr(event, "src_path", ""))
                if not str(path):
                    return
                if any(part in watcher.ignore_dirs for part in path.parts):
                    return
                watcher._on_event(path)

        handler = _Handler(self)
        for project in self.projects.list():
            if not project.enabled:
                continue
            workspace = Path(project.path).resolve(strict=False)
            if not workspace.is_dir():
                continue
            try:
                observer.schedule(handler, str(workspace), recursive=True)
            except OSError:
                continue
            self._workspace_to_project[str(workspace)] = project.id
        if not self._workspace_to_project:
            return False
        observer.start()
        self._observer = observer
        return True

    def stop(self) -> None:
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
        observer = self._observer
        self._observer = None
        if observer is not None:
            observer.stop()
            observer.join(timeout=5)

    def _on_event(self, path: Path) -> None:
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            return
        for workspace in self._workspace_to_project:
            try:
                resolved.relative_to(workspace)
            except ValueError:
                continue
            project_id = self._workspace_to_project[workspace]
            with self._lock:
                timer = self._timers.get(project_id)
                if timer is not None:
                    timer.cancel()
                timer = threading.Timer(self.debounce_seconds, self._fire, args=(project_id,))
                timer.daemon = True
                timer.start()
                self._timers[project_id] = timer
            return  # the first matching workspace wins (no nested projects)

    def _fire(self, project_id: UUID) -> None:
        with self._lock:
            self._timers.pop(project_id, None)
        loop = self._loop
        callback = self._callback
        if loop is not None and callback is not None:
            asyncio.run_coroutine_threadsafe(callback(project_id), loop)
