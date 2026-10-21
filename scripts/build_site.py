#!/usr/bin/env python3
"""summary/summary.json + 진행 현황 + 전사본 → docs/index.html, 공유용 HTML 조각, README.md 생성."""
import datetime as dt, html, json, os, re, subprocess, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("GK_WORK", "/home/user/gk_work")
KST = dt.timezone(dt.timedelta(hours=9))
CFG = json.load(open(os.path.join(REPO, "config.json"), encoding="utf-8"))
E = html.escape

PARTY = {"더불어민주당": "dp", "국민의힘": "ppp", "조국혁신당": "rk", "개혁신당": "rf"}


# ---------- 자료 수집 ----------
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


def last_transcribed():
    st = os.path.join(WORK, "transcriber_state.json")
    if os.path.exists(st):
        s = json.load(open(st))
        if s.get("last_end"):
            return dt.datetime.fromisoformat(s["last_end"]).strftime("%H:%M")
    return "-"


def parse_transcript(path):
    """### 구간 제목 / `시각` 문장 / > ⚠️ 공백 표기를 구간 목록으로 변환."""
    chunks, cur = [], None
    if not os.path.exists(path):
        return chunks
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = re.match(r"^### (\d\d:\d\d:\d\d) ~ (\d\d:\d\d:\d\d)", line)
        if m:
            cur = {"start": m.group(1), "end": m.group(2), "lines": []}
            chunks.append(cur)
            continue
        m = re.match(r"^`(\d\d:\d\d:\d\d)` (.+)$", line)
        if m and cur is not None:
            cur["lines"].append((m.group(1), m.group(2)))
            continue
        if line.startswith("> ⚠️"):
            chunks.append({"start": None, "gap": line[2:].strip(), "lines": []})
    return chunks


def all_chunks():
    base = os.path.join(REPO, CFG["transcript_file"])
    morning = base.replace(".md", "_오전보강.md")
    cs = [c for c in parse_transcript(morning) if c.get("start")]  # 보강분의 공백 표기는 제외
    live = parse_transcript(base)
    first_live = next((c["start"] for c in live if c.get("start")), "99")
    cs = [c for c in cs if c["start"] < first_live]
    return cs + live


