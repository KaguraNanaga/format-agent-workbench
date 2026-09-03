import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import LLMClient, LLMError
from core.model_settings import (
    MANAGED_KEYS,
    PROVIDER_PRESETS,
    consume_scheduled_api_key_clear,
    normalize_temperature,
    read_env_values,
    save_model_settings,
    schedule_api_key_clear,
    temperature_value,
)


class _Response:
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {
            "choices": [{"message": {"content": json.dumps({"ok": True})}}]
        }
        self.headers = {}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


def test_api_key_clear_is_deferred_until_the_next_render():
    state = {"model_api_key_input": "secret-being-edited"}

    schedule_api_key_clear(state)
    assert state["model_api_key_input"] == "secret-being-edited"
    assert state["model_api_key_clear_pending"] is True

    assert consume_scheduled_api_key_clear(state) is True
    assert state["model_api_key_input"] == ""
    assert "model_api_key_clear_pending" not in state
    assert consume_scheduled_api_key_clear(state) is False


def test_common_multimodal_presets_default_to_automatic_temperature():
    expected = {"kimi_code", "kimi_api", "glm", "qwen", "gemini", "openai"}
    assert expected.issubset(PROVIDER_PRESETS)
    for provider_id in expected:
        preset = PROVIDER_PRESETS[provider_id]
        assert preset["base_url"].startswith("https://")
        assert preset["model"]
        assert preset["temperature"] == "auto"


@pytest.mark.parametrize(
    ("raw", "normalized", "value"),
    [
        ("auto", "auto", None),
        ("omit", "auto", None),
        (None, "auto", None),
        ("0.2", "0.2", 0.2),
        (1, "1", 1.0),
    ],
)
def test_temperature_normalization(raw, normalized, value):
    assert normalize_temperature(raw) == normalized
    assert temperature_value(raw) == value


@pytest.mark.parametrize("raw", ["warm", "-0.1", "2.1"])
def test_invalid_temperature_is_rejected(raw):
    with pytest.raises(ValueError):
        normalize_temperature(raw)


def test_save_model_settings_preserves_unmanaged_values(tmp_path, monkeypatch):
    for key in MANAGED_KEYS:
        monkeypatch.delenv(key, raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LIBREOFFICE_PATH=C:\\\\Program Files\\\\LibreOffice\\\\soffice.exe\n"
        "LLM_MODEL=old-model\n"
        "LLM_MODEL=duplicate-model\n",
        encoding="utf-8",
    )

    saved_path = save_model_settings(
        provider_id="kimi_code",
        base_url="https://api.kimi.com/coding/v1/",
        api_key="local-test-key",
        model="kimi-for-coding",
        temperature="auto",
        max_tokens=32768,
        path=env_path,
    )

    assert saved_path == env_path
    text = env_path.read_text(encoding="utf-8")
    assert "LIBREOFFICE_PATH=" in text
    assert text.count("LLM_MODEL=") == 1
    values = read_env_values(env_path)
    assert values["LLM_PROVIDER"] == "kimi_code"
    assert values["LLM_BASE_URL"] == "https://api.kimi.com/coding/v1"
    assert values["LLM_MODEL"] == "kimi-for-coding"
    assert values["LLM_TEMPERATURE"] == "auto"
    assert values["LLM_MAX_TOKENS"] == "32768"
    assert values["LLM_ALLOW_PUBLIC_IMAGE_UPLOAD"] == "false"


def test_llm_auto_temperature_is_omitted(monkeypatch):
    calls = []

    def fake_post(_url, **kwargs):
        calls.append(kwargs["json"].copy())
        return _Response()

    monkeypatch.setattr("core.llm.requests.post", fake_post)
    client = LLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="vision-model",
        temperature=None,
    )
    assert client.chat_json("return JSON") == {"ok": True}
    assert "temperature" not in calls[0]


def test_llm_numeric_temperature_is_sent(monkeypatch):
    calls = []

    def fake_post(_url, **kwargs):
        calls.append(kwargs["json"].copy())
        return _Response()

    monkeypatch.setattr("core.llm.requests.post", fake_post)
    client = LLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="vision-model",
        temperature=0.2,
    )
    client.chat_json("return JSON")
    assert calls[0]["temperature"] == 0.2


def test_temperature_400_retries_once_without_parameter(monkeypatch):
    calls = []

    def fake_post(_url, **kwargs):
        calls.append(kwargs["json"].copy())
        if len(calls) == 1:
            return _Response(
                status_code=400,
                text="temperature is fixed; do not pass temperature",
            )
        return _Response()

    monkeypatch.setattr("core.llm.requests.post", fake_post)
    client = LLMClient(
        base_url="https://example.test/v1",
        api_key="key",
        model="vision-model",
        temperature=0.7,
        max_retries=0,
    )
    assert client.chat_json("return JSON") == {"ok": True}
    assert calls[0]["temperature"] == 0.7
    assert "temperature" not in calls[1]


def test_llm_rejects_unknown_temperature(monkeypatch):
    with pytest.raises(LLMError, match="auto 或数字"):
        LLMClient(
            base_url="https://example.test/v1",
            api_key="key",
            model="vision-model",
            temperature="warm",
        )


def test_llm_rejects_out_of_range_temperature():
    with pytest.raises(LLMError, match="0 到 2"):
        LLMClient(
            base_url="https://example.test/v1",
            api_key="key",
            model="vision-model",
            temperature=2.1,
        )
