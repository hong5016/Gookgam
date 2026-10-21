#!/usr/bin/env python3
"""녹음된 3분 단위 WAV를 faster-whisper로 전사해 Markdown에 누적 기록.

사용: transcriber.py --work /home/user/gk_work --out transcript/2026-10-21_부산대등.md
"""
import argparse, datetime as dt, glob, json, os, re, sys, time, wave
import numpy as np
from faster_whisper import WhisperModel

KST = dt.timezone(dt.timedelta(hours=9))
CHUNK_RE = re.compile(r"(\d{8}_\d{6})\.wav$")

# 오인식 보정용 어휘 (국회 의사중계 좌석배치·안건 API 기준)
VOCAB = (
    "국정감사 교육위원회 지방1반. 위원장 김희정. "
    "위원 고민정 김문수 김준혁 박범계 백승아 안규백 윤호중 한병도 "
    "이인선 박정훈 서범수 장동혁 정성국 강경숙 이주영. "
    "피감기관 부산대학교 경상국립대학교 경북대학교 강원대학교 부경대학교 "
    "한국해양대학교 부산교육대학교 창원대학교 진주교육대학교. 총장 위원님 질의 답변."
)

# 무음 구간에서 Whisper가 자주 만들어내는 허위 문장
HALLUCINATIONS = [
    "시청해 주셔서 감사합니다", "시청해주셔서 감사합니다", "구독과 좋아요",
    "MBC 뉴스", "KBS 뉴스", "자막 제공", "다음 영상에서 만나요", "끝까지 시청",
]


def load_wav(path):
    """segment 진행 중이던 파일도 읽을 수 있도록 헤더 길이를 신뢰하지 않음."""
    with open(path, "rb") as f:
        raw = f.read()
    idx = raw.find(b"data")
    start = idx + 8 if 0 <= idx < 200 else 44
    pcm = raw[start:]
    pcm = pcm[: len(pcm) // 2 * 2]
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def is_hallucination(seg):
    t = seg.text.strip()
    if not t:
        return True
    if any(h in t for h in HALLUCINATIONS):
        return True
    if seg.no_speech_prob > 0.6 and seg.avg_logprob < -1.0:
        return True
    if seg.compression_ratio > 2.6:  # 같은 말 반복 루프
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="/home/user/gk_work")
    ap.add_argument("--out", required=True, help="Markdown 출력 경로")
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--beam", type=int, default=3)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--once", action="store_true", help="남은 파일 처리 후 종료(보강용)")
    args = ap.parse_args()

    state_path = os.path.join(args.work, "transcriber_state.json")
    jsonl_path = os.path.join(args.work, "transcript.jsonl")
    state = {"done": [], "last_end": None, "tail": ""}
    if os.path.exists(state_path):
        state = json.load(open(state_path))
    done = set(state["done"])

    model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=args.threads)
    print(f"{dt.datetime.now(KST):%H:%M:%S} 모델 로드 완료", flush=True)

    while True:
        if os.path.exists(os.path.join(args.work, "STOP_TRANSCRIBER")):
            print("STOP_TRANSCRIBER 감지, 종료", flush=True)
            return
        files = sorted(glob.glob(os.path.join(args.work, "chunks", "*.wav")))
        todo = []
        for i, f in enumerate(files):
            name = os.path.basename(f)
            if name in done:
                continue
            newest = i == len(files) - 1 and not args.once
            # 마지막 파일은 녹음 중이므로, 90초 이상 갱신이 없을 때만 처리
            if newest and time.time() - os.path.getmtime(f) < 90:
                continue
            todo.append(f)
        if not todo:
            if args.once:
                print("보강 완료", flush=True)
                return
            time.sleep(10)
            continue

        for f in todo:
            name = os.path.basename(f)
            m = CHUNK_RE.search(name)
            t0 = dt.datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=KST)
            audio = load_wav(f)
            dur = len(audio) / 16000
            tic = time.time()
            lines, recs = [], []
            if dur >= 1.0:
                prompt = VOCAB + " " + state.get("tail", "")[-150:]
                segs, _ = model.transcribe(
                    audio, language="ko", beam_size=args.beam, vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 700},
                    condition_on_previous_text=False, initial_prompt=prompt,
                )
                prev = None
                for s in segs:
                    if is_hallucination(s):
                        continue
                    txt = s.text.strip()
                    if txt == prev:
                        continue
                    prev = txt
                    ts = t0 + dt.timedelta(seconds=s.start)
                    lines.append(f"`{ts:%H:%M:%S}` {txt}")
                    recs.append({"t": ts.isoformat(), "text": txt})

            # Markdown 누적 기록
            out = []
            if state["last_end"]:
                last_end = dt.datetime.fromisoformat(state["last_end"])
                gap = (t0 - last_end).total_seconds()
                if gap > 30:
                    out.append(f"\n> ⚠️ 수집 공백 {last_end:%H:%M}~{t0:%H:%M} ({int(gap // 60)}분)\n")
            t1 = t0 + dt.timedelta(seconds=dur)
            out.append(f"\n### {t0:%H:%M:%S} ~ {t1:%H:%M:%S}\n")
            out.append("\n".join(lines) if lines else "_(발언 인식 없음 — 정회·무음 구간 추정)_")
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "a", encoding="utf-8") as fo:
                fo.write("\n".join(out) + "\n")
            with open(jsonl_path, "a", encoding="utf-8") as fj:
                for r in recs:
                    fj.write(json.dumps(r, ensure_ascii=False) + "\n")

            done.add(name)
            state["done"] = sorted(done)
            state["last_end"] = t1.isoformat()
            if recs:
                state["tail"] = " ".join(r["text"] for r in recs)[-300:]
            json.dump(state, open(state_path, "w"), ensure_ascii=False)
            print(f"{dt.datetime.now(KST):%H:%M:%S} {name} 오디오 {dur:.0f}s → "
                  f"{len(recs)}문장, 처리 {time.time() - tic:.0f}s", flush=True)


if __name__ == "__main__":
    main()
