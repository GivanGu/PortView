# AGENTS.md — PortView

> Docker 容器与主机端口监控可视化工具。Python 3.12 + FastAPI 后端，Vue 3 + Vite 前端，Docker 多阶段部署。

## Tech Stack

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 · FastAPI · Uvicorn · Docker SDK · psutil |
| 包管理 | uv |
| 前端 | Vue 3 · Vite · TypeScript · vue-i18n |
| 数据库 | SQLite (aiosqlite) |
| 部署 | Docker（多阶段构建） |

## Commands

### Backend
```bash
# Lint + typecheck (run before commits)
uv run ruff check app/ tests/
uv run ruff format app/ tests/

# Tests
uv run pytest tests/ -v          # all tests (pytest-asyncio, asyncio_mode=auto)
uv run pytest tests/test_api.py -v  # single file
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # :3000, proxies /api → :8081
npm run build    # vue-tsc -b && vite build → dist/
```

### Local Docker Build
```bash
docker compose -f docker-compose.local.yml up -d --build --force-recreate
./verify.sh  # smoke test: hits /api/ports, checks offline container ports
```

### Full Local Dev (no Docker)
```bash
# Terminal 1 — backend
uv venv --python 3.12
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8081

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

## AI 工具插件

### OpenCodeReview (OCR)
- **位置**: `.opencode/plugins/open-code-review.ts` — 项目级插件，随仓库提交（`.opencode/.gitignore` 已排除 `node_modules` 等生成物）
- **工具**: `ocr_review`（对 workspace 变更 / 单个 commit / ref 范围做行级审查，返回结构化 findings；`preview=true` 只列待审文件不调 LLM）、`ocr_health`（检查 OCR 版本与 LLM 连通性）
- **LLM 配置**: `~/.opencodereview/config.json` — provider `local-llm`，指向本地 LiteLLM 代理（`http://192.168.31.4:22511/v1`，model `Qwen3.8-27B-Q4_K_M`）
- **注意**: 本地 27B 模型较慢，审查建议 `timeoutMinutes: 20`、`overallTimeoutMinutes: 40`
- **依赖**: `ocr` CLI 需全局可用（`/config/.local/bin/ocr` 软链），node/npm 在 PATH 上

### Ponytail（全局）
- 全局插件，配置在 `~/.config/opencode/opencode.jsonc` 的 `plugin` 字段（npm 包 `@dietrichgebert/ponytail`），对所有项目生效，**不在本仓库内**
- 每轮对话自动注入"懒资深开发"规则集（默认 `full` 档），并提供 `/ponytail [lite|full|ultra|off]`、`/ponytail-review`、`/ponytail-audit`、`/ponytail-debt`、`/ponytail-gain`、`/ponytail-help` 命令

## Branching & Release

### 分支模型
- **`main`** — 稳定分支。仅接受已验证的功能合并，合并后触发 stable 发版（版本号已在 dev 开发前 bump）。
- **`dev`** — 开发分支。开发前先 bump 版本号，日常功能开发在此进行，验证通过后合并回 `main`。

### CI / 镜像构建
| 分支 | Workflow | 镜像 Tag | 说明 |
|---|---|---|---|
| `main` | `docker-publish.yml` | `<version>` + `latest` | 稳定版，版本号取自 `app/__init__.py` |
| `dev` | `docker-dev.yml` | `dev` + `dev-<version>` | 开发版，`dev` 为移动标签，`dev-<version>` 带版本号（如 `dev-1.4.9`） |

两个 workflow 均推送 **GHCR + ACR**，tag 命名空间完全隔离，互不覆盖。

### 发版流程
1. 在 `dev` 分支 bump `app/__init__.py` 版本号（如 `1.4.8` → `1.4.9`），作为本次开发目标版本
   - **版本号只在当前版本基础上 +1（patch 位）**，不要跳号或回退；每次更新都基于上一个已发布版本递增
2. 开发功能，push 触发 `docker-dev.yml` 构建开发镜像（tag: `dev` + `dev-1.4.9`）
3. 验证 `dev` 镜像（`docker pull <registry>/portview:dev-1.4.9`）
4. 合并 `dev` → `main`
5. push `main` 触发 `docker-publish.yml` 构建稳定镜像（tag: `1.4.9` + `latest`）
6. 创建 GitHub Release（英文 changelog），tag `v1.4.9`

