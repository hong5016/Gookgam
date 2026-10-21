#!/usr/bin/env bash
# 국회 의사중계 HLS 오디오를 3분 단위 WAV로 저장. 끊기면 재접속.
# 사용: recorder.sh <xcode> <workdir>
XCODE="${1:-58}"; WORK="${2:-/home/user/gk_work}"
export TZ=Asia/Seoul
mkdir -p "$WORK/chunks" "$WORK/logs"
while true; do
  [ -f "$WORK/STOP" ] && { echo "$(date) STOP 파일 감지, 종료"; exit 0; }
  # 스트림 주소를 매번 조회 (중계 채널이 바뀔 수 있음)
  INFO=$(curl -sS -m 20 -e "https://assembly.webcast.go.kr/main/player.asp?xcode=$XCODE" \
    "https://assembly.webcast.go.kr/main/service/live_list.asp?vv=$(date +%s)")
  CGCD=$(python3 -c "import json,sys;d=json.loads(sys.stdin.read().lstrip('﻿'));print(next((x['xcgcd'] for x in d['xlist'] if x['xcode']=='$XCODE'),''))" <<<"$INFO" 2>/dev/null)
  PLAY=$(curl -sS -m 20 -e "https://assembly.webcast.go.kr/main/player.asp?xcode=$XCODE" \
    "https://assembly.webcast.go.kr/main/service/live_play.asp?xcode=$XCODE&xcgcd=$CGCD&vv=$(date +%s)&xreferer=&")
  URL=$(python3 -c "import json,sys;d=json.loads(sys.stdin.read().lstrip('﻿'));print(d['xhls'][0].get('240p') or d['xhls'][0]['default'])" <<<"$PLAY" 2>/dev/null)
  [ -z "$URL" ] && URL="https://w-assembly.hscdn.com/assembly/gyoyuk_240p/playlist.m3u8"
  echo "$(date) 접속: $URL (cgcd=$CGCD)"
  ffmpeg -hide_banner -loglevel warning -nostdin \
    -reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 -reconnect_delay_max 20 \
    -rw_timeout 30000000 -i "$URL" -vn -ac 1 -ar 16000 -c:a pcm_s16le \
    -f segment -segment_time 180 -reset_timestamps 1 -strftime 1 \
    "$WORK/chunks/%Y%m%d_%H%M%S.wav"
  echo "$(date) ffmpeg 종료 (코드 $?), 30초 후 재접속"
  sleep 30
done
