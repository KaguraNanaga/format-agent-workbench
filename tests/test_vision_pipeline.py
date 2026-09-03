# -*- coding: utf-8 -*-
"""视觉自检协议与失败降级回归测试。"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import LLMClient, LLMError
from core.verify_visual import (
    VisualInconclusiveError,
    VisualResponseError,
    _image_batches,
    _validate_response,
    apply_fixes,
)


def test_windows_pdf_render_falls_back_from_word_to_wps(tmp_path, monkeypatch):
    import core.render as render

    calls = []

    def fake_candidate(source, destination, prog_id, display_name):
        calls.append((prog_id, display_name))
        if prog_id == "Word.Application":
            raise RuntimeError("Word timeout")
        Path(destination).write_bytes(b"%PDF-1.4\n%%EOF")
        return str(destination)

    monkeypatch.setattr(render, "_docx_to_pdf_com_candidate", fake_candidate)
    output = tmp_path / "render.pdf"
    assert render.docx_to_pdf_office_com("source.docx", output) == str(output)
    assert calls[:2] == [
        ("Word.Application", "Microsoft Word"),
        ("Kwps.Application", "WPS"),
    ]


valid = {
    "status": "fail",
    "pages_checked": [1, 2],
    "issues": [{
        "role": "body",
        "field": "first_line_indent_chars",
        "pass": "false",
        "observed": "0 字符",
        "expected": "2 字符",
    }],
}
items = _validate_response(valid, [1, 2])
assert items[0]["pass"] is False  # 字符串 "false" 不得被 bool() 误转为 True

try:
    _validate_response(valid["issues"], [1, 2])
except VisualResponseError:
    pass
else:
    raise AssertionError("顶层数组必须被拒绝")

try:
    _validate_response({"status": "pass", "pages_checked": [1], "issues": []}, [1])
except VisualResponseError:
    pass
else:
    raise AssertionError("空 issues 不得被当成通过")

try:
    _validate_response({
        "status": "inconclusive", "pages_checked": [1], "issues": [],
        "reason": "图片空白",
    }, [1])
except VisualInconclusiveError as exc:
    assert "空白" in str(exc)
else:
    raise AssertionError("inconclusive 必须单独上报")

spec = {
    "roles": {
        "body": {
            "font_eastasia": "仿宋_GB2312",
            "size_pt": 16,
            "alignment": "justify",
            "first_line_indent_chars": 0,
        }
    }
}
fixed, applied = apply_fixes(spec, items)
assert fixed["roles"]["body"]["first_line_indent_chars"] == 2
assert applied
assert spec["roles"]["body"]["first_line_indent_chars"] == 0

with tempfile.TemporaryDirectory() as td:
    paths = []
    for index, size in enumerate((60, 60, 60, 60), 1):
        path = os.path.join(td, f"page-{index}.png")
        with open(path, "wb") as handle:
            handle.write(b"x" * size)
        paths.append(path)
    old_pages = os.environ.get("LLM_VISION_PAGES_PER_REQUEST")
    old_bytes = os.environ.get("LLM_VISION_MAX_BYTES")
    try:
        os.environ["LLM_VISION_PAGES_PER_REQUEST"] = "3"
        os.environ["LLM_VISION_MAX_BYTES"] = "100000"
        batches = list(_image_batches(paths))
        assert [len(batch) for batch in batches] == [3, 1]
        assert [page for page, _ in batches[0]] == [1, 2, 3]
    finally:
        if old_pages is None:
            os.environ.pop("LLM_VISION_PAGES_PER_REQUEST", None)
        else:
            os.environ["LLM_VISION_PAGES_PER_REQUEST"] = old_pages
        if old_bytes is None:
            os.environ.pop("LLM_VISION_MAX_BYTES", None)
        else:
            os.environ["LLM_VISION_MAX_BYTES"] = old_bytes

client = object.__new__(LLMClient)
try:
    client.chat_vision_json("测试", [])
except LLMError:
    pass
else:
    raise AssertionError("空图片列表不得降级成纯文本请求")

print("视觉自检测试通过：JSON 对象、空结果、布尔值、分批与修正方向均正常")
