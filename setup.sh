#!/usr/bin/env bash
# Установка инструментов для нарезки. Запуск: bash setup.sh
set -euo pipefail
cd "$(dirname "$0")"
pip install -q -U -r requirements.txt
mkdir -p assets/models
M=assets/models/face_detection_yunet_2023mar.onnx
[ -s "$M" ] || curl -sSL -o "$M" "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx"
command -v ffmpeg >/dev/null || { apt-get update -qq && apt-get install -y -qq ffmpeg; }
python3 -c "import faster_whisper, cv2, pyloudnorm; print('python deps ok')"
yt-dlp --version
ffmpeg -hide_banner -filters 2>/dev/null | grep " ass " >/dev/null && echo "ffmpeg libass ok"
