#!/usr/bin/env bash
# N분 동안 1분마다 프로세스 상태 점검·재기동 후 종료(종료 시 Claude 세션이 깨어나 요약 갱신).
MIN="${1:-25}"; REPO="$(cd "$(dirname "$0")/.." && pwd)"
for ((i=0;i<MIN;i++)); do "$REPO/scripts/start.sh" >/dev/null 2>&1; sleep 60; done
echo "watchdog done $(TZ=Asia/Seoul date '+%H:%M')"; pgrep -af "recorder.sh|transcriber.py|publish.sh" | grep -v pgrep | cut -c1-90
