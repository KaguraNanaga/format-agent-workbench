"""用真实 WPS 将验收 DOCX 导出为 PDF，供逐页视觉检查。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("documents", nargs="+", type=Path)
    args = parser.parse_args()
    output_root = args.output_root.resolve()

    import pythoncom
    import win32com.client

    app = None
    results = {}
    pythoncom.CoInitialize()
    try:
        app = win32com.client.DispatchEx("Kwps.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        for source in args.documents:
            source = source.resolve()
            label = source.stem.replace("_final", "")
            directory = output_root / label
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / f"{source.stem}-wps.pdf"
            document = None
            try:
                document = app.Documents.Open(str(source), False, True)
                document.SaveAs2(str(destination), 17)
                results[label] = {
                    "status": "CREATED" if destination.is_file() else "FAIL",
                    "source": str(source),
                    "pdf": str(destination),
                    "size": destination.stat().st_size if destination.is_file() else 0,
                }
            except Exception as exc:  # noqa: BLE001 - Office diagnostic
                results[label] = {
                    "status": "FAIL", "source": str(source), "error": str(exc)
                }
            finally:
                if document is not None:
                    try:
                        document.Close(False)
                    except Exception:
                        pass
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(value["status"] == "FAIL" for value in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
