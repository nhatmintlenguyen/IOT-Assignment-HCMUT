#!/usr/bin/env bash
# ==============================================================================
# Smart Safe Guardian - Periodic Auto-Update Worker (Raspberry Pi Zero 2W)
# Checks origin/main every 5 minutes. If new commits exist, pulls & restarts gateway.
# ==============================================================================
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# 1. Quick connectivity test (non-blocking, 1s timeout)
if ! ping -c 1 -W 1 1.1.1.1 >/dev/null 2>&1 && ! ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1; then
    # No Internet right now, exit quietly without burning CPU
    exit 0
fi

# 2. Fetch remote state quietly
git config --global --add safe.directory "$REPO_DIR" >/dev/null 2>&1 || true
if ! git fetch origin main >/dev/null 2>&1; then
    exit 0
fi

LOCAL_HASH=$(git rev-parse HEAD)
REMOTE_HASH=$(git rev-parse origin/main)

# 3. Compare commits
if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
    echo "[AUTO-UPDATE] Update available! Local: ${LOCAL_HASH:0:7} -> Remote: ${REMOTE_HASH:0:7}"
    git reset --hard origin/main

    # Update dependencies if virtual environment exists
    if [ -d "gateway/.venv" ]; then
        gateway/.venv/bin/pip install -r gateway/requirements.txt >/dev/null 2>&1 || true
    fi

    # Restart gateway service to load the new code
    echo "[AUTO-UPDATE] Restarting smart-safe-gateway.service..."
    systemctl restart smart-safe-gateway.service || true
fi
