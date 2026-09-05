# PortView — 开发待办（Sprint 清单）

> 本文件是 **唯一权威任务清单**，由打工仔在每次推进任务后维护（打 ✅ / 改状态 / 记 commit 号）。
> 新上下文接手时，**先读本文件**，看哪些 `[ ]` 未勾，按 Sprint 顺序往下做。
> 目标版本：**v1.2.0**（当前 v1.1.1）

---

## Sprint A — 登录 + 监控区间 + 备注打通（承诺锁定）

| # | 任务 | 后端 | 前端 | 测试 | 状态 | 备注 |
|---|---|---|---|---|---|---|
| A1 | 密码登录（可关闭） | `app/services/auth.py` + `app/routers/auth.py` + `app/middleware.py`；`argon2id` 哈希；`httpOnly` cookie `portview_session`；关闭走 `PORTVIEW_REQUIRE_AUTH=0` 或 `user_prefs.require_auth=0` | `frontend/src/router.ts` 加 `/login` 路由；`AuthGate.vue` 判断 401 → redirect；`login.vue` 表单 | +6 用例（login ok / bad / disabled / expiry / logout / csrf） | ✅ `44c5367`（后端）· 前端 `44c5367` | 依赖：`pyproject.toml` 加 `argon2-cffi>=23.1` |
| A2 | 多段监控区间 | `app/routers/ranges.py` `GET/POST/PUT/DELETE /api/ranges`；从 `range_rules` 表读（已有 0.7 schema）；`port_monitor.get_port_analysis` 接受 `ranges` 参数并过滤 | `PortsView.vue` 顶部加「监控区间」下拉 + 新建对话框；改完驱动 get_port_analysis | +8 用例 | ✅ | 依赖 A1（登录后可见） |
| A3 | 备注打通到卡片 | `port_monitor` 内 `JOIN port_notes`，`PortCard.remark` 字段；`_apply_search` 也搜 remark | `PortsView.vue` 卡片底部加 `.port-remark` 行（仅当非空渲染） | +6 用例（含搜索命中 remark） | ✅ | — |
| A4 | 配置清理 | 改 `config/config.json.example`：`caddy:docker: 2019:tcp` → 建议改成 `caddy: 443:tcp`（或按真实服务名）；`dockports:docker: 7577:tcp` → `portview:docker: 7577:tcp`（PortView 本身） | README 同步 | 已有 api test 覆盖 | [ ] | 顺手 |
| A5 | 凭证位规范化 | 把 `ghp_...` 从 `.venv` 里挪走；`.gitignore` 加 `.github/.secrets`；`docker-publish.yml` 改用 `${{ secrets.GITHUB_TOKEN }}`（GH Actions 自带） | — | — | [ ] | 本次发版直接靠 built-in token（见 v1.2.0 验证） |
| A6 | 发版 v1.2.0 | `app/__init__.py` 1.1.1 → 1.2.0 | — | 全量 pytest + npm build ✅ | ✅ | 触发 docker-publish |

## Sprint B — 体验（登录后可做，可合并进 A）

| # | 任务 | 状态 |
|---|---|---|
| B1 | 端口卡片 5s 轮询 + ETag 短路 + 状态栏「实时」 | [ ] |
| B2 | 导出 CSV / JSON（把死代码 `frontend/src/utils/export.ts` 接上，加「导出」按钮） | [ ] |
| B3 | 排序 toggle（默认升序，支持降序） | [ ] |
| B4 | 端口卡片「本页全选」→ 批量隐藏/取消 | [ ] |

## Sprint C — 收尾（选做）

| # | 任务 | 状态 |
|---|---|---|
| C1 | 接 `audit_log`（每次 hide/unhide/edit 写一条） | [ ] |
| C2 | README 补 v1.2 变更摘要 | [ ] |
| C3 | `ja` 语言（看需求） | [ ] |

---

## 关键文件速查

| 关注点 | 路径 |
|---|---|
| 端口合并逻辑 + 卡片生成 | `app/services/port_monitor.py` |
| SQLite schema + 迁移 | `app/services/db.py`（5 张表：schema_version / port_notes / user_prefs / range_rules / audit_log） |
| 路由注册 | `app/main.py`（`include_router` 块） |
| 路由文件 | `app/routers/{ports,config,notes,prefs,ranges,auth}.py` |
| 模型 | `app/models.py`（`PortCard` / `APIResponse` / `UserPrefsRead` / `NoteRead`…） |
| 配置读写 | `app/config.py`（`load_config` / `load_hidden_ports` / `save_hidden_ports`） |
| 前端 API | `frontend/src/api/index.ts` |
| 前端组件 | `frontend/src/components/{Overview,Ports,Notes,Hidden,Settings}View.vue` |
| 前端样式 | `frontend/src/style.css` |
| i18n 词典 | `frontend/src/locales/{zh,en}.json`（`vue-i18n`，fallback `zh`） |
| CI/CD | `.github/workflows/{docker-publish,docker-dev}.yml` |
| 发布触发 | tag `v*.*.*` → `docker-publish.yml`（GHCR 主，ACR best-effort `continue-on-error:true`） |

## 当前基线（v1.1.1 @ 2026-09-05）

- 后端：FastAPI + SQLite（aiosqlite）+ psutil（7.x 兼容）+ Docker SDK；34 用例通过
- 前端：Vue 3.5 + Vite 7 + TS + vue-i18n；暗色主题 + 6 色强调色选择器
- 部署：多阶段 Dockerfile（node:22-alpine → python:3.12），`uv` 管理依赖
- 已修：psutil 7.x `laddr.address` → `ip` / `.proto` → `.type`；卡片等高；在线/离线显式

## 发版流程（每次）

1. `python -m pytest` 全绿 + `cd frontend && npm run build` 通过
2. `git add -A && git commit -m "<type>(<scope>): <summary>"`
3. `git tag -a vX.Y.Z -m "..." && git push origin main vX.Y.Z`
4. 观察 `https://github.com/GivanGu/PortView/actions?query=workflow%3ADocker+Build` 直到 `success`
5. 更新本文档：把对应任务打 ✅，在「已完成」记 commit 号
6. 通知用户

## 已完成

- ✅ v1.1.1 (`550a1ea`, 2026-09-05)：psutil 7.x 兼容 + 卡片等高 + 在线/离线 + 备注字段
- ✅ v1.1.0 (`d4e60eb`, 2026-09-04)：P1-1 备注 / P1-2 偏好 / 暗色主题重做
