"""Windows executable entry point for Format Agent Workbench."""

from __future__ import annotations

import json
import os
import socket
import sys

from core.runtime import resource_path, resource_root


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _worker_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    return 2


def run_worker(kind: str, arguments: list[str]) -> int:
    """Dispatch isolated Office work to the same executable."""
    if kind == "com-conversion":
        if len(arguments) != 4:
            return _worker_error("COM 文档转换参数数量不正确")
        from core.com_conversion_worker import main

        sys.argv = ["com_conversion_worker", *arguments]
        return int(main())

    if kind == "com-pdf":
        if len(arguments) != 4:
            return _worker_error("COM PDF 渲染参数数量不正确")
        from core.com_pdf_worker import main

        sys.argv = ["com_pdf_worker", *arguments]
        return int(main())

    if kind == "field-refresh":
        if len(arguments) != 1:
            return _worker_error("Word 域刷新参数数量不正确")
        from core.field_refresh import _worker_main

        return int(_worker_main(arguments[0]))

    return _worker_error(f"未知工作进程类型：{kind}")


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def choose_port() -> int:
    requested = os.environ.get("FORMAT_AGENT_PORT", "").strip()
    if requested:
        try:
            port = int(requested)
        except ValueError as exc:
            raise RuntimeError("FORMAT_AGENT_PORT 必须是数字") from exc
        if not 1 <= port <= 65535:
            raise RuntimeError("FORMAT_AGENT_PORT 必须在 1–65535 之间")
        if not _port_available(port):
            raise RuntimeError(f"端口 {port} 已被占用")
        return port
    for port in range(8501, 8521):
        if _port_available(port):
            return port
    raise RuntimeError("8501–8520 端口均被占用，无法启动工作台")


def run_workbench() -> int:
    from streamlit.web import cli as streamlit_cli

    port = choose_port()
    app_path = resource_path("app.py")
    os.chdir(resource_root())
    print("Format Agent 工作台正在启动 / Workbench is starting...")
    print(f"浏览器地址 / Browser URL: http://127.0.0.1:{port}")
    print("关闭此窗口即可停止工作台 / Close this window to stop the workbench.")
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    if "STREAMLIT_SERVER_HEADLESS" not in os.environ:
        sys.argv.append("--server.headless=false")
    return int(streamlit_cli.main())


def main() -> int:
    _configure_utf8_streams()
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        return run_worker(sys.argv[2], sys.argv[3:])
    try:
        return run_workbench()
    except Exception as exc:  # noqa: BLE001 - keep double-click failures visible
        print(f"启动失败 / Startup failed: {exc}", file=sys.stderr)
        if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty():
            try:
                input("按 Enter 退出 / Press Enter to exit...")
            except (EOFError, OSError):
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
