# Changelog

## 0.3.0 — 2026-09-03

### 中文

- 新增无需安装 Python 的 64 位 Windows 便携 EXE，解压后双击即可打开 Streamlit 工作台。
- 将只读资源与用户数据分离：内置示例随程序打包，API Key 与历史结果保存在 EXE 所在目录。
- Office/WPS 转换、PDF 渲染和 Word 域刷新改用同一 EXE 的隔离工作进程，并保留超时与进程清理边界。
- 修复模板未规定编号时，目标文档原有的有效标题/正文自动编号被样式重置删除的问题；保留后的编号继续继承新样式的字体字号。
- 修复修订模式 DOCX 在 WPS 中“接受所有修订”后字体回退为默认字体的问题：修订稿在保留命名样式的同时，把新格式显式写入段落与文字的直接格式（与 Word 原生录制的格式修订一致），干净稿不受影响。
- 原子保存增加 Windows 短暂文件占用重试，降低安全软件扫描 DOCX 或 `.env` 时造成的偶发保存失败。
- 增加 PyInstaller 可复现构建脚本及 GitHub Actions Windows 构建流程。
- 便携包附带中英文快速说明，并在启动窗口显示中英文状态与访问地址。

### English

- Added a self-contained 64-bit Windows portable EXE that opens the Streamlit workbench without requiring Python.
- Separated bundled read-only resources from user data: built-in samples stay inside the package, while API Keys and history remain beside the EXE.
- Routed Office/WPS conversion, PDF rendering, and Word field refresh through isolated worker modes in the same EXE while preserving timeout and process-cleanup boundaries.
- Fixed valid heading/body numbering being removed when the template did not specify numbering; preserved labels continue to inherit the newly applied style font and size.
- Fixed tracked-changes DOCX reverting to the default font after "Accept All Revisions" in WPS Office: the tracked document now also writes the new formatting as explicit direct formatting (matching Word's native tracked-format pattern); the clean output is unchanged.
- Added bounded retries around atomic saves to tolerate brief Windows file locks caused by security scanning of DOCX or `.env` files.
- Added a reproducible PyInstaller build script and a GitHub Actions Windows build workflow.
- Added bilingual quick-start instructions and bilingual startup status output to the portable package.

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
