#!/usr/bin/env bash
set -euo pipefail
studio_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$studio_root"
if [[ ! -x .venv/bin/python ]]; then
  echo "Set up the Python environment using README.md before starting the studio." >&2
  exit 1
fi
if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm ci --cache ../.cache/npm --no-audit --no-fund)
fi
(cd frontend && npm run build)
exec .venv/bin/python -m smartroute.web.server --port "${SMARTROUTE_PORT:-8765}"