# ---------- HTML ----------
CSS = """
/* 레이아웃: 좌측 회의 정보 레일 + 우측 본문(개요 → 쟁점 → 질의 타임라인 → 요구 → 전사본). 좁은 화면은 1단. */
:root{
  --paper:#f4f6f5; --sheet:#ffffff; --ink:#18211e; --muted:#5a6762; --rule:#d7dedb;
  --accent:#264a7d; --accent-soft:#e6ecf5; --mark:#fff0b8;
  --ok:#1f7a4d; --warn:#a46500; --off:#6b7076;
  --dp:#1f5fbf; --ppp:#d0343b; --rk:#173f8f; --rf:#e07012;
  --f-display:"Gowun Batang","Nanum Myeongjo",serif;
  --f-body:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#111715; --sheet:#18201d; --ink:#e3e9e6; --muted:#9aa8a2; --rule:#2c3633;
  --accent:#8fb0e6; --accent-soft:#1f2a3a; --mark:#5a4a12;
  --ok:#5cc58e; --warn:#e2a740; --off:#9097a0;
  --dp:#6b9cf0; --ppp:#f07379; --rk:#7f9fe8; --rf:#f5a15a; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#111715; --sheet:#18201d; --ink:#e3e9e6; --muted:#9aa8a2; --rule:#2c3633;
  --accent:#8fb0e6; --accent-soft:#1f2a3a; --mark:#5a4a12;
  --ok:#5cc58e; --warn:#e2a740; --off:#9097a0;
  --dp:#6b9cf0; --ppp:#f07379; --rk:#7f9fe8; --rf:#f5a15a; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:var(--f-body);font-size:15px;line-height:1.7;word-break:keep-all;overflow-wrap:anywhere;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 56px}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{max-width:1140px;margin:0 auto;display:grid;gap:28px}
header.top{display:grid;gap:10px;border-bottom:2px solid var(--ink);padding-bottom:18px}
.eyebrow{font-size:12.5px;letter-spacing:.06em;color:var(--muted)}
h1{font-family:var(--f-display);font-weight:700;font-size:clamp(24px,4vw,34px);line-height:1.3;margin:0;text-wrap:balance}
.meta{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;font-size:13.5px;color:var(--muted)}
.pill{display:inline-flex;align-items:center;gap:7px;padding:3px 11px;border-radius:999px;font-size:13px;font-weight:600;border:1px solid currentColor}
.pill .dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.pill.ok{color:var(--ok)} .pill.warn{color:var(--warn)} .pill.off{color:var(--off)}
@media (prefers-reduced-motion:no-preference){.pill.ok .dot{animation:pulse 1.8s ease-in-out infinite}}
@keyframes pulse{50%{opacity:.25}}
.cols{display:grid;gap:28px;grid-template-columns:1fr}
@media (min-width:920px){.cols{grid-template-columns:270px minmax(0,1fr)}}
aside.rail{display:grid;gap:20px;align-content:start;font-size:13.5px;order:2}
@media (min-width:920px){aside.rail{order:0}}
@media (min-width:920px){aside.rail{position:sticky;top:calc(env(safe-area-inset-top,0px) + 16px)}}
.rail h3{font-size:12px;letter-spacing:.08em;color:var(--muted);margin:0 0 6px;font-weight:600}
dl.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:0}
dl.kv dt{color:var(--muted)} dl.kv dd{margin:0;font-variant-numeric:tabular-nums}
ul.plain{list-style:none;margin:0;padding:0;display:grid;gap:2px}
.members{display:flex;flex-wrap:wrap;gap:4px 10px}
.mem{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.pd{width:7px;height:7px;border-radius:50%;display:inline-block;flex:none}
.pd.dp{background:var(--dp)} .pd.ppp{background:var(--ppp)} .pd.rk{background:var(--rk)} .pd.rf{background:var(--rf)}
main{display:grid;gap:34px;min-width:0}
section{display:grid;gap:12px;min-width:0}
h2{font-family:var(--f-display);font-size:21px;margin:0;display:flex;align-items:baseline;gap:10px;text-wrap:balance}
h2 small{font-family:var(--f-body);font-size:12.5px;color:var(--muted);font-weight:400}
.lead{font-size:16.5px;max-width:68ch;margin:0}
.note{font-size:13px;color:var(--muted);margin:0}
ul.keys{margin:0;padding-left:1.1em;display:grid;gap:8px;max-width:72ch}
.issues{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.issue{background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:16px 18px;display:grid;gap:8px;align-content:start}
.issue h4{margin:0;font-size:16px}
.issue p{margin:0;font-size:14px}
.tags{display:flex;flex-wrap:wrap;gap:5px}
.tag{font-size:11.5px;padding:1px 8px;border-radius:4px;background:var(--accent-soft);color:var(--accent)}
.tl-row{display:grid;grid-template-columns:62px minmax(0,1fr);gap:14px;padding:14px 0;border-top:1px solid var(--rule)}
.tl-row:first-of-type{border-top:0}
.tl-time{font-family:var(--f-mono);font-size:13px;color:var(--muted);padding-top:2px;font-variant-numeric:tabular-nums}
.tl-who{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
.tl-who b{font-size:15.5px}
.tl-who .to{font-size:13px;color:var(--muted)}
.tl-who .inf{font-size:11.5px;color:var(--warn)}
.tl-row ul{margin:6px 0 0;padding-left:1.1em;display:grid;gap:4px;font-size:14px}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.04em}
.search{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.search input{flex:1 1 220px;min-width:0;font:inherit;padding:8px 12px;border:1px solid var(--rule);border-radius:6px;background:var(--sheet);color:var(--ink)}
.search output{font-size:13px;color:var(--muted)}
details.hour{border-top:1px solid var(--rule)}
details.hour summary{cursor:pointer;padding:9px 0;font-weight:600;font-variant-numeric:tabular-nums}
details.hour summary span{font-weight:400;color:var(--muted);font-size:13px;margin-left:8px}
.tx{display:grid;gap:2px;padding-bottom:12px}
.tx p{margin:0;display:grid;grid-template-columns:68px minmax(0,1fr);gap:10px;font-size:14px}
.tx time{font-family:var(--f-mono);font-size:12.5px;color:var(--muted);padding-top:2px}
.tx .gap{display:block;color:var(--warn);font-size:13px}
mark{background:var(--mark);color:inherit}
footer{font-size:12.5px;color:var(--muted);border-top:1px solid var(--rule);padding-top:14px;display:grid;gap:4px}
"""

