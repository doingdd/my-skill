#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <xiaohongshu_url> [output_dir]" >&2
  exit 2
fi

URL="$1"
OUT_DIR="${2:-/tmp/openclaw/xiaohongshu}"

mkdir -p "$OUT_DIR"

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "yt-dlp not found in PATH" >&2
  exit 127
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
TEMPLATE="$OUT_DIR/xiaohongshu-${STAMP}.%(ext)s"

TMP_LOG="$(mktemp)"
cleanup() {
  rm -f "$TMP_LOG"
}
trap cleanup EXIT

if ! yt-dlp \
  --no-playlist \
  --merge-output-format mp4 \
  --print after_move:filepath \
  -o "$TEMPLATE" \
  "$URL" >"$TMP_LOG" 2>&1; then
  cat "$TMP_LOG" >&2
  exit 1
fi

FINAL_PATH="$(tail -n 1 "$TMP_LOG" | tr -d '\r')"

if [[ -z "$FINAL_PATH" ]]; then
  echo "Download command finished but no output path was returned" >&2
  cat "$TMP_LOG" >&2
  exit 1
fi

if [[ ! -f "$FINAL_PATH" ]]; then
  echo "Downloaded path does not exist: $FINAL_PATH" >&2
  cat "$TMP_LOG" >&2
  exit 1
fi

SIZE="$(stat -f %z "$FINAL_PATH" 2>/dev/null || echo 0)"
if [[ "$SIZE" -le 0 ]]; then
  echo "Downloaded file is empty: $FINAL_PATH" >&2
  exit 1
fi

printf '%s\n' "$FINAL_PATH"
