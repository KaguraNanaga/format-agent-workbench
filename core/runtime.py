"""Source and PyInstaller runtime path/worker helpers.

The frozen application keeps read-only assets inside PyInstaller's bundle while
placing user-owned state (model settings and history) beside the executable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if is_frozen() and bundle_root:
        return Path(bundle_root).resolve()
    return source_root()


def data_root() -> Path:
    override = os.environ.get("FORMAT_AGENT_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return source_root()


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def data_path(*parts: str) -> Path:
    return data_root().joinpath(*parts)


def settings_path() -> Path:
    return data_path(".env")


_SOURCE_WORKERS = {
    "com-conversion": ("core", "com_conversion_worker.py"),
    "com-pdf": ("core", "com_pdf_worker.py"),
    "field-refresh": ("core", "field_refresh.py"),
}


def worker_command(kind: str, *arguments: object) -> list[str]:
    """Return a worker command that works both from source and a frozen EXE."""
    if kind not in _SOURCE_WORKERS:
        raise ValueError(f"未知工作进程类型：{kind}")
    args = [str(value) for value in arguments]
    if is_frozen():
        return [sys.executable, "--worker", kind, *args]
    script = resource_path(*_SOURCE_WORKERS[kind])
    if kind == "field-refresh":
        return [sys.executable, str(script), "--worker", *args]
    return [sys.executable, str(script), *args]