JS = """
(function(){
  var q=document.getElementById('q'), out=document.getElementById('qcount');
  var rows=[].slice.call(document.querySelectorAll('.tx p[data-t]'));
  var hours=[].slice.call(document.querySelectorAll('details.hour'));
  rows.forEach(function(p){p._raw=p.querySelector('span').textContent;});
  function esc(s){return s.replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
  q.addEventListener('input',function(){
    var v=q.value.trim(), n=0;
    rows.forEach(function(p){
      var sp=p.querySelector('span');
      if(!v){p.hidden=false; sp.textContent=p._raw; return;}
      var hit=p._raw.indexOf(v)>=0; p.hidden=!hit;
      if(hit){n++; sp.innerHTML=esc(p._raw).split(esc(v)).join('<mark>'+esc(v)+'</mark>');}
    });
    hours.forEach(function(d){
      var any=d.querySelector('.tx p[data-t]:not([hidden])');
      if(v){d.hidden=!any; d.open=!!any;} else {d.hidden=false; d.open=d.hasAttribute('data-latest');}
    });
    out.textContent=v?(n+'건'):'';
  });
})();
"""


def party_dot(party):
    return f'<i class="pd {PARTY.get(party, "")}" aria-hidden="true"></i>'


def status_class(s):
    if "산회" in s:
        return "off"
    if "정회" in s or "중지" in s:
        return "warn"
    if "확인" in s:
        return "off"
    return "ok"


