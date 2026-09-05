---
outline: deep
---

# 架构

## 项目结构

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
└── docker-compose.yml
```

## 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 后端框架 | FastAPI | 自动生成 OpenAPI 文档 |
| 后端运行 | Uvicorn | ASGI 服务器 |
| 端口扫描 | Docker SDK + psutil | 容器 + 主机端口 |
| 存储 | SQLite | 用户信息 + 配置 |
| 认证 | JWT + bcrypt | 单用户模式 |
| 前端框架 | Vue 3.5 | 渐进式 UI |
| 状态管理 | Pinia | 轻量状态容器 |
| 路由 | Vue Router 5 | SPA + 登录守卫 |
| 虚拟滚动 | @tanstack/vue-virtual | 65535 端口流畅渲染 |
| 图标 | @lucide/vue | 专业一致 |

## 架构决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 缓存 | 不使用 | NAS 场景刷新低频，扫一次 <500ms |
| 实时推送 | 不使用 | 违背「小内存、小占用」原则 |
| 多 Docker Host | 不支持 | 单机 NAS 足够 |
| 历史趋势 | 不需要 | 无时序库，SQLite 存不下 |
| 图标库 | @lucide/vue | 专业一致、Tree-shaking、零 Emoji |
| 虚拟滚动 | @tanstack/vue-virtual | 65535 端口卡片流畅渲染 |
| 鉴权 | 单用户 + 密码 | NAS 个家/家庭用户，配置少 |
