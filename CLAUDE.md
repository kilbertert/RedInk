# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RedInk (红墨 AI 图文生成器) — 输入一句话,生成小红书风格的多页图文(封面 + 内页 + 总结页)。后端生成大纲和图像,前端编排页面、配置与历史预览。

- Backend: Python 3.11+ / Flask / uv / google-genai / Pillow / PyYAML
- Frontend: Vue 3 + TypeScript / Vite / Pinia / axios
- Packaging: `pyproject.toml` 走 hatchling,Python 包名仍是 `backend`

## Common commands

依赖:`uv sync`(后端);`cd frontend && pnpm install`(前端)。

本地起服务(两个终端):
- 后端:`uv run python -m backend.app` → `http://127.0.0.1:12398`
- 前端:`cd frontend && pnpm dev` → `http://localhost:5173`(Vite dev proxy 把 `/api/*` 转给后端 12398)

一键脚本:`./start.sh` / `scripts/start-macos.command` / `start.bat`(自动装依赖并同时拉起两端)。

后端测试(在仓库根):
- 全量:`uv run pytest tests/ -v`
- 单文件:`uv run pytest tests/errors_test.py -v`
- 关键字:`uv run pytest tests/ -k history -v`

前端检查:
- 类型:`cd frontend && pnpm typecheck`(`vue-tsc --noEmit`,PR 前必须过)
- 构建:`cd frontend && pnpm build` — 产物落到 `frontend/dist`,`backend/app.py` 检测到后会托管静态资源,这同时也是 Docker 单容器部署的入口

Docker:
- `docker run -d -p 12398:12398 -v ./history:/app/history -v ./output:/app/output histonemax/redink:latest`
- `history` 必须挂载(历史持久化),`output` 按需挂载(下载图片),`text_providers.yaml` / `image_providers.yaml` 也可挂载覆盖默认

## Backend architecture

入口:`backend/app.py:create_app()`。`create_app` 探测 `frontend/dist` 是否存在:存在就走 Flask 静态托管 + Vue history fallback,否则走开发模式(返回 JSON 端点说明)。`Config` 从 `backend/config.py` 装载,启动时 `setup_logging()` 统一日志格式。

配置来源:`backend/config.py` + 仓库根的 `text_providers.yaml` / `image_providers.yaml`(模板是同名 `*.example`)。启动时 `_validate_config_on_startup` 会把 active provider + API Key 是否就绪打到日志,**缺 key 不阻塞启动**。

代码分层:

- `backend/routes/` — Flask 蓝图,按域拆分:`outline_routes`、`content_routes`、`image_routes`、`history_routes`、`config_routes`,统一通过 `backend/routes/__init__.py:register_routes(app)` 装载。
- `backend/services/` — 业务用例层,不接触 HTTP:`outline`, `content`, `image`, `history`, `history_image_merger`, `image_rate_limiter`。`history_image_merger` 与 `image_rate_limiter` 是 `v1.4.3` 拆出来的复用组件。
- `backend/generators/` — provider 抽象:
  - `factory.py` 按 active provider 选实现;
  - 文本:`openai_compatible.py`、`google_genai.py`,共用 `backend/utils/text_client.py`;
  - 图像:`google_genai.py`、`image_api.py`,加上 v1.4.3 引入的共享层 `image_provider_policy.py` / `image_api_client.py` / `image_response_extractor.py`(响应里 b64_json / data URL / 临时 URL 都走这里归一化)。
- `backend/utils/` — `genai_client`、`text_client`、`image_compressor`(Pillow 压缩)。

错误模型:`backend/errors.py` 定义 Problem Details 风格的异常类,蓝图捕获后序列化为统一结构化错误体,前端有对应错误卡片组件。

测试夹具(`tests/conftest.py`):`app`、`client`、`temp_history_dir`、`sample_pages`、`sample_outline`、`sample_history_record`。

## Frontend architecture

`frontend/src/` 按页面/组件拆分;状态走 Pinia store,HTTP 走 axios;`pnpm typecheck` 在 PR 前必须通过。`vite.config.ts` 配置 `/api/*` dev proxy → 后端 12398。`pnpm build` 之后由 Flask 接管静态资源,这就是 Docker 单容器入口。

## Project-specific conventions

- **License**: CC BY-NC-SA 4.0。商业使用需联系作者申请商用许可(见 README 末段)。本仓库不接收商业闭源衍生。
- **Secrets**: API Key 不进仓库。`text_providers.yaml` / `image_providers.yaml` 在 `.gitignore`,模板是 `*.yaml.example`。`scripts/`、CI、PR 内容都不能提交真实 key。
- **High concurrency**: 图像出图最多 15 并发,由 `image_providers.yaml` 的 `high_concurrency: true` 启用,默认 `false`。GCP $300 试用账户保持 `false`,否则会被限流。
- **Image recovery**: `v1.4.3` 起,历史记录在刷新/重试时复用已有图像(`per-record recovery`),不会重复消耗上游配额。修改历史相关代码前先看 `backend/services/history.py` 与 `backend/services/history_image_merger.py`。
- **Structured errors**: 后端用 `backend/errors.py` 的 Problem Details 风格,前端有配套错误卡片组件。新增 API 失败路径应当抛出这些异常类,不要直接 `return jsonify({"error": ...})`。
- **Logging**: 后端日志格式由 `backend/app.py:setup_logging()` 统一,新代码直接 `logging.getLogger(__name__)`,不要再 `addHandler`。
- **Commit messages**: 仓库实际历史用 Conventional Commits(`<type>(<scope>): <subject>`),以 git 历史为准。`CONTRIBUTING.md` 写的 `type: description` 是简版,不要混用。
- **PR gate**: deterministic CI(前端 typecheck/build + 后端 pytest)是必过项;AI review 是辅助。本仓库的全局策略继承自 `~/.claude/CLAUDE.md`,本文件不重复。