def build_fragment(S, status, last, chunks, now):
    c = CFG
    members = "".join(f'<span class="mem">{party_dot(p)}{E(n)}</span>' for n, p in c["members"])
    insts = "".join(f"<li>{E(i)}</li>" for i in c["institutions"])
    keys = "".join(f"<li>{E(k)}</li>" for k in S.get("key_points", []))
    issues = "".join(
        f'<article class="issue"><h4>{E(i["title"])}</h4><div class="tags">'
        + "".join(f'<span class="tag">{E(t)}</span>' for t in i.get("inst", []))
        + f'</div><p>{E(i["body"])}</p></article>' for i in S.get("issues", []))
    tl = []
    for r in S.get("timeline", []):
        role = f' <span class="to">{E(r["role"])}</span>' if r.get("role") else ""
        inf = ' <span class="inf">호명 기준 추정</span>' if r.get("inferred") else ""
        pts = "".join(f"<li>{E(p)}</li>" for p in r.get("points", []))
        tl.append(f'<div class="tl-row"><div class="tl-time">{E(r["start"])}</div><div>'
                  f'<div class="tl-who">{party_dot(r.get("party", ""))}<b>{E(r["member"])}</b>{role}'
                  f'<span class="to">{E(r.get("party", ""))} · 대상: {E(r.get("targets", ""))}</span>{inf}</div>'
                  f'<ul>{pts}</ul></div></div>')
    reqs = "".join(f'<tr><td>{E(q["from"])}</td><td>{E(q["to"])}</td><td>{E(q["what"])}</td></tr>'
                   for q in S.get("requests", []))

    # 전사본: 시(時) 단위 묶음
    hours, order = {}, []
    for ch in chunks:
        if ch.get("gap"):
            key = order[-1] if order else "기타"
            hours.setdefault(key, []).append(f'<span class="gap">{E(ch["gap"])}</span>')
            continue
        key = ch["start"][:2]
        if key not in hours:
            hours[key] = []
            order.append(key)
        for t, txt in ch["lines"]:
            hours[key].append(f'<p data-t="{t}"><time>{t}</time><span>{E(txt)}</span></p>')
    tx = []
    for i, h in enumerate(order):
        latest = i == len(order) - 1
        n = sum(1 for x in hours[h] if x.startswith("<p"))
        tx.append(f'<details class="hour"{" open data-latest" if latest else ""}>'
                  f'<summary>{h}시 대<span>{n}문장</span></summary><div class="tx">{"".join(hours[h])}</div></details>')
    pend = f'<p class="note">{E(S["pending"])}</p>' if S.get("pending") else ""
    sc = status_class(status)

    return f"""<title>교육위 국감 실시간 요약</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@700&family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans+KR:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="top">
  <div class="eyebrow">{E(c["session"])} · {E(c["date_label"])}</div>
  <h1>교육위원회 국정감사 — 부산대학교 등 9개 국립대</h1>
  <div class="meta">
    <span class="pill {sc}"><i class="dot"></i>{E(status)}</span>
    <span>요약 기준 {E(S.get("updated", "-")[-5:])} · 반영 구간 {E(S.get("covered", "-"))}</span>
    <span>다음 요약 {E(S.get("next_update", "-"))}</span>
  </div>
  <p class="note">AI 자동 전사·요약본입니다. 이름·수치를 잘못 알아들었을 수 있고, 질의자는 위원장 호명으로 추정했습니다. 공식 회의록이 아닙니다.</p>
</header>
<div class="cols">
<aside class="rail">
  <div><h3>현황</h3><dl class="kv">
    <dt>회의 상태</dt><dd>{E(status)}</dd>
    <dt>전사 완료</dt><dd>{E(last)}까지</dd>
    <dt>페이지 생성</dt><dd>{now:%H:%M}</dd></dl></div>
  <div><h3>피감기관</h3><ul class="plain">{insts}</ul></div>
  <div><h3>위원장</h3><span class="mem">{party_dot(c["chair"]["party"])}{E(c["chair"]["name"])}</span></div>
  <div><h3>위원</h3><div class="members">{members}</div></div>
  <div><h3>생중계</h3><ul class="plain">
    <li><a href="{E(c["youtube"])}" target="_blank" rel="noopener">YouTube 국회방송</a></li>
    <li><a href="https://assembly.webcast.go.kr/main/player.asp?xcode={E(c["xcode"])}" target="_blank" rel="noopener">국회 의사중계시스템</a></li></ul></div>
</aside>
<main>
  <section><h2>개요</h2><p class="lead">{E(S.get("lead", ""))}</p>{pend}</section>
  <section><h2>핵심 요약</h2><ul class="keys">{keys}</ul></section>
  <section><h2>주요 쟁점</h2><div class="issues">{issues}</div></section>
  <section><h2>질의 흐름 <small>시각은 질의 시작 기준</small></h2><div>{"".join(tl)}</div></section>
  <section><h2>자료 제출·시정 요구</h2><div class="tbl"><table>
    <thead><tr><th>요구</th><th>대상</th><th>내용</th></tr></thead><tbody>{reqs}</tbody></table></div></section>
  <section><h2>자동 전사본 <small>3분 단위, 약 5분 지연</small></h2>
    <div class="search"><label for="q" class="note">본문 검색</label>
      <input id="q" type="search" placeholder="예: 통합, 감사, 등록금" autocomplete="off"><output id="qcount"></output></div>
    <div>{"".join(tx) or '<p class="note">전사 대기 중</p>'}</div></section>
  <footer>
    <span>자료원: 국회 의사중계시스템 생중계·퀵VOD 음성(유튜브 국회방송 생중계와 같은 회의)</span>
    <span>전사: Whisper large-v3-turbo(faster-whisper) · 요약: Claude, 약 25분 간격 갱신</span>
    <span>국회에서 공개적으로 한 진술은 저작권법 제24조에 따라 자유롭게 이용할 수 있습니다.</span>
  </footer>
</main>
</div>
</div>
<script>{JS}</script>
"""


