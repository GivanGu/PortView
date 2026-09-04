#!/usr/bin/env bash
# PortView 离线容器端口展示验证脚本
#
# 用法:
#   ./verify.sh                      # 使用默认地址 http://127.0.0.1:7577
#   ./verify.sh http://192.168.1.5:7577   # 指定地址
#
# 功能:
#   1. 检查服务是否可达
#   2. 拉取 /api/ports 数据
#   3. 统计并列出离线(已停止)容器的端口，判断新功能是否生效
set -eu

BASE_URL="${1:-http://127.0.0.1:7577}"
PORT_JSON="$(mktemp)"
trap 'rm -f "$PORT_JSON"' EXIT

echo "==> 1. 服务可用性: $BASE_URL"
if ! curl -sf -o /dev/null "$BASE_URL/"; then
    echo "   无法访问，请确认服务已启动"
    exit 1
fi
echo "   OK"

echo "==> 2. 拉取端口数据 /api/ports"
if ! curl -sf "$BASE_URL/api/ports" -o "$PORT_JSON"; then
    echo "   获取失败"
    exit 1
fi
echo "   OK"

echo "==> 3. 统计"
if command -v python3 >/dev/null 2>&1; then
    python3 - "$PORT_JSON" <<'PY'
import sys, json

path = sys.argv[1]
try:
    payload = json.load(open(path, encoding='utf-8'))
except Exception as e:
    print(f"   解析JSON失败: {e}")
    sys.exit(1)

if not payload.get('success'):
    print(f"   API返回失败: {payload.get('error')}")
    sys.exit(1)

data = payload.get('data', {})
cards = [c for c in data.get('port_cards', []) if c.get('type') == 'used']
offline = [c for c in cards
           if c.get('source') == 'docker' and c.get('is_running') is False]

print(f"   已使用端口:   {data.get('total_used')}")
print(f"   Docker容器数: {data.get('docker_containers')}")
print(f"   离线容器端口: {len(offline)}")
for c in sorted(offline, key=lambda x: x.get('port', 0)):
    print(f"     - 端口 {c.get('port')}  容器 {c.get('container')}  状态 {c.get('container_status')}")

if offline:
    print("   ✔ 离线容器端口已正确展示（新版代码生效）")
else:
    print("   ⚠ 未发现离线容器端口，请逐项排查:")
    print("     1) 确定已重建镜像: docker compose -f docker-compose.local.yml up -d --build --force-recreate")
    print("     2) 确认停止的容器确实配置了端口映射")
    print("     3) 容器日志确认新代码: docker compose -f docker-compose.local.yml logs portview | grep '发现'")
print()
PY
else
    echo "   已使用端口/容器数见页面顶部统计"
    echo "   离线端口数: $(grep -o '"is_running": false' "$PORT_JSON" | wc -l)  (>0 即新版生效)"
fi

echo "==> 完成。浏览器请硬刷新(Ctrl+Shift+R)后再看「容器」标签。"