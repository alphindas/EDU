#!/usr/bin/env bash
# EduNest 2.0 one-command dev start (Linux / macOS / WSL).  ./run.sh [--reset]
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(pwd)

command -v python3 >/dev/null || { echo "Python 3.11+ is required"; exit 1; }
command -v npm >/dev/null || { echo "Node.js 18+ (npm) is required"; exit 1; }

cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "▶ Creating Python virtualenv…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
if [ ! -f edunest.db ] || [ "${1:-}" = "--reset" ]; then
  echo "▶ Seeding demo school…"
  .venv/bin/python -m app.seed --reset
fi

cd "$ROOT/frontend"
[ -d node_modules ] || { echo "▶ Installing web app packages…"; npm install --no-audit --no-fund; }

cd "$ROOT/backend"
.venv/bin/uvicorn app.main:app --reload --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT
cd "$ROOT/frontend"
echo ""
echo "  EduNest 2.0  →  http://localhost:5173     (API docs: http://localhost:8000/docs)"
echo "  Logins: student EN-26-001 / 15082010 · teacher T-001 / teacher123 · parent 9000000001 / OTP 000000 · admin admin / admin123"
echo ""
npm run dev
