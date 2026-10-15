#!/usr/bin/env bash
set -euo pipefail
studio_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$studio_root"
studio_port="${SMARTROUTE_PORT:-8765}"
if [[ ! "$studio_port" =~ ^[0-9]+$ ]] || (( ${#studio_port} > 5 )); then
  echo "SMARTROUTE_PORT must be a number from 1 to 65535." >&2
  exit 1
fi
studio_port=$((10#$studio_port))
if (( studio_port < 1 || studio_port > 65535 )); then
  echo "SMARTROUTE_PORT must be a number from 1 to 65535." >&2
  exit 1
fi
for studio_tool in node npm lsof; do
  if ! command -v "$studio_tool" >/dev/null 2>&1; then
    echo "Missing $studio_tool. Install Node.js 24 and the system lsof utility first." >&2
    exit 1
  fi
done
if [[ ! -x .venv/bin/python ]]; then
  echo "Set up the Python environment using README.md before starting the studio." >&2
  exit 1
fi
if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm ci --cache ../.cache/npm --no-audit --no-fund)
fi
echo "Preparing SmartRoute…"
.venv/bin/python -c 'from smartroute.intelligence.model_io import load_model; load_model("models/selected")'
.venv/bin/python scripts/generate-results.py
(cd frontend && npm run build)

# Build successfully before stopping the current listener. Only this TCP port is cleared.
studio_listeners() { lsof -nP -t -iTCP:"$studio_port" -sTCP:LISTEN 2>/dev/null | sort -u || true; }
studio_pids="$(studio_listeners)"
if [[ -n "$studio_pids" ]]; then
  echo "Stopping listener(s) on port $studio_port: $studio_pids"
  while IFS= read -r studio_pid; do kill -TERM "$studio_pid" 2>/dev/null || true; done <<< "$studio_pids"
  for ((studio_try=0; studio_try<30; studio_try++)); do
    [[ -z "$(studio_listeners)" ]] && break
    sleep 0.1
  done
  studio_remaining="$(studio_listeners)"
  if [[ -n "$studio_remaining" ]]; then
    while IFS= read -r studio_pid; do
      # Escalate only original listeners still holding the port.
      if [[ $'\n'"$studio_pids"$'\n' == *$'\n'"$studio_pid"$'\n'* ]]; then
        kill -KILL "$studio_pid" 2>/dev/null || true
      fi
    done <<< "$studio_remaining"
    sleep 0.2
  fi
fi
if [[ -n "$(studio_listeners)" ]]; then
  echo "Port $studio_port could not be cleared. Check ownership or set SMARTROUTE_PORT." >&2
  exit 1
fi
echo "Studio:  http://127.0.0.1:$studio_port/"
echo "Results: http://127.0.0.1:$studio_port/#results"
echo "Keep this window open. Press Ctrl+C to stop."
exec .venv/bin/python -m smartroute.web.server --port "$studio_port"
