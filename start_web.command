#!/bin/bash
# 双击启动「网页版」：判定后端（FastAPI）+ 前端（Vite）。
#
# 后端必须是能跑 mediapipe 的那个 Python：
#   优先用本目录 .venv/，没有就退回上一级目录的 .venv/（Windows 版 venv 在这台 Mac 上用不了）。
cd "$(dirname "$0")" || exit 1

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x "../.venv/bin/python" ]; then
  PY="../.venv/bin/python"
else
  echo "找不到可用的虚拟环境：先跑 ./setup_env.sh"
  exit 1
fi

echo "判定后端：$PY"
"$PY" -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000 &
BACKEND=$!
# 关窗口 / Ctrl+C 时把后端一起收掉，避免 8000 端口被占住
trap 'kill $BACKEND 2>/dev/null' EXIT INT TERM

# 等后端把模型加载完再开前端，免得第一次点「开始训练」还要等
for _ in $(seq 1 60); do
  if curl -s --max-time 1 http://127.0.0.1:8000/api/health | grep -q '"model_loaded":true'; then
    echo "判定后端就绪 ✓"
    break
  fi
  sleep 1
done

echo "前端：http://localhost:5173"
cd web/frontend || exit 1
npm run dev
