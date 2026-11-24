#!/usr/bin/env bash
# ==============================================================================
# Smart Safe Guardian - Raspberry Pi Zero 2W Auto-Update & Gateway Daemon Runner
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "=== [SMART SAFE RPI BOOT] Starting Auto-Update & Launch ==="

# 1. Non-blocking network check (max 2 seconds)
echo "[INFO] Checking network connectivity..."
if ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1 || ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
    echo "[INFO] Network online. Fetching latest origin/main..."
    git config --global --add safe.directory "$REPO_DIR" >/dev/null 2>&1 || true
    git fetch origin main >/dev/null 2>&1 && git reset --hard origin/main >/dev/null 2>&1 || true
else
    echo "[WARN] Network offline at boot. Starting gateway immediately using local code."
    echo "[INFO] Periodic timer (smart-safe-autoupdate.timer) will auto-pull whenever Wi-Fi connects."
fi

# 3. Setup Python venv on Raspberry Pi if not present
if [ ! -d "gateway/.venv" ]; then
    echo "[INFO] Initializing gateway/.venv on Raspberry Pi..."
    python3 -m venv gateway/.venv
    gateway/.venv/bin/pip install --upgrade pip
    gateway/.venv/bin/pip install -r gateway/requirements.txt
fi

# 4. Resolve ThingsBoard server target
# Defaults to "auto" (LAN UDP Beacon auto-discovery), with fallback to last known LAN IP.
# Can be overridden manually in .env via THINGSBOARD_HOST=1.2.3.4
if [ -f "$REPO_DIR/.env" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line="$(echo "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        [[ -z "$line" || "$line" =~ ^# ]] && continue
        if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            val="${BASH_REMATCH[2]}"
            val="${val%\"}"
            val="${val#\"}"
            val="${val%\'}"
            val="${val#\'}"
            export "$key"="$val"
        fi
    done < "$REPO_DIR/.env"
fi

TB_HOST="${THINGSBOARD_HOST:-auto}"
TB_FALLBACK="${THINGSBOARD_FALLBACK_HOST:-10.128.36.158}"
TB_PORT="${THINGSBOARD_PORT:-1883}"
TB_TOKEN="${THINGSBOARD_TOKEN:-6EzRR6gcTvnOcgVF53hP}"
SERIAL_PORT="${SERIAL_PORT:-auto}"

echo "[INFO] Launching Gateway daemon (Host: ${TB_HOST}, Fallback: ${TB_FALLBACK}, Port: ${TB_PORT})..."
exec gateway/.venv/bin/python gateway/gateway.py \
    --host "$TB_HOST" \
    --fallback-host "$TB_FALLBACK" \
    --port "$TB_PORT" \
    --token "$TB_TOKEN" \
    --serial-port "$SERIAL_PORT" \
    "$@"
