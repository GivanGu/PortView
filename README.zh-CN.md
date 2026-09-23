# PortView

> 端口监控与可视化工具 — 把 Docker 容器与主机的端口，变成一眼看懂的卡片。

[English](README.md) | [简体中文](README.zh-CN.md)

PortView 运行在 NAS / 服务器上，实时读取 **Docker 容器端口映射** 与 **本机监听端口**，
以卡片形式可视化展示。支持多段区间筛选、快速搜索、端口隐藏、Logo 管理、收藏分组，
以及可选的密码登录保护。

![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 功能特性

**端口监控**
- **Docker 端口** — 实时读取所有容器（含已停止）的端口映射
- **主机端口** — 检测本机监听端口
- **离线容器** — 已停止容器的端口映射依然展示，在线 / 离线一目了然
- **概览统计** — 端口占用率、协议 / 来源 / 在线离线分布图表

**组织与筛选**
- **多段区间监控** — 自定义任意端口区间（如 80s / 8000s），只看你关心的范围
- **快速筛选** — 一键过滤「未知服务」「无 Logo」卡片
- **快速搜索** — `⌘K` 全局搜索端口、服务名、容器名
- **隐藏端口** — 一键隐藏不关心的端口，独立页面管理
- **收藏分组** — 收藏端口或自定义网址，文件夹归类，拖拽整理

**卡片能力**
- **Logo 管理** — 自动识别 / 手动上传，支持「铺满背景」与「Logo 框」两种展示模式
- **服务协议** — HTTP / HTTPS 识别与手动指定，一键「打开服务」跳转
- **服务命名** — 为未知服务命名；同一镜像的多个端口自动归组
- **导出** — 端口数据导出 CSV / JSON

**体验**
- **主题** — 深色 / 浅色 + 6 种强调色
- **背景图** — 自定义毛玻璃背景（仅收藏页 / 全应用）
- **登录保护** — 可选单用户密码（argon2id），适合公网暴露
- **多语言** — 简体中文 / English

## 界面展示

### 概览
![概览](docs/screenshots/overview.png)

### 端口监控
![端口监控](docs/screenshots/ports.png)

### 收藏
![收藏](docs/screenshots/favorites.png)

### 设置
![设置](docs/screenshots/settings.png)

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/GivanGu/PortView.git portview
cd portview
docker compose up -d
```

默认监听 `8081` 端口，访问 `http://<host>:8081`。

### 方式二：独立 compose 文件（无需克隆仓库）

在任意目录（如 `~/portview/`）新建 `docker-compose.yml`，填入以下内容，再 `docker compose up -d`：

```yaml
services:
  portview:
    # 默认用阿里 ACR（国内拉取快）；如需改用 GHCR，注释上一行并取消下一行注释
    image: crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:latest
    # image: ghcr.io/givangu/portview:latest
    container_name: portview
    network_mode: host
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./config:/app/config
    environment:
      - PORTVIEW_PORT=8081
    restart: unless-stopped
```

```bash
docker compose up -d          # 启动
docker compose logs -f        # 查看日志
```

> `./config` 首次启动自动创建，存放唯一的 SQLite 数据库。`8081` 被占用时改 `PORTVIEW_PORT`。

### 方式三：拉取镜像

```bash
# GHCR
docker pull ghcr.io/givangu/portview:latest

# 或 ACR（国内）
docker pull crpi-bywv2frq7uqt57e1.cn-hangzhou.personal.cr.aliyuncs.com/selfwarehouse/portview:latest

docker run -d --name portview \
  --network host \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v ./config:/app/config \
  -e PORTVIEW_PORT=8081 \
  ghcr.io/givangu/portview:latest
```

> 绑定挂载 `config/` 目录可持久化所有数据（密码、监控区间、端口标注、隐藏端口、登录态），全部存于单个 `config/portview.db`。

### 本地开发

贡献与本地开发流程见 [AGENTS.md](AGENTS.md)。

## 许可证

MIT
