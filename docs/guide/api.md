# API 参考

完整的 API 文档也可在运行时访问 `/docs`（Swagger UI）。

## 端口

### GET `/api/ports`

获取端口数据（分页/搜索/筛选）。

**查询参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| `cursor` | string | 游标分页 |
| `limit` | number | 每页数量 (默认 50) |
| `protocol` | string | 过滤协议 (TCP/UDP) |
| `start_port` | number | 起始端口 |
| `end_port` | number | 结束端口 |
| `search` | string | 搜索关键词 |
| `range_id` | string | 自定义区间 ID |

**响应：**
```json
{
  "success": true,
  "data": {
    "port_cards": [...],
    "total_used": 100,
    "total_available": 65435,
    "tcp_used": 80,
    "udp_used": 20,
    "docker_containers": 5,
    "hidden_ports": [22],
    "next_cursor": "abc123",
    "has_more": true
  }
}
```

### POST `/api/refresh`

刷新 Docker + 主机端口数据。

### GET `/api/health`

健康检查，返回 `{"status": "ok", "version": "1.0.0"}`。

## 配置

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

## 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | 登录 `{"password": "xxx"}` |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 获取当前用户 |
| POST | `/api/auth/change-password` | 修改密码 |

## 通知

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/notifications` | 获取最近通知 |
| POST | `/api/notifications/read-all` | 全部标记已读 |
| POST | `/api/notifications/read/{id}` | 标记单条已读 |
| DELETE | `/api/notifications/clear-read` | 清除已读 |
