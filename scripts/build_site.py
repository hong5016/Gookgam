#!/usr/bin/env python3
"""summary/summary.json + 전사본 + 중계 상태 → docs/index.html, 공유용 HTML 조각, README.md 생성.

페이지는 세 가지 보기(주제별 · 타임테이블 · 전사본)를 가지며 서로 연결됨:
  주제 카드 → 관련 발언(타임테이블) → 전사본 해당 시각 → 유튜브 해당 시점
"""
import datetime as dt, html, json, os, re, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("GK_WORK", "/home/user/gk_work")
KST = dt.timezone(dt.timedelta(hours=9))
CFG = json.load(open(os.path.join(REPO, "config.json"), encoding="utf-8"))
E = html.escape

PARTY = {"더불어민주당": "dp", "국민의힘": "ppp", "조국혁신당": "rk", "개혁신당": "rf"}
KIND = {"opening": "개회", "report": "업무보고", "procedural": "의사진행", "question": "질의", "closing": "마무리"}
YT_START = dt.datetime.strptime(CFG["youtube_start"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
DAY = YT_START.date()


# ---------- 자료 수집 ----------
def live_status():
    # 프록시 연결이 간헐적으로 끊겨 최대 4회 재시도
    import time
    for i in range(4):
        try:
            req = urllib.request.Request(
                "https://assembly.webcast.go.kr/main/service/live_list.asp",
                headers={"Referer": "https://assembly.webcast.go.kr/main/"})
            d = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8-sig"))
            for x in d["xlist"]:
                if x["xcode"] == CFG["xcode"]:
                    return x.get("xdesc") or "-"
        except Exception:
            time.sleep(2 * (i + 1))
    return "확인 불가"


def last_transcribed():
    st = os.path.join(WORK, "transcriber_state.json")
    if os.path.exists(st):
        s = json.load(open(st))
        if s.get("last_end"):
            return dt.datetime.fromisoformat(s["last_end"]).strftime("%H:%M")
    return "-"


def parse_transcript(path):
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


def transcript_lines():
    """[(시각, 문장)] 시간순. 보강분은 실시간분 시작 전까지만. 생략 구간은 ('gap', 표시문)."""
    base = os.path.join(REPO, CFG["transcript_file"])
    morning = base.replace(".md", "_오전보강.md")
    live = parse_transcript(base)
    first_live = next((c["start"] for c in live if c.get("start")), "99")
    out = []
    for c in parse_transcript(morning):
        if c.get("start") and c["start"] < first_live:
            out += c["lines"]
    for c in live:
        if c.get("gap"):
            out.append(("gap", c["gap"]))
        else:
            out += c["lines"]
    res, done = [], set()
    for t, txt in out:
        if t == "gap":
            res.append((t, txt))
            continue
        red = next((r for r in CFG.get("redact", []) if r[0] <= t <= r[1]), None)
        if red:
            if red[0] not in done:
                res.append(("gap", f"({red[2]})"))
                done.add(red[0])
            continue
        res.append((t, txt))
    return res


# ---------- 유틸 ----------
def yt_url(hhmmss):
    """KST 시각 → 유튜브 해당 시점 링크."""
    h, m, s = (hhmmss + ":00").split(":")[:3]
    t = dt.datetime(DAY.year, DAY.month, DAY.day, int(h), int(m), int(s), tzinfo=KST)
    sec = max(0, int((t - YT_START).total_seconds()))
    return f"https://www.youtube.com/watch?v={CFG['youtube_id']}&t={sec}s"


def pdot(party):
    return f'<i class="pd {PARTY.get(party, "none")}" aria-hidden="true"></i>'


def status_class(s):
    if "산회" in s or "종료" in s or "확인" in s:
        return "off"
    if any(k in s for k in ("정회", "중지", "예정")):
        return "warn"
    return "ok"


def member_label(x):
    role = f' <span class="role">{E(x["role"])}</span>' if x.get("role") else ""
    return f'{pdot(x.get("party", ""))}<b>{E(x["member"])}</b>{role}'


# ---------- CSS / JS ----------
CSS = """
/* 레이아웃: 상단 회의 현황 → 고정 탭(주제별·타임테이블·전사본) → 선택한 보기. 폭이 좁으면 모든 행이 1단으로. */
:root{
  --paper:#f4f6f5; --sheet:#ffffff; --ink:#18211e; --muted:#5a6762; --rule:#d7dedb; --rule2:#e8edeb;
  --accent:#264a7d; --on-accent:#ffffff; --accent-soft:#e6ecf5; --mark:#fff0b8; --yt:#b3261e;
  --ok:#1f7a4d; --warn:#a46500; --off:#6b7076;
  --dp:#1f5fbf; --ppp:#d0343b; --rk:#173f8f; --rf:#e07012; --none:#9aa49f;
  --f-display:"Gowun Batang","Nanum Myeongjo",serif;
  --f-body:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#111715; --sheet:#18201d; --ink:#e3e9e6; --muted:#9aa8a2; --rule:#2c3633; --rule2:#222b28;
  --accent:#8fb0e6; --on-accent:#0f1a2b; --accent-soft:#1f2a3a; --mark:#5a4a12; --yt:#ff7b73;
  --ok:#5cc58e; --warn:#e2a740; --off:#9097a0;
  --dp:#6b9cf0; --ppp:#f07379; --rk:#7f9fe8; --rf:#f5a15a; --none:#6b746f; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#111715; --sheet:#18201d; --ink:#e3e9e6; --muted:#9aa8a2; --rule:#2c3633; --rule2:#222b28;
  --accent:#8fb0e6; --on-accent:#0f1a2b; --accent-soft:#1f2a3a; --mark:#5a4a12; --yt:#ff7b73;
  --ok:#5cc58e; --warn:#e2a740; --off:#9097a0;
  --dp:#6b9cf0; --ppp:#f07379; --rk:#7f9fe8; --rf:#f5a15a; --none:#6b746f; color-scheme:dark}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--f-body);font-size:15px;line-height:1.7;word-break:keep-all;overflow-wrap:anywhere;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:24px 56px}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--paper)}
a{color:var(--accent)}
button{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{max-width:1040px;margin:0 auto;display:grid;gap:20px}
header.top{display:grid;gap:8px;border-bottom:2px solid var(--ink);padding-bottom:16px}
.brand{font-family:var(--f-display);font-size:15px;font-weight:700;letter-spacing:.12em;display:flex;gap:10px;align-items:baseline}
.brand span{font-family:var(--f-body);font-weight:400;font-size:12px;letter-spacing:.04em;color:var(--muted)}
.eyebrow{font-size:12.5px;letter-spacing:.06em;color:var(--muted)}
h1{font-family:var(--f-display);font-weight:700;font-size:clamp(23px,4vw,32px);line-height:1.3;margin:0;text-wrap:balance}
.meta{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;font-size:13.5px;color:var(--muted)}
.pill{display:inline-flex;align-items:center;gap:7px;padding:3px 11px;border-radius:999px;font-size:13px;font-weight:600;border:1px solid currentColor}
.pill .dot{width:8px;height:8px;border-radius:50%;background:currentColor}
.pill.ok{color:var(--ok)} .pill.warn{color:var(--warn)} .pill.off{color:var(--off)}
@media (prefers-reduced-motion:no-preference){.pill.ok .dot{animation:pulse 1.8s ease-in-out infinite}}
@keyframes pulse{50%{opacity:.25}}
.note{font-size:13px;color:var(--muted);margin:0}
details.info{font-size:13.5px}
details.info summary{cursor:pointer;color:var(--muted);list-style:none;display:inline-flex;gap:6px;align-items:center}
details.info summary::-webkit-details-marker{display:none}
details.info summary::before{content:"▸";font-size:11px} details.info[open] summary::before{content:"▾"}
.info-grid{display:grid;gap:14px 28px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));padding-top:10px}
.info-grid h3{font-size:12px;letter-spacing:.08em;color:var(--muted);margin:0 0 4px;font-weight:600}
ul.plain{list-style:none;margin:0;padding:0;display:grid;gap:2px}
.members{display:flex;flex-wrap:wrap;gap:4px 10px}
.mem{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.pd{width:8px;height:8px;border-radius:50%;display:inline-block;flex:none}
.pd.dp{background:var(--dp)} .pd.ppp{background:var(--ppp)} .pd.rk{background:var(--rk)} .pd.rf{background:var(--rf)} .pd.none{background:var(--none)}
/* 탭 */
nav.tabs{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--paper);display:flex;gap:4px;border-bottom:1px solid var(--rule);padding-top:4px}
.tab{background:none;border:0;border-bottom:3px solid transparent;padding:9px 14px;font-size:15px;font-weight:600;color:var(--muted);cursor:pointer;margin-bottom:-1px}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent)}
.tab small{font-weight:400;font-size:12px;margin-left:4px}
section.view{display:grid;gap:22px;min-width:0}
h2{font-family:var(--f-display);font-size:20px;margin:0;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;text-wrap:balance}
h2 small{font-family:var(--f-body);font-size:12.5px;color:var(--muted);font-weight:400}
.lead{font-size:16px;max-width:70ch;margin:0}
/* 주제 카드 */
.topics{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
details.topic{background:var(--sheet);border:1px solid var(--rule);border-radius:8px;min-width:0}
details.topic[open]{grid-column:1/-1;border-color:var(--accent)}
details.topic summary{list-style:none;cursor:pointer;padding:14px 16px;display:grid;gap:6px}
details.topic summary::-webkit-details-marker{display:none}
.t-head{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.t-title{font-size:16.5px;font-weight:600}
.t-n{font-size:12px;color:var(--muted);white-space:nowrap}
.t-short{font-size:13.5px;color:var(--muted);margin:0}
.tags{display:flex;flex-wrap:wrap;gap:5px}
.tag{font-size:11.5px;padding:1px 8px;border-radius:4px;background:var(--accent-soft);color:var(--accent);border:0;cursor:default}
button.tag{cursor:pointer} button.tag:hover{text-decoration:underline}
.tag.inst{background:var(--rule2);color:var(--muted)}
.t-body{padding:12px 16px 16px;display:grid;gap:12px;border-top:1px solid var(--rule2)}
.t-body p{margin:0;max-width:75ch}
.t-body h5{margin:0;font-size:12px;letter-spacing:.06em;color:var(--muted);font-weight:600}
ul.t-x{list-style:none;margin:0;padding:0;display:grid;gap:6px}
ul.t-x li{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;font-size:14px}
ul.t-x .when{font-family:var(--f-mono);font-size:12.5px}
ul.t-x .to{color:var(--muted);font-size:13px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border:1px solid var(--accent);border-radius:6px;background:var(--sheet);color:var(--accent);font-size:13px;cursor:pointer;text-decoration:none;justify-self:start}
.btn:hover{background:var(--accent-soft)}
.btn.sm{padding:2px 8px;font-size:12px;border-color:var(--rule);color:var(--muted)}
.btn.sm:hover{color:var(--accent);border-color:var(--accent)}
a.yt{color:var(--yt);text-decoration:none;font-size:12.5px;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
a.yt:hover{text-decoration:underline}
a.yt::before{content:"▶";font-size:10px}
/* 필터 */
.filters{display:grid;gap:8px;background:var(--sheet);border:1px solid var(--rule);border-radius:8px;padding:12px 14px}
.fgroup{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.fgroup .lab{font-size:12px;color:var(--muted);letter-spacing:.04em;width:52px;flex:none}
.chip{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border:1px solid var(--rule);border-radius:999px;background:var(--paper);font-size:13px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--accent);color:var(--on-accent);border-color:var(--accent)}
.chip small{color:inherit;opacity:.7;font-size:11px}
.fstat{display:flex;gap:12px;align-items:center;font-size:13px;color:var(--muted)}
/* 타임테이블 */
.tl{display:grid;gap:0}
.row{display:grid;grid-template-columns:64px minmax(0,1fr);gap:14px;padding:14px 0;border-top:1px solid var(--rule)}
.row:first-child{border-top:0}
.r-time{font-family:var(--f-mono);font-size:13.5px;font-variant-numeric:tabular-nums;display:grid;align-content:start}
.r-time span{font-size:11.5px;color:var(--muted)}
.r-body{display:grid;gap:8px;min-width:0}
.r-head{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
.r-head b{font-size:15.5px}
.kind{font-size:11px;padding:1px 7px;border-radius:4px;border:1px solid var(--rule);color:var(--muted);letter-spacing:.04em}
.row.k-question .kind{border-color:var(--accent);color:var(--accent)}
.role{font-size:12px;color:var(--muted)}
.to{font-size:13px;color:var(--muted)}
ul.pts{margin:0;padding-left:1.1em;display:grid;gap:5px;font-size:14px;max-width:80ch}
details.more summary{cursor:pointer;font-size:13.5px;color:var(--accent)}
.req{font-size:13.5px;background:var(--accent-soft);border-radius:6px;padding:8px 12px;display:grid;gap:3px}
.req b{font-weight:600;font-size:12px;letter-spacing:.04em;color:var(--accent)}
.links{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
.row.brk{color:var(--warn);font-size:13.5px;border-top:1px dashed var(--rule);padding:10px 0}
.row.now{color:var(--muted);font-size:13px;border-top:1px dashed var(--rule);padding:10px 0}
/* 요구 표 */
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.04em;white-space:nowrap}
td.when{white-space:nowrap}
/* 전사본 */
.search{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.search input{flex:1 1 220px;min-width:0;font:inherit;padding:8px 12px;border:1px solid var(--rule);border-radius:6px;background:var(--sheet);color:var(--ink)}
.search output{font-size:13px;color:var(--muted)}
details.hour{border-top:1px solid var(--rule)}
details.hour summary{cursor:pointer;padding:9px 0;font-weight:600;font-variant-numeric:tabular-nums}
details.hour summary span{font-weight:400;color:var(--muted);font-size:13px;margin-left:8px}
.tx{display:grid;gap:2px;padding-bottom:12px}
.tx p{margin:0;display:grid;grid-template-columns:70px minmax(0,1fr);gap:10px;font-size:14px;padding:1px 4px;border-radius:4px}
.tx p a.t{font-family:var(--f-mono);font-size:12.5px;color:var(--muted);text-decoration:none;padding-top:2px}
.tx p a.t:hover{color:var(--yt);text-decoration:underline}
.tx .gap{display:block;color:var(--warn);font-size:13px;padding:4px}
.mark{margin:10px 0 4px;padding:8px 12px;border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:0 6px 6px 0;font-size:13.5px;display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center}
.mark b{font-weight:600}
mark{background:var(--mark);color:inherit}
.flash{animation:flash 1.8s ease-out}
@keyframes flash{0%{background:var(--mark)}100%{background:transparent}}
@media (prefers-reduced-motion:reduce){.flash{animation:none;outline:2px solid var(--accent)}}
footer{font-size:12.5px;color:var(--muted);border-top:1px solid var(--rule);padding-top:14px;display:grid;gap:4px}
@media (max-width:560px){.row{grid-template-columns:52px minmax(0,1fr);gap:10px} .tx p{grid-template-columns:62px minmax(0,1fr)} .fgroup .lab{width:100%}}
"""

JS = """
(function(){
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var sb = reduce ? 'auto' : 'smooth';
  var views = ['topics','timeline','transcript'];
  function show(v, keep){
    views.forEach(function(k){
      var s=document.getElementById('v-'+k); if(s) s.hidden=(k!==v);
      var b=document.querySelector('.tab[data-view="'+k+'"]'); if(b) b.setAttribute('aria-selected', k===v?'true':'false');
    });
    if(!keep){ try{ localStorage.setItem('gk_view', v); }catch(e){} }
  }
  function flash(el){ el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash'); setTimeout(function(){ el.classList.remove('flash'); }, 1900); }
  function goEl(el, block){ setTimeout(function(){ el.scrollIntoView({behavior:sb, block:block||'start'}); flash(el); }, 60); }
  document.querySelectorAll('.tab').forEach(function(b){ b.addEventListener('click', function(){ show(b.dataset.view); window.scrollTo({top:0,behavior:sb}); }); });

  /* 타임테이블 필터 */
  var state={m:new Set(),a:new Set(),t:new Set()};
  var rows=[].slice.call(document.querySelectorAll('#tl .row[data-member]'));
  var reqRows=[].slice.call(document.querySelectorAll('#reqs tbody tr[data-member]'));
  function active(){ return state.m.size||state.a.size||state.t.size; }
  function match(el){
    var a=(el.dataset.ans||'').split('|'), t=(el.dataset.topics||'').split('|').filter(Boolean);
    if(state.m.size && !state.m.has(el.dataset.member)) return false;
    if(state.a.size && !a.some(function(v){return state.a.has(v);})) return false;
    if(state.t.size && !t.some(function(v){return state.t.has(v);})) return false;
    return true;
  }
  function applyFilter(){
    var n=0; rows.forEach(function(el){ var ok=match(el); el.hidden=!ok; if(ok) n++; });
    reqRows.forEach(function(el){ el.hidden=!match(el); });
    document.querySelectorAll('.row.brk,.row.now').forEach(function(el){ el.hidden=!!active(); });
    document.querySelectorAll('.chip').forEach(function(c){ c.setAttribute('aria-pressed', state[c.dataset.g].has(c.dataset.v)?'true':'false'); });
    var st=document.getElementById('fstat'); if(st) st.textContent = active() ? n+'건 표시 (전체 '+rows.length+'건)' : '전체 '+rows.length+'건';
    var r=document.getElementById('freset'); if(r) r.hidden=!active();
  }
  function clearFilter(){ state.m.clear(); state.a.clear(); state.t.clear(); }
  document.querySelectorAll('.chip').forEach(function(c){ c.addEventListener('click', function(){ var s=state[c.dataset.g]; s.has(c.dataset.v)?s.delete(c.dataset.v):s.add(c.dataset.v); applyFilter(); }); });
  var fr=document.getElementById('freset'); if(fr) fr.addEventListener('click', function(){ clearFilter(); applyFilter(); });

  /* 보기 간 연결 */
  function openTopic(id){ show('topics'); var d=document.getElementById(id); if(!d) return; d.open=true; goEl(d,'start'); }
  function goX(id){ show('timeline'); clearFilter(); applyFilter(); var el=document.getElementById(id); if(el) goEl(el,'start'); }
  function filterTopic(id){ show('timeline'); clearFilter(); state.t.add(id); applyFilter(); window.scrollTo({top:0,behavior:sb}); }
  function goTx(hhmm){
    show('transcript');
    var q=document.getElementById('q'); if(q && q.value){ q.value=''; q.dispatchEvent(new Event('input')); }
    var t=hhmm+':00', ps=document.querySelectorAll('.tx p[data-t]'), p=null;
    for(var i=0;i<ps.length;i++){ if(ps[i].dataset.t>=t){ p=ps[i]; break; } }
    if(!p) return; var d=p.closest('details'); if(d) d.open=true; goEl(p,'center');
  }
  document.addEventListener('click', function(e){
    var b=e.target.closest('[data-topic-open],[data-x-go],[data-topic-filter],[data-tx-go]'); if(!b) return;
    e.preventDefault();
    if(b.dataset.topicOpen) openTopic(b.dataset.topicOpen);
    else if(b.dataset.xGo) goX(b.dataset.xGo);
    else if(b.dataset.topicFilter) filterTopic(b.dataset.topicFilter);
    else if(b.dataset.txGo) goTx(b.dataset.txGo);
  });

  /* 전사본 검색 */
  var q=document.getElementById('q'), out=document.getElementById('qcount');
  var lines=[].slice.call(document.querySelectorAll('.tx p[data-t]'));
  var hours=[].slice.call(document.querySelectorAll('details.hour'));
  lines.forEach(function(p){ p._raw=p.querySelector('span').textContent; });
  function esc(s){ return s.replace(/[&<>]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]; }); }
  if(q) q.addEventListener('input', function(){
    var v=q.value.trim(), n=0;
    lines.forEach(function(p){
      var sp=p.querySelector('span');
      if(!v){ p.hidden=false; sp.textContent=p._raw; return; }
      var hit=p._raw.indexOf(v)>=0; p.hidden=!hit;
      if(hit){ n++; sp.innerHTML=esc(p._raw).split(esc(v)).join('<mark>'+esc(v)+'</mark>'); }
    });
    document.querySelectorAll('.mark').forEach(function(m){ m.hidden=!!v; });
    hours.forEach(function(d){
      var any=d.querySelector('.tx p[data-t]:not([hidden])');
      if(v){ d.hidden=!any; d.open=!!any; } else { d.hidden=false; d.open=d.hasAttribute('data-latest'); }
    });
    out.textContent=v?(n+'건'):'';
  });

  /* 시작 보기: #topics #timeline #transcript #t_… #x_… */
  var h=(location.hash||'').replace('#','');
  if(views.indexOf(h)>=0) show(h,true);
  else if(/^t_/.test(h)) openTopic(h);
  else if(/^x_/.test(h)) goX(h);
  else { var v=null; try{ v=localStorage.getItem('gk_view'); }catch(e){} show(views.indexOf(v)>=0?v:'topics',true); }
  applyFilter();
})();
"""


# ---------- HTML 조각 ----------
def build(S, status, last, lines, now):
    c = CFG
    topics = {t["id"]: t for t in S["topics"]}
    xs = sorted(S["exchanges"], key=lambda x: x["start"])
    by_topic = {t["id"]: [x for x in xs if t["id"] in x.get("topics", [])] for t in S["topics"]}

    # 회의 정보
    members = "".join(f'<span class="mem">{pdot(p)}{E(n)}</span>' for n, p in c["members"])
    insts = "".join(f"<li>{E(i)}</li>" for i in c["institutions"])
    info = f"""<details class="info"><summary>회의 정보 · 피감기관 · 출석 위원</summary><div class="info-grid">
  <div><h3>피감기관(지방1반)</h3><ul class="plain">{insts}</ul></div>
  <div><h3>위원장</h3><span class="mem">{pdot(c["chair"]["party"])}{E(c["chair"]["name"])}</span>
    <h3 style="margin-top:10px">{E(c.get("members_label", "위원"))}</h3><div class="members">{members}</div>
    {f'<p class="note" style="margin-top:6px">{E(c["members_note"])}</p>' if c.get("members_note") else ""}</div>
  <div><h3>생중계·다시보기</h3><ul class="plain">
    <li><a href="{E(c["youtube"])}" target="_blank" rel="noopener">YouTube 국회방송</a></li>
    <li><a href="https://assembly.webcast.go.kr/main/player.asp?xcode={E(c["xcode"])}" target="_blank" rel="noopener">국회 의사중계시스템</a></li></ul>
    <p class="note" style="margin-top:6px">▶ 표시는 유튜브의 해당 시점으로 이동합니다(±10초).</p></div>
</div></details>"""

    # 주제 카드
    cards = []
    for t in S["topics"]:
        rel = by_topic[t["id"]]
        n_label = f"발언 {len(rel)}건" if rel else "언급 없음"
        inst = "".join(f'<span class="tag inst">{E(i)}</span>' for i in t.get("inst", []))
        items, reqs = [], []
        for x in rel:
            items.append(f'<li><a href="#{x["id"]}" class="when" data-x-go="{x["id"]}">{E(x["start"])}</a> '
                         f'{member_label(x)} <span class="to">→ {E(", ".join(x["answerers"]))}</span> '
                         f'<button class="btn sm" data-tx-go="{E(x["start"])}">전사본</button> '
                         f'<a class="yt" href="{yt_url(x["start"])}" target="_blank" rel="noopener">유튜브 {E(x["start"])}</a></li>')
            for r in x.get("requests", []):
                due = f' <span class="to">({E(r["due"])})</span>' if r.get("due") else ""
                reqs.append(f"<li><b>{E(r['to'])}</b>: {E(r['what'])}{due} <span class=\"to\">— {E(x['member'])}</span></li>")
        req_html = f'<h5>자료 제출·시정 요구</h5><ul class="pts">{"".join(reqs)}</ul>' if reqs else ""
        cards.append(f"""<details class="topic" id="{t['id']}">
  <summary><span class="t-head"><span class="t-title">{E(t['title'])}</span><span class="t-n">{n_label}</span></span>
    <span class="t-short">{E(t['short'])}</span><span class="tags">{inst}</span></summary>
  <div class="t-body"><p>{E(t['body'])}</p>
    <h5>관련 발언</h5><ul class="t-x">{"".join(items) or "<li class='to'>아직 없음</li>"}</ul>
    {req_html}
    <button class="btn" data-topic-filter="{t['id']}">타임테이블에서 이 주제만 보기</button></div>
</details>""")

    # 요구 표
    req_rows = []
    for x in xs:
        for r in x.get("requests", []):
            tp = ", ".join(topics[i]["title"] for i in x.get("topics", []) if i in topics)
            req_rows.append(f'<tr data-member="{E(x["member"])}" data-ans="{E("|".join(x["answerers"]))}" data-topics="{E("|".join(x.get("topics", [])))}">'
                            f'<td class="when"><a href="#{x["id"]}" data-x-go="{x["id"]}">{E(x["start"])}</a> {E(x["member"])}</td>'
                            f'<td>{E(r["to"])}</td><td>{E(r["what"])}</td><td class="when">{E(r.get("due", "-"))}</td><td>{E(tp)}</td></tr>')

    # 타임테이블 필터
    members_seen, ans_count, topic_count = [], {}, {}
    for x in xs:
        if x["member"] not in [m for m, _ in members_seen]:
            members_seen.append((x["member"], x.get("party", "")))
        for a in x["answerers"]:
            ans_count[a] = ans_count.get(a, 0) + 1
        for tid in x.get("topics", []):
            topic_count[tid] = topic_count.get(tid, 0) + 1
    mcount = {m: sum(1 for x in xs if x["member"] == m) for m, _ in members_seen}
    chips_m = "".join(f'<button class="chip" data-g="m" data-v="{E(m)}" aria-pressed="false">{pdot(p)}{E(m)}<small>{mcount[m]}</small></button>' for m, p in members_seen)
    order = c.get("answerer_order", [])
    ans_order = [a for a in order if a in ans_count] + [a for a in ans_count if a not in order]
    chips_a = "".join(f'<button class="chip" data-g="a" data-v="{E(a)}" aria-pressed="false">{E(a)}<small>{ans_count[a]}</small></button>' for a in ans_order)
    chips_t = "".join(f'<button class="chip" data-g="t" data-v="{t["id"]}" aria-pressed="false">{E(t["title"])}<small>{topic_count[t["id"]]}</small></button>' for t in S["topics"] if topic_count.get(t["id"]))
    filters = f"""<div class="filters">
  <div class="fgroup"><span class="lab">발언자</span>{chips_m}</div>
  <div class="fgroup"><span class="lab">답변</span>{chips_a}</div>
  <div class="fgroup"><span class="lab">주제</span>{chips_t}</div>
  <div class="fstat"><span id="fstat"></span><button class="btn sm" id="freset" hidden>필터 지우기</button></div>
</div>"""

    # 타임테이블 행
    events = [("x", x) for x in xs] + [("b", b) for b in S.get("breaks", [])]
    events.sort(key=lambda e: e[1]["start"])
    rows = []
    for kind, ev in events:
        if kind == "b":
            rows.append(f'<div class="row brk"><div class="r-time">{E(ev["start"])}<span>~{E(ev["end"])}</span></div><div>{E(ev["label"])}</div></div>')
            continue
        x = ev
        tags = "".join(f'<button class="tag" data-topic-open="{tid}">{E(topics[tid]["title"])}</button>' for tid in x.get("topics", []) if tid in topics)
        pts = "".join(f"<li>{E(p)}</li>" for p in x.get("points", []))
        if x["kind"] == "report":
            body = f'<details class="more"><summary>9개 기관 보고 요지 펼치기</summary><ul class="pts">{pts}</ul></details>'
        else:
            body = f'<ul class="pts">{pts}</ul>'
        reqs = "".join(f"<span><b>{E(r['to'])}</b> {E(r['what'])}{' (' + E(r['due']) + ')' if r.get('due') else ''}</span>" for r in x.get("requests", []))
        req_html = f'<div class="req"><b>자료 제출·시정 요구</b>{reqs}</div>' if reqs else ""
        rows.append(f"""<article class="row k-{x['kind']}" id="{x['id']}" data-member="{E(x['member'])}" data-ans="{E('|'.join(x['answerers']))}" data-topics="{E('|'.join(x.get('topics', [])))}">
  <div class="r-time">{E(x['start'])}<span>~{E(x['end'])}</span></div>
  <div class="r-body">
    <div class="r-head"><span class="kind">{KIND.get(x['kind'], x['kind'])}</span>{member_label(x)}<span class="to">→ {E(', '.join(x['answerers']))}</span></div>
    {f'<div class="tags">{tags}</div>' if tags else ''}
    {body}{req_html}
    <div class="links"><button class="btn sm" data-tx-go="{E(x['start'])}">전사본 {E(x['start'])}</button>
      <a class="yt" href="{yt_url(x['start'])}" target="_blank" rel="noopener">유튜브 {E(x['start'])}</a></div>
  </div></article>""")
    now_txt = S.get("final_note") or f'여기까지 전사·요약 반영됨 (요약 기준 {S.get("updated", "-")[-5:]}, 약 10분 간격 갱신)'
    rows.append(f'<div class="row now"><div class="r-time">{E(last)}</div><div>{E(now_txt)}</div></div>')

    # 전사본: 시 단위 묶음 + 발언 표지
    marks = {x["start"] + ":00": x for x in xs}
    pending = sorted(marks)
    hours, horder = {}, []
    for t, txt in lines:
        if t == "gap":
            key = horder[-1] if horder else "기타"
            hours.setdefault(key, []).append(f'<span class="gap">{E(txt)}</span>')
            continue
        key = t[:2]
        if key not in hours:
            hours[key] = []
            horder.append(key)
        while pending and pending[0] <= t:
            x = marks[pending.pop(0)]
            tp = " · ".join(topics[i]["title"] for i in x.get("topics", []) if i in topics)
            hours[key].append(f'<div class="mark" id="m_{x["id"]}"><b>{E(x["start"])} {E(x["member"])} {KIND.get(x["kind"], "")}</b>'
                              f'{f"<span>{E(tp)}</span>" if tp else ""}'
                              f'<a href="#{x["id"]}" data-x-go="{x["id"]}">타임테이블</a>'
                              f'<a class="yt" href="{yt_url(x["start"])}" target="_blank" rel="noopener">유튜브</a></div>')
        hours[key].append(f'<p data-t="{t}"><a class="t" href="{yt_url(t)}" target="_blank" rel="noopener" title="유튜브에서 이 시점 보기(±10초)">{t}</a><span>{E(txt)}</span></p>')
    tx = []
    for i, h in enumerate(horder):
        latest = i == len(horder) - 1
        n = sum(1 for v in hours[h] if v.startswith("<p"))
        tx.append(f'<details class="hour"{" open data-latest" if latest else ""}><summary>{h}시 대<span>{n}문장</span></summary><div class="tx">{"".join(hours[h])}</div></details>')

    sc = status_class(status)
    nq = sum(1 for x in xs if x["kind"] == "question")
    return f"""<title>국감록 교육위 10·21</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@700&family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans+KR:wght@400;600&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="top">
  <div class="brand">{E(c.get("brand", "국감록"))}<span>{E(c.get("brand_sub", ""))}</span></div>
  <div class="eyebrow">{E(c["session"])} · {E(c["date_label"])}</div>
  <h1>교육위원회 국정감사 — 부산대학교 등 9개 국립대</h1>
  <div class="meta">
    <span class="pill {sc}"><i class="dot"></i>{E(status)}</span>
    <span>요약 {E(S.get("updated", "-")[-5:])} 기준 · {E(S.get("covered", "-"))}</span>
    <span>전사 {E(last)}까지 · 페이지 {now:%H:%M}</span>
  </div>
  <p class="note">AI 자동 전사·요약본입니다. 이름·수치를 잘못 알아들었을 수 있고, 발언자는 위원장 호명으로 추정했습니다. 공식 회의록이 아닙니다.</p>
  {info}
</header>
<nav class="tabs" role="tablist" aria-label="보기 선택">
  <button class="tab" role="tab" data-view="topics" aria-selected="true">주제별<small>{len(S["topics"])}</small></button>
  <button class="tab" role="tab" data-view="timeline" aria-selected="false">타임테이블<small>{len(xs)}</small></button>
  <button class="tab" role="tab" data-view="transcript" aria-selected="false">전사본<small>{sum(1 for t, _ in lines if t != "gap")}</small></button>
</nav>
<section class="view" id="v-topics">
  <p class="lead">{E(S.get("lead", ""))}</p>
  {f'<p class="note">{E(S["pending"])}</p>' if S.get("pending") else ""}
  <h2>논의 주제 <small>카드를 누르면 상세 내용과 관련 발언이 열립니다</small></h2>
  <div class="topics">{"".join(cards)}</div>
  <h2>자료 제출·시정 요구 <small>{len(req_rows)}건</small></h2>
  <div class="tbl"><table id="reqs"><thead><tr><th>요구</th><th>대상</th><th>내용</th><th>기한</th><th>주제</th></tr></thead><tbody>{"".join(req_rows)}</tbody></table></div>
</section>
<section class="view" id="v-timeline" hidden>
  <h2>타임테이블 <small>질의 {nq}건 · 발언자·답변기관·주제로 거를 수 있습니다</small></h2>
  {filters}
  <div class="tl" id="tl">{"".join(rows)}</div>
</section>
<section class="view" id="v-transcript" hidden>
  <h2>자동 전사본 <small>3분 단위, 약 5분 지연 · 시각을 누르면 유튜브 해당 시점으로</small></h2>
  <div class="search"><label for="q" class="note">본문 검색</label>
    <input id="q" type="search" placeholder="예: 통합, 감사, 등록금" autocomplete="off"><output id="qcount"></output></div>
  <div>{"".join(tx) or '<p class="note">전사 대기 중</p>'}</div>
</section>
<footer>
  <span>자료원: 국회 의사중계시스템 생중계·퀵VOD 음성(유튜브 국회방송 생중계와 같은 회의). 유튜브 시점은 방송 시작 {YT_START:%H:%M:%S} 기준으로 계산(±10초).</span>
  <span>전사: Whisper large-v3-turbo(faster-whisper) · 요약: Claude, 약 10분 간격 갱신</span>
  <span>국회에서 공개적으로 한 진술은 저작권법 제24조에 따라 자유롭게 이용할 수 있습니다.</span>
</footer>
</div>
<script>{JS}</script>
"""


def build_readme(S, status, last, now):
    c = CFG
    topics = {t["id"]: t for t in S["topics"]}
    xs = sorted(S["exchanges"], key=lambda x: x["start"])
    tp = "\n".join(f"- **{t['title']}** — {t['short']}" for t in S["topics"])
    tl = "\n".join(f"| {x['start']}~{x['end']} | {KIND.get(x['kind'], '')} | {x['member']}{(' ' + x['role']) if x.get('role') else ''} | "
                   f"{', '.join(x['answerers'])} | {', '.join(topics[i]['title'] for i in x.get('topics', []) if i in topics)} | "
                   f"[▶]({yt_url(x['start'])}) |" for x in xs)
    rq = "\n".join(f"| {x['start']} {x['member']} | {r['to']} | {r['what']} | {r.get('due', '-')} |"
                   for x in xs for r in x.get("requests", []))
    detail = "\n\n".join(f"### {x['start']} {x['member']}{(' ' + x['role']) if x.get('role') else ''} ({KIND.get(x['kind'], '')}) → {', '.join(x['answerers'])}\n"
                         + "\n".join(f"- {p}" for p in x.get("points", [])) for x in xs)
    tfile = c["transcript_file"]
    return f"""# {c['title']}

> {c['subtitle']}
> 생중계: [YouTube 국회방송]({c['youtube']}) · [국회 의사중계시스템](https://assembly.webcast.go.kr/main/player.asp?xcode={c['xcode']})
> ⚠️ AI 자동 전사·요약본. 고유명사·수치 오인식 가능, 발언자는 사회자 호명으로 추정. **공식 회의록이 아님.**

**HTML 보기(주제별·타임테이블·전사본·유튜브 연결)**: [docs/index.html](docs/index.html) — 저장소 공개 후 GitHub Pages로 게시 가능

| 항목 | 상태 |
|---|---|
| 페이지 갱신 | {now:%Y-%m-%d %H:%M} KST |
| 회의 상태(국회 중계 기준) | {status} |
| 전사 완료 시점 | {last} |
| 요약 기준 / 반영 구간 | {S.get('updated', '-')} / {S.get('covered', '-')} |

## 1. 개요

{S.get('lead', '')}
{('> ' + S['pending']) if S.get('pending') else ''}

## 2. 논의 주제

{tp}

## 3. 타임테이블

| 시각 | 구분 | 발언자 | 답변 | 주제 | 유튜브 |
|---|---|---|---|---|---|
{tl}

## 4. 자료 제출·시정 요구

| 요구 | 대상 | 내용 | 기한 |
|---|---|---|---|
{rq}

## 5. 발언 요지

{detail}

## 자료

- 전체 자동 전사본(실시간): [{tfile}]({tfile})
- 오전 보강 전사본(10:02~11:23): [{tfile.replace('.md', '_오전보강.md')}]({tfile.replace('.md', '_오전보강.md')})
- 수집·전사·게시 스크립트: [scripts/](scripts/)

## 방법 및 한계

1. 자료원: 국회 의사중계시스템 HLS 생중계·퀵VOD 음성(유튜브 국회방송 생중계와 같은 회의). 클라우드 서버에서 유튜브가 차단돼 국회 공식 스트림 사용.
2. 전사: Whisper large-v3-turbo(faster-whisper, int8 CPU), 3분 단위, 무음 구간 제거.
3. 요약: Claude가 약 10분 간격으로 새 전사분을 읽고 주제·발언 단위로 정리.
4. 유튜브 시점: 생중계 HLS 재생목록의 절대시각으로 역산한 방송 시작({c['youtube_start']}) 기준. 오차 ±10초.
5. 한계: 화자 분리 미적용, 동시 발언 누락, 수집 공백은 전사본에 ⚠️로 표기. 회의장에서 재생한 보도 영상은 생략.
6. 국회에서 공개적으로 한 진술은 저작권법 제24조에 따라 자유롭게 이용 가능.
"""


def main():
    now = dt.datetime.now(KST)
    S = json.load(open(os.path.join(REPO, "summary", "summary.json"), encoding="utf-8"))
    status, last, lines = live_status(), last_transcribed(), transcript_lines()
    frag = build(S, status, last, lines, now)
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
