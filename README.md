# PortView

> Docker 容器与主机端口监控与可视化工具

PortView 运行在 NAS / 服务器上，实时读取 Docker 容器的端口映射与本机监听端口，
以卡片形式可视化展示，并支持自定义端口备注、隐藏端口、快速搜索。

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![Vue](https://img.shields.io/badge/Vue-3.5+-blue)

---

## 功能特性

- **Docker 端口监控** — 实时读取所有容器（含已停止）的端口映射
- **主机端口监控** — 检测本机监听端口（psutil）
- **端口卡片展示** — 按服务分类，显示端口、协议、状态、备注
- **自定义备注** — 为任意端口添加说明
- **备注打通** — 端口卡片直接展示该端口的备注，搜索可命中备注
- **多段监控区间** — 定义任意段数区间（如 80s / 8000s），一键筛选仅看关心的区间
- **密码登录（可关闭）** — 单用户密码 + 会话 Cookie（`argon2id` 哈希），适合暴露 8081 端口时防误触
- **隐藏端口** — 一键隐藏不关心的端口
- **快速搜索** — 按名称 / 端口号 / 备注即时过滤
- **离线容器** — 已停止容器的端口映射同样展示

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 · FastAPI · Uvicorn · Docker SDK · psutil |
| 包管理 | uv |
| 前端 | Vue 3 · Vite 7 · TypeScript |
| 部署 | Docker（多阶段构建） |

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 克隆仓库
git clone https://github.com/GivanGu/DockPorts.git portview
cd portview

# 启动
docker compose up -d
```

服务默认监听 `8081` 端口，访问 `http://<host>:8081`。

### 方式二：拉取 ACR 镜像

```bash
# 登录 ACR（交互式输入用户名和密码）
docker login crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com

docker pull crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:latest

docker run -d --name portview \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v $(pwd)/config:/app/config \
  -v portview-data:/app/.data \
  -e PORTVIEW_PORT=8081 \
  crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:latest
# 上面 -v portview-data:/app/.data 命名卷用于持久化密码/备注/区间/登录态，
# 详见上方「首次使用与数据持久化」。
```

### 方式三：本地开发

```bash
# 后端（需要 uv）
uv venv --python 3.12
uv pip install fastapi "uvicorn[standard]" docker psutil pydantic
uvicorn app.main:app --reload --port 8081

# 前端（需要 Node 22+）
cd frontend
npm install
npm run dev   # http://localhost:3000（proxy 到 :8081）
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORTVIEW_PORT` | `8081` | Web 服务监听端口 |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | 配置文件目录 |
| `PORTVIEW_REQUIRE_AUTH` | 未设 | `1` 强制开启登录门；`0`/`off` 强制关闭；未设则读数据库 `user_prefs.require_auth`（默认关闭） |
| `PORTVIEW_DB` | `/app/.data/portview.db` | 运行时数据（SQLite）文件路径。生产建议用命名卷挂载 `/app/.data`，见下节 |

## 首次使用与数据持久化

**运行时数据**（密码、端口备注、监控区间、登录开关、主题/强调色、审计日志）都存在 SQLite，默认落在容器内 **`/app/.data/portview.db`**。`.dockerignore` 已把 `.data` 排除出镜像，所以**数据不会随镜像烘焙**，必须由卷挂载来持久化——否则每次 `docker compose up --force-recreate` / 换 tag 重建，都会重置为全新空库，UI 回到"设置密码 + 空卡片"首屏。

- **Docker Compose（推荐）**：`docker-compose.yml` 已用命名卷 `portview-data:/app/.data` 持久化，直接 `docker compose up -d` 即可，密码/备注/区间跨重建保留。
- **裸 `docker run`**：自行加 `-v portview-data:/app/.data`（命名卷）或 `-v <host>/.data:/app/.data`（宿主目录）。
- **备份 / 迁移**（命名卷）：
  ```bash
  docker run --rm \
    -v portview-data:/src -v "$(pwd)/.data:./dst" alpine \
    cp -a /src/. ./dst/
  ```

**首次进入**：新用户（`users` 表为空）访问时首屏是"设置密码"。设一次即可，之后即为登录态。若只想开放本机、不想要登录门，可设 `PORTVIEW_REQUIRE_AUTH=0`（或在设置页"安全与登录"关闭）。

## 配置

配置文件位于 `config/config.json`，格式：

```json
{
  "远程登录:host": "22:tcp",
  "MySQL数据库:host": "3306:tcp",
  "PortView:docker": "7575:tcp"
}
```

键格式：`服务名:类型`，类型为 `docker` 或 `host`。
值格式：`端口:协议`。

隐藏端口保存在 `config/hidden_ports.json`。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/ports` | 获取端口数据 |
| POST | `/api/refresh` | 刷新端口数据 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config/edit` | 编辑配置 |
| GET | `/api/config/hidden` | 获取隐藏端口 |
| POST | `/api/config/hidden` | 隐藏端口 |
| POST | `/api/config/hidden/unhide` | 取消隐藏 |
| POST | `/api/config/hidden/batch` | 批量隐藏/取消 |

完整文档：启动后访问 `/docs`（Swagger UI）。

## 项目结构

```
portview/
├── app/                  # FastAPI 后端
│   ├── main.py           # 入口
│   ├── config.py         # 配置管理
│   ├── models.py         # 数据模型
│   ├── dependencies.py   # 依赖注入
│   ├── routers/          # 路由
│   │   ├── ports.py
│   │   └── config.py
│   └── services/
│       └── port_monitor.py
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   ├── App.vue
│   │   ├── api/
│   │   ├── components/
│   │   └── style.css
│   └── package.json
├── config/               # 运行时配置（卷挂载）
│   ├── config.json
│   └── hidden_ports.json
├── tests/                # 后端测试
├── Dockerfile            # 多阶段构建
├── docker-compose.yml
├── pyproject.toml
└── verify.sh             # 验证脚本
```

## 版本历史

### v1.3.0（2026-09-07）
- 新增：端口归类筛选（本地 / Docker 归类视图）+ 未备注快补
- 新增：在线 / 离线视觉强化
- 优化：端口卡片等高（port / gap / unknown 全部 135px）；归类视图聚焦已用端口、隐藏间隙与未知范围卡
- 部署：`/app/.data` 以命名卷持久化（密码 / 备注 / 监控区间跨重建保留；README 与 compose 同步更新）
- 镜像：`v1.3.0` 同 digest 推送到 GHCR + ACR（`:1.3.0` / `:1.3` / `:1` / `:latest`）

### v1.2.0（2026-09-05）
- 新增：多段监控区间（`/api/ranges` CRUD + `/api/ports?range_ids=` 收窄卡片）
- 新增：密码登录（可关闭，`argon2id` 哈希 + httpOnly 会话 Cookie，7 天 TTL）
- 新增：端口卡片打通备注（`port_notes.remark` 注入 `used` / `unknown_range` 卡片）
- 新增：搜索命中备注
- 前端：端口页工具栏加「区间」选择器 + 新建/删除按钮；设置页加「安全与登录」卡片；登录门
- 测试：后端 +12 用例，全量 60 passed

### v1.1.1（2026-09-05）
- 修复：`psutil` 7.x `laddr.address` / `.proto` API 变更
- 优化：卡片等高 + 在线/离线状态显式

### v1.1.0（2026-09-04）
- 新增：P1-1 备注（`port_notes.remark`）
- 新增：P1-2 用户偏好（暗色主题 + 强调色）

## 测试

```bash
uv pip install pytest httpx
uv run pytest tests/ -v
```

## CI/CD

- **docker-dev.yml** — push `dev` 分支自动构建并推送 ACR
- **docker-publish.yml** — push `v*.*.*` 标签构建并推送 GHCR

## 许可证

MIT
