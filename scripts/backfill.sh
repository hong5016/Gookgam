#!/usr/bin/env bash
# 퀵VOD 다운로드 완료 대기 → 실제 시각으로 파일명 변환 → 전사(--once).
# 사용: backfill.sh <시작시각 YYYYmmddHHMMSS> <출력 md>
START="$1"; OUT="$2"; W=/home/user/gk_work; REPO="$(cd "$(dirname "$0")/.." && pwd)"
until grep -q DONE "$W/logs/backfill_dl.log" || ! pgrep -f "quickvod" >/dev/null; do sleep 15; done
python3 - "$START" <<'PY'
import sys, os, glob, datetime as dt
t0 = dt.datetime.strptime(sys.argv[1], "%Y%m%d%H%M%S")
for f in sorted(glob.glob("/home/user/gk_work/bf_raw/bf_*.wav")):
    n = int(os.path.basename(f)[3:6])
    t = t0 + dt.timedelta(seconds=180 * n)
    os.rename(f, f"/home/user/gk_work/bf/chunks/{t:%Y%m%d_%H%M%S}.wav")
PY
HF_HUB_DISABLE_PROGRESS_BARS=1 python3 "$REPO/scripts/transcriber.py" --work "$W/bf" --out "$OUT" --once --threads 2 --beam 2
