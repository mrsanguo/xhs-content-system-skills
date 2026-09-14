#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${XHS_PYTHON_BIN:-$(command -v python3)}"

if ! "$PYTHON_BIN" -c 'from PIL import Image' >/dev/null 2>&1; then
  echo "当前 Python 缺少 Pillow；请通过 XHS_PYTHON_BIN 指向已安装 Pillow 的 Python" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/render_cover.py" "$@"
