#!/usr/bin/env bash
# ===== 知南·Echo 服务器一键部署脚本 =====
# 用法：在项目目录（含 backend/ frontend/ deploy/）执行  bash deploy_remote.sh
# 要求：Linux x86_64 / arm64，Python 3.10+，可访问外网
set -e
cd "$(dirname "$0")"

echo "🌸 [1/6] 安装系统依赖（nginx）"
if command -v apt-get >/dev/null; then
  apt-get update -qq && apt-get install -y -qq nginx >/dev/null
elif command -v yum >/dev/null; then
  yum install -y -q nginx >/dev/null
fi

echo "🐍 [2/6] 检查 Python"
python3 --version || { echo "请先安装 Python 3.10+"; exit 1; }

echo "📦 [3/6] 创建虚拟环境并安装依赖"
python3 -m venv /opt/echo/venv 2>/dev/null || { mkdir -p /opt/echo && python3 -m venv /opt/echo/venv; }
/opt/echo/venv/bin/pip install -q --upgrade pip
/opt/echo/venv/bin/pip install -q -r backend/requirements.txt

echo "📂 [4/6] 部署代码到 /opt/echo"
mkdir -p /opt/echo
rm -rf /opt/echo/app
cp -r backend/app backend/run.py backend/requirements.txt /opt/echo/
[ -f backend/.env ] && cp backend/.env /opt/echo/.env

echo "🏗 [5/6] 构建前端（服务器无 node 时跳过，使用预构建产物）"
if command -v npm >/dev/null; then
  cd frontend && npm install --silent && npm run build && cd ..
fi
if [ -d frontend/dist ]; then
  rm -rf /opt/echo/frontend && mkdir -p /opt/echo/frontend
  cp -r frontend/dist /opt/echo/frontend/dist
fi

echo "⚙️ [6/6] 配置 systemd 与 nginx"
cp deploy/nginx-standalone.conf /etc/nginx/conf.d/echo.conf 2>/dev/null || true
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t 2>/dev/null && systemctl reload nginx || systemctl restart nginx

cat > /etc/systemd/system/echo.service <<'UNIT'
[Unit]
Description=Zhinan Echo - Learning DDL Agent
After=network.target

[Service]
WorkingDirectory=/opt/echo
ExecStart=/opt/echo/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now echo
sleep 3
systemctl --no-pager status echo | head -5
echo
echo "✅ 部署完成！访问 http://$(curl -s -m 3 ifconfig.me 2>/dev/null || echo '服务器IP')/"
echo "   测试账号：demo1 / echo123456"
