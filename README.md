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

服务默认监听 `7577` 端口，访问 `http://<host>:7577`。

### 方式二：拉取 ACR 镜像

```bash
docker login crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com \
  --username=810086218@qq.com

docker pull crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:dev

docker run -d --name portview \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v $(pwd)/config:/app/config \
  -e PORTVIEW_PORT=7577 \
  crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:dev
```

### 方式三：本地开发

```bash
# 后端（需要 uv）
uv venv --python 3.12
uv pip install fastapi "uvicorn[standard]" docker psutil pydantic
uvicorn app.main:app --reload --port 7577

# 前端（需要 Node 22+）
cd frontend
npm install
npm run dev   # http://localhost:3000（proxy 到 :7577）
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORTVIEW_PORT` | `7577` | Web 服务监听端口 |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | 配置文件目录 |

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