## Architecture

### Backend (`app/`)
- **Entry**: `app/main.py` → `create_app()` factory, lifespan inits config + SQLite
- **Services**: `app/services/port_monitor.py` (Docker SDK + psutil → PortCard list), `app/services/db.py` (SQLite via aiosqlite, 11 tables), `app/services/auth.py` (argon2id sessions), `app/services/migrate.py` (v1.6.12 统一存储迁移：旧库搬家 + JSON 入库)
- **Routers**: `app/routers/{ports,config,prefs,ranges,auth}.py` — all under `/api/`
- **Auth guard**: middleware in `main.py` checks `portview_session` cookie; whitelist is `/api/health`, `/api/auth/*`
- **Config**: `app/config.py` 全部落 SQLite（v1.6.12 统一存储）——端口标注 `port_labels` 表（端口主键，服务名非唯一）、访问地址 `user_prefs.access_address` 列、隐藏端口 `hidden_ports` 表。旧 `config/config.json` + `config/hidden_ports.json` 由 `migrate.py` 在启动时迁入 DB 并删除
- **Access address API**: `GET/POST /api/config/access_address` — read/write the global base URL (e.g. `http://192.168.31.1`)

### Frontend (`frontend/`)
- Vue 3 + TypeScript + vue-i18n, dark theme, no UI framework
- `@` alias → `frontend/src/`
- Components in `frontend/src/components/` — main views: `OverviewView`, `PortsView`, `HiddenPortsView`, `SettingsView`, `LoginView`, `PasswordPrompt`
- i18n: `frontend/src/locales/{zh,en}.json`, fallback `zh`
- Built assets (`frontend/dist/`) are served by FastAPI in production via SPA fallback

### Data Flow
1. `port_monitor.get_docker_ports()` — Docker SDK reads container port mappings (including stopped containers)
2. `port_monitor.get_host_ports()` — psutil reads local listening ports
3. `merge` → deduplicated `PortCard` list
4. `config.py` overlays hide rules
5. Frontend renders cards with search/filter

## Project Structure

```
portview/
├── app/                  # FastAPI 后端
│   ├── main.py           # 入口（create_app 工厂）
│   ├── config.py         # 配置管理
│   ├── models.py         # Pydantic 模型
│   ├── routers/          # 路由
│   │   ├── ports.py
│   │   ├── config.py
│   │   ├── prefs.py
│   │   ├── ranges.py
│   │   ├── auth.py
│   │   ├── logos.py
│   │   └── background.py
│   └── services/
│       ├── port_monitor.py  # Docker + 主机端口检测
│       ├── db.py            # SQLite (aiosqlite)
│       ├── auth.py          # argon2id + 会话
│       └── migrate.py       # v1.6.12 存储迁移
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   ├── App.vue
│   │   ├── api/
│   │   ├── components/
│   │   ├── locales/
│   │   └── style.css
│   └── package.json
├── config/               # 运行时数据（bind mount）— 单个 SQLite 库
│   └── portview.db       # 全部用户数据（标注、隐藏端口、偏好、鉴权）
├── tests/                # 后端测试
├── Dockerfile            # 多阶段构建
├── docker-compose.yml
├── pyproject.toml
└── verify.sh             # 冒烟测试脚本
```

