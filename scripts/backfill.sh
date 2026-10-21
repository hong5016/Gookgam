#!/usr/bin/env bash
# 퀵VOD 음성을 받는 대로 실제 시각 파일명으로 옮겨 전사. 다운로드 완료 후 잔여분까지 처리하고 종료.
# 사용: backfill.sh <시작시각 YYYYmmddHHMMSS> <출력 md>
START="$1"; OUT="$2"; W=/home/user/gk_work; REPO="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$W/bf/chunks"
while true; do
  DONE=0; grep -q DONE "$W/logs/backfill_dl.log" && DONE=1
  pgrep -f "quickvod" >/dev/null || DONE=1
  python3 - "$START" "$DONE" <<'PY'
import sys, os, glob, datetime as dt
t0 = dt.datetime.strptime(sys.argv[1], "%Y%m%d%H%M%S"); done = sys.argv[2] == "1"
fs = sorted(glob.glob("/home/user/gk_work/bf_raw/bf_*.wav"))
if not done: fs = fs[:-1]          # 받는 중인 마지막 파일은 제외
for f in fs:
    n = int(os.path.basename(f)[3:6])
    t = t0 + dt.timedelta(seconds=180 * n)
    os.rename(f, f"/home/user/gk_work/bf/chunks/{t:%Y%m%d_%H%M%S}.wav")
PY
  HF_HUB_DISABLE_PROGRESS_BARS=1 python3 "$REPO/scripts/transcriber.py" --work "$W/bf" --out "$OUT" --once --threads 2 --beam 2
  [ "$DONE" = 1 ] && [ -z "$(ls "$W/bf_raw" 2>/dev/null)" ] && { echo "보강 전체 완료"; exit 0; }
  sleep 30
done
