"""Format Agent 的 Streamlit 工作台。

设计目标不是做一个“大号表单”，而是让用户清楚地感知：
1. 现在应该提供什么；2. Agent 正在做什么；3. 长耗时步骤是否仍在等待；
4. 完成后去哪里下载结果。运行：streamlit run app.py
"""

import html
import json
import os
import tempfile
import time
from datetime import datetime

import streamlit as st

from core.agent import Agent
from core.history import list_runs, save_run
from core.llm import load_dotenv
from core.llm import LLMClient
from core.model_settings import (
    PROVIDER_PRESETS,
    consume_scheduled_api_key_clear,
    detect_provider,
    get_provider_preset,
    normalize_temperature,
    save_model_settings,
    schedule_api_key_clear,
    temperature_value,
    validate_model_settings,
)
from core.render import renderer_status as _renderer_status
from core.schema import validate_spec


# 长驻 Streamlit 进程每次重跑都读取最新配置。
load_dotenv(override=True)

st.set_page_config(
    page_title="Format Agent · 文档排版智能体",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------- 视觉系统 ----------------
# 主题：默认纸白工作台，夜墨模式为次级选择。
st.session_state.setdefault("ui_theme", "白色")
_THEME = st.session_state["ui_theme"]

# 主题颜色由 OpenDesign token 分层定义；布局与组件规则只维护一份。

# OpenDesign `modern-minimal` 方向：用一套语义 token 替代早期演示稿的
# 蓝紫光晕/玻璃卡片。选择器仅依赖稳定的 data-testid 与项目自有 class。
_OD_THEME_CSS = """
:root {
    color-scheme: dark;
    --od-bg: #0d1015;
    --od-surface: #121720;
    --od-surface-2: #171d27;
    --od-paper: #f7f5ef;
    --od-ink: #f4f6f8;
    --od-ink-2: #c7ced8;
    --od-muted: #8b96a7;
    --od-border: #28313d;
    --od-border-strong: #3a4655;
    --od-accent: #e5e7eb;
    --od-accent-hover: #f4f4f5;
    --od-accent-soft: rgba(229, 231, 235, .10);
    --od-success: #78b092;
    --od-warning: #e9b35f;
    --od-danger: #ef7b83;
    --od-on-accent: #111317;
    --od-grid: rgba(255, 255, 255, .035);
    --od-shadow: 0 24px 70px rgba(0, 0, 0, .24);
    --ink: var(--od-ink);
    --muted: var(--od-muted);
    --panel: var(--od-surface);
    --panel-strong: var(--od-surface);
    --line: var(--od-border);
    --cyan: var(--od-accent);
    --green: var(--od-success);
    --amber: var(--od-warning);
    --red: var(--od-danger);
}
""" if _THEME == "深色" else """
:root {
    color-scheme: light;
    --od-bg: #fcfcfb;
    --od-surface: #ffffff;
    --od-surface-2: #f7f7f5;
    --od-paper: #fffefa;
    --od-ink: #171716;
    --od-ink-2: #3f3f3b;
    --od-muted: #777771;
    --od-border: #e2e2de;
    --od-border-strong: #c8c8c2;
    --od-accent: #1e1e1c;
    --od-accent-hover: #363633;
    --od-accent-soft: rgba(30, 30, 28, .07);
    --od-success: #3f6f56;
    --od-warning: #936218;
    --od-danger: #a83b3b;
    --od-on-accent: #ffffff;
    --od-grid: rgba(23, 23, 22, .035);
    --od-shadow: 0 24px 70px rgba(23, 23, 22, .08);
    --ink: var(--od-ink);
    --muted: var(--od-muted);
    --panel: var(--od-surface);
    --panel-strong: var(--od-surface);
    --line: var(--od-border);
    --cyan: var(--od-accent);
    --green: var(--od-success);
    --amber: var(--od-warning);
    --red: var(--od-danger);
}
"""

_OPENDESIGN_CSS = """
:root {
    --od-display: "Noto Serif SC", "Source Han Serif SC", "Songti SC",
                  STSong, SimSun, serif;
    --od-ui: Inter, "Segoe UI Variable Text", "PingFang SC",
             "Microsoft YaHei", system-ui, sans-serif;
}
html, body, [data-testid="stAppViewContainer"], .stApp {
    font-family: var(--od-ui);
    color: var(--od-ink);
}
[data-testid="stAppViewContainer"], .stApp {
    background-color: var(--od-bg);
}
[data-testid="stAppViewContainer"]::before {
    content: ""; position: fixed; z-index: 999; inset: 0 0 auto; height: 3px;
    background: var(--od-accent); pointer-events: none;
}
[data-testid="stHeader"], #MainMenu, footer { visibility: hidden; }
.block-container { max-width: 1200px; padding-top: 22px; padding-bottom: 96px; }

/* Quiet editorial utility: content first, no dashboard chrome. */
.product-lockup { display: flex; align-items: center; gap: 12px; min-height: 42px; }
.product-mark { display: grid; place-items: center; width: 30px; height: 34px;
    color: var(--od-accent); border: 1.5px solid currentColor; border-radius: 3px;
    font: 750 12px/1 ui-monospace, "SFMono-Regular", Consolas, monospace; }
.product-name { color: var(--od-ink); font-size: 13px; font-weight: 750; letter-spacing: .08em; }
.product-caption { margin-left: 3px; color: var(--od-muted); font-size: 12px; }
.st-key-topbar [data-testid="stHorizontalBlock"] {
    flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important;
}
.st-key-topbar [data-testid="stColumn"]:first-child {
    flex: 1 1 auto !important; min-width: 0 !important; width: auto !important;
}
.st-key-topbar [data-testid="stColumn"]:nth-child(2) {
    flex: 0 0 116px !important; min-width: 116px !important; width: 116px !important;
}
.st-key-topbar [data-testid="stColumn"]:last-child {
    flex: 0 0 42px !important; min-width: 42px !important; width: 42px !important;
}
.st-key-model_settings_button { display: flex; width: 100%; justify-content: flex-end; }
.st-key-model_settings_button button {
    width: 108px !important; min-width: 108px !important; height: 40px !important;
    min-height: 40px !important; padding: 0 13px !important;
    color: var(--od-ink) !important; background: transparent !important;
    border: 1px solid var(--od-border) !important; border-radius: 5px !important;
    box-shadow: none !important; font-size: 12px !important;
}
.st-key-model_settings_button button:hover {
    color: var(--od-ink) !important; background: var(--od-surface-2) !important;
    border-color: var(--od-border-strong) !important; transform: none !important;
}
.st-key-theme_toggle { display: flex; width: 100%; justify-content: flex-end; }
.st-key-theme_toggle button {
    width: 40px !important; min-width: 40px !important; height: 40px !important;
    min-height: 40px !important; padding: 0 !important;
    color: var(--od-ink) !important; background: transparent !important;
    border: 1px solid var(--od-border) !important; border-radius: 5px !important;
    box-shadow: none !important;
}
.st-key-theme_toggle button:hover {
    color: var(--od-ink) !important; background: var(--od-surface-2) !important;
    border-color: var(--od-border-strong) !important; transform: none !important;
}
.st-key-theme_toggle button [data-testid="stMarkdownContainer"] {
    position: absolute !important; width: 1px !important; height: 1px !important;
    padding: 0 !important; margin: -1px !important; overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important; clip-path: inset(50%) !important;
    white-space: nowrap !important;
}
.st-key-theme_toggle button [data-testid="stIconMaterial"] { font-size: 20px !important; }

.agent-hero {
    position: relative; min-height: 474px; display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(440px, .96fr);
    align-items: center; gap: clamp(38px, 4.5vw, 62px);
    padding: 58px 8px 68px; margin: 8px 0 0;
    border: 0; border-bottom: 1px solid var(--od-border); border-radius: 0;
    background: transparent; box-shadow: none;
    animation: od-hero-enter 440ms cubic-bezier(.23, 1, .32, 1) both;
}
.hero-copy { position: relative; z-index: 2; }
.eyebrow { margin-bottom: 22px; color: var(--od-muted);
    font: 650 12px/1.2 ui-monospace, "SFMono-Regular", Consolas, monospace;
    letter-spacing: .1em; text-transform: uppercase; }
.agent-hero h1 {
    max-width: 610px; margin: 0 0 24px; color: var(--od-ink);
    font-family: var(--od-display); font-size: clamp(48px, 4.5vw, 66px); line-height: 1.08;
    letter-spacing: -.045em; font-weight: 850;
}
.hero-nowrap { display: inline-block; white-space: nowrap; }
.agent-hero p { max-width: 660px; margin: 0; color: var(--od-ink-2);
    font-family: var(--od-display); font-size: 16px; line-height: 1.95; font-weight: 500; }
.hero-facts { display: flex; flex-wrap: wrap; align-items: center; gap: 0; margin-top: 30px; }
.hero-fact { display: inline-flex; align-items: center; color: var(--od-muted);
    font: 620 11px/1.3 ui-monospace, "SFMono-Regular", Consolas, monospace;
    letter-spacing: .035em; }
.hero-fact:not(:last-child)::after { content: "·"; margin: 0 12px; color: var(--od-border-strong); }

/* The hero's visual is a real formatting sequence: page, margins, type and leading. */
.document-compare { position: relative; width: 100%; max-width: 540px; height: 354px;
    align-self: center; overflow: hidden; color: var(--od-ink);
    border-top: 1px solid var(--od-border); border-bottom: 1px solid var(--od-border);
    animation: od-compare-enter 560ms cubic-bezier(.23,1,.32,1) 80ms both; }
.format-stage-head { position: absolute; z-index: 5; inset: 14px 0 auto;
    display: flex; justify-content: space-between; align-items: center;
    color: var(--od-muted); font: 650 9px/1.2 ui-monospace, "SFMono-Regular", Consolas, monospace;
    letter-spacing: .14em; text-transform: uppercase; }
.format-stage-head strong { color: var(--od-accent); font-weight: 760; }
.format-field { position: absolute; inset: 47px 0 48px; }
.format-grid { position: absolute; inset: 0;
    background-image: linear-gradient(to right, var(--od-grid) 1px, transparent 1px),
                      linear-gradient(to bottom, var(--od-grid) 1px, transparent 1px);
    background-size: 26px 26px; mask-image: linear-gradient(to right, transparent, #000 16%, #000 84%, transparent); }
.format-page { position: absolute; z-index: 2; left: 50%; top: 50%; width: 190px; height: 246px;
    padding: 31px 25px 25px; color: #172033; border: 1px solid #d8d3c8;
    background: #fffdf8; box-shadow: 0 22px 50px rgba(23,32,51,.13);
    transform: translate(-50%, -50%); animation: od-page-cycle 7.2s cubic-bezier(.23,1,.32,1) infinite; }
.format-page::before, .format-page::after { content: ""; position: absolute; pointer-events: none; opacity: 0;
    animation: od-margin-guides 7.2s ease infinite; }
.format-page::before { inset: 22px 18px; border: 1px solid rgba(30,30,28,.20); }
.format-page::after { left: 25px; right: 25px; top: 77px; height: 1px; background: rgba(30,30,28,.32); }
.format-page .doc-title { width: 76%; height: 9px; margin: 0 auto 20px; background: #30394b;
    transform-origin: center; animation: od-title-cycle 7.2s cubic-bezier(.23,1,.32,1) infinite; }
.format-page .doc-line { height: 4px; margin: 0 0 8px; border-radius: 1px; background: #c7c3ba;
    transform-origin: left center; animation: od-line-cycle 7.2s cubic-bezier(.23,1,.32,1) infinite both; }
.format-page .doc-line:nth-child(2) { width: 100%; --messy-x: 12px; --messy-s: .79; animation-delay: 0s; }
.format-page .doc-line:nth-child(3) { width: 94%; --messy-x: -6px; --messy-s: .64; animation-delay: .08s; }
.format-page .doc-line:nth-child(4) { width: 100%; --messy-x: 18px; --messy-s: .74; animation-delay: .16s; }
.format-page .doc-line:nth-child(5) { width: 78%; --messy-x: 4px; --messy-s: 1.15; animation-delay: .24s; }
.format-page .doc-subhead { width: 44%; height: 6px; margin: 20px 0 12px; background: #596273;
    transform-origin: left center; animation: od-subhead-cycle 7.2s cubic-bezier(.23,1,.32,1) infinite; }
.format-page .doc-line:nth-child(7) { width: 100%; --messy-x: -9px; --messy-s: .76; animation-delay: .32s; }
.format-page .doc-line:nth-child(8) { width: 88%; --messy-x: 15px; --messy-s: .72; animation-delay: .40s; }
.format-page .doc-page-number { position: absolute; left: 0; right: 0; bottom: 12px; text-align: center;
    color: #9c9a94; font: 600 7px/1 ui-monospace, monospace; letter-spacing: .12em;
    animation: od-detail-cycle 7.2s ease infinite; }
.format-ruler { position: absolute; z-index: 1; left: calc(50% - 116px); top: 5px; width: 232px; height: 11px;
    border-top: 1px solid var(--od-border-strong); opacity: 0;
    background: repeating-linear-gradient(to right, var(--od-border-strong) 0 1px, transparent 1px 18px);
    background-size: auto 5px; background-repeat: repeat-x;
    animation: od-ruler-cycle 7.2s ease infinite; }
.format-ruler::before, .format-ruler::after { position: absolute; top: -6px; color: var(--od-muted);
    font: 600 8px/1 ui-monospace, monospace; }
.format-ruler::before { content: "0"; left: -12px; } .format-ruler::after { content: "180 mm"; right: -40px; }
.format-callout { position: absolute; z-index: 4; min-width: 106px; padding-top: 7px;
    border-top: 1px solid var(--od-border-strong); color: var(--od-muted);
    font: 600 9px/1.35 ui-monospace, "SFMono-Regular", Consolas, monospace;
    letter-spacing: .08em; opacity: 0; animation: od-callout-cycle 7.2s ease infinite both;
    animation-delay: var(--callout-delay, 0s); }
.format-callout b { display: block; margin-top: 4px; color: var(--od-ink); font-size: 11px; letter-spacing: .02em; }
.format-callout::after { content: ""; position: absolute; top: -1px; width: 46px; height: 1px;
    background: var(--od-border-strong); transform-origin: left; }
.callout-title { left: 4px; top: 47px; --callout-delay: 0s; }
.callout-title::after { left: 100%; transform: rotate(19deg); }
.callout-leading { right: 0; top: 112px; text-align: right; --callout-delay: .16s; }
.callout-leading::after { right: 100%; transform-origin: right; transform: rotate(-15deg); }
.callout-margin { left: 16px; bottom: 20px; --callout-delay: .32s; }
.callout-margin::after { left: 100%; transform: rotate(-17deg); }
.format-seal { position: absolute; z-index: 5; left: calc(50% + 69px); top: calc(50% + 82px);
    display: grid; place-items: center; width: 34px; height: 34px; color: #fff;
    border: 3px solid var(--od-bg); border-radius: 50%; background: var(--od-success);
    opacity: 0; transform: scale(.72); animation: od-seal-cycle 7.2s cubic-bezier(.2,.8,.25,1.2) infinite; }
.format-seal svg { width: 16px; height: 16px; }
.format-timeline { position: absolute; z-index: 5; inset: auto 0 14px; display: grid;
    grid-template-columns: repeat(3, 1fr); gap: 18px; }
.format-timeline span { position: relative; padding-top: 9px; color: var(--od-muted);
    border-top: 1px solid var(--od-border); font: 620 9px/1.2 ui-monospace, "SFMono-Regular", Consolas, monospace;
    letter-spacing: .055em; }
.format-timeline span::before { content: ""; position: absolute; left: 0; top: -1px; width: 0; height: 1px;
    background: var(--od-accent); animation: od-timeline-cycle 7.2s ease infinite both; }
.format-timeline span:nth-child(1)::before { animation-delay: 0s; }
.format-timeline span:nth-child(2)::before { animation-delay: .55s; }
.format-timeline span:nth-child(3)::before { animation-delay: 1.10s; }

.section-kicker { margin-top: 46px; color: var(--od-accent);
    font: 700 13px/1.3 ui-monospace, "SFMono-Regular", Consolas, monospace;
    letter-spacing: .13em; text-transform: uppercase; }
.section-title { margin: 54px 0 26px; color: var(--od-ink); font-family: var(--od-display);
    font-size: 34px; line-height: 1.2; font-weight: 800; letter-spacing: -.025em; }
.section-help { margin: 0 0 18px; color: var(--od-muted); font-size: 13px; }

/* Streamlit primitives aligned to the OpenDesign token system. */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--od-border) !important; border-radius: 8px !important;
    background: var(--od-surface) !important; box-shadow: none !important;
    transition: border-color 180ms cubic-bezier(.23,1,.32,1),
                transform 180ms cubic-bezier(.23,1,.32,1) !important;
}
.input-head { display: grid; grid-template-columns: 74px minmax(0, 1fr); align-items: center;
    min-height: 72px; margin-bottom: 24px; padding-bottom: 22px;
    border-bottom: 1px solid var(--od-border); }
.input-step { color: var(--od-accent);
    font: 760 36px/1 ui-monospace, "SFMono-Regular", Consolas, monospace;
    letter-spacing: -.05em; }
.input-title-row { display: flex; align-items: center; gap: 9px; min-width: 0; }
.input-title { color: var(--od-ink); font-size: 21px; line-height: 1.25;
    font-family: var(--od-display); font-weight: 800; letter-spacing: -.02em; }
.input-help { position: relative; flex: none; display: grid; place-items: center; width: 18px; height: 18px;
    color: var(--od-muted); border: 1px solid var(--od-border-strong); border-radius: 50%;
    font: 700 11px/1 system-ui, sans-serif; cursor: help; }
.input-help::after { content: attr(data-tooltip); position: absolute; z-index: 20;
    top: calc(100% + 10px); left: 50%; width: 280px; padding: 10px 12px;
    color: var(--od-ink); background: var(--od-surface); border: 1px solid var(--od-border);
    border-radius: 7px; box-shadow: 0 12px 32px rgba(23,32,51,.14);
    font: 500 12px/1.55 Inter, "PingFang SC", system-ui, sans-serif;
    letter-spacing: 0; opacity: 0; pointer-events: none;
    transform: translate(-50%, -3px); transition: opacity 150ms cubic-bezier(.23,1,.32,1),
    transform 150ms cubic-bezier(.23,1,.32,1); }
.input-help:hover::after, .input-help:focus-visible::after {
    opacity: 1; transform: translate(-50%, 0); }
.st-key-format_rules_card,
.st-key-upload_document_card {
    box-sizing: border-box; padding: 26px 24px !important;
    border: 1px solid var(--od-border) !important; border-radius: 8px !important;
    background: var(--od-surface) !important;
}
label, [data-testid="stWidgetLabel"] p, .stMarkdown p, .stCaption { color: var(--od-ink-2); }
[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input {
    color: var(--od-ink) !important; background: var(--od-surface-2) !important;
    border: 1px solid var(--od-border) !important; border-radius: 5px !important;
    transition: border-color 160ms cubic-bezier(.23,1,.32,1),
                box-shadow 160ms cubic-bezier(.23,1,.32,1) !important;
}
[data-testid="stTextArea"] textarea:focus, [data-testid="stTextInput"] input:focus {
    border-color: var(--od-accent) !important;
    box-shadow: 0 0 0 3px var(--od-accent-soft) !important;
}
[data-testid="stTextArea"] textarea::placeholder,
[data-testid="stTextInput"] input::placeholder { color: var(--od-muted) !important; opacity: .88; }
[data-testid="stFileUploader"] section {
    min-height: 126px; display: flex !important; flex-direction: column !important;
    align-items: flex-start !important; justify-content: center !important; gap: 12px !important;
    padding: 20px 22px !important;
    border: 1px dashed var(--od-border-strong); border-radius: 5px;
    background: var(--od-surface-2); transition: border-color 180ms cubic-bezier(.23,1,.32,1),
    background-color 180ms cubic-bezier(.23,1,.32,1);
}
[data-testid="stFileUploaderDropzone"] > span { flex: none !important; }
[data-testid="stFileUploaderDropzoneInstructions"] { width: 100%; text-align: left; }
[data-testid="stFileUploaderDropzoneInstructions"] > div { display: block !important; }
[data-testid="stFileUploaderDropzoneInstructions"] span {
    display: block; color: var(--od-muted) !important; font-size: 0 !important; line-height: 0 !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] span::after {
    content: "每个文件不超过200MB"; display: block; color: var(--od-muted);
    font: 500 12px/1.65 var(--od-ui); white-space: normal;
}
.st-key-target [data-testid="stFileUploaderDropzoneInstructions"] span::after,
.st-key-demo-target [data-testid="stFileUploaderDropzoneInstructions"] span::after {
    content: "每个文件不超过200MB，支持 .wps、.docx、.doc、.rtf、.odt 等格式";
}
.st-key-template [data-testid="stFileUploaderDropzoneInstructions"] span::after {
    content: "每个文件不超过200MB，支持 .docx 格式";
}
.st-key-spec-json [data-testid="stFileUploaderDropzoneInstructions"] span::after,
.st-key-rolemap-json [data-testid="stFileUploaderDropzoneInstructions"] span::after {
    content: "每个文件不超过200MB，支持 .json 格式";
}
[data-testid="stFileUploaderDropzoneInstructions"] small { color: var(--od-muted) !important; }
[data-testid="stFileUploader"] section button {
    color: var(--od-ink) !important; background: var(--od-surface) !important;
    border: 1px solid var(--od-border-strong) !important; border-radius: 5px !important;
    box-shadow: none !important;
}
[data-testid="stFileUploader"] section button p { font-size: 0 !important; }
[data-testid="stFileUploader"] section button p::after {
    content: "选择文件"; font: 650 13px/1 var(--od-ui);
}
[data-testid="stExpander"] { border: 1px solid var(--od-border); border-radius: 6px;
    background: var(--od-surface); }
[data-testid="stExpander"] summary p { color: var(--od-ink) !important; font-weight: 620; }
[data-testid="stAlert"] { border-radius: 6px; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 6px; }
[data-testid="stTabs"] button { border-radius: 4px 4px 0 0; }
[data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child {
    color: var(--od-accent) !important; border-color: var(--od-accent) !important;
    background: var(--od-accent) !important;
}
[data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child > div {
    background: var(--od-surface) !important;
}
[data-testid="stRadioOption"]:not([data-selected="true"]) > div > div > div:first-child {
    border-color: var(--od-border-strong) !important; background: transparent !important;
}

.readiness { display: flex; align-items: center; gap: 11px; min-height: 42px; }
.ready-icon { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 50%;
    font-size: 14px; font-weight: 800; }
.ready-icon.ok { color: #fff; background: var(--od-success); box-shadow: none; }
.ready-icon.wait { color: #fff; background: var(--od-warning); }
.ready-title { color: var(--od-ink); font-size: 14px; font-weight: 670; }
.ready-sub { color: var(--od-muted); font-size: 12px; margin-top: 2px; }
.stButton > button, .stDownloadButton > button { border-radius: 5px !important;
    transition: color 140ms cubic-bezier(.23,1,.32,1),
                background-color 140ms cubic-bezier(.23,1,.32,1),
                border-color 140ms cubic-bezier(.23,1,.32,1),
                transform 140ms cubic-bezier(.23,1,.32,1) !important; }
.stButton > button[kind="primary"] {
    min-height: 52px; color: var(--od-on-accent); background: var(--od-accent);
    border: 1px solid var(--od-accent); font-size: 15px; font-weight: 720;
    letter-spacing: -.01em; box-shadow: none; animation: none;
}
.stButton > button[kind="primary"]:hover { color: var(--od-on-accent); background: var(--od-accent-hover);
    border-color: var(--od-accent-hover); filter: none; transform: translateY(-1px); }
.stButton > button[kind="primary"]:active { transform: scale(.98); }
.stButton > button[kind="primary"]:disabled { color: var(--od-muted); background: var(--od-surface-2);
    border-color: var(--od-border); box-shadow: none; animation: none; }
.stDownloadButton > button { min-height: 44px; color: var(--od-accent);
    background: var(--od-surface); border: 1px solid var(--od-border); font-weight: 650; }
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
    outline: 3px solid var(--od-accent-soft); outline-offset: 2px; }

/* Processing state: only the progress cue loops. */
.agent-stage { position: relative; overflow: hidden; margin-top: 12px; padding: 25px 28px;
    border: 1px solid var(--od-border); border-radius: 14px; background: var(--od-surface);
    box-shadow: none; }
.agent-stage.running::before { content: ""; position: absolute; left: 0; top: 0;
    width: 34%; height: 2px; background: var(--od-accent);
    transform: translateX(-120%); animation: od-progress-scan 1.7s cubic-bezier(.77,0,.175,1) infinite; }
.stage-head { display: flex; justify-content: space-between; gap: 16px; align-items: center;
    margin-bottom: 24px; }
.stage-state { display: flex; align-items: center; gap: 9px; color: var(--od-ink); font-weight: 670; }
.stage-state .pulse { position: relative; width: 8px; height: 8px; border-radius: 50%;
    background: var(--od-accent); box-shadow: none; animation: none; }
.stage-state .pulse::after { content: ""; position: absolute; inset: -4px; border: 1px solid currentColor;
    border-radius: 50%; opacity: .22; }
.stage-state.done .pulse { color: var(--od-success); background: var(--od-success); }
.stage-state.failed .pulse { color: var(--od-danger); background: var(--od-danger); }
.stage-note { color: var(--od-muted); font-size: 12px; }
.workflow { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0; }
.flow-step { position: relative; text-align: center; min-width: 0; }
.flow-step:not(:last-child)::after { content: ""; position: absolute; height: 1px;
    left: calc(50% + 19px); right: calc(-50% + 19px); top: 17px;
    background: var(--od-border); }
.flow-step.done:not(:last-child)::after { background: var(--od-success); }
.flow-node { position: relative; z-index: 1; display: grid; place-items: center; width: 34px; height: 34px;
    margin: 0 auto 9px; border-radius: 50%; color: var(--od-muted); background: var(--od-surface-2);
    border: 1px solid var(--od-border); font: 750 11px/1 ui-monospace, monospace; }
.flow-step.active .flow-node { color: var(--od-on-accent); border-color: var(--od-accent);
    background: var(--od-accent); box-shadow: none; animation: none; }
.flow-step.active .flow-node::after { content: ""; position: absolute; inset: -6px;
    border: 1px solid var(--od-accent); border-radius: 50%;
    animation: od-node-ring 1.4s cubic-bezier(.23,1,.32,1) infinite; }
.flow-step.done .flow-node { color: #fff; border-color: var(--od-success); background: var(--od-success); }
.flow-step.failed .flow-node { color: #fff; border-color: var(--od-danger); background: var(--od-danger); }
.flow-step.skipped .flow-node { color: var(--od-muted); background: var(--od-surface-2); }
.flow-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    color: var(--od-muted); font-size: 11px; }
.flow-step.active .flow-name, .flow-step.done .flow-name { color: var(--od-ink-2); }
.flow-detail { margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--od-border);
    color: var(--od-muted); font-size: 12px; line-height: 1.65; }
.event-line { display: grid; grid-template-columns: 58px 82px 1fr; gap: 10px; align-items: start;
    padding: 9px 5px; border-bottom: 1px solid var(--od-border); font-size: 12px; }
.event-time { color: var(--od-muted); font-variant-numeric: tabular-nums; }
.event-step { color: var(--od-ink-2); font-weight: 650; }
.event-msg { color: var(--od-ink-2); line-height: 1.55; }

.success-banner { padding: 25px 28px; margin: 12px 0 18px; border-radius: 14px;
    border: 1px solid color-mix(in srgb, var(--od-success) 45%, var(--od-border));
    background: var(--od-surface); box-shadow: none;
    animation: od-panel-enter 260ms cubic-bezier(.23,1,.32,1) both; }
.success-banner .label { color: var(--od-success);
    font: 750 10px/1.2 ui-monospace, "SFMono-Regular", Consolas, monospace; letter-spacing: .13em; }
.success-banner h2 { color: var(--od-ink); margin: 7px 0 6px; font-size: 26px; }
.success-banner p { color: var(--od-muted); margin: 0; font-size: 13px; }
[data-testid="stMetric"] { padding: 14px 16px; border: 1px solid var(--od-border);
    border-radius: 10px; background: var(--od-surface); }
[data-testid="stMetricValue"] { color: var(--od-ink); font-variant-numeric: tabular-nums; }

@keyframes od-hero-enter { from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); } }
@keyframes od-compare-enter { from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); } }
@keyframes od-page-cycle {
    0%, 8% { transform: translate(-50%, -47%) rotate(-1.8deg); box-shadow: 0 13px 30px rgba(23,32,51,.08); }
    30%, 88% { transform: translate(-50%, -50%) rotate(0); box-shadow: 0 22px 50px rgba(23,32,51,.13); }
    100% { transform: translate(-50%, -47%) rotate(-1.8deg); box-shadow: 0 13px 30px rgba(23,32,51,.08); }
}
@keyframes od-title-cycle {
    0%, 14% { opacity: .74; transform: translateX(18px) scaleX(.72); }
    31%, 88% { opacity: 1; transform: translateX(0) scaleX(1); }
    100% { opacity: .74; transform: translateX(18px) scaleX(.72); }
}
@keyframes od-line-cycle {
    0%, 14% { opacity: .66; transform: translateX(var(--messy-x)) scaleX(var(--messy-s)); }
    18% { opacity: .66; transform: translateX(var(--messy-x)) scaleX(var(--messy-s)); }
    34%, 88% { opacity: 1; transform: translateX(0) scaleX(1); }
    100% { opacity: .66; transform: translateX(var(--messy-x)) scaleX(var(--messy-s)); }
}
@keyframes od-subhead-cycle {
    0%, 23% { opacity: .62; transform: translateX(14px) scaleX(.78); }
    38%, 88% { opacity: 1; transform: translateX(0) scaleX(1); }
    100% { opacity: .62; transform: translateX(14px) scaleX(.78); }
}
@keyframes od-margin-guides { 0%, 16%, 100% { opacity: 0; }
    25%, 46% { opacity: 1; } 60%, 88% { opacity: .2; } }
@keyframes od-ruler-cycle { 0%, 11%, 100% { opacity: 0; transform: scaleX(.55); }
    23%, 48% { opacity: .8; transform: scaleX(1); } 70%, 88% { opacity: .3; transform: scaleX(1); } }
@keyframes od-callout-cycle { 0%, 29%, 100% { opacity: 0; transform: translateY(5px); }
    40%, 78% { opacity: 1; transform: translateY(0); } 88% { opacity: .35; transform: translateY(0); } }
@keyframes od-detail-cycle { 0%, 30%, 100% { opacity: 0; } 42%, 88% { opacity: 1; } }
@keyframes od-seal-cycle { 0%, 44%, 100% { opacity: 0; transform: scale(.72); }
    54%, 86% { opacity: 1; transform: scale(1); } 92% { opacity: 0; transform: scale(.88); } }
@keyframes od-timeline-cycle { 0% { width: 0; }
    18%, 84% { width: 100%; } 100% { width: 0; } }
@keyframes od-panel-enter { from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); } }
@keyframes od-progress-scan { 0% { transform: translateX(-120%); }
    70%, 100% { transform: translateX(420%); } }
@keyframes od-node-ring { 0% { opacity: .45; transform: scale(.92); }
    75%, 100% { opacity: 0; transform: scale(1.25); } }

@media (hover: hover) and (pointer: fine) {
    [data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: var(--od-border-strong) !important;
        transform: translateY(-1px); box-shadow: none !important; }
    [data-testid="stFileUploader"] section:hover { border-color: var(--od-accent);
        background: var(--od-accent-soft); }
}
@media (max-width: 860px) {
    .block-container { padding-top: 18px; }
    .agent-hero { grid-template-columns: 1fr; padding: 52px 4px 62px; gap: 48px; }
    .hero-copy { max-width: 690px; }
    .document-compare { width: min(100%, 560px); margin: 0 auto; }
    .workflow { grid-template-columns: repeat(3, 1fr); row-gap: 22px; }
    .flow-step::after { display: none; }
}
@media (max-width: 520px) {
    .block-container { padding-inline: 14px; }
    .product-caption { display: none; }
    .product-name { font-size: 12px; }
    .agent-hero { min-height: auto; padding: 42px 0 48px; gap: 38px; }
    .agent-hero h1 { font-size: clamp(39px, 12vw, 48px); }
    .agent-hero p { font-size: 14px; line-height: 1.75; }
    .hero-facts { margin-top: 24px; }
    .hero-fact { font-size: 9px; }
    .hero-fact:not(:last-child)::after { margin: 0 7px; }
    .document-compare { display: block; height: 308px; }
    .format-field { inset: 43px 0 45px; }
    .format-page { width: 154px; height: 206px; padding: 27px 20px 22px; }
    .format-ruler { left: calc(50% - 88px); width: 176px; }
    .format-ruler::after { content: "150 mm"; right: -34px; }
    .format-callout { min-width: 76px; font-size: 7px; }
    .format-callout b { font-size: 9px; }
    .format-callout::after { width: 26px; }
    .callout-title { top: 36px; }
    .callout-leading { top: 96px; }
    .callout-margin { left: 3px; bottom: 12px; }
    .format-seal { left: calc(50% + 52px); top: calc(50% + 65px); }
    .format-timeline { gap: 8px; }
    .format-timeline span { font-size: 7px; }
    .input-head { grid-template-columns: 62px minmax(0, 1fr); }
    .input-step { font-size: 31px; }
    .event-line { grid-template-columns: 52px 66px 1fr; }
}
@media (prefers-reduced-motion: reduce) {
    .agent-hero, .document-compare, .format-page, .format-page::before, .format-page::after,
    .format-page .doc-title, .format-page .doc-line, .format-page .doc-subhead,
    .format-page .doc-page-number, .format-ruler, .format-callout, .format-seal,
    .format-timeline span::before, .success-banner {
        animation: none !important; opacity: 1 !important; transform: none !important; }
    .format-page { transform: translate(-50%, -50%) !important; }
    .format-callout { opacity: .82 !important; }
    .agent-stage.running::before, .flow-step.active .flow-node::after { animation: none !important; }
    .stButton > button, .stDownloadButton > button,
    [data-testid="stVerticalBlockBorderWrapper"] { transform: none !important; }
}
@keyframes od-reduced-fade { from { opacity: .7; } to { opacity: 1; } }
"""

st.markdown(f"<style>{_OD_THEME_CSS}{_OPENDESIGN_CSS}</style>", unsafe_allow_html=True)


_WORKFLOW = [
    ("理解规范", "理解格式来源"),
    ("解析文档", "读取文档结构"),
    ("标注角色", "判断段落角色"),
    ("执行排版", "写入 Word 样式"),
    ("视觉自检", "检查渲染结果"),
    ("完成", "交付结果"),
]
_STEP_INDEX = {key: index for index, (key, _) in enumerate(_WORKFLOW)}


def _escape(value):
    return html.escape(str(value or ""), quote=True)


def _llm_available():
    return bool(
        os.environ.get("LLM_BASE_URL")
        and os.environ.get("LLM_API_KEY")
        and os.environ.get("LLM_MODEL")
    )


_TEMPERATURE_OPTIONS = {
    "自动兼容（推荐）": "auto",
    "固定 0": "0",
    "固定 0.2": "0.2",
    "固定 0.7": "0.7",
    "固定 1.0": "1",
    "自定义": "custom",
}


def _initialize_model_settings_state():
    if st.session_state.get("model_settings_initialized"):
        return
    provider_id = detect_provider(
        os.environ.get("LLM_BASE_URL"), os.environ.get("LLM_PROVIDER")
    )
    preset = get_provider_preset(provider_id)
    base_url = os.environ.get("LLM_BASE_URL") or preset["base_url"]
    model = os.environ.get("LLM_MODEL") or preset["model"]
    raw_temperature = os.environ.get("LLM_TEMPERATURE") or preset["temperature"]
    try:
        normalized_temperature = normalize_temperature(raw_temperature)
    except ValueError:
        normalized_temperature = "auto"
    matching_label = next(
        (
            label for label, value in _TEMPERATURE_OPTIONS.items()
            if value == normalized_temperature
        ),
        "自定义",
    )

    st.session_state["model_provider_choice"] = provider_id
    st.session_state["model_saved_provider_id"] = provider_id
    st.session_state["model_base_url_input"] = base_url
    st.session_state["model_name_input"] = model
    st.session_state["model_api_key_input"] = ""
    st.session_state["model_temperature_choice"] = matching_label
    st.session_state["model_custom_temperature"] = (
        normalized_temperature if matching_label == "自定义" else "0.2"
    )
    try:
        max_tokens = int(os.environ.get("LLM_MAX_TOKENS") or preset["max_tokens"])
    except (TypeError, ValueError):
        max_tokens = preset["max_tokens"]
    st.session_state["model_max_tokens_input"] = max(256, max_tokens)
    st.session_state["model_public_upload_input"] = (
        os.environ.get("LLM_ALLOW_PUBLIC_IMAGE_UPLOAD", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    st.session_state["model_settings_initialized"] = True


def _apply_provider_preset():
    provider_id = st.session_state.get("model_provider_choice", "custom")
    preset = get_provider_preset(provider_id)
    # 不把一个服务商刚输入的密钥带到另一个服务商。
    st.session_state["model_api_key_input"] = ""
    if provider_id != "custom":
        st.session_state["model_base_url_input"] = preset["base_url"]
        st.session_state["model_name_input"] = preset["model"]
        st.session_state["model_temperature_choice"] = "自动兼容（推荐）"
        st.session_state["model_max_tokens_input"] = preset["max_tokens"]
    st.session_state.pop("model_connection_result", None)


def _selected_temperature():
    selected = _TEMPERATURE_OPTIONS.get(
        st.session_state.get("model_temperature_choice"), "auto"
    )
    if selected == "custom":
        return normalize_temperature(
            st.session_state.get("model_custom_temperature", "0.2")
        )
    return selected


def _model_form_values():
    existing_api_key = os.environ.get("LLM_API_KEY", "")
    entered_api_key = st.session_state.get("model_api_key_input", "").strip()
    same_provider = (
        st.session_state.get("model_provider_choice")
        == st.session_state.get("model_saved_provider_id")
    )
    api_key = entered_api_key or (existing_api_key if same_provider else "")
    temperature = _selected_temperature()
    checked = validate_model_settings(
        st.session_state.get("model_base_url_input"),
        api_key,
        st.session_state.get("model_name_input"),
        temperature,
    )
    return {
        "provider_id": st.session_state.get("model_provider_choice", "custom"),
        "base_url": checked["接口地址"],
        "api_key": checked["API Key"],
        "model": checked["模型名称"],
        "temperature": temperature,
        "max_tokens": int(st.session_state.get("model_max_tokens_input", 8192)),
        "allow_public_image_upload": bool(
            st.session_state.get("model_public_upload_input", False)
        ),
    }


@st.dialog("模型设置", width="large")
def _model_settings_dialog():
    _initialize_model_settings_state()
    # Streamlit 不允许在输入框实例化后修改同名 session_state。保存成功时只设置
    # 待清理标记，并在下一次 dialog fragment 重绘、输入框创建之前清空密钥字段。
    consume_scheduled_api_key_clear(st.session_state)
    provider_labels = {
        provider_id: preset["label"]
        for provider_id, preset in PROVIDER_PRESETS.items()
    }
    st.selectbox(
        "模型服务",
        options=list(PROVIDER_PRESETS),
        format_func=lambda provider_id: provider_labels[provider_id],
        key="model_provider_choice",
        on_change=_apply_provider_preset,
    )
    preset = get_provider_preset(st.session_state["model_provider_choice"])
    st.caption(preset["note"])
    if preset["docs_url"]:
        st.markdown(f"[查看该服务的官方配置说明]({preset['docs_url']})")

    st.text_input(
        "接口地址",
        key="model_base_url_input",
        placeholder="https://provider.example/v1",
    )
    st.text_input(
        "API Key",
        key="model_api_key_input",
        type="password",
        placeholder=(
            "已在本机保存；留空保持不变"
            if (
                os.environ.get("LLM_API_KEY")
                and st.session_state.get("model_provider_choice")
                == st.session_state.get("model_saved_provider_id")
            )
            else "粘贴这个服务的 API Key"
        ),
        help="只写入当前工作台目录下的 .env，不会提交到 GitHub。",
    )
    st.text_input("模型名称", key="model_name_input")

    with st.expander("高级设置"):
        st.selectbox(
            "Temperature",
            options=list(_TEMPERATURE_OPTIONS),
            key="model_temperature_choice",
            help=(
                "自动兼容会完全省略 temperature，让服务商使用模型默认值。"
                "Kimi Code、Kimi K3 和部分推理模型应使用此选项。"
            ),
        )
        if _TEMPERATURE_OPTIONS[
            st.session_state["model_temperature_choice"]
        ] == "custom":
            st.text_input(
                "自定义 Temperature（0–2）",
                key="model_custom_temperature",
            )
        st.number_input(
            "最大输出 Tokens",
            min_value=256,
            max_value=131072,
            step=1024,
            key="model_max_tokens_input",
        )
        st.checkbox(
            "接口拒绝内联图片时，允许上传临时公共图床",
            key="model_public_upload_input",
            help="敏感文档请保持关闭。默认直接以内联 base64 发送给模型服务。",
        )
        preview_temperature = _selected_temperature()
        st.code(
            json.dumps(
                {
                    "provider": st.session_state["model_provider_choice"],
                    "base_url": st.session_state["model_base_url_input"],
                    "model": st.session_state["model_name_input"],
                    "temperature": preview_temperature,
                    "api_key": (
                        "已填写"
                        if st.session_state.get("model_api_key_input")
                        else (
                            "已保存"
                            if (
                                os.environ.get("LLM_API_KEY")
                                and st.session_state.get("model_provider_choice")
                                == st.session_state.get("model_saved_provider_id")
                            )
                            else "未填写"
                        )
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            language="json",
        )

    result = st.session_state.get("model_connection_result")
    if result:
        (st.success if result["ok"] else st.error)(result["message"])

    test_col, save_col = st.columns(2)
    if test_col.button(
        "测试多模态连接",
        width="stretch",
        help="会向当前服务发送一张项目示例图，产生一次很小的模型调用。",
    ):
        try:
            values = _model_form_values()
            client = LLMClient(
                base_url=values["base_url"],
                api_key=values["api_key"],
                model=values["model"],
                timeout=45,
                max_retries=0,
                temperature=temperature_value(values["temperature"]),
                max_tokens=min(values["max_tokens"], 4096),
                allow_public_image_upload=values["allow_public_image_upload"],
            )
            test_image = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "docs", "images", "workbench-home.png",
            )
            client.chat_vision_json(
                "这是连接测试。请确认你能读取图片，只返回一个 JSON 对象："
                '{"ok": true, "message": "multimodal ready"}',
                [test_image],
            )
            st.session_state["model_connection_result"] = {
                "ok": True,
                "message": "连接成功：模型能够接收图片并返回 JSON。",
            }
        except Exception as exc:  # noqa: BLE001
            st.session_state["model_connection_result"] = {
                "ok": False,
                "message": f"连接失败：{exc}",
            }
        st.rerun(scope="fragment")

    if save_col.button("保存到本机", type="primary", width="stretch"):
        try:
            values = _model_form_values()
            save_model_settings(**values)
            load_dotenv(override=True)
            st.session_state["model_saved_provider_id"] = values["provider_id"]
            schedule_api_key_clear(st.session_state)
            st.session_state["model_connection_result"] = {
                "ok": True,
                "message": "设置已保存到本机并立即生效。可以关闭窗口开始排版。",
            }
        except Exception as exc:  # noqa: BLE001
            st.session_state["model_connection_result"] = {
                "ok": False,
                "message": f"保存失败：{exc}",
            }
        st.rerun(scope="fragment")


def _toggle_ui_theme():
    st.session_state["ui_theme"] = (
        "深色" if st.session_state.get("ui_theme", "白色") == "白色" else "白色"
    )


def _save_upload(uploaded, suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as handle:
        handle.write(uploaded.getbuffer())
    return path


def _input_heading(number, title, hint):
    safe_hint = _escape(hint)
    st.markdown(
        f'<div class="input-head"><div class="input-step">{int(number):02d}</div>'
        f'<div class="input-title-row"><div class="input-title">{_escape(title)}</div>'
        f'<span class="input-help" tabindex="0" data-tooltip="{safe_hint}" aria-label="{safe_hint}">?</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _workflow_markup(states, current_step=None, detail=None):
    state_values = set(states.values())
    if "failed" in state_values:
        stage_class, state_class, headline = "", "failed", "Agent 遇到问题"
    elif states.get("完成") == "done":
        stage_class, state_class, headline = "", "done", "Agent 已完成任务"
    else:
        stage_class, state_class, headline = "running", "", "Agent 正在运行"

    nodes = []
    for index, (key, label) in enumerate(_WORKFLOW, 1):
        state = states.get(key, "pending")
        symbol = "✓" if state == "done" else ("—" if state == "skipped" else str(index))
        nodes.append(
            f'<div class="flow-step {state}"><div class="flow-node">{symbol}</div>'
            f'<div class="flow-name">{_escape(label)}</div></div>'
        )
    current_label = dict(_WORKFLOW).get(current_step, current_step or "准备启动")
    detail = detail or "每完成一步，轨道会自动向前推进。"
    return (
        f'<div class="agent-stage {stage_class}"><div class="stage-head">'
        f'<div class="stage-state {state_class}"><span class="pulse"></span>{headline}</div>'
        f'<div class="stage-note">当前 · {_escape(current_label)}</div></div>'
        f'<div class="workflow">{"".join(nodes)}</div>'
        f'<div class="flow-detail">{_escape(detail)}</div></div>'
    )


def _render_step_clock(placeholder, step_label, started_at):
    """浏览器侧持续计时；Python 被模型/渲染器阻塞时也不会停。"""
    elapsed = max(0, int(time.time() - started_at))
    safe_label = _escape(step_label)
    # 计时器是独立 iframe 文档，配色要跟随主题
    if st.session_state.get("ui_theme", "白色") == "深色":
        c_text, c_bg, c_border, c_bold, c_accent = (
            "#c7ced8", "#121720", "#28313d", "#f4f6f8", "#e5e7eb")
    else:
        c_text, c_bg, c_border, c_bold, c_accent = (
            "#3f3f3b", "#ffffff", "#e2e2de", "#171716", "#1e1e1c")
    with placeholder.container():
        st.iframe(
            f"""
<!doctype html><html><head><style>
* {{ box-sizing:border-box; }} body {{ margin:0; color:{c_text}; background:transparent;
font-family:Inter,-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif; }}
.clock {{ height:52px; display:flex; align-items:center; justify-content:space-between; gap:16px;
padding:0 17px; border:1px solid {c_border}; border-radius:5px;
background:{c_bg}; }}
.left {{ display:flex; align-items:center; gap:10px; min-width:0; }}
.wave {{ display:flex; align-items:center; gap:3px; height:18px; }}
.wave i {{ display:block; width:2px; height:14px; border-radius:2px; background:{c_accent};
transform:scaleY(.35); animation:wave 1s cubic-bezier(.77,0,.175,1) infinite; }} .wave i:nth-child(2){{animation-delay:.14s}}
.wave i:nth-child(3){{animation-delay:.28s}} .wave i:nth-child(4){{animation-delay:.42s}}
.copy {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-size:12px; }}
.copy b {{ color:{c_bold}; }} .timer {{ flex:none; color:{c_accent}; font:700 13px ui-monospace,SFMono-Regular,Menlo,monospace; }}
.clock.slow {{ border-color:rgba(255,200,107,.4); }} .clock.slow .timer {{ color:#e08600; }}
@keyframes wave {{ 0%,100%{{transform:scaleY(.35);opacity:.45}} 50%{{transform:scaleY(1);opacity:1}} }}
@media (prefers-reduced-motion:reduce) {{ .wave i {{ animation:none; transform:scaleY(.55); }} }}
</style></head><body>
<div class="clock" id="clock"><div class="left"><span class="wave"><i></i><i></i><i></i><i></i></span>
<span class="copy" id="copy"><b>{safe_label}</b> 正在处理；计时持续表示页面仍在等待返回</span></div>
<span class="timer" id="timer">00:00</span></div>
<script>
const base={elapsed}; const start=Date.now();
function tick() {{
  const total=base+Math.floor((Date.now()-start)/1000);
  const m=String(Math.floor(total/60)).padStart(2,'0');
  const s=String(total%60).padStart(2,'0');
  document.getElementById('timer').textContent=m+':'+s;
  if(total>=120) {{
    document.getElementById('clock').classList.add('slow');
    document.getElementById('copy').innerHTML='<b>{safe_label}</b> 等待较久，通常仍在等待模型或渲染器；可继续等待或稍后重试';
  }}
}}
tick(); setInterval(tick,1000);
</script></body></html>
""",
            height=58,
            width="stretch",
        )


def _event_markup(events):
    rows = []
    for event in events[-24:]:
        status = event.get("status", "run")
        rows.append(
            f'<div class="event-line {status}"><span class="event-time">{_escape(event["time"])}</span>'
            f'<span class="event-step">{_escape(event["step"])}</span>'
            f'<span class="event-msg">{_escape(event["message"])}</span></div>'
        )
    return '<div class="event-list">' + "".join(rows) + "</div>"


# ---------------- 首屏 ----------------
renderer_status = _renderer_status()

with st.container(key="topbar"):
    brand_col, settings_col, theme_col = st.columns(
        [1, 0.13, 0.08], vertical_alignment="center"
    )
    brand_col.markdown(
        '<div class="product-lockup"><span class="product-mark">F</span>'
        '<span class="product-name">FORMAT AGENT</span>'
        '<span class="product-caption">文档排版工作台</span></div>',
        unsafe_allow_html=True,
    )
    with settings_col:
        open_model_settings = st.button(
            "模型设置",
            key="model_settings_button",
            icon=":material/tune:",
            type="tertiary",
        )
    with theme_col:
        next_theme = "深色" if _THEME == "白色" else "白色"
        theme_icon = ":material/dark_mode:" if _THEME == "白色" else ":material/light_mode:"
        st.button(
            f"切换到{next_theme}模式",
            key="theme_toggle",
            icon=theme_icon,
            type="tertiary",
            on_click=_toggle_ui_theme,
        )

if open_model_settings:
    _model_settings_dialog()

st.markdown(
    """
<section class="agent-hero" data-od-id="format-agent-hero">
  <div class="hero-copy">
    <div class="eyebrow">DOCUMENT FORMATTING</div>
    <h1>格式有标准，<br><span class="hero-nowrap">排版不必费时。</span></h1>
    <p>给出格式要求，上传原始文档。标题层级、字体字号、段落间距与页面设置，
       会被整理成一份可继续编辑的 Word 文档。</p>
    <div class="hero-facts">
      <span class="hero-fact">正文内容保留</span>
      <span class="hero-fact">Word 原生样式</span>
      <span class="hero-fact">修改记录可追溯</span>
    </div>
  </div>
  <div class="document-compare" aria-label="文档从乱稿到规范成稿的循环排版动画">
    <div class="format-stage-head"><span>FORMAT PASS / 7.2 S</span><strong>DOCX · LIVE</strong></div>
    <div class="format-field">
      <div class="format-grid" aria-hidden="true"></div>
      <div class="format-ruler" aria-hidden="true"></div>
      <div class="format-page">
        <div class="doc-title"></div>
        <div class="doc-line"></div><div class="doc-line"></div>
        <div class="doc-line"></div><div class="doc-line"></div>
        <div class="doc-subhead"></div>
        <div class="doc-line"></div><div class="doc-line"></div>
        <div class="doc-page-number">01</div>
      </div>
      <div class="format-callout callout-title">TITLE / 标题<b>22 PT · CENTER</b></div>
      <div class="format-callout callout-leading">LEADING / 行距<b>28 PT</b></div>
      <div class="format-callout callout-margin">MARGIN / 页边距<b>30 MM</b></div>
      <span class="format-seal" aria-label="排版完成">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 4 4L19 6"/></svg>
      </span>
    </div>
    <div class="format-timeline" aria-hidden="true">
      <span>01 · 识别结构</span><span>02 · 写入样式</span><span>03 · 验收成稿</span>
    </div>
  </div>
</section>
""",
    unsafe_allow_html=True,
)

if not _llm_available():
    st.warning(
        "还没有配置模型。可以先载入演示任务；处理自己的文档前，请点击右上角"
        "“模型设置”。也可以在“高级设置”中上传 FormatSpec 与 RoleMap，使用完全"
        "确定性的排版流程。"
    )
if not renderer_status["available"]:
    st.info("没有检测到可用的渲染器（依次尝试 Microsoft Word、WPS、LibreOffice）："
            "DOCX 仍可生成，但前后对比和视觉复核将不可用。")


# ---------------- 输入任务 ----------------
st.markdown('<div class="section-title">开始一次排版</div>', unsafe_allow_html=True)

use_demo = st.toggle(
    "载入演示任务",
    value=False,
    help="自动使用 assets/spec.txt 和 assets/messy.docx。",
)

left, right = st.columns(2, gap="large")
with left:
    with st.container(border=True, key="format_rules_card", height=430):
        _input_heading(
            "1",
            "指定排版要求",
            "可以直接描述字体、字号、标题层级和页边距，也可以上传一份排版正确的参考文档。",
        )
        if use_demo:
            spec_mode = "文字说明"
            template_file = None
            with open("assets/spec.txt", encoding="utf-8") as handle:
                spec_text = handle.read()
            st.text_area("已加载的示例规范", value=spec_text, height=190, disabled=True)
            st.success("示例格式要求已准备好")
        else:
            spec_mode = st.radio(
                "格式来源",
                ["文字说明", "参考模板"],
                horizontal=True,
                label_visibility="collapsed",
            )
            spec_text = None
            template_file = None
            if spec_mode == "文字说明":
                spec_text = st.text_area(
                    "排版要求",
                    height=190,
                    placeholder=(
                        "例如：标题用方正小标宋二号、居中；正文用仿宋三号、"
                        "每段首行缩进 2 字符；一级标题用黑体……"
                    ),
                    help=(
                        "不需要使用专业术语。建议写明标题、正文、页边距和行距；"
                        "没有说明的部分由排版流程结合文档结构判断。"
                    ),
                )
            else:
                template_file = st.file_uploader(
                    "上传排版正确的参考文档",
                    type=["docx"],
                    key="template",
                    help="会读取参考文档中的字号、字体、间距、标题层级和编号。建议模板至少包含一个标题和一段正文。",
                )

with right:
    with st.container(border=True, key="upload_document_card", height=430):
        _input_heading(
            "2",
            "上传原始文档",
            "支持 DOCX、DOC、WPS、ODT 和 RTF。正文语义保持不变，最终统一交付 DOCX。",
        )
        if use_demo:
            target_file = None
            st.file_uploader(
                "已加载示例文档",
                type=["docx"],
                key="demo-target",
                disabled=True,
            )
            st.success("示例文档 messy.docx 已准备好")
        else:
            target_file = st.file_uploader(
                "上传待排版文档",
                type=["docx", "doc", "wps", "odt", "rtf"],
                key="target",
                help=(
                    "DOCX 可直接处理；DOC、WPS、ODT、RTF 会先转换为临时 DOCX，"
                    "再进入预检、排版与验收。"
                ),
            )
            if target_file is not None:
                st.success(f"已接收：{target_file.name}")


# 低频技术入口收进高级设置，不干扰主路径。
with st.expander("高级设置 · 预制 JSON / 跳过自动标注", expanded=False):
    st.caption(
        "这里面向熟悉 FormatSpec 和 RoleMap 的高级用户。上传预制规则后，会覆盖上方对应的自动理解步骤。"
    )
    advanced_left, advanced_right = st.columns(2)
    with advanced_left:
        spec_json_file = st.file_uploader(
            "FormatSpec JSON（可选）",
            type=["json"],
            key="spec-json",
            help="直接提供格式规则，跳过对文字说明或模板的理解。",
        )
    with advanced_right:
        rolemap_json_file = st.file_uploader(
            "RoleMap JSON（可选）",
            type=["json"],
            key="rolemap-json",
            help="直接提供段落角色，跳过 Agent 自动标注。",
        )
    if spec_json_file is not None:
        st.info("本次将优先使用预制 FormatSpec；上方格式来源不会参与规则抽取。")


# ---------------- 主行动区 ----------------
target_ready = use_demo or target_file is not None
if spec_json_file is not None or use_demo:
    source_ready = True
elif spec_mode == "文字说明":
    source_ready = bool(spec_text and spec_text.strip())
else:
    source_ready = template_file is not None
can_run = target_ready and source_ready

missing = []
if not source_ready:
    missing.append("格式要求")
if not target_ready:
    missing.append("原始文档")

with st.container(border=True):
    action_left, action_right = st.columns([1.9, 1], gap="large", vertical_alignment="center")
    with action_left:
        if can_run:
            st.markdown(
                '<div class="readiness"><div class="ready-icon ok">✓</div><div>'
                '<div class="ready-title">材料齐全，可以开始排版</div>'
                '<div class="ready-sub">开始后会显示每一步的处理状态与耗时。</div></div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="readiness"><div class="ready-icon wait">!</div><div>'
                f'<div class="ready-title">还差：{_escape("、".join(missing))}</div>'
                '<div class="ready-sub">完成上方缺失项后，运行按钮会自动点亮。</div></div></div>',
                unsafe_allow_html=True,
            )
        verify = st.checkbox(
            "完成排版后，再做一次视觉复核",
            value=False,
            disabled=not renderer_status["available"],
            help="会把排版结果渲染成图片，并调用多模态模型检查；耗时会更长。",
        )
    with action_right:
        run = st.button(
            "开始排版 →",
            type="primary",
            width="stretch",
            disabled=not can_run,
        )


# ---------------- Agent 执行 ----------------
if run and can_run:
    st.markdown('<div class="section-kicker">PROCESS</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">正在处理这份文档</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-help">轨道显示整体进度；下方计时器在模型或渲染器等待期间也会持续运行。</div>',
        unsafe_allow_html=True,
    )

    workflow_states = {key: "pending" for key, _ in _WORKFLOW}
    workflow_box = st.empty()
    clock_box = st.empty()
    events = []
    step_started_at = time.time()
    runtime = {"current_step": None, "started_at": step_started_at}

    workflow_box.markdown(
        _workflow_markup(workflow_states, detail="正在唤醒 Agent，准备读取任务材料。"),
        unsafe_allow_html=True,
    )
    _render_step_clock(clock_box, "准备任务", step_started_at)

    with st.expander("实时事件流 · 遇到长时间等待时可在这里查看", expanded=True):
        log_box = st.empty()

    def on_event(event):
        step = str(event.get("step") or "Agent")
        status = str(event.get("status") or "run")
        message = str(event.get("message") or "")

        if step in _STEP_INDEX:
            if runtime["current_step"] != step:
                runtime["current_step"] = step
                runtime["started_at"] = time.time()
            if status == "run":
                workflow_states[step] = "active"
            elif status == "ok":
                workflow_states[step] = "done"
            elif status == "err":
                workflow_states[step] = "failed"
            elif workflow_states.get(step) != "done":
                workflow_states[step] = "active"

            # 一旦进入后续步骤，前面的 pending 项即视为已完成；视觉复核可跳过。
            step_index = _STEP_INDEX[step]
            for earlier_key, _ in _WORKFLOW[:step_index]:
                if workflow_states[earlier_key] == "pending":
                    workflow_states[earlier_key] = (
                        "skipped"
                        if earlier_key == "视觉自检" and step == "完成" and not verify
                        else "done"
                    )

        events.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "step": step,
                "message": message,
                "status": status,
            }
        )
        active_step = runtime["current_step"]
        workflow_box.markdown(
            _workflow_markup(workflow_states, active_step, message),
            unsafe_allow_html=True,
        )
        if workflow_states.get("完成") != "done" and "failed" not in workflow_states.values():
            _render_step_clock(
                clock_box,
                dict(_WORKFLOW).get(active_step, active_step or "处理中"),
                runtime["started_at"],
            )
        else:
            clock_box.empty()
        log_box.markdown(_event_markup(events), unsafe_allow_html=True)

    target_suffix = ".docx" if use_demo else os.path.splitext(target_file.name)[1].lower()
    target_path = "assets/messy.docx" if use_demo else _save_upload(target_file, target_suffix)
    out_dir = tempfile.mkdtemp(prefix="format-agent-")
    out_path = os.path.join(out_dir, "formatted.docx")
    report_path = os.path.join(out_dir, "report.md")

    try:
        kwargs = {
            "target_path": target_path,
            "out_path": out_path,
            "report_path": report_path,
            "verify": verify,
        }
        if spec_json_file is not None:
            kwargs["spec"] = json.loads(spec_json_file.getvalue().decode("utf-8"))
            validate_spec(kwargs["spec"])
        elif use_demo:
            # 一键示例使用项目内置标准答案，保证演示稳定且不产生外部模型调用。
            with open("assets/spec_std.json", encoding="utf-8") as handle:
                kwargs["spec"] = json.load(handle)
        elif spec_mode == "参考模板":
            kwargs["template_path"] = _save_upload(template_file, ".docx")
        else:
            kwargs["spec_text"] = spec_text

        if rolemap_json_file is not None:
            kwargs["rolemap"] = {
                int(key): value
                for key, value in json.loads(
                    rolemap_json_file.getvalue().decode("utf-8")
                ).items()
            }
        elif use_demo:
            with open("assets/rolemap_std.json", encoding="utf-8") as handle:
                kwargs["rolemap"] = {
                    int(key): value for key, value in json.load(handle).items()
                }

        result = Agent(on_event=on_event).run(**kwargs)
    except Exception as exc:  # 演示界面兜底：错误必须明确落在当前步骤。
        failed_step = runtime["current_step"]
        if failed_step in workflow_states:
            workflow_states[failed_step] = "failed"
        on_event({"step": failed_step or "Agent", "message": str(exc), "status": "err"})
        st.error(f"任务没有完成：{exc}")
        st.caption("你的原始文档没有被修改。检查事件流中的最后一条信息后，可以修正输入并重试。")
        st.stop()

    # ---------------- 结果 ----------------
    st.markdown(
        f"""
<div class="success-banner">
  <div class="label">MISSION COMPLETE</div>
  <h2>排版完成，结果已经准备好</h2>
  <p>Agent 共处理 {len(result['changelog'])} 个段落，生成可继续编辑的 Word 命名样式和完整修改记录。</p>
</div>
""",
        unsafe_allow_html=True,
    )

    summary_cols = st.columns(4)
    summary_cols[0].metric("解析段落", len(result["paragraphs"]))
    summary_cols[1].metric("已处理段落", len(result["changelog"]))
    summary_cols[2].metric("命名样式", len(result["stylemap"]))
    summary_cols[3].metric("视觉问题", len([i for i in result["issues"] if not i.get("pass")]))

    result_tab, summary_tab, technical_tab = st.tabs(["下载结果", "处理摘要", "技术详情"])
    with result_tab:
        st.markdown("#### 先下载排版后的 Word 文档")
        download_left, download_right = st.columns(2)
        with open(result["out_path"], "rb") as handle:
            download_left.download_button(
                "下载排版后的 DOCX",
                handle.read(),
                "formatted.docx",
                width="stretch",
                type="primary",
            )
        with open(result["tracked_path"], "rb") as handle:
            download_right.download_button(
                "下载修订模式 DOCX（审阅视图可见改动）",
                handle.read(),
                "formatted_tracked.docx",
                width="stretch",
            )
        report_left, report_right = st.columns(2)
        with open(result["report_docx_path"], "rb") as handle:
            report_left.download_button(
                "下载修改报告 DOCX",
                handle.read(),
                "format-report.docx",
                width="stretch",
            )
        with open(result["report_path"], "rb") as handle:
            report_right.download_button(
                "下载修改报告 Markdown",
                handle.read(),
                "format-report.md",
                width="stretch",
            )
        with st.expander("在页面中查看修改报告"):
            with open(result["report_path"], encoding="utf-8") as handle:
                st.markdown(handle.read())

    with summary_tab:
        st.caption("这些是 Agent 对每个段落作出的结构判断。")
        style_by_idx = {
            change["idx"]: change.get("style_name", "")
            for change in result["changelog"]
        }
        st.dataframe(
            [
                {
                    "段落": paragraph["idx"],
                    "角色": result["rolemap"].get(paragraph["idx"], "未处理"),
                    "应用样式": style_by_idx.get(paragraph["idx"], "保留原样式"),
                    "内容": paragraph["text"][:52],
                }
                for paragraph in result["paragraphs"]
            ],
            width="stretch",
            hide_index=True,
        )
        if result["issues"]:
            st.markdown("#### 视觉复核记录")
            st.dataframe(result["issues"], width="stretch", hide_index=True)

    with technical_tab:
        st.caption("面向开发者和高级用户的 JSON 中间产物；普通使用无需处理。")
        tech_one, tech_two, tech_three = st.tabs(["FormatSpec", "RoleMap", "Word 样式"])
        with tech_one:
            st.json(result["spec"])
        with tech_two:
            st.json({str(key): value for key, value in sorted(result["rolemap"].items())})
        with tech_three:
            st.dataframe(
                [{"角色": role, "Word 命名样式": name} for role, name in result["stylemap"].items()],
                width="stretch",
                hide_index=True,
            )

    source_name = "内置示例 messy.docx" if use_demo else target_file.name
    save_run(
        result["out_path"],
        result["report_path"],
        {
            "source_name": source_name,
            "spec_mode": "内置示例" if use_demo else ("预制规则" if spec_json_file else spec_mode),
            "issues_count": len(result.get("issues") or []),
        },
    )

    st.markdown('<div class="section-kicker">03 / Visual compare</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">排版前后对比</div>', unsafe_allow_html=True)
    try:
        with st.spinner("正在生成前后对比图……"):
            from core.render import render_docx_to_png

            after_pages = render_docx_to_png(result["out_path"], os.path.join(out_dir, "after"))
            before_pages = (
                render_docx_to_png(target_path, os.path.join(out_dir, "before"))
                if target_suffix == ".docx"
                else []
            )
    except Exception as exc:
        st.warning(f"DOCX 已正常生成，但本机暂时无法生成对比图：{exc}")
    else:
        if before_pages:
            before_col, after_col = st.columns(2, gap="large")
            before_col.caption("排版前")
            after_col.caption("排版后")
            for page_index in range(min(len(before_pages), len(after_pages))):
                before_col.image(before_pages[page_index], caption=f"第 {page_index + 1} 页")
                after_col.image(after_pages[page_index], caption=f"第 {page_index + 1} 页")
        else:
            st.caption("原文件为旧格式：已在转换后执行完整预检；页面仅展示最终 DOCX 预览。")
            for page_index, page in enumerate(after_pages):
                st.image(page, caption=f"排版后 · 第 {page_index + 1} 页", width="stretch")


# ---------------- 历史记录 ----------------
runs = list_runs()
if runs:
    st.markdown('<div class="section-kicker">04 / Recent work</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">最近完成的任务</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-help">历史结果默认收起，不干扰当前任务。</div>',
        unsafe_allow_html=True,
    )
    with st.expander(f"查看历史任务（{len(runs)}）", expanded=False):
        for record in runs:
            columns = st.columns([4.2, 1.4, 1.5, 1.5], vertical_alignment="center")
            columns[0].markdown(
                f"**{_escape(record.get('source_name', '未命名文档'))}**  \n"
                f"<span style='color:#7f8ba1;font-size:12px'>{_escape(record.get('time', ''))}</span>",
                unsafe_allow_html=True,
            )
            columns[1].caption(record.get("spec_mode", ""))
            with open(record["docx"], "rb") as handle:
                columns[2].download_button(
                    "DOCX",
                    handle.read(),
                    file_name=f"formatted_{record['run_id']}.docx",
                    key="history-docx-" + record["run_id"],
                    width="stretch",
                )
            if os.path.isfile(record["report"]):
                with open(record["report"], "rb") as handle:
                    columns[3].download_button(
                        "报告",
                        handle.read(),
                        file_name=f"report_{record['run_id']}.md",
                        key="history-report-" + record["run_id"],
                        width="stretch",
                    )
            st.divider()
