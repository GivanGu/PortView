# PortView — 开发任务看板 & 进度追踪

**分支**：`dagongzai/portview-refactor`
**目标**：Phase 1 架构重构 — 模块化 + 分页 + 冲突检测 + 配置 UI + 虚拟滚动 + 图标系统
**约束**：极小体积、NAS 友好、零 UI 框架、不加 Redis/时序库/WebSocket

---

## 📌 总览

| 阶段 | 状态 | 开始日期 | 目标日期 |
|---|---|---|---|
| **Phase 1 — 架构重构 + 基础** | ✅ **完成**（发版就绪） | 2026-09-04 | 2026-09-10 |
| Phase 2 — 配置界面 + 自定义区间 | ✅ 完成 | — | — |
| Phase 3 — 登录鉴权 + 通知面板 | ✅ 完成 | — | — |
| Phase 4 — 工程化 + 文档 | ✅ 完成 | — | — |

---

## P0-后端核心重构

### ✅ Week 1 任务

- [x] **分支创建**：`dagongzai/portview-refactor`
- [x] **开发计划文档**：`DEVELOPMENT.md`
- [x] **模块拆分**：`port_monitor.py` → `docker_scanner.py` / `host_scanner.py` / `port_analyzer.py` / `notification_bus.py`
- [x] **统一错误码**：`app/utils/errors.py` + `app/utils/logging.py`
- [x] **自定义区间 CRUD API**：`/api/config/ranges` (GET/POST/PUT/DELETE)
- [x] **端口冲突检测**：`conflict` 字段 + `conflict_sources`
- [x] **分页 API**：`cursor/limit` 参数 + 响应格式
- [x] **后端单元测试**：69 tests pass (单元 + 集成 + 认证 + 区间 + 通知)

### ✅ Week 2 任务
- [x] **分页 API 联调**：前端虚拟滚动 + 后端游标
- [x] **冲突检测前端展示**：PortCard 红边 + Tooltip

---

## P0-前端核心体验

### ✅ Week 1 任务
- [x] **图标方案**：`lucide-vue-next` + `src/icons/index.ts` 导出
- [x] **色板系统**：`style.css` 变量化暗/亮主题
- [x] **PortCard 视觉重写**：紧凑模式 + 状态点动画

### ✅ Week 2 任务
- [x] **虚拟滚动**：`@tanstack/vue-virtual` 接入 `PortsView`
- [x] **LoginView**：登录页 + 路由守卫 + Token 存储
- [x] **ConfigView**：服务映射表格 + 自定义区间管理
- [x] **侧边栏自定义区间入口**：下拉/标签页快速切换
- [x] **PortsView 面包屑**：激活区间显示 + 返回全量

### ✅ Week 3 任务
- [x] **NotificationBell**：点击展开面板
- [x] **键盘快捷键**：`/` 搜索, `j/k` 导航, `?` 帮助
- [x] **响应式调试**：NAS 端各种屏幕尺寸

---

## P1-工程化

- [x] **CI/CD**：GitHub Actions (ruff/pytest + vite build/vitest)
- [x] **文档站**：VitePress + GitHub Pages
- [x] **README 更新**：部署、配置、快捷键、截图
- [x] **Dockerfile**：多阶段构建
- [x] **docker-compose.yml**：生产部署
- [x] **.env.example**：环境变量模板

---

## 🏗️ 架构决议

| 决策 | 选项 | 确定 |
|---|---|---|
| 虚拟滚动 | `@tanstack/vue-virtual` | ✅ |
| 鉴权模式 | 单用户+密码 (JWT + SQLite + bcrypt) | ✅ |
| 图标库 | `@lucide/vue` | ✅ |
| 缓存层 | 无 | ✅ |
| 实时推送 | 无 | ✅ |
| 多 Docker Host | 不支持 | ✅ |
| 历史趋势 | 不需要 | ✅ |

---

## 🔧 依赖清单

```bash
# backend (pyproject.toml)
bcrypt                  # 密码哈希
python-jose[cryptography] # JWT
psutil                  # 主机端口扫描
docker                  # 容器端口扫描
fastapi                 # Web 框架
uvicorn[standard]       # ASGI 服务器

# frontend (package.json)
@lucide/vue             # 图标库
@tanstack/vue-virtual   # 虚拟滚动
pinia                   # 状态管理
vue-router              # 路由
vitest                  # 单元测试
@vue/test-utils         # Vue 测试工具
happy-dom               # DOM 模拟

# dev
pytest, pytest-asyncio, httpx
ruff                    # 代码检查
mypy                    # 类型检查
```

---

## 📡 API 设计

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/ports` | 分页: `cursor`, `limit`, `search`, `protocol`, `start_port`, `end_port` |
| POST | `/api/refresh` | 刷新 Docker 端口数据 |
| GET | `/api/config` | 获取服务映射 |
| POST | `/api/config` | 保存服务映射 |
| POST | `/api/config/edit` | 单个端口编辑 |
| GET | `/api/config/hidden` | 获取隐藏端口 |
| POST | `/api/config/hidden` | 隐藏端口 |
| POST | `/api/config/hidden/unhide` | 取消隐藏 |
| POST | `/api/config/hidden/batch` | 批量操作 |
| GET | `/api/config/ranges` | **[NEW]** 获取自定义区间列表 |
| POST | `/api/config/ranges` | **[NEW]** 添加自定义区间 |
| PUT | `/api/config/ranges/{id}` | **[NEW]** 修改自定义区间 |
| DELETE | `/api/config/ranges/{id}` | **[NEW]** 删除自定义区间 |
| GET | `/api/notifications` | **[NEW]** 获取最近通知 |
| POST | `/api/notifications/read-all` | **[NEW]** 全部标记已读 |
| POST | `/api/notifications/read/{id}` | **[NEW]** 标记单条已读 |
| DELETE | `/api/notifications/clear-read` | **[NEW]** 清除已读 |
| POST | `/api/auth/login` | **[NEW]** 登录 |
| POST | `/api/auth/logout` | **[NEW]** 登出 |
| GET | `/api/auth/me` | **[NEW]** 获取当前用户 |
| POST | `/api/auth/change-password` | **[NEW]** 修改密码 |

---

## 🧪 测试覆盖率

| 层 | 测试文件 | Tests |
|---|---|---|
| 后端 API | `test_api.py` | 18 |
| 后端配置 | `test_config.py` | 14 |
| 后端端口监控 | `test_port_monitor.py` | 14 |
| 后端端口分析 | `test_port_analyzer.py` | 7 |
| 后端认证 | `test_auth.py` | 6 |
| 后端自定义区间 | `test_ranges.py` | 6 |
| 后端通知 | `test_notifications.py` | 4 |
| 前端 API/types | `api.spec.ts` | 3 |
| 前端 PortCard 类型 | `PortCard.spec.ts` | 3 |
| **总计** | | **69 + 6** |

---

## 🚀 发版 checklist

- [x] 后端模块拆分
- [x] 后端单元测试（69 pass）
- [x] 前端视图层开发
- [x] 前端单元测试 (6 pass)
- [x] CI/CD 流水线
- [x] VitePress 文档站
- [x] README 更新
- [x] Dockerfile + docker-compose
- [x] .env.example
- [x] .gitignore

---

*维护者：dagongzai | 更新日期：2026-09-04*
