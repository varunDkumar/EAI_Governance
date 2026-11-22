#!/usr/bin/env bash
# Runs the Agent Trust Fabric backend + Tauri dev shell together.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export NVM_DIR="$HOME/.nvm"
[ -s "/usr/local/opt/nvm/nvm.sh" ] && \. "/usr/local/opt/nvm/nvm.sh"
nvm use 20 >/dev/null

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "Starting Python backend on :8756 ..."
(cd "$ROOT_DIR/backend" && .venv/bin/python -m uvicorn main:app --port 8756 --reload) &
BACKEND_PID=$!

sleep 1
echo "Starting Tauri dev shell ..."
cd "$ROOT_DIR/app"
npm run tauri dev
