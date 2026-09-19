#!/usr/bin/env bash
# 控制台镜像入口：与本机 systemd 同口径（Pi + Yak MCP/MITM + 前端 :2334）。
# 不是 TSecBench 托管模式，不会自行拉题开打。
set -euo pipefail

export ATKBRAIN_HOSTED="${ATKBRAIN_HOSTED:-0}"
export ATKBRAIN_LLM_GATEWAY="${ATKBRAIN_LLM_GATEWAY:-0}"
export ATKBRAIN_HOST="${ATKBRAIN_HOST:-0.0.0.0}"
export ATKBRAIN_PORT="${ATKBRAIN_PORT:-2333}"
export ATKBRAIN_ADMIN_USER="${ATKBRAIN_ADMIN_USER:-admin}"
export ATKBRAIN_ADMIN_PASSWORD="${ATKBRAIN_ADMIN_PASSWORD:-admin}"
export ATKBRAIN_CORS_ORIGINS="${ATKBRAIN_CORS_ORIGINS:-http://127.0.0.1:2334,http://localhost:2334,http://127.0.0.1:2333,http://localhost:2333}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export HOME="${HOME:-/root}"
export PATH="/opt/atkbrain/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH}"
export PI_TELEMETRY="${PI_TELEMETRY:-0}"
export PI_SKIP_VERSION_CHECK="${PI_SKIP_VERSION_CHECK:-1}"
export PI_OFFLINE="${PI_OFFLINE:-1}"
export ATKBRAIN_PI_BIN="${ATKBRAIN_PI_BIN:-pi}"
export ATKBRAIN_PI_PROVIDER="${ATKBRAIN_PI_PROVIDER:-deepseek}"
export ATKBRAIN_PI_MODEL="${ATKBRAIN_PI_MODEL:-deepseek-flash}"

cd /opt/atkbrain/backend
mkdir -p data/workspaces data/loot data/reports data/logs

if [[ -z "${DEEPSEEK_API_KEY:-}" && -n "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
  export DEEPSEEK_API_KEY="${ANTHROPIC_AUTH_TOKEN}"
fi
if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" && -n "${DEEPSEEK_API_KEY:-}" ]]; then
  export ANTHROPIC_AUTH_TOKEN="${DEEPSEEK_API_KEY}"
fi

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "[entrypoint] 警告: 未设置 DEEPSEEK_API_KEY（或 ANTHROPIC_AUTH_TOKEN）。控制台能开，猎面 Pi 不会就绪。" >&2
fi

if ! command -v yak >/dev/null 2>&1 && [[ ! -x /usr/local/bin/yak ]]; then
  echo "[entrypoint] 警告: 镜像里没有 yak，顶栏会一直「Yakit 未就绪」。请用 Dockerfile.console 构建。" >&2
fi

/opt/atkbrain/venv/bin/python - <<'PY'
from atkbrain.agents.pi_runtime import ensure_pi_agent_dir
p = ensure_pi_agent_dir(hosted=False)
print(f"[entrypoint] Pi 配置已写入 {p}")
PY

# 与本机一致：浏览器开 :2334。API 仍在 :2333，静态前端由 FastAPI 托管。
if command -v socat >/dev/null 2>&1; then
  if socat TCP-LISTEN:2334,fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:2333 >/opt/atkbrain/backend/data/logs/console-2334.log 2>&1 & then
echo "[entrypoint] 控制台走 :2334 → :2333。浏览器地址用容器内 python -m atkbrain.panel 打印的入口 URL。"
  else
    echo "[entrypoint] 2334 未能监听（可能被本机 Vite/旧进程占用），请用 http://127.0.0.1:2333/" >&2
  fi
else
  echo "[entrypoint] 未安装 socat，请用 http://127.0.0.1:2333/" >&2
fi

echo "[entrypoint] StrikeAgent_AtkBrain-Flash 控制台启动"
exec /opt/atkbrain/venv/bin/python -m atkbrain.main
