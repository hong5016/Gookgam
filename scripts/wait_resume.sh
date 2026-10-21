#!/usr/bin/env bash
# 정회 중 대기: 1분마다 프로세스 점검, 국회 중계 상태가 재개(또는 산회)로 바뀌면 종료해 Claude를 깨움.
MAX="${1:-100}"; REPO="$(cd "$(dirname "$0")/.." && pwd)"
for ((i=0;i<MAX;i++)); do
  "$REPO/scripts/start.sh" >/dev/null 2>&1
  S=$(curl -sS -m 15 -e "https://assembly.webcast.go.kr/main/" "https://assembly.webcast.go.kr/main/service/live_list.asp?vv=$(date +%s)" | python3 -c "import json,sys;d=json.loads(sys.stdin.read().lstrip('﻿'));print(next(x['xdesc'] for x in d['xlist'] if x['xcode']=='58'))" 2>/dev/null)
  case "$S" in *예정*|*중지*|*정회*|"") ;; *) echo "상태 변경: $S ($(TZ=Asia/Seoul date '+%H:%M'))"; exit 0;; esac
  sleep 60
done
echo "최대 대기 도달 ($(TZ=Asia/Seoul date '+%H:%M')), 마지막 상태: $S"
