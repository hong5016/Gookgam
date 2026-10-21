#!/usr/bin/env bash
# 컨테이너 재시작 시에도 쓸 수 있는 멱등 실행 스크립트. 빠진 프로세스만 다시 띄움.
REPO="$(cd "$(dirname "$0")/.." && pwd)"; WORK="${GK_WORK:-/home/user/gk_work}"
mkdir -p "$WORK/chunks" "$WORK/logs"
python3 -c "import faster_whisper" 2>/dev/null || pip3 install -q --break-system-packages faster-whisper
X=$(python3 -c "import json;print(json.load(open('$REPO/config.json'))['xcode'])")
T=$(python3 -c "import json;print(json.load(open('$REPO/config.json'))['transcript_file'])")
cd "$WORK"
pgrep -f "recorder.sh" >/dev/null || setsid nohup "$REPO/scripts/recorder.sh" "$X" "$WORK" >> logs/recorder.log 2>&1 < /dev/null &
pgrep -f "transcriber.py --work $WORK --out" >/dev/null || HF_HUB_DISABLE_PROGRESS_BARS=1 setsid nohup python3 "$REPO/scripts/transcriber.py" --work "$WORK" --out "$REPO/$T" >> logs/transcriber.log 2>&1 < /dev/null &
pgrep -f "publish.sh" >/dev/null || setsid nohup "$REPO/scripts/publish.sh" >> logs/publish.log 2>&1 < /dev/null &
sleep 2; pgrep -af "recorder.sh|transcriber.py|publish.sh" | grep -v pgrep
