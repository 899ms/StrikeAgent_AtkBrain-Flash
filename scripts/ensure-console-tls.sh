#!/usr/bin/env bash
# 控制台 TLS 证书：自签，写到 backend/data/tls/（gitignore）。已有则跳过。
set -euo pipefail

DIR="${1:-}"
if [[ -z "$DIR" ]]; then
  REPO="$(cd "$(dirname "$0")/.." && pwd)"
  DIR="$REPO/backend/data/tls"
fi
mkdir -p "$DIR"
chmod 700 "$DIR"
if [[ -s "$DIR/cert.pem" && -s "$DIR/key.pem" ]]; then
  exit 0
fi
command -v openssl >/dev/null || { echo "[tls] 需要 openssl" >&2; exit 1; }

SAN="IP:127.0.0.1,DNS:localhost"
if command -v hostname >/dev/null; then
  hn="$(hostname 2>/dev/null || true)"
  [[ -n "$hn" ]] && SAN="${SAN},DNS:${hn}"
fi
if command -v hostname >/dev/null; then
  for ip in $(hostname -I 2>/dev/null || true); do
    case "$ip" in
      *:*) continue ;;
      "") continue ;;
      *) SAN="${SAN},IP:${ip}" ;;
    esac
  done
fi

CNF="$(mktemp)"
trap 'rm -f "$CNF"' EXIT
cat > "$CNF" <<EOF
[req]
distinguished_name = dn
x509_extensions = ext
prompt = no
[dn]
CN = StrikeAgent-AtkBrain-Flash
[ext]
subjectAltName = ${SAN}
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF

openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 825 \
  -keyout "$DIR/key.pem" -out "$DIR/cert.pem" -config "$CNF" >/dev/null 2>&1
cat "$DIR/cert.pem" "$DIR/key.pem" > "$DIR/combined.pem"
chmod 600 "$DIR/key.pem" "$DIR/combined.pem"
chmod 644 "$DIR/cert.pem"
echo "[tls] 已写入自签证书 ${DIR}/cert.pem（SAN ${SAN}）"
