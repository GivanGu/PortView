# 配置

PortView 的所有配置通过 JSON 文件或前端 UI 管理，存储在 `config/` 目录下。

## 服务映射

`config/config.json` — 将端口映射到服务名称：

```json
{
  "ssh": {"port": 22, "protocol": "TCP", "service_type": "host"},
  "mysql": {"port": 3306, "protocol": "TCP", "service_type": "host"},
  "portview": {"port": 7577, "protocol": "TCP", "service_type": "docker"}
}
```

通过前端 **设置 → 服务映射** 页面编辑，无需手动编写 JSON。

## 隐藏端口

`config/hidden_ports.json` — 隐藏不关心的端口：

```json
[22, 53]
```

点击端口卡片的 🚫 按钮即可快速隐藏。

## 自定义监听区间

在 **设置 → 自定义区间** 页面添加，如：

```json
[
  {
    "id": "a1b2c3d4",
    "name": "游戏服务器",
    "start_port": 22500,
    "end_port": 22600,
    "color": "#00b4d8",
    "created_at": "2025-01-01T00:00:00.000Z"
  }
]
```

添加后在侧边栏快速访问，点击即可切换到该区间视图。

## 用户管理

用户信息存储在 SQLite (`config/users.db`)：

- **默认用户**：`admin`，密码 `portview123`（可通过环境变量 `PORTVIEW_DEFAULT_PASSWORD` 修改）
- **修改密码**：登录后在 **设置 → 修改密码** 页面完成
- **JWT Token**：有效期 7 天，存储在浏览器 `localStorage`

## 文件结构

```
config/
├── config.json         # 服务映射
├── hidden_ports.json   # 隐藏端口列表
├── ranges.json         # 自定义监控区间
├── users.db            # SQLite 用户数据库 (bcrypt 哈希)
└── portview.log        # 结构化日志
```
