# PortView

> Docker 容器与主机端口监控可视化工具。

[English](README.md) | [简体中文](README.zh-CN.md)

PortView 运行在 NAS / 服务器上，实时读取 Docker 容器的端口映射与本机监听端口，
以卡片形式可视化展示，并支持隐藏端口、多段区间筛选、快速筛选、快速搜索。

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![Vue](https://img.shields.io/badge/Vue-3.5+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 功能特性

- **Docker 端口监控** — 实时读取所有容器（含已停止）的端口映射
- **主机端口监控** — 检测本机监听端口（psutil）
- **端口卡片展示** — 按服务分类，显示端口、协议、状态
- **多段监控区间** — 定义任意段数区间（如 80s / 8000s），一键筛选仅看关心的区间
- **快速筛选** — 工具栏一键筛选「未知服务」端口与未显示 Logo 的卡片
- **密码登录（可关闭）** — 单用户密码 + 会话 Cookie（argon2id 哈希），适合暴露 8081 端口时防误触
- **隐藏端口** — 一键隐藏不关心的端口
- **快速搜索** — 按名称 / 端口号即时过滤
- **离线容器** — 已停止容器的端口映射同样展示
- **暗色 / 亮色主题** — 6 种强调色可选
- **国际化** — 英文 & 简体中文界面

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 · FastAPI · Uvicorn · Docker SDK · psutil |
| 包管理 | uv |
| 前端 | Vue 3 · Vite · TypeScript · vue-i18n |
| 数据库 | SQLite (aiosqlite) |
| 部署 | Docker（多阶段构建） |

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/GivanGu/PortView.git portview
cd portview
docker compose up -d
```

服务默认监听 `8081` 端口，访问 `http://<host>:8081`。

### 方式二：拉取镜像

```bash
# GHCR
docker pull ghcr.io/givangu/portview:latest

# 或 ACR（国内）
docker pull crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:latest

docker run -d --name portview \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v ./config:/app/config \
  -e PORTVIEW_PORT=8081 \
  ghcr.io/givangu/portview:latest
```

> 通过 bind mount 挂载 `config/` 目录，可持久化全部数据（密码、监控区间、端口标注、隐藏端口、登录态），跨容器重建保留。所有数据统一存储在单个 `config/portview.db` SQLite 文件中。

### 方式三：本地开发

```bash
# 后端（需要 uv）
uv venv --python 3.12
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8081

# 前端（需要 Node 22+）
cd frontend
npm install
npm run dev   # http://localhost:3000（proxy 到 :8081）
```

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORTVIEW_PORT` | `8081` | Web 服务监听端口 |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | 配置目录（存放 SQLite 数据库） |
| `PORTVIEW_REQUIRE_AUTH` | 未设 | `1` 强制开启登录；`0` 强制关闭；未设则读数据库 |
| `PORTVIEW_DB` | `/app/config/portview.db` | SQLite 数据文件路径 |

### 服务标注与隐藏端口

自 v1.6.12 起，全部用户数据统一存储在单个 `config/portview.db` SQLite 文件中。端口标注（端口 → 服务名）与隐藏端口通过界面管理并持久化到数据库。

> 旧版 `config/config.json`（服务→端口映射）与 `config/hidden_ports.json` 会在首次启动时自动迁入数据库并删除，无需手动编辑。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/ports` | 获取端口数据（支持 `?range_ids=`） |
| POST | `/api/refresh` | 刷新端口数据 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config/edit` | 编辑配置 |
| GET | `/api/config/hidden` | 获取隐藏端口 |
| POST | `/api/config/hidden` | 隐藏端口 |
| POST | `/api/config/hidden/unhide` | 取消隐藏 |
| POST | `/api/config/hidden/batch` | 批量隐藏/取消 |
| GET | `/api/prefs` | 获取用户偏好 |
| PATCH | `/api/prefs` | 更新偏好 |
| POST | `/api/prefs/reset` | 重置为默认 |
| GET | `/api/ranges` | 监控区间列表 |
| POST | `/api/ranges` | 新建区间 |
| PUT | `/api/ranges/{id}` | 更新区间 |
| DELETE | `/api/ranges/{id}` | 删除区间 |
| POST | `/api/auth/set_password` | 设置/修改密码 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 当前会话状态 |
| PATCH | `/api/auth/toggle` | 开启/关闭登录保护 |

完整交互文档：启动后访问 `/docs`（Swagger UI）。

## 项目结构

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
│   │   └── auth.py
│   └── services/
│       ├── port_monitor.py  # Docker + 主机端口检测
│       ├── db.py            # SQLite (aiosqlite)
│       └── auth.py          # argon2id + 会话
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

## 测试

```bash
uv run pytest tests/ -v
```

## 许可证

MIT
