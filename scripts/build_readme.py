#!/usr/bin/env python3
"""README.md 재생성: 진행 현황(자동) + 핵심 요약(summary/brief.md) + 자료 링크."""
import datetime as dt, glob, json, os, re, subprocess, sys, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("GK_WORK", "/home/user/gk_work")
CFG = json.load(open(os.path.join(REPO, "config.json"), encoding="utf-8"))
KST = dt.timezone(dt.timedelta(hours=9))


def live_status():
    try:
        req = urllib.request.Request(
            "https://assembly.webcast.go.kr/main/service/live_list.asp",
            headers={"Referer": "https://assembly.webcast.go.kr/main/"})
        d = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8-sig"))
        for x in d["xlist"]:
            if x["xcode"] == CFG["xcode"]:
                return x.get("xdesc") or "-"
    except Exception:
        pass
    return "확인 불가"


def alive(pattern):
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def transcript_stats():
    st = os.path.join(WORK, "transcriber_state.json")
    last, n = "-", 0
    if os.path.exists(st):
        s = json.load(open(st))
        n = len(s.get("done", []))
        if s.get("last_end"):
            last = dt.datetime.fromisoformat(s["last_end"]).strftime("%H:%M")
    return last, n


def main():
    now = dt.datetime.now(KST)
    last, n = transcript_stats()
    rec = "🟢 수집 중" if alive("recorder.sh") else "🔴 중지"
    trn = "🟢 전사 중" if alive("transcriber.py") else "🔴 중지"
    brief_path = os.path.join(REPO, "summary", "brief.md")
    brief = open(brief_path, encoding="utf-8").read().strip() if os.path.exists(brief_path) \
        else "_첫 요약 작성 중입니다._"
    t = CFG

    md = f"""# {t['title']}

> {t['subtitle']}
> 생중계: [YouTube 국회방송]({t['youtube']}) · [국회 의사중계시스템](https://assembly.webcast.go.kr/main/player.asp?xcode={t['xcode']})
> ⚠️ AI 자동 전사·요약본. 고유명사·수치 오인식 가능, 화자는 사회자 호명으로 추정. **공식 회의록이 아님.**

## 0. 진행 현황 (3분마다 자동 갱신)

| 항목 | 상태 |
|---|---|
| 페이지 갱신 | {now:%Y-%m-%d %H:%M} KST |
| 회의 상태(국회 중계 기준) | {live_status()} |
| 마지막 전사 시점 | {last} (3분 단위 {n}개 구간) |
| 수집 / 전사 | {rec} / {trn} |

{brief}

## 자료

| 구분 | 파일 |
|---|---|
| 시간대별 상세 요약 | [{t['summary_file']}]({t['summary_file']}) |
| 전체 자동 전사본(3분 지연) | [{t['transcript_file']}]({t['transcript_file']}) |
| 수집·전사 스크립트 | [scripts/](scripts/) |

## 방법 및 한계

1. **자료원**: 국회 의사중계시스템 HLS 생중계 음성(YouTube 국회방송 생중계와 동일 회의).
2. **전사**: OpenAI Whisper large-v3-turbo(faster-whisper, int8 CPU), 3분 단위, VAD 무음 제거.
3. **요약**: Claude가 약 30분 간격으로 누적 전사본을 읽고 쟁점·질의 중심으로 정리.
4. **한계**: 화자 분리 미적용, 동시 발언·마이크 미사용 구간 누락, 수집 공백은 전사본에 ⚠️로 표기.
5. **법적 근거**: 국회에서 공개적으로 행한 진술은 저작권법 제24조에 따라 자유 이용 가능.
"""
    open(os.path.join(REPO, "README.md"), "w", encoding="utf-8").write(md)


if __name__ == "__main__":
    main()
