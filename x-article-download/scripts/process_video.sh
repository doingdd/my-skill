#!/bin/bash
# X Article/Video Downloader - Video Processing Script
# Usage: process_video.sh <x_url> <output_dir> [whisper_model]
#
# Steps:
#   1. Download video with yt-dlp
#   2. Extract audio for whisper
#   3. Run whisper transcription (auto-detect language)
#   4. If English detected, generate Chinese translation
#   5. Output transcript as Markdown

set -euo pipefail

URL="${1:?Usage: process_video.sh <x_url> <output_dir> [whisper_model]}"
OUTPUT_DIR="${2:?Output directory required}"
WHISPER_MODEL="${3:-medium}"

VIDEOS_DIR="${OUTPUT_DIR}/videos"
TRANSCRIPTS_DIR="${OUTPUT_DIR}/transcripts"

mkdir -p "$VIDEOS_DIR" "$TRANSCRIPTS_DIR"

VIDEO_FILE="${VIDEOS_DIR}/video.mp4"
AUDIO_FILE="${VIDEOS_DIR}/audio.wav"

echo "=== Step 1: Downloading video ==="
if [ -f "$VIDEO_FILE" ]; then
    echo "Video already exists, skipping download: $VIDEO_FILE"
else
    yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]" \
        -o "$VIDEO_FILE" \
        --continue \
        "$URL"
    echo "Video downloaded: $VIDEO_FILE"
fi

echo "=== Step 2: Extracting audio ==="
if [ -f "$AUDIO_FILE" ]; then
    echo "Audio already exists, skipping extraction: $AUDIO_FILE"
else
    ffmpeg -i "$VIDEO_FILE" -vn -acodec pcm_s16le -ar 16000 -ac 1 "$AUDIO_FILE" -y 2>/dev/null
    echo "Audio extracted: $AUDIO_FILE"
fi

echo "=== Step 3: Whisper transcription (model: ${WHISPER_MODEL}) ==="
whisper "$AUDIO_FILE" \
    --model "$WHISPER_MODEL" \
    --output_format txt \
    --output_dir "$TRANSCRIPTS_DIR" \
    --verbose False

# Get detected language from whisper output
DETECTED_LANG=$(whisper "$AUDIO_FILE" --model "$WHISPER_MODEL" --output_format txt --output_dir /tmp/whisper_lang_detect 2>&1 | grep -oP 'Detected language: \K\w+' || echo "unknown")
echo "Detected language: $DETECTED_LANG"

echo "=== Step 4: Generating transcript Markdown ==="
TRANSCRIPT_TXT="${TRANSCRIPTS_DIR}/audio.txt"
TRANSCRIPT_MD="${OUTPUT_DIR}/transcript.md"

if [ ! -f "$TRANSCRIPT_TXT" ]; then
    echo "ERROR: Whisper output not found at $TRANSCRIPT_TXT"
    exit 1
fi

# Get video metadata
TITLE=$(yt-dlp --get title "$URL" 2>/dev/null || echo "Unknown")
AUTHOR=$(yt-dlp --get uploader "$URL" 2>/dev/null || echo "Unknown")
DATE=$(yt-dlp --get upload_date "$URL" 2>/dev/null || echo "Unknown")

cat > "$TRANSCRIPT_MD" << EOF
# ${TITLE}

- **作者**: ${AUTHOR}
- **日期**: ${DATE}
- **原文链接**: ${URL}
- **语言**: ${DETECTED_LANG}

---

## 视频逐字稿

$(cat "$TRANSCRIPT_TXT")

---

> 视频文件: \`videos/video.mp4\`
EOF

echo "Transcript saved: $TRANSCRIPT_MD"

# Step 5: If English, translate to Chinese
if [ "$DETECTED_LANG" = "english" ] || [ "$DETECTED_LANG" = "en" ]; then
    echo "=== Step 5: English detected - translation needed ==="
    echo "Translation will be handled by the skill's LLM translation step."
    echo "TRANSLATE_NEEDED=true"
else
    echo "=== Step 5: Non-English content, no translation needed ==="
    echo "TRANSLATE_NEEDED=false"
fi

echo "=== Done! ==="
echo "Video: $VIDEO_FILE"
echo "Transcript: $TRANSCRIPT_MD"
