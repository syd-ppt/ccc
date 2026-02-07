#!/bin/bash
# Render Gource visualization of CCC compiler evolution to MP4.
# Two-step: Gource → PPM pipe → ffmpeg with ASS subtitle overlay.
# Requires: Gource (C:\Users\Syd\AppData\Local\Gource\gource.exe), ffmpeg (C:\ffmpeg\bin\ffmpeg)

set -euo pipefail

GOURCE="C:/Users/Syd/AppData/Local/Gource/gource.exe"
FFMPEG="C:/ffmpeg/bin/ffmpeg.exe"
LOG="D:/projects/ccc/gource_custom.log"
CAPTIONS="D:/projects/ccc/gource_captions.txt"
ASS_OVERLAY="D:/projects/ccc/counter_overlay.ass"
OUTPUT="D:/projects/ccc/ccc_creative_iteration.mp4"

# Verify inputs exist
for f in "$LOG" "$CAPTIONS" "$ASS_OVERLAY"; do
    if [ ! -f "$f" ]; then
        echo "Missing: $f"
        echo "Run: python generate_gource_log.py"
        exit 1
    fi
done

echo "Rendering Gource visualization..."
echo "Log: $LOG"
echo "Captions: $CAPTIONS"
echo "ASS overlay: $ASS_OVERLAY"
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
  --elasticity 0.01 \
  --dir-name-depth 3 \
  --bloom-multiplier 0.01 \
  --disable-auto-rotate \
  --caption-file "$CAPTIONS" \
  --caption-size 22 \
  --caption-duration 5 \
  --caption-colour FFCC00 \
  --output-framerate 30 \
  -o - \
| "$FFMPEG" -y -r 30 -f image2pipe -vcodec ppm -i - \
  -vf "ass='${ASS_OVERLAY//:/\\:}'" \
  -c:v libx264 -profile:v high -preset veryslow \
  -crf 23 -pix_fmt yuv420p -g 30 -bf 2 \
  -movflags faststart \
  "$OUTPUT"

echo "Done: $OUTPUT"
ls -lh "$OUTPUT"
