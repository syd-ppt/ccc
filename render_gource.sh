#!/bin/bash
# Render Gource visualization of CCC compiler evolution to MP4.
# Requires: Gource (C:\Users\Syd\AppData\Local\Gource\gource.exe), ffmpeg (C:\ffmpeg\bin\ffmpeg)

set -euo pipefail

GOURCE="C:/Users/Syd/AppData/Local/Gource/gource.exe"
FFMPEG="C:/ffmpeg/bin/ffmpeg.exe"
LOG="D:/projects/ccc/gource_custom.log"
OUTPUT="D:/projects/ccc/ccc_evolution.mp4"

echo "Rendering Gource visualization..."
echo "Log: $LOG"
echo "Output: $OUTPUT"

"$GOURCE" \
  --log-format custom "$LOG" \
  -1920x1080 \
  --seconds-per-day 17 \
  --auto-skip-seconds 0.5 \
  --max-file-lag 0.1 \
  --file-idle-time 0 \
  --hide usernames,users,mouse,progress \
  --key \
  --file-extensions \
  --date-format "%Y-%m-%d %H:%M" \
  --font-size 28 \
  --font-colour FFFFFF \
  --background-colour 000000 \
  --title "claudes-c-compiler — 14 Days, 3982 Commits" \
  --camera-mode overview \
  --elasticity 0.1 \
  --dir-name-depth 3 \
  --bloom-multiplier 0.5 \
  --output-framerate 60 \
  -o - \
| "$FFMPEG" -y -r 60 -f image2pipe -vcodec ppm -i - \
  -c:v libx264 -profile:v high -preset slow \
  -crf 18 -pix_fmt yuv420p -g 30 -bf 2 \
  -movflags faststart \
  "$OUTPUT"

echo "Done: $OUTPUT"
ls -lh "$OUTPUT"