def build_readme(S, status, last, now):
    c = CFG
    keys = "\n".join(f"- {k}" for k in S.get("key_points", []))
    issues = "\n\n".join(f"**{i['title']}** ({', '.join(i.get('inst', []))})  \n{i['body']}" for i in S.get("issues", []))
    tl = []
    for r in S.get("timeline", []):
        inf = " _(호명 기준 추정)_" if r.get("inferred") else ""
        role = f" {r['role']}" if r.get("role") else ""
        tl.append(f"- **{r['start']} {r['member']}**{role}({r.get('party', '')}) → {r.get('targets', '')}{inf}\n"
                  + "\n".join(f"  - {p}" for p in r.get("points", [])))
    reqs = "\n".join(f"| {q['from']} | {q['to']} | {q['what']} |" for q in S.get("requests", []))
    pend = f"\n> {S['pending']}\n" if S.get("pending") else ""
    return f"""# {c['title']}

> {c['subtitle']}
> 생중계: [YouTube 국회방송]({c['youtube']}) · [국회 의사중계시스템](https://assembly.webcast.go.kr/main/player.asp?xcode={c['xcode']})
> ⚠️ AI 자동 전사·요약본. 고유명사·수치 오인식 가능, 화자는 사회자 호명으로 추정. **공식 회의록이 아님.**

**HTML 보기**: [docs/index.html](docs/index.html) (저장소 공개 후 GitHub Pages로 게시 가능)

| 항목 | 상태 |
|---|---|
| 페이지 갱신 | {now:%Y-%m-%d %H:%M} KST |
| 회의 상태(국회 중계 기준) | {status} |
| 전사 완료 시점 | {last} |
| 요약 기준 / 반영 구간 | {S.get('updated', '-')} / {S.get('covered', '-')} |

## 1. 개요

{S.get('lead', '')}
{pend}
## 2. 핵심 요약

{keys}

## 3. 주요 쟁점

{issues}

## 4. 질의 흐름

{chr(10).join(tl)}

## 5. 자료 제출·시정 요구

| 요구 | 대상 | 내용 |
|---|---|---|
{reqs}

## 자료

- 전체 자동 전사본(실시간): [{c['transcript_file']}]({c['transcript_file']})
- 오전 보강 전사본(10:02~11:23): [{c['transcript_file'].replace('.md', '_오전보강.md')}]({c['transcript_file'].replace('.md', '_오전보강.md')})
- 수집·전사·게시 스크립트: [scripts/](scripts/)

## 방법 및 한계

1. 자료원: 국회 의사중계시스템 HLS 생중계·퀵VOD 음성(유튜브 국회방송 생중계와 같은 회의). 클라우드 서버에서 유튜브가 차단돼 국회 공식 스트림 사용.
2. 전사: Whisper large-v3-turbo(faster-whisper, int8 CPU), 3분 단위, 무음 구간 제거.
3. 요약: Claude가 약 25분 간격으로 새 전사분을 읽고 쟁점·질의 중심으로 정리.
4. 한계: 화자 분리 미적용, 동시 발언 누락, 수집 공백은 전사본에 ⚠️로 표기.
5. 국회에서 공개적으로 한 진술은 저작권법 제24조에 따라 자유롭게 이용 가능.
"""


def main():
    now = dt.datetime.now(KST)
    S = json.load(open(os.path.join(REPO, "summary", "summary.json"), encoding="utf-8"))
    status, last, chunks = live_status(), last_transcribed(), all_chunks()
    frag = build_fragment(S, status, last, chunks, now)
    os.makedirs(os.path.join(REPO, "docs"), exist_ok=True)
    full = ('<!doctype html>\n<html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '</head><body>\n' + frag + "\n</body></html>\n")
    open(os.path.join(REPO, "docs", "index.html"), "w", encoding="utf-8").write(full)
    if CFG.get("artifact_out"):
        os.makedirs(os.path.dirname(CFG["artifact_out"]), exist_ok=True)
        open(CFG["artifact_out"], "w", encoding="utf-8").write(frag)
    open(os.path.join(REPO, "README.md"), "w", encoding="utf-8").write(build_readme(S, status, last, now))


if __name__ == "__main__":
    main()
