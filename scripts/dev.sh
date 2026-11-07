#!/usr/bin/env bash
# LexTec Bridge - local development launcher (macOS / Linux / Git Bash)
#   ./scripts/dev.sh          set up if needed, then start API + web
#   ./scripts/dev.sh --seed   additionally create synthetic demo cases (mock AI)
#   API_PORT=8001 WEB_PORT=5174 ./scripts/dev.sh   if the default ports are taken
set -euo pipefail

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="$ROOT/apps/api"
WEB="$ROOT/apps/web"
if [ -x "$API/.venv/Scripts/python.exe" ]; then PY="$API/.venv/Scripts/python.exe"; else PY="$API/.venv/bin/python"; fi

step() { printf '\033[32m==> %s\033[0m\n' "$1"; }

[ -f "$ROOT/.env" ] || { cp "$ROOT/.env.example" "$ROOT/.env"; step "Created .env from .env.example (AI_PROVIDER=mock)"; }

if [ ! -x "$PY" ]; then
  step "Creating Python virtual environment (apps/api/.venv)"
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 "$API/.venv"
    if [ -x "$API/.venv/Scripts/python.exe" ]; then PY="$API/.venv/Scripts/python.exe"; else PY="$API/.venv/bin/python"; fi
    uv pip install --python "$PY" -e "$API[dev]"
  else
    python3 -m venv "$API/.venv"
    if [ -x "$API/.venv/Scripts/python.exe" ]; then PY="$API/.venv/Scripts/python.exe"; else PY="$API/.venv/bin/python"; fi
    "$PY" -m pip install --quiet -e "$API[dev]"
  fi
fi

[ -d "$WEB/node_modules" ] || { step "Installing frontend dependencies"; (cd "$WEB" && npm install); }

step "Applying database migrations"
(cd "$API" && "$PY" -W ignore -m app.cli migrate)
if [ "${1:-}" = "--seed" ]; then step "Seeding synthetic demo cases"; (cd "$API" && "$PY" -W ignore -m app.cli seed-demo); fi

step "Starting API on http://localhost:$API_PORT and web on http://localhost:$WEB_PORT (Ctrl+C to stop)"
(cd "$API" && "$PY" -W ignore -m uvicorn app.main:app --reload --port "$API_PORT") &
API_PID=$!
(cd "$WEB" && VITE_API_PROXY="http://localhost:$API_PORT" VITE_PORT="$WEB_PORT" npm run dev) &
WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null || true' EXIT INT TERM
wait
