#!/usr/bin/env bash
# ==============================================================================
# Smart Safe Guardian - Raspberry Pi Zero 2W Auto-Update & Gateway Daemon Runner
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "=== [SMART SAFE RPI BOOT] Starting Auto-Update & Launch ==="

# 1. Wait for network connectivity (up to 30s)
echo "[INFO] Waiting for network..."
for i in $(seq 1 30); do
    if ping -c 1 -W 1 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1; then
        echo "[INFO] Network connection verified."
        break
    fi
    sleep 1
done

# 2. Pull latest changes from origin/main
echo "[INFO] Pulling latest code from origin/main..."
git fetch origin main || true
git reset --hard origin/main || git pull origin main || true

# 3. Setup Python venv on Raspberry Pi if not present
if [ ! -d "gateway/.venv" ]; then
    echo "[INFO] Initializing gateway/.venv on Raspberry Pi..."
    python3 -m venv gateway/.venv
    gateway/.venv/bin/pip install --upgrade pip
    gateway/.venv/bin/pip install -r gateway/requirements.txt
fi

# 4. Resolve ThingsBoard server target
# Default to host PC on LAN or local Docker, overridable by .env or env var
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

TB_HOST="${THINGSBOARD_HOST:-10.128.36.158}"
TB_PORT="${THINGSBOARD_PORT:-1883}"
TB_TOKEN="${THINGSBOARD_TOKEN:-6EzRR6gcTvnOcgVF53hP}"
SERIAL_PORT="${SERIAL_PORT:-auto}"

echo "[INFO] Starting Gateway daemon -> ThingsBoard at ${TB_HOST}:${TB_PORT} (Device Token: ${TB_TOKEN})..."
exec gateway/.venv/bin/python gateway/gateway.py \
    --host "$TB_HOST" \
    --port "$TB_PORT" \
    --token "$TB_TOKEN" \
    --serial-port "$SERIAL_PORT"
