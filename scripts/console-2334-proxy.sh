#!/usr/bin/env bash
# 把 :2334 反代到后端 :2333，使安全入口在控制台端口生效（与 Docker socat 同口径）。
set -euo pipefail
BACKEND="${ATKBRAIN_PORT:-2333}"
FRONT="${ATKBRAIN_FRONTEND_PORT:-2334}"
if command -v socat >/dev/null 2>&1; then
  exec socat "TCP-LISTEN:${FRONT},fork,reuseaddr,bind=0.0.0.0" "TCP:127.0.0.1:${BACKEND}"
fi
exec /usr/bin/python3 - <<'PY'
import os, socket, threading
backend = int(os.environ.get("ATKBRAIN_PORT", "2333") or 2333)
front = int(os.environ.get("ATKBRAIN_FRONTEND_PORT", "2334") or 2334)

def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except Exception:
        pass
    try:
        a.close()
    except Exception:
        pass
    try:
        b.close()
    except Exception:
        pass

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", front))
srv.listen(128)
while True:
    c, _ = srv.accept()
    u = socket.create_connection(("127.0.0.1", backend))
    threading.Thread(target=pipe, args=(c, u), daemon=True).start()
    threading.Thread(target=pipe, args=(u, c), daemon=True).start()
PY