## Runtime Configuration

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORTVIEW_PORT` | `8081` | Web 服务监听端口 |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | 配置目录（存放 SQLite 数据库） |
| `PORTVIEW_REQUIRE_AUTH` | 未设 | `1` 强制开启登录；`0` 强制关闭；未设则读数据库 |
| `PORTVIEW_DB` | `/app/config/portview.db` | SQLite 数据文件路径 |

自 v1.6.12 起，全部用户数据统一存储在单个 `config/portview.db` SQLite 文件中。端口标注（端口 → 服务名）与隐藏端口通过界面管理并持久化到数据库。旧版 `config/config.json`（服务→端口映射）与 `config/hidden_ports.json` 会在首次启动时自动迁入数据库并删除，无需手动编辑。

## API Reference

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/ports` | 获取端口数据（支持 `?range_ids=`） |
| POST | `/api/refresh` | 刷新端口数据 |
| POST | `/api/ports/probe_scheme` | 探测单个端口的服务协议 |
| POST | `/api/ports/probe_schemes` | 批量探测服务协议 |
| GET | `/api/ports/schemes` | 获取协议映射表 |
| POST | `/api/ports/scheme` | 设置人工指定协议 |
| DELETE | `/api/ports/scheme/{port}` | 清除人工指定协议 |
| GET | `/api/config/access_address` | 获取访问地址 |
| POST | `/api/config/access_address` | 设置访问地址 |
| POST | `/api/config/edit` | 编辑端口标注（服务名） |
| GET | `/api/config/hidden` | 获取隐藏端口 |
| GET | `/api/config/hidden/details` | 获取隐藏端口详情 |
| POST | `/api/config/hidden` | 隐藏端口 |
| DELETE | `/api/config/hidden/{port}` | 取消隐藏单个端口 |
| POST | `/api/config/hidden/batch` | 批量隐藏 |
| POST | `/api/config/hidden/unhide/batch` | 批量取消隐藏 |
| GET | `/api/prefs` | 获取用户偏好 |
| PATCH | `/api/prefs` | 更新偏好 |
| POST | `/api/prefs/reset` | 重置为默认 |
| GET | `/api/ranges` | 监控区间列表 |
| POST | `/api/ranges` | 新建区间 |
| PUT | `/api/ranges/{rid}` | 更新区间 |
| DELETE | `/api/ranges/{rid}` | 删除区间 |
| POST | `/api/auth/set_password` | 设置/修改密码 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 当前会话状态 |
| PATCH | `/api/auth/toggle` | 开启/关闭登录保护 |
| GET | `/api/logos` | Logo 元数据列表 |
| GET | `/api/logos/defaults` | 内置默认 Logo 键列表 |
| GET | `/api/logos/default/{key}` | 获取默认 Logo 图片 |
| GET | `/api/logos/{app_key}` | 获取 Logo 图片 |
| PUT | `/api/logos/{app_key}` | 上传 Logo |
| DELETE | `/api/logos/{app_key}` | 删除 Logo |
| POST | `/api/logos/discover` | 自动识别 favicon |
| POST | `/api/logos/fetch` | 从外部 URL 抓取 favicon |
| PUT | `/api/background` | 上传背景图 |
| DELETE | `/api/background` | 移除背景图 |

完整交互文档：启动后访问 `/docs`（Swagger UI）。

## Key Gotchas

- **SQLite location**: default `/app/config/portview.db`（v1.6.12 起统一存储，DB 是唯一持久化点）。旧 `.data/portview.db` 由 `migrate.py` 在启动时自动搬家（复制→integrity_check→原子落位→删旧库）；旧 `config.json`/`hidden_ports.json` 同样自动入库并删除。Docker 中 bind mount `config/` 目录即可持久化。
- **psutil 7.x breaking change**: `laddr.address` → `laddr.ip`, `.proto` → `.type` — already patched in `port_monitor.py`
- **Frontend build required before backend SPA fallback works**: if `frontend/dist/` missing, root `/` returns a JSON hint instead of the app
- **uv.lock**: backend deps are pinned in lockfile; use `uv sync --no-install-project --no-dev` in Docker for reproducible installs
- **Docker socket**: mount `/var/run/docker.sock:ro` or port monitoring fails silently (no Docker containers shown)
- **Version**: `app/__init__.py` → `__version__` is the single source of truth for version strings

## Conventions

- Python: ruff (line-length 100, target py312), isort with `app` as first-party; RUF001/002/003 (Chinese fullwidth chars) and B008 (FastAPI Depends) are ignored
- Commit style: `<type>(<scope>): <summary>` — e.g. `feat(port-monitor): add offline container support`
- Release: `main` → `docker-publish.yml` (version + latest); `dev` → `docker-dev.yml` (dev + dev-<version>); version read from `app/__init__.py`
- **Every release must create a GitHub Release** (via API or `gh release create`) with an English changelog; the in-app update badge links to the latest release page (`/releases/tag/vX.Y.Z`)
- Release notes 只写更新内容与修复内容（Features/Fixes），不展开说明问题产生的原因
- Language: code comments and commit messages are in Chinese; README is bilingual (English default `README.md` + Chinese `README.zh-CN.md`)
