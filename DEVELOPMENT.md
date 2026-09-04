# PortView — 开发任务看板 & 进度追踪

**分支**：`dagongzai/portview-refactor`
**目标**：Phase 1 架构重构 — 模块化 + 分页 + 冲突检测 + 配置 UI + 虚拟滚动 + 图标系统
**约束**：极小体积、NAS 友好、零 UI 框架、不加 Redis/时序库/WebSocket

---

## 📌 总览

| 阶段 | 状态 | 开始日期 | 目标日期 |
|---|---|---|---|
| **Phase 1 — 架构重构 + 基础** | 🟡 进行中 | 2026-09-04 | 2026-09-10 |
| Phase 2 — 配置界面 + 自定义区间 | ⬜ 待开始 | — | — |
| Phase 3 — 登录鉴权 + 通知面板 | ⬜ 待开始 | — | — |
| Phase 4 — 工程化 + 文档 | ⬜ 待开始 | — | — |

---

## P0-后端核心重构

### ✅ Week 1 任务

- [x] **分支创建**：`dagongzai/portview-refactor`
- [x] **开发计划文档**：`DEVELOPMENT.md`
- [ ] **模块拆分**：`port_monitor.py` → `docker_scanner.py` / `host_scanner.py` / `port_analyzer.py` / `notification_bus.py`
- [ ] **统一错误码**：`app/utils/errors.py` + `app/utils/logging.py`
- [ ] **自定义区间 CRUD API**：`/api/config/ranges` (GET/POST/PUT/DELETE)
- [ ] **端口冲突检测**：`conflict` 字段 + `conflict_sources`
- [ ] **分页 API**：`cursor/limit` 参数 + 响应格式
- [ ] **后端单元测试**：`tests/unit/test_docker_scanner.py`, `test_port_analyzer.py`, `test_ranges.py`

### ⬜ Week 2 (计划)
- [ ] **分页 API 联调**：前端虚拟滚动 + 后端游标
- [ ] **冲突检测前端展示**：PortCard 红边 + Tooltip

---

## P0-前端核心体验

### ✅ Week 1 任务
- [ ] **图标方案**：`npm i lucide-vue-next` + `src/icons/index.ts` 导出
- [ ] **色板系统**：`style.css` 变量化暗/亮主题
- [ ] **PortCard 视觉重写**：紧凑模式 + 状态点动画

### ⬜ Week 2 任务
- [ ] **虚拟滚动**：`@tanstack/vue-virtual` 接入 `PortsView`
- [ ] **LoginView**：登录页 + 路由守卫 + Token 存储
- [ ] **ConfigView**：服务映射表格 + 自定义区间管理
- [ ] **侧边栏自定义区间入口**：下拉/标签页快速切换
- [ ] **PortsView 面包屑**：激活区间显示 + 返回全量

### ⬜ Week 3 任务
- [ ] **NotificationBell**：点击展开面板
- [ ] **键盘快捷键**：`/` 搜索, `j/k` 导航, `?` 帮助
- [ ] **响应式调试**：NAS 端各种屏幕尺寸

---

## P1-工程化

- [ ] **CI/CD**：ruff/mypy/pytest + npm lint/typecheck
- [ ] **文档站**：VitePress + GitHub Pages
- [ ] **README 更新**：部署、配置、快捷键、截图

---

## 🏗️ 架构决议

| 决策 | 选项 | 确定 |
|---|---|---|
| 虚拟滚动 | A. `@tanstack/vue-virtual` / B. 自研 | ✅ A |
| 鉴权模式 | A. 单用户+密码 / B. 多用户+SQLite | ✅ A |
| 图标库 | A. Inline SVG / B. lucide-vue-next | ✅ B |
| 缓存层 | 有 / 无 | ✅ 无 |
| 实时推送 | WebSocket / 轮询 / 无 | ✅ 无 |
| 多 Docker Host | 支持 / 不支持 | ✅ 不支持 |
| 历史趋势 | SQLite/InnoDB / 不需要 | ✅ 不需要 |

---

## 🔧 依赖清单

```
# frontend (package.json devDependencies)
lucide-vue-next        # 图标库
@tanstack/vue-virtual   # 虚拟滚动
zod                     # 前端表单校验 (可选)

# backend (pyproject.toml)
bcrypt                  # 密码哈希
python-jose[cryptography] # JWT
structlog               # 结构化日志

# dev
pytest, pytest-asyncio, httpx
ruff, mypy
vitest, @vue/test-utils, jsdom
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
| POST | `/api/auth/login` | **[NEW]** 登录 |
| GET | `/api/auth/me` | **[NEW]** 获取当前用户 |

---

*维护者：dagongzai | 更新日期：2026-09-04*