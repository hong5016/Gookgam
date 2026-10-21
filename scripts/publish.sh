#!/usr/bin/env bash
# README·HTML 재생성 → 변경분 커밋 → push. 10분 간격 반복 (once 인자 시 1회).
REPO="$(cd "$(dirname "$0")/.." && pwd)"; BR="claude/awesome-babbage-y72moa"
WORK="${GK_WORK:-/home/user/gk_work}"; export TZ=Asia/Seoul
publish() {
  cd "$REPO" || return
  ( flock -w 120 9 || exit 1
    python3 scripts/build_site.py
    git add -A README.md docs summary transcript scripts config.json .gitignore 2>/dev/null
    if ! git diff --cached --quiet; then
      git commit -q -m "자동 갱신 $(date '+%H:%M') KST" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WGBi2A23N2wTt9mRxmSo1p"
    fi
    for d in 2 4 8 16; do git push -q -u origin "$BR" 2>&1 && break; sleep $d; done
  ) 9>"$WORK/git.lock"
}
if [ "$1" = "once" ]; then publish; exit; fi
while true; do
  [ -f "$WORK/STOP_PUBLISHER" ] && exit 0
  publish; echo "$(date '+%H:%M:%S') published"; sleep 600
done
