# AGENTS.md — PortView

> Docker 容器与主机端口监控可视化工具。Python 3.12 + FastAPI 后端，Vue 3 + Vite 前端，Docker 多阶段部署。

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
2. 开发功能，push 触发 `docker-dev.yml` 构建开发镜像（tag: `dev` + `dev-1.4.9`）
3. 验证 `dev` 镜像（`docker pull <registry>/portview:dev-1.4.9`）
4. 合并 `dev` → `main`
5. push `main` 触发 `docker-publish.yml` 构建稳定镜像（tag: `1.4.9` + `latest`）
6. 创建 GitHub Release（英文 changelog），tag `v1.4.9`

## Architecture

### Backend (`app/`)
- **Entry**: `app/main.py` → `create_app()` factory, lifespan inits config + SQLite
- **Services**: `app/services/port_monitor.py` (Docker SDK + psutil → PortCard list), `app/services/db.py` (SQLite via aiosqlite, 5 tables), `app/services/auth.py` (argon2id sessions)
- **Routers**: `app/routers/{ports,config,notes,prefs,ranges,auth}.py` — all under `/api/`
- **Auth guard**: middleware in `main.py` checks `portview_session` cookie; whitelist is `/api/health`, `/api/auth/*`
- **Config**: `app/config.py` reads `config/config.json` + `config/hidden_ports.json`; `__access_address__` key stores global base URL for "open service" links
- **Access address API**: `GET/POST /api/config/access_address` — read/write the global base URL (e.g. `http://192.168.31.1`)

### Frontend (`frontend/`)
- Vue 3 + TypeScript + vue-i18n, dark theme, no UI framework
- `@` alias → `frontend/src/`
- Components in `frontend/src/components/` — main views: `OverviewView`, `PortsView`, `NotesView`, `HiddenPortsView`, `SettingsView`, `LoginView`, `PasswordPrompt`
- i18n: `frontend/src/locales/{zh,en}.json`, fallback `zh`
- Built assets (`frontend/dist/`) are served by FastAPI in production via SPA fallback

### Data Flow
1. `port_monitor.get_docker_ports()` — Docker SDK reads container port mappings (including stopped containers)
2. `port_monitor.get_host_ports()` — psutil reads local listening ports
3. `merge` → deduplicated `PortCard` list
4. `config.py` overlays user notes + hide rules
5. Frontend renders cards with search/filter

## Key Gotchas

- **SQLite location**: default `/app/.data/portview.db`; must mount volume or data resets on recreate. `portview-data` named volume in compose files handles this.
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
- Language: code comments and commit messages are in Chinese; README is bilingual (English default `README.md` + Chinese `README.zh-CN.md`)
