import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import runtime


def test_source_paths_and_worker_commands(monkeypatch, tmp_path):
    monkeypatch.delattr(runtime.sys, "frozen", raising=False)
    monkeypatch.delenv("FORMAT_AGENT_DATA_DIR", raising=False)
    root = Path(__file__).resolve().parents[1]

    assert runtime.resource_root() == root
    assert runtime.data_root() == root
    assert runtime.settings_path() == root / ".env"
    conversion = runtime.worker_command("com-conversion", "a.doc", "b.docx", "Word", "Word")
    refresh = runtime.worker_command("field-refresh", "b.docx")
    assert conversion[0] == sys.executable
    assert Path(conversion[1]) == root / "core" / "com_conversion_worker.py"
    assert refresh[2] == "--worker"


def test_frozen_paths_and_worker_commands(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    executable = tmp_path / "portable" / "Format Agent.exe"
    monkeypatch.setattr(runtime.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime.sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(runtime.sys, "executable", str(executable))
    monkeypatch.delenv("FORMAT_AGENT_DATA_DIR", raising=False)

    assert runtime.resource_root() == bundle.resolve()
    assert runtime.data_root() == executable.parent.resolve()
    assert runtime.settings_path() == executable.parent.resolve() / ".env"
    assert runtime.worker_command("com-pdf", "a.docx", "a.pdf", "Word", "Word") == [
        str(executable), "--worker", "com-pdf", "a.docx", "a.pdf", "Word", "Word"
    ]


def test_data_directory_override(monkeypatch, tmp_path):
    monkeypatch.setenv("FORMAT_AGENT_DATA_DIR", str(tmp_path / "user-data"))
    assert runtime.data_root() == (tmp_path / "user-data").resolve()


def test_unknown_worker_is_rejected():
    try:
        runtime.worker_command("unknown")
    except ValueError as exc:
        assert "未知工作进程类型" in str(exc)
    else:
        raise AssertionError("unknown worker should fail")
