# PortView

> 🚀 Docker 容器与主机端口监控与可视化工具 — **NAS 友好 · 轻量 · 极简依赖**

PortView 运行在 NAS / 服务器上，实时读取 Docker 容器的端口映射与本机监听端口，
以卡片形式可视化展示，并支持自定义端口备注、隐藏端口、快速搜索、端口冲突检测、
自定义监控区间、登录认证、消息通知。

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![Vue](https://img.shields.io/badge/Vue-3.5+-blue)
![License](https://img.shields.io/badge/License-MIT-blue)

---

## ✨ 功能特性

### 端口监控
- **Docker 端口监控** — 实时读取所有容器（含已停止）的端口映射
- **主机端口监控** — 检测本机监听端口（psutil）
- **端口冲突检测** — 自动发现被多个来源占用的端口，红色标出冲突来源
- **端口卡片展示** — 按服务分类，显示端口、协议、状态、容器、备注
- **离线容器** — 已停止容器的端口映射同样展示

### 便捷操作
- **自定义备注** — 为任意端口添加说明（服务名、来源类型）
- **隐藏端口** — 一键隐藏不关心的端口
- **快速搜索** — 按名称 / 端口号 / 备注 / 容器名即时过滤
- **虚拟滚动** — 海量端口卡片流畅渲染
- **快捷键导航** — `/` 聚焦搜索，`j/k` 翻页，`Esc` 关闭，`?` 帮助

### 自定义区间
- **自定义监控区间** — 添加如「22500-22600」这样的固定端口段，
  在侧边栏点击即可快速切换到该区间视图
- **多区间管理** — 在配置页面增删改查，支持自定义名称 & 颜色标签

### 安全与通知
- **登录认证** — 单用户 JWT + bcrypt 密码，SQLite 存储
- **消息面板** — 端口冲突、容器启停、配置变更记录在通知中心查看
- **结构化日志** — JSON 格式，便于 ELK/Grafana Loki 采集

---

## 🏗️ 技术架构

```
PortView
├── Backend: Python 3.12 · FastAPI · Uvicorn
├── Docker SDK + psutil 端口扫描
├── SQLite 存储用户 & 配置
├── JWT + bcrypt 认证
├── JSON 结构化日志
└── Docker 多阶段构建
├── Frontend: Vue 3 · Vite 7 · TypeScript
├── Pinia 状态管理
├── Vue Router + 登录守卫
├── @lucide/vue 图标
├── @tanstack/vue-virtual 虚拟滚动
└── 纯 CSS 设计系统（深/浅色）
```

### 架构决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 缓存 | 不使用 | NAS 场景刷新低频，扫一次 <500ms |
| 实时推送 | 不使用 | 违背「小内存、小占用」原则 |
| 多 Docker Host | 不支持 | 单机 NAS 足够 |
| 历史趋势 | 不需要 | 无时序库，SQLite 存不下 |
| 图标库 | @lucide/vue | 专业一致、Tree-shaking、零 Emoji |
| 虚拟滚动 | @tanstack/vue-virtual | 65535 端口卡片流畅渲染 |
| 鉴权 | 单用户 + 密码 | NAS 个人/家庭用户，配置少 |

---

## 📦 部署

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/GivanGu/PortView.git
cd PortView

docker compose up -d
```

服务默认监听 `7577` 端口，访问 `http://<host>:7577`。

> **首次运行**：默认管理员密码为 `portview123`，登录后请尽快修改。

### 方式二：Docker Run

```bash
docker run -d --name portview \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v ./config:/app/config \
  -e PORTVIEW_PORT=7577 \
  ghcr.io/givangu/portview:latest
```

### 方式三：本地开发

```bash
# 后端（需要 uv）
uv venv --python 3.12
uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 7577

# 前端（需要 Node 22+）
cd frontend
npm install
npm run dev   # http://localhost:5173，代理到 :7577
```

---

## ⚙️ 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORTVIEW_PORT` | `7577` | Web 服务监听端口 |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | 配置目录（卷挂载） |
| `PORTVIEW_JWT_SECRET` | `portview-jwt-secret-change-me` | JWT 密钥 |
| `PORTVIEW_DEFAULT_PASSWORD` | `portview123` | 首次运行默认密码 |
| `PORTVIEW_LOG_LEVEL` | `INFO` | 日志等级 |
| `PORTVIEW_LOG_FORMAT` | `json` | 日志格式 (json/human) |

---

## 🔧 配置

### 服务映射

`config/config.json`：

```json
{
  "ssh": {"port": 22, "protocol": "TCP", "service_type": "host"},
  "mysql": {"port": 3306, "protocol": "TCP", "service_type": "host"},
  "portview": {"port": 7577, "protocol": "TCP", "service_type": "docker"}
}
```

### 隐藏端口

`config/hidden_ports.json` — 数组形式。

### 自定义监听区间

在配置页面添加，如：

```json
[
  {"id": "a1b2c3d4", "name": "游戏服务器", "start_port": 22500, "end_port": 22600, "color": "#00b4d8"}
]
```

---

## 🌐 API 接口

### 端口
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ports` | 获取端口数据 (分页/搜索/筛选) |
| POST | `/api/refresh` | 刷新 Docker + 主机端口数据 |
| GET | `/api/health` | 健康检查 |

查询参数：`cursor`, `limit`, `protocol`, `start_port`, `end_port`, `search`, `range_id`

### 配置
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/config` | 获取服务映射 |
| POST | `/api/config` | 保存服务映射 |
| POST | `/api/config/edit` | 编辑单个端口 |
| GET | `/api/config/hidden` | 获取隐藏端口 |
| POST | `/api/config/hidden` | 隐藏端口 |
| DELETE | `/api/config/hidden/{port}` | 取消隐藏 |
| POST | `/api/config/hidden/batch` | 批量隐藏/取消 |
| GET | `/api/config/ranges` | 获取自定义区间列表 |
| POST | `/api/config/ranges` | 添加自定义区间 |
| PUT | `/api/config/ranges/{id}` | 修改自定义区间 |
| DELETE | `/api/config/ranges/{id}` | 删除自定义区间 |

### 认证
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录 (`{"password": "xxx"}`) |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 获取当前用户 |
| POST | `/api/auth/change-password` | 修改密码 |

### 通知
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/notifications` | 获取最近通知 |
| POST | `/api/notifications/read-all` | 全部标记已读 |
| DELETE | `/api/notifications/clear-read` | 清除已读 |

> 完整 API 文档：启动后访问 `/docs`（Swagger UI）。

---

## 🎮 前端快捷键

| 快捷键 | 行为 |
|---|---|
| `/` | 聚焦搜索框 |
| `Esc` | 关闭弹窗 / 清空搜索 |
| `j` / `k` | 端口列表上下导航 |
| `?` | 显示快捷键帮助 |
| `g` + `1-9` | 快速跳转前 9 个自定义区间 |

---

## 🧪 测试

```bash
uv run pytest tests/ -v              # 后端单元测试
npm --prefix frontend run test:unit   # 前端单元测试
npm --prefix frontend run test:e2e    # E2E (Playwright)
```

---

## 📁 项目结构

```
portview/
├── app/
│   ├── main.py                 # 入口 + 路由注册 + SPA 回退
│   ├── config.py               # 配置 CRUD (config/hidden/ranges)
│   ├── models.py               # Pydantic 数据模型
│   ├── dependencies.py         # 依赖注入 (lru_cache 单例)
│   ├── routers/
│   │   ├── auth.py             # JWT 认证 + SQLite 用户
│   │   ├── ports.py            # 端口查询 / 刷新 (分页/搜索/冲突)
│   │   ├── config.py           # 服务映射 / 隐藏端口 CRUD
│   │   ├── ranges.py           # 自定义区间 CRUD
│   │   └── notifications.py    # 通知面板 API
│   ├── services/
│   │   ├── docker_scanner.py   # Docker 容器端口扫描
│   │   ├── host_scanner.py     # 主机端口扫描 (psutil)
│   │   ├── port_analyzer.py    # 合并 + 冲突检测 + 分页
│   │   ├── notification_bus.py # 通知环形缓冲区
│   │   └── port_monitor.py     # 向后兼容 shim
│   └── utils/
│       ├── errors.py           # 统一错误码
│       └── logging.py          # JSON 结构化日志
├── frontend/src/
│   ├── router/                 # Vue Router + 登录守卫
│   ├── stores/                 # Pinia (auth/ports/notifications)
│   ├── views/                  # Login/Overview/Ports/Hidden/Config/Notifications
│   ├── components/             # PortCard/VirtualList/NotificationBell
│   ├── icons/                  # @lucide/vue 图标导出
│   ├── api/                    # API 封装
│   └── style.css               # CSS 变量化设计系统
├── tests/                      # pytest 单元测试
├── Dockerfile                  # 多阶段构建
├── docker-compose.yml
├── pyproject.toml
└── DEVELOPMENT.md              # 开发任务看板
```

---

## 🧰 贡献

开发分支：`dagongzai/portview-refactor`

```bash
git checkout -b feature/your-feature
# ... 提交
git push origin feature/your-feature
```

---

## 📄 许可证

MIT
