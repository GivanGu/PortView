# PortView — 项目文档

> 最近更新：2026-09-03 · 版本：v1.0.0 · 分支：`dev`
> 本仓库由 `coracoo/DockPorts` fork 而来，已断开 fork 关系并重置历史，作为全新项目 **PortView** 维护。

## 项目定位

PortView 是一个面向 NAS / 服务器的 **Docker 容器 + 主机端口监控与可视化工具**。
核心能力：读取 Docker 容器端口映射（含已停止容器）、检测本机监听端口、
以卡片形式展示、自定义备注、隐藏端口、快速搜索。

## 技术栈

- **后端**：Python 3.12 · FastAPI · Uvicorn · Docker SDK · psutil · Pydantic
- **包管理**：uv（本地 venv + 镜像内 `uv pip install`）
- **前端**：Vue 3.5 · Vite 7 · TypeScript · Pinia（暗色主题，自研样式，无 UI 框架）
- **部署**：Docker 多阶段构建（Node 构建前端 → Python 3.12 运行）
- **CI/CD**：GitHub Actions（dev 分支 → ACR；tag → GHCR）

## 目录结构

```
portview/
├── app/                        # FastAPI 后端
│   ├── __init__.py             # __version__ = "1.0.0"
│   ├── main.py                 # 入口：创建 app、挂载路由、静态资源、健康检查
│   ├── config.py               # 配置读写（config.json / hidden_ports.json）
│   ├── models.py               # Pydantic 模型（PortCard / PortAnalysis / ConfigModal）
│   ├── dependencies.py         # 依赖注入（PortMonitor 单例）
│   ├── routers/
│   │   ├── ports.py            # /api/ports · /api/refresh
│   │   └── config.py           # /api/config · /api/config/edit · hidden 系列
│   └── services/
│       └── port_monitor.py     # 核心：get_docker_ports · get_host_ports · merge
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── App.vue             # 布局：侧边栏 + 主内容（ports / hidden 两个 Tab）
│   │   ├── api/index.ts        # API 封装
│   │   ├── components/         # PortsView · HiddenPortsView · PortCard · GapCard 等
│   │   └── style.css           # 全局暗色主题
│   ├── index.html
│   └── package.json
├── config/                     # 运行时配置（Docker 卷挂载）
│   ├── config.json
│   ├── config.json.example     # 首次启动复制源
│   └── hidden_ports.json
├── tests/                      # pytest（test_config · test_api）
├── Dockerfile                  # 多阶段：node:22-alpine 构建前端 → python:3.12-slim
├── docker-compose.yml          # 发布版（拉 ACR 镜像）
├── docker-compose.local.yml    # 本地构建版
├── pyproject.toml              # name = "portview" · requires-python >= 3.12
├── verify.sh                   # 离线容器端口验证脚本
└── .github/workflows/
    ├── docker-dev.yml          # push dev → ACR
    └── docker-publish.yml      # push tag → GHCR
```

## 核心数据流

1. `port_monitor.py` 通过 Docker SDK 读取容器端口映射（`get_docker_ports`）
2. 通过 psutil 读取本机监听端口（`get_host_ports`）
3. `merge` 合并去重，生成 `PortCard` 列表
4. `config.py` 叠加用户备注 / 隐藏规则
5. 前端 `PortsView` 渲染卡片，支持搜索 / 隐藏

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（返回 name/version/status） |
| GET | `/api/ports` | 端口数据（port_cards / 统计） |
| POST | `/api/refresh` | 刷新端口数据 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config/edit` | 编辑配置 |
| GET | `/api/config/hidden` | 获取隐藏端口 |
| POST | `/api/config/hidden` | 隐藏端口 |
| POST | `/api/config/hidden/unhide` | 取消隐藏 |
| POST | `/api/config/hidden/batch` | 批量隐藏/取消 |

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORTVIEW_PORT` | `7577` | Web 监听端口 |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | 配置目录 |

## 构建与发布

```bash
# 本地构建
docker compose -f docker-compose.local.yml up -d --build --force-recreate
./verify.sh

# CI
# push dev  → ACR  selfwarehouse/portview:dev
# push v*.*.* → GHCR ghcr.io/givangu/portview
```

## 版本记录

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0.0 | 2026-09-03 | 更名 PortView；断开 fork；重置历史；基座升级 Python 3.12；多阶段 Dockerfile |
| v0.3.0 | — | FastAPI 重写（原 DockPorts） |
| v0.2.0 | — | 离线容器端口展示 |
| v0.1.0 | — | Flask 初版 |
