# 快速开始

## 安装

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/GivanGu/PortView.git
cd PortView

# 可选：自定义配置
cp .env.example .env.local
# 编辑 .env.local，设置 PORTVIEW_JWT_SECRET 等

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
# 后端（需要 Python 3.12+）
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 7577

# 前端（需要 Node 20+）
cd frontend
npm install
npm run dev   # http://localhost:5173，代理到 :7577
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PORTVIEW_PORT` | `7577` | Web 服务监听端口 |
| `PORTVIEW_CONFIG_DIR` | `/app/config` | 配置目录（卷挂载） |
| `PORTVIEW_JWT_SECRET` | `portview-jwt-secret-change-me` | JWT 密钥 |
| `PORTVIEW_DEFAULT_PASSWORD` | `portview123` | 首次运行默认密码 |
| `PORTVIEW_LOG_LEVEL` | `INFO` | 日志等级 |
| `PORTVIEW_LOG_FORMAT` | `json` | 日志格式 (json/human) |

## 验证安装

```bash
curl http://localhost:7577/api/health
# 预期输出: {"status":"ok","version":"1.0.0"}
```
