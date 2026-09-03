"""User-facing model presets and safe local ``.env`` persistence."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


PROVIDER_PRESETS = {
    "kimi_code": {
        "label": "Kimi Code（会员接口）",
        "base_url": "https://api.kimi.com/coding/v1",
        "model": "kimi-for-coding",
        "temperature": "auto",
        "max_tokens": 32768,
        "docs_url": "https://www.kimi.com/code/docs/en/",
        "note": (
            "使用 Kimi Code Console 创建的 API Key。Kimi 新模型对采样参数有固定约束，"
            "工作台默认不发送 temperature，避免常见的 400 错误。"
        ),
    },
    "kimi_api": {
        "label": "Kimi API（Moonshot）",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k3",
        "temperature": "auto",
        "max_tokens": 32768,
        "docs_url": "https://platform.kimi.ai/docs/api/overview",
        "note": (
            "适合按量付费的 Kimi 开放平台。海外平台可把地址改为 "
            "https://api.moonshot.ai/v1。temperature 默认省略。"
        ),
    },
    "glm": {
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-5v-turbo",
        "temperature": "auto",
        "max_tokens": 8192,
        "docs_url": "https://docs.bigmodel.cn/cn/guide/develop/openai/introduction",
        "note": "默认使用支持文字和图片的 GLM-5V-Turbo；采样参数交给模型默认值。",
    },
    "qwen": {
        "label": "阿里云百炼（千问）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen3-vl-plus",
        "temperature": "auto",
        "max_tokens": 8192,
        "docs_url": "https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope",
        "note": (
            "默认使用中国站与 Qwen3-VL-Plus。子业务空间或海外地域的接口地址不同，"
            "请按百炼控制台显示的地址修改。"
        ),
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-3.7-flash",
        "temperature": "auto",
        "max_tokens": 8192,
        "docs_url": "https://ai.google.dev/gemini-api/docs/openai",
        "note": "通过 Google 官方 OpenAI 兼容接口调用；temperature 保持模型默认值。",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.6-luna",
        "temperature": "auto",
        "max_tokens": 8192,
        "docs_url": "https://developers.openai.com/api/docs/models",
        "note": (
            "默认选择支持图片输入、成本较低的 GPT-5.6 Luna。推理模型可能不接受"
            "显式 temperature，因此使用自动兼容。"
        ),
    },
    "custom": {
        "label": "其他 OpenAI 兼容接口",
        "base_url": "",
        "model": "",
        "temperature": "auto",
        "max_tokens": 8192,
        "docs_url": "",
        "note": "填写服务商提供的 Base URL 和多模态模型名称。工作台使用 Chat Completions 协议。",
    },
}


MANAGED_KEYS = (
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    "LLM_ALLOW_PUBLIC_IMAGE_UPLOAD",
)

API_KEY_CLEAR_PENDING = "model_api_key_clear_pending"
API_KEY_WIDGET_KEY = "model_api_key_input"


def schedule_api_key_clear(state):
    """Queue clearing without mutating an already-instantiated Streamlit widget."""
    state[API_KEY_CLEAR_PENDING] = True


def consume_scheduled_api_key_clear(state):
    """Clear the API Key before the next widget render, if a clear was queued."""
    if not state.pop(API_KEY_CLEAR_PENDING, False):
        return False
    state[API_KEY_WIDGET_KEY] = ""
    return True


def get_provider_preset(provider_id):
    return PROVIDER_PRESETS.get(provider_id) or PROVIDER_PRESETS["custom"]


def detect_provider(base_url, configured_id=None):
    if configured_id in PROVIDER_PRESETS:
        return configured_id
    normalized = (base_url or "").rstrip("/").lower()
    for provider_id, preset in PROVIDER_PRESETS.items():
        if provider_id == "custom":
            continue
        if normalized == preset["base_url"].rstrip("/").lower():
            return provider_id
    return "custom" if normalized else "kimi_code"


def normalize_temperature(value):
    raw = str(value if value is not None else "auto").strip().lower()
    if raw in {"", "auto", "default", "omit", "none"}:
        return "auto"
    try:
        number = float(raw)
    except ValueError as exc:
        raise ValueError("temperature 必须填写 auto 或数字") from exc
    if not 0 <= number <= 2:
        raise ValueError("temperature 必须在 0 到 2 之间")
    return f"{number:g}"


def temperature_value(value):
    normalized = normalize_temperature(value)
    return None if normalized == "auto" else float(normalized)


def validate_api_key(value):
    """Return a bearer-token-safe API Key without ever logging its contents."""
    key = str(value or "").strip()
    if not key:
        raise ValueError("请填写 API Key")
    lowered = key.lower()
    has_bearer_prefix = (
        lowered.startswith("bearer")
        and len(key) > len("bearer")
        and key[len("bearer")].isspace()
    )
    has_assignment_prefix = lowered.startswith(
        ("api_key=", "apikey=", "llm_api_key=")
    )
    has_wrapping_quote = key[0] in "\"'“”‘’" or key[-1] in "\"'“”‘’"
    has_unsafe_character = any(ord(character) < 33 or ord(character) > 126
                               for character in key)
    if (has_bearer_prefix or has_assignment_prefix or has_wrapping_quote
            or has_unsafe_character):
        raise ValueError(
            "API Key 只能粘贴控制台生成的原始英文令牌；请不要包含中文说明、"
            "空格、引号、Bearer 或 API_KEY= 前缀。"
        )
    return key


def validate_model_settings(base_url, api_key, model, temperature="auto"):
    values = {
        "接口地址": str(base_url or "").strip(),
        "API Key": str(api_key or "").strip(),
        "模型名称": str(model or "").strip(),
    }
    missing = [label for label, value in values.items() if not value]
    if missing:
        raise ValueError("请填写" + "、".join(missing))
    values["API Key"] = validate_api_key(values["API Key"])
    for label, value in values.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"{label}不能包含换行")
    parsed = urlparse(values["接口地址"])
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("接口地址必须是完整的 http:// 或 https:// URL")
    normalize_temperature(temperature)
    return values


def read_env_values(path=None):
    path = Path(path or DEFAULT_ENV_PATH)
    values = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def save_model_settings(
    *,
    provider_id,
    base_url,
    api_key,
    model,
    temperature="auto",
    max_tokens=8192,
    allow_public_image_upload=False,
    path=None,
):
    checked = validate_model_settings(base_url, api_key, model, temperature)
    try:
        token_limit = max(256, int(max_tokens))
    except (TypeError, ValueError) as exc:
        raise ValueError("最大输出长度必须是整数") from exc

    values = {
        "LLM_PROVIDER": provider_id if provider_id in PROVIDER_PRESETS else "custom",
        "LLM_BASE_URL": checked["接口地址"].rstrip("/"),
        "LLM_API_KEY": checked["API Key"],
        "LLM_MODEL": checked["模型名称"],
        "LLM_TEMPERATURE": normalize_temperature(temperature),
        "LLM_MAX_TOKENS": str(token_limit),
        "LLM_ALLOW_PUBLIC_IMAGE_UPLOAD": (
            "true" if allow_public_image_upload else "false"
        ),
    }

    target = Path(path or DEFAULT_ENV_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    original_lines = (
        target.read_text(encoding="utf-8-sig").splitlines() if target.exists() else []
    )
    rendered = []
    seen = set()
    for raw_line in original_lines:
        stripped = raw_line.strip()
        key = stripped.partition("=")[0].strip() if "=" in stripped else ""
        if key in values:
            if key not in seen:
                rendered.append(f"{key}={values[key]}")
                seen.add(key)
        else:
            rendered.append(raw_line)
    if rendered and rendered[-1].strip():
        rendered.append("")
    for key in MANAGED_KEYS:
        if key not in seen:
            rendered.append(f"{key}={values[key]}")

    handle, temporary_name = tempfile.mkstemp(
        prefix=".env.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(rendered).rstrip() + "\n")
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)

    for key, value in values.items():
        os.environ[key] = value
    return target
