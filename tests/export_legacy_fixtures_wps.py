"""用真实 WPS COM 从 DOCX 生成旧格式验收夹具。"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


FORMATS = (("doc", 0), ("rtf", 6), ("wps", None))


def _build_genuine_odt(destination: Path) -> None:
    """创建标准 ODF 文本包；避免把 OLE/DOC 误标为 .odt。"""
    mimetype = "application/vnd.oasis.opendocument.text"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.3">
 <office:automatic-styles>
  <style:style style:name="PageBreak" style:family="paragraph">
   <style:paragraph-properties fo:break-before="page"/>
  </style:style>
 </office:automatic-styles>
 <office:body><office:text>
  <text:h text:outline-level="1">Format Agent 真实环境验收</text:h>
  <text:h text:outline-level="2">一、转换基准 / Conversion Baseline</text:h>
  <text:p>中文完整性：甲乙丙，标点“引号”（括号）及 2026-09-02。 English integrity: bold and italic survive formatting.</text:p>
  <text:p>第二段用于验证正文顺序、空白归一与跨语言字体。 The second paragraph verifies order, whitespace, and mixed-script fonts.</text:p>
  <table:table table:name="AcceptanceTable">
   <table:table-row><table:table-cell><text:p>项目 / Item</text:p></table:table-cell><table:table-cell><text:p>中文值</text:p></table:table-cell><table:table-cell><text:p>English value</text:p></table:table-cell></table:table-row>
   <table:table-row><table:table-cell><text:p>编号 / ID</text:p></table:table-cell><table:table-cell><text:p>A-001</text:p></table:table-cell><table:table-cell><text:p>42.50</text:p></table:table-cell></table:table-row>
   <table:table-row><table:table-cell><text:p>状态 / Status</text:p></table:table-cell><table:table-cell><text:p>待验收</text:p></table:table-cell><table:table-cell><text:p>Pending</text:p></table:table-cell></table:table-row>
  </table:table>
  <text:p text:style-name="PageBreak">第二页固定文本 / Fixed text on page two.</text:p>
  <text:p>页眉、页脚和分页必须保留；表格不得移动到正文末尾之外。</text:p>
 </office:text></office:body>
</office:document-content>"""
    styles = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles
 xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 office:version="1.3"><office:styles/></office:document-styles>"""
    manifest = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">
 <manifest:file-entry manifest:full-path="/" manifest:media-type="{mimetype}"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr(
            "mimetype", mimetype,
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr("styles.xml", styles, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr(
            "META-INF/manifest.xml", manifest,
            compress_type=zipfile.ZIP_DEFLATED,
        )


def export(source: Path, output_dir: Path) -> dict:
    import pythoncom
    import win32com.client

    output_dir.mkdir(parents=True, exist_ok=True)
    app = None
    results = {}
    pythoncom.CoInitialize()
    try:
        app = win32com.client.DispatchEx("Kwps.Application")
        try:
            app.Visible = False
            app.DisplayAlerts = 0
            app.AutomationSecurity = 3
            app.Options.UpdateLinksAtOpen = False
        except Exception:
            pass
        for extension, file_format in FORMATS:
            destination = output_dir / f"reference.{extension}"
            document = None
            try:
                try:
                    document = app.Documents.Open(
                        str(source), ConfirmConversions=False, ReadOnly=True,
                        AddToRecentFiles=False, Visible=False,
                        OpenAndRepair=False, NoEncodingDialog=True,
                    )
                except Exception:
                    document = app.Documents.Open(str(source), False, True)
                if file_format is None:
                    document.SaveAs2(str(destination))
                else:
                    document.SaveAs2(str(destination), FileFormat=file_format)
                results[extension] = {
                    "status": "CREATED" if destination.is_file() else "FAIL",
                    "path": str(destination.resolve()),
                    "size": destination.stat().st_size if destination.is_file() else 0,
                    "signature_hex": (
                        destination.read_bytes()[:16].hex()
                        if destination.is_file() else ""
                    ),
                }
            except Exception as exc:  # noqa: BLE001 - 真实 Office 诊断
                results[extension] = {
                    "status": "FAIL", "error": str(exc),
                    "path": str(destination.resolve()),
                }
            finally:
                if document is not None:
                    try:
                        document.Close(SaveChanges=False)
                    except Exception:
                        pass
    finally:
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
    odt = output_dir / "reference.odt"
    try:
        _build_genuine_odt(odt)
        results["odt"] = {
            "status": "CREATED",
            "path": str(odt.resolve()),
            "size": odt.stat().st_size,
            "signature_hex": odt.read_bytes()[:16].hex(),
            "mimetype": zipfile.ZipFile(odt).read("mimetype").decode("ascii"),
        }
    except Exception as exc:  # noqa: BLE001 - fixture diagnostic
        results["odt"] = {
            "status": "FAIL", "error": str(exc), "path": str(odt.resolve())
        }
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = export(args.source.resolve(), args.output_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if any(value["status"] == "CREATED" for value in result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
