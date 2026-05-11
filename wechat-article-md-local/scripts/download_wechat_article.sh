#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <url> [output_dir]" >&2
  exit 1
fi

URL="$1"
OUTPUT_DIR="${2:-$HOME/Downloads}"
TMP_JSON="$(mktemp /tmp/wechat_article.XXXXXX).json"

# Try to find the Python script relative to skill dir first, then as plain command
if [ -f "${SKILL_DIR}/scripts/save_wechat_article.py" ]; then
  PYTHON_SCRIPT="${SKILL_DIR}/scripts/save_wechat_article.py"
else
  PYTHON_SCRIPT="save_wechat_article.py"
fi

if [ -f "${SKILL_DIR}/scripts/extract_wechat_article.mjs" ]; then
  NODE_SCRIPT="${SKILL_DIR}/scripts/extract_wechat_article.mjs"
else
  echo "extract_wechat_article.mjs not found in ${SKILL_DIR}/scripts/" >&2
  exit 1
fi

node "$NODE_SCRIPT" "$URL" > "$TMP_JSON"
python "$PYTHON_SCRIPT" --input "$TMP_JSON" --output-dir "$OUTPUT_DIR"
