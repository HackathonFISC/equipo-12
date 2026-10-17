#!/usr/bin/env bash
# Push this working tree to k3s-cp-de-01 and rebuild the Compose app.
# Does not overwrite the remote .env (never synced in the first place).
set -euo pipefail

HOST="${EQUIPO12_DEMO_HOST:-k3s-cp-de-01}"
REMOTE_DIR="${EQUIPO12_DEMO_DIR:-equipo-12}"
DEMO_URL="${EQUIPO12_DEMO_URL:-http://equipo12.belta.dev}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

RSYNC=(
  rsync -az --delete
  --exclude '.git/'
  --exclude '.env'
  --exclude '.venv/'
  --exclude 'data/*.db'
  --exclude '.cursor/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude 'node_modules/'
)

if [[ "$DRY" -eq 1 ]]; then
  echo "==> dry-run rsync -> ${HOST}:${REMOTE_DIR}/"
  "${RSYNC[@]}" -n --info=stats1 "$ROOT/" "${HOST}:${REMOTE_DIR}/"
  exit 0
fi

echo "==> rsync -> ${HOST}:${REMOTE_DIR}/"
"${RSYNC[@]}" "$ROOT/" "${HOST}:${REMOTE_DIR}/"

echo "==> build + up on ${HOST}"
ssh -o BatchMode=yes "$HOST" "set -euo pipefail
cd ~/${REMOTE_DIR}
args=()
if [[ -f .env ]] && grep -q '^WHATSAPP_TOKEN=.' .env && grep -q '^WHATSAPP_VERIFY_TOKEN=.' .env && grep -Eq '^(PHONE_NUMBER_ID|WHATSAPP_PHONE_NUMBER_ID)=.' .env; then
  args+=(--profile whatsapp)
  echo '==> perfil whatsapp activo'
else
  echo '==> perfil whatsapp apagado: en el .env del nodo faltan WHATSAPP_TOKEN, WHATSAPP_VERIFY_TOKEN y PHONE_NUMBER_ID'
fi
sudo docker compose \"\${args[@]}\" up -d --build
python3 - << 'PY'
from pathlib import Path
path = Path.home() / 'gong-cha' / 'Caddyfile'
text = path.read_text()
needle = 'reverse_proxy 127.0.0.1:18082'
if needle not in text:
    old = 'equipo12.belta.dev {\n\treverse_proxy 127.0.0.1:18081\n}'
    new = (
        'equipo12.belta.dev {\n'
        '\thandle /webhook* {\n'
        '\t\treverse_proxy 127.0.0.1:18082\n'
        '\t}\n'
        '\thandle {\n'
        '\t\treverse_proxy 127.0.0.1:18081\n'
        '\t}\n'
        '}'
    )
    if old not in text:
        raise SystemExit('caddy: el bloque equipo12.belta.dev no coincide')
    path.write_text(text.replace(old, new, 1))
    print('caddy: /webhook -> 127.0.0.1:18082')
else:
    print('caddy: /webhook ya apunta a 18082')
PY
sudo docker exec gongcha-caddy-1 caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
"

echo "==> health ${DEMO_URL}/api/health"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS "${DEMO_URL}/api/health" >/dev/null; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" -ne 1 ]]; then
  echo "health check failed" >&2
  exit 1
fi
echo "ok  ${DEMO_URL}"
