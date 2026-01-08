#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
CONFIG="$REPO_DIR/config.yaml"
LOG_DIR="$REPO_DIR/logs"
LOCK_FILE="/tmp/scrapdept.lock"

mkdir -p "$LOG_DIR"

if [ ! -f "$CONFIG" ]; then
  echo "Config not found: $CONFIG" >&2
  exit 1
fi

# Ensure config has safe permissions
chmod 600 "$CONFIG" || true

# Create temporary config overriding persist=false
TMPCFG="$(mktemp)"
python3 - "$CONFIG" "$TMPCFG" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
cfg['persist'] = False
yaml.safe_dump(cfg, open(sys.argv[2], 'w'))
PY

# Acquire lock to avoid concurrent runs
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Another run in progress, exiting."; exit 1; }

# Run the main script using venv python with PYTHONPATH set
PYTHONPATH=. "$REPO_DIR/venv/bin/python" "$REPO_DIR/main.py" "$TMPCFG" >> "$LOG_DIR/daily.log" 2>&1 || rc=$?

# Cleanup
rm -f "$TMPCFG"

exit ${rc:-0}
