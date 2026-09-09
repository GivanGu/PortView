# PortView

> Docker container & host port monitoring and visualization tool.

[English](README.md) | [简体中文](README.zh-CN.md)

PortView runs on a NAS or server, reads Docker container port mappings and local listening ports in real time, and displays them as visual cards. It supports custom port notes, port hiding, multi-range filtering, and quick search.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![Vue](https://img.shields.io/badge/Vue-3.5+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

- **Docker port monitoring** — reads port mappings from all containers (including stopped ones)
- **Host port monitoring** — detects local listening ports via psutil
- **Port cards** — grouped by service, showing port, protocol, status, and notes
- **Custom notes** — attach a remark to any port; notes appear directly on port cards
- **Multi-range filtering** — define any number of port ranges (e.g. 80s / 8000s) and filter to only those
- **Password login (optional)** — single-user password + session cookie (argon2id), useful when exposing port 8081
- **Port hiding** — one-click hide for ports you don't care about
- **Quick search** — instant filter by name / port number / note
- **Offline containers** — stopped containers' port mappings are still shown
- **Dark / Light theme** — with 6 accent color choices
- **i18n** — English & Simplified Chinese UI

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · Uvicorn · Docker SDK · psutil |
| Package manager | uv |
| Frontend | Vue 3 · Vite · TypeScript · vue-i18n |
| Database | SQLite (aiosqlite) |
| Deployment | Docker (multi-stage build) |

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
git clone https://github.com/GivanGu/PortView.git portview
cd portview
docker compose up -d
```

The service listens on port `8081` by default. Visit `http://<host>:8081`.

### Option 2: Pull image directly

```bash
# GHCR
docker pull ghcr.io/givangu/portview:latest

# or ACR (China)
docker pull crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:latest

docker run -d --name portview \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v portview-data:/app/.data \
  -e PORTVIEW_PORT=8081 \
  ghcr.io/givangu/portview:latest
```

> The named volume `portview-data` persists password, notes, ranges, and login state across container rebuilds.

### Option 3: Local development

```bash
# Backend (requires uv)
uv venv --python 3.12
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8081

# Frontend (requires Node 22+)
cd frontend
npm install
npm run dev   # http://localhost:3000 (proxies /api to :8081)
```

## Configuration

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORTVIEW_PORT` | `8081` | Web service listen port |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | Config file directory |
| `PORTVIEW_REQUIRE_AUTH` | unset | `1` force-enable login; `0` force-disable; unset reads DB |
| `PORTVIEW_DB` | `/app/.data/portview.db` | SQLite data file path |

### Service mapping (`config/config.json`)

Maps known services to ports for display:

```json
{
  "SSH:host": "22:tcp",
  "MySQL:host": "3306:tcp",
  "PortView:docker": "8081:tcp"
}
```

Key format: `ServiceName:type` where type is `docker` or `host`.
Value format: `port:protocol`.

### Hidden ports

Stored in `config/hidden_ports.json`, managed via the UI.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/ports` | Get port data (supports `?range_ids=`) |
| POST | `/api/refresh` | Refresh port data |
| GET | `/api/config` | Get config |
| POST | `/api/config/edit` | Edit config |
| GET | `/api/config/hidden` | Get hidden ports |
| POST | `/api/config/hidden` | Hide port(s) |
| POST | `/api/config/hidden/unhide` | Unhide port(s) |
| POST | `/api/config/hidden/batch` | Batch hide/unhide |
| GET | `/api/notes` | List notes (`?search=`) |
| POST | `/api/notes` | Create/update note (upsert by port) |
| DELETE | `/api/notes/{port}` | Delete note |
| GET | `/api/prefs` | Get user preferences |
| PATCH | `/api/prefs` | Update preferences |
| POST | `/api/prefs/reset` | Reset to defaults |
| GET | `/api/ranges` | List monitoring ranges |
| POST | `/api/ranges` | Create range |
| PUT | `/api/ranges/{id}` | Update range |
| DELETE | `/api/ranges/{id}` | Delete range |
| POST | `/api/auth/set_password` | Set/change password |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Current session status |
| PATCH | `/api/auth/toggle` | Enable/disable auth |

Full interactive docs: visit `/docs` (Swagger UI) after startup.

## Project Structure

```
portview/
├── app/                  # FastAPI backend
│   ├── main.py           # Entry point (create_app factory)
│   ├── config.py         # Config management
│   ├── models.py         # Pydantic models
│   ├── routers/          # API routers
│   │   ├── ports.py
│   │   ├── config.py
│   │   ├── notes.py
│   │   ├── prefs.py
│   │   ├── ranges.py
│   │   └── auth.py
│   └── services/
│       ├── port_monitor.py  # Docker + host port detection
│       ├── db.py            # SQLite (aiosqlite)
│       └── auth.py          # argon2id + sessions
├── frontend/             # Vue 3 frontend
│   ├── src/
│   │   ├── App.vue
│   │   ├── api/
│   │   ├── components/
│   │   ├── locales/
│   │   └── style.css
│   └── package.json
├── config/               # Runtime config (volume mount)
│   ├── config.json
│   └── hidden_ports.json
├── tests/                # Backend tests (63 cases)
├── Dockerfile            # Multi-stage build
├── docker-compose.yml
├── pyproject.toml
└── verify.sh             # Smoke test script
```

## Testing

```bash
uv run pytest tests/ -v
```

## License

MIT
