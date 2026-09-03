# Changelog

## 0.2.2 — 2026-09-03

### 中文

- 保存或测试模型配置时校验 API Key，拒绝包含中文说明、空格、引号、`Bearer` 或 `API_KEY=` 前缀的内容。
- 手动编辑 `.env` 后即使留下了无效 Key，LLM 客户端也会在发送请求前给出明确提示。
- API Key 格式错误不再进入三次网络重试，也不会继续显示难以理解的 `latin-1` 编码异常。

### English

- Validate API Keys when saving or testing model settings, rejecting values that include explanatory text, whitespace, quotes, a `Bearer` prefix, or an `API_KEY=` prefix.
- Invalid Keys left by manual `.env` edits are now reported clearly by the LLM client before any request is sent.
- API Key format errors no longer enter three network retries or surface as an opaque `latin-1` encoding exception.

## 0.2.1 — 2026-09-03

### 中文

- 修复保存模型设置后，Streamlit 因在输入框创建后清空 API Key 状态而报错的问题。
- 保存成功后仍会清空界面中的 API Key，但改为在下一次安全重绘开始前执行。
- 从本版本起，新版本的变更日志与 GitHub Release Notes 同时提供中文和英文。

### English

- Fixed a Streamlit session-state error raised after saving model settings and clearing the API Key field.
- The API Key is still cleared from the visible form after a successful save, now before the next safe dialog render.
- Starting with this version, new changelog entries and GitHub Release Notes are provided in both Chinese and English.

## 0.2.0 — 2026-09-03

- 在工作台内新增模型设置窗口，无需手动创建或编辑 `.env`。
- 增加 Kimi Code、Kimi API、智谱 GLM、阿里云百炼、Gemini 与 OpenAI 预设。
- 默认省略 `temperature`，兼容固定采样参数的 Kimi 新模型和部分推理模型。
- 支持在保存前测试图片输入与 JSON 输出能力。
- 切换模型服务时不复用其他服务的 API Key，并继续默认禁止公共图床上传。

## 0.1.0 — 2026-09-03

- 首个独立公开版本。
- 提供现代化 Streamlit 工作台与无需 API Key 的内置演示。
- 支持格式要求或 Word 模板作为规则来源。
- 输出排版后 DOCX、修订模式 DOCX 与修改对照报告。
- 增加可选视觉自检和多模态模型配置。
- 提供 Windows 一键安装与启动脚本。
- 增加隐私、安全、许可证和自动化测试说明。
