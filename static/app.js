/* 3차원 측정데이터 AI 대시보드 — 외부 라이브러리 없이 순수 JS + SVG */
"use strict";
const $ = (s) => document.querySelector(s);
const el = (id) => document.getElementById(id);

const KO = {
  section:"공정/섹션", dim_id:"측정ID", char_type:"특성", feature:"측정부위", axis:"축",
  nominal:"기준값", tol_plus:"+공차", tol_minus:"-공차", meas:"측정값", dev:"편차",
  outtol:"공차초과", tol_used_pct:"소진율%", judge:"판정", direction:"방향"
};
const COLS = ["section","dim_id","char_type","feature","axis","nominal","tol_plus",
  "tol_minus","meas","dev","outtol","tol_used_pct","judge","direction"];

let DATA = { table: [], analytics: null };

/* ---------- 업로드 ---------- */
const dz = el("dropzone"), fi = el("fileInput");
dz.addEventListener("click", () => fi.click());
fi.addEventListener("change", () => fi.files.length && upload(fi.files));
["dragover","dragenter"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.add("drag"); }));
["dragleave","drop"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", ev => { if (ev.dataTransfer.files.length) upload(ev.dataTransfer.files); });
el("btnSample").addEventListener("click", () => post("/api/sample"));

function upload(files) {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  post("/api/analyze", fd);
}
async function post(url, body) {
  el("loading").hidden = false;
  try {
    const r = await fetch(url, { method:"POST", body });
    const j = await r.json();
    if (j.error) { showUploadError(j); return; }
    DATA = j; render();
  } catch (e) { alert("요청 실패: " + e); }
  finally { el("loading").hidden = true; }
}
function showUploadError(j) {
  let msg = "❌ " + (j.error || "분석 실패");
  if (j.debug) {
    const d = j.debug;
    msg += `\n\n[진단] 추출된 줄 ${d["추출_줄수"]}개 · DIM정의 ${d["DIM정의_줄"]}개 · 축데이터 ${d["축데이터_줄"]}개`;
    if ((d["추출_줄수"]||0) === 0)
      msg += "\n→ PDF에서 글자가 안 뽑혔어요(스캔/이미지 PDF일 수 있음).";
    else if ((d["DIM정의_줄"]||0) === 0)
      msg += "\n→ 측정 양식이 예상과 달라요. 아래 샘플을 캡처해서 알려주세요.";
    msg += "\n\n[추출 샘플]\n" + (d["샘플"]||[]).slice(0,20).join("\n");
  }
  const box = el("uploadMsg");
  box.hidden = false; box.textContent = msg;
}

/* ---------- 렌더 ---------- */
let curFilter = "all", curSearch = "";
function render() {
  el("kpis").hidden = false; el("main").hidden = false;
  el("btnExcel").disabled = false;
  renderKPI(); renderInsights(); renderTable(); renderCharts();
  el("main").scrollIntoView({ behavior:"smooth", block:"start" });
}
function renderKPI() {
  const k = DATA.analytics.kpi;
  el("kpis").innerHTML = [
    ["total", k.total, "총 측정항목", ""],
    ["ng", k.ng, `불합격 (${k.ng_rate}%)`, "ng"],
    ["risk", k.risk, "위험(예비불량)", "risk"],
    ["ok", k.ok, "합격", "ok"],
    ["sec", k.sections, "공정 수", ""],
  ].map(([_,v,l,c]) => `<div class="kpi ${c}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
}
function renderInsights() {
  el("insights").innerHTML = DATA.analytics.insights.map(t => `<li>${esc(t)}</li>`).join("");
}

function renderTable() {
  const th = $("#dataTable thead"), tb = $("#dataTable tbody");
  th.innerHTML = "<tr>" + COLS.map(c => `<th>${KO[c]||c}</th>`).join("") + "</tr>";
  let rows = DATA.table;
  if (curFilter === "ng") rows = rows.filter(r => r.judge === "NG");
  if (curFilter === "risk") rows = rows.filter(r => r.judge === "OK" && num(r.tol_used_pct) >= 70);
  if (curSearch) {
    const q = curSearch.toLowerCase();
    rows = rows.filter(r => (r.section+r.feature+r.dim_id+r.char_type).toLowerCase().includes(q));
  }
  el("rowcount").textContent = `${rows.length}행`;
  tb.innerHTML = rows.map(r => {
    const pct = num(r.tol_used_pct);
    const cls = r.judge === "NG" ? "ng" : (r.judge === "OK" && pct >= 70 ? "risk" : "");
    return `<tr class="${cls}">` + COLS.map(c => {
      if (c === "judge") return `<td class="${r.judge==='NG'?'badge-ng':'badge-ok'}">${r.judge}</td>`;
      if (c === "tol_used_pct") return `<td class="bar-cell">${bar(pct)}</td>`;
      let v = r[c]; if (typeof v === "number") v = (Math.round(v*1000)/1000);
      return `<td>${v===""||v==null?"":v}</td>`;
    }).join("") + "</tr>";
  }).join("");
}
function bar(pct) {
  if (isNaN(pct)) return "";
  const w = Math.min(100, pct), col = pct>=100?"var(--red)":pct>=70?"var(--amber)":"var(--green)";
  return `<div class="bar-bg"><div class="bar-fill" style="width:${w}%;background:${col}"></div></div>
          <span class="muted">${pct}%</span>`;
}
document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active"); curFilter = t.dataset.filter; renderTable();
}));
el("search").addEventListener("input", e => { curSearch = e.target.value; renderTable(); });
el("btnExcel").addEventListener("click", () => location.href = "/api/excel");

/* ---------- 차트 (순수 SVG) ---------- */
function renderCharts() {
  const a = DATA.analytics;
  el("chartTrend").innerHTML = trendChart(a.trend);
  el("chartPareto").innerHTML = paretoChart(a.pareto);
  el("chartDist").innerHTML = distChart(a.dist);
  el("chartBias").innerHTML = biasChart(a.bias);
}
const W=380,H=200,PAD={l:42,r:30,t:14,b:54};
const IW=W-PAD.l-PAD.r, IH=H-PAD.t-PAD.b;
function svg(inner){return `<svg viewBox="0 0 ${W} ${H}">${inner}</svg>`;}
function txt(x,y,s,o={}){return `<text x="${x}" y="${y}" fill="${o.c||'#8aa0bb'}" font-size="${o.s||10}" text-anchor="${o.a||'middle'}" ${o.r?`transform="rotate(${o.r} ${x} ${y})"`:''}>${esc(s)}</text>`;}

function paretoChart(p){
  if(!p.labels||!p.labels.length) return empty("불합격 없음 🎉");
  const max=Math.max(...p.counts), bw=IW/p.labels.length;
  let s="";
  // y축
  for(let i=0;i<=4;i++){const v=Math.round(max*i/4),y=PAD.t+IH-IH*i/4;
    s+=`<line x1="${PAD.l}" y1="${y}" x2="${W-PAD.r}" y2="${y}" stroke="#26344a"/>`+txt(PAD.l-6,y+3,v,{a:'end'});}
  p.counts.forEach((c,i)=>{const h=IH*c/max,x=PAD.l+bw*i+bw*.15,y=PAD.t+IH-h;
    s+=`<rect x="${x}" y="${y}" width="${bw*.7}" height="${h}" fill="#ef4444" rx="2"/>`;
    s+=txt(x+bw*.35,y-3,c,{c:'#e7edf5'});
    s+=txt(PAD.l+bw*i+bw*.5,H-PAD.b+12,short(p.labels[i],10),{s:8,r:35});});
  // 누적선
  const pts=p.cum.map((v,i)=>`${PAD.l+bw*i+bw*.5},${PAD.t+IH-IH*v/100}`).join(" ");
  s+=`<polyline points="${pts}" fill="none" stroke="#3b82f6" stroke-width="2"/>`;
  p.cum.forEach((v,i)=>{s+=`<circle cx="${PAD.l+bw*i+bw*.5}" cy="${PAD.t+IH-IH*v/100}" r="3" fill="#3b82f6"/>`;});
  s+=`<line x1="${PAD.l}" y1="${PAD.t+IH*.2}" x2="${W-PAD.r}" y2="${PAD.t+IH*.2}" stroke="#64748b" stroke-dasharray="3"/>`;
  return svg(s);
}
function distChart(d){
  if(!d.labels) return empty("데이터 없음");
  const max=Math.max(1,...d.ok.map((v,i)=>v+d.ng[i])), bw=IW/d.labels.length;
  let s="";
  for(let i=0;i<=4;i++){const y=PAD.t+IH-IH*i/4;s+=`<line x1="${PAD.l}" y1="${y}" x2="${W-PAD.r}" y2="${y}" stroke="#26344a"/>`+txt(PAD.l-6,y+3,Math.round(max*i/4),{a:'end'});}
  // 위험구간(70~100) 음영
  const x70=PAD.l+IW*(70/200),x100=PAD.l+IW*(100/200);
  s+=`<rect x="${x70}" y="${PAD.t}" width="${x100-x70}" height="${IH}" fill="#f59e0b" opacity=".12"/>`;
  s+=`<line x1="${x100}" y1="${PAD.t}" x2="${x100}" y2="${PAD.t+IH}" stroke="#fff" stroke-dasharray="3"/>`;
  d.labels.forEach((lb,i)=>{
    const okH=IH*d.ok[i]/max,ngH=IH*d.ng[i]/max,x=PAD.l+bw*i+1,bwi=bw-2;
    let y=PAD.t+IH-okH;s+=`<rect x="${x}" y="${y}" width="${bwi}" height="${okH}" fill="#22c55e"/>`;
    y-=ngH;s+=`<rect x="${x}" y="${y}" width="${bwi}" height="${ngH}" fill="#ef4444"/>`;
    if(i%2===0)s+=txt(x+bwi/2,H-PAD.b+12,lb,{s:8});});
  s+=txt(W-PAD.r,H-6,"공차 소진율(%)",{a:'end',s:9});
  s+=legend(W-150,PAD.t,[["#22c55e","합격"],["#ef4444","불합격"]]);
  return svg(s);
}
function biasChart(b){
  if(!b.labels||!b.labels.length) return empty("데이터 없음");
  const vals=b.values,max=Math.max(10,...vals.map(Math.abs)),n=vals.length;
  const rh=Math.min(16,(IH)/n),x0=PAD.l+IW/2;
  let s=`<line x1="${x0}" y1="${PAD.t}" x2="${x0}" y2="${PAD.t+IH}" stroke="#64748b"/>`;
  vals.forEach((v,i)=>{const y=PAD.t+i*(IH/n)+2,w=(IW/2)*Math.abs(v)/max;
    const col=Math.abs(v)>50?"#ef4444":Math.abs(v)>30?"#f59e0b":"#22c55e";
    const x=v<0?x0-w:x0;
    s+=`<rect x="${x}" y="${y}" width="${w}" height="${rh-3}" fill="${col}" rx="2"/>`;
    s+=txt(v<0?x-3:x+w+3,y+rh-5,`${v}%`,{a:v<0?'end':'start',s:8,c:'#cbd5e1'});
    s+=txt(PAD.l-4,y+rh-5,short(b.labels[i],11),{a:'end',s:8});});
  s+=txt(x0,H-8,"← 작게 가공 | 크게 가공 →",{s:9});
  return svg(s);
}
function trendChart(t){
  const b=t&&t.bore;
  if(!b||!b.blocks||b.blocks.length<1) return empty("반복 측정 데이터 부족(추세는 회차가 쌓일수록 정확)");
  // 모든 점 모으기
  let all=[]; Object.values(b.scatter).forEach(arr=>arr.forEach(p=>all.push(p[0])));
  if(b.tol!=null) all.push(b.tol,-Math.abs(b.tol));
  const mn=Math.min(...all,0),mx=Math.max(...all),rng=(mx-mn)||1;
  const xs=b.blocks,xmin=Math.min(...xs),xmax=Math.max(...xs),xr=(xmax-xmin)||1;
  const X=v=>PAD.l+IW*(v-xmin)/xr, Y=v=>PAD.t+IH-IH*(v-mn)/rng;
  let s="";
  for(let i=0;i<=4;i++){const val=mn+rng*i/4,y=Y(val);
    s+=`<line x1="${PAD.l}" y1="${y}" x2="${W-PAD.r}" y2="${y}" stroke="#26344a"/>`+txt(PAD.l-6,y+3,val.toFixed(3),{a:'end',s:8});}
  if(b.tol!=null){const yt=Y(b.tol);
    s+=`<line x1="${PAD.l}" y1="${yt}" x2="${W-PAD.r}" y2="${yt}" stroke="#ef4444" stroke-dasharray="4"/>`+txt(W-PAD.r,yt-3,`상한 +${b.tol}`,{a:'end',c:'#ef4444',s:8});}
  // 산점
  Object.entries(b.scatter).forEach(([blk,arr])=>arr.forEach(p=>{
    s+=`<circle cx="${X(+blk)}" cy="${Y(p[0])}" r="3" fill="${p[1]==='NG'?'#ef4444':'#3b82f6'}" opacity=".7"/>`;}));
  // 평균 추세선
  const pts=xs.map((x,i)=>`${X(x)},${Y(b.mean[i])}`).join(" ");
  s+=`<polyline points="${pts}" fill="none" stroke="#f59e0b" stroke-width="2.5"/>`;
  xs.forEach((x,i)=>{s+=`<circle cx="${X(x)}" cy="${Y(b.mean[i])}" r="4" fill="#f59e0b"/>`;
    s+=txt(X(x),H-PAD.b+14,`${i+1}회차`,{s:9});});
  s+=legend(W-150,PAD.t,[["#f59e0b","회차 평균"],["#ef4444","규격초과 점"]]);
  return svg(s);
}
function legend(x,y,items){return items.map((it,i)=>`<rect x="${x}" y="${y+i*14}" width="9" height="9" fill="${it[0]}" rx="2"/>`+txt(x+13,y+i*14+8,it[1],{a:'start',s:9})).join("");}
function empty(msg){return `<div class="muted" style="padding:24px;text-align:center">${esc(msg)}</div>`;}

/* ---------- AI ---------- */
el("btnAuto").addEventListener("click", () => ai(""));
el("btnAsk").addEventListener("click", () => { ai(el("aiMsg").value); el("aiMsg").value=""; });
el("aiMsg").addEventListener("keydown", e => { if(e.key==="Enter"){ ai(e.target.value); e.target.value=""; }});
async function ai(message) {
  if (!DATA.analytics) { alert("먼저 데이터를 분석하세요."); return; }
  const out = el("aiOut"); out.textContent = "🤖 생각 중…";
  try {
    const r = await fetch("/api/ai", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ message }) });
    const j = await r.json();
    out.textContent = j.answer;
    const bdg = el("aiState");
    bdg.textContent = j.configured ? "연결됨" : "미연결";
    bdg.className = "badge " + (j.configured ? "on" : "off");
  } catch(e){ out.textContent = "AI 호출 실패: " + e; }
}

/* ---------- AI 설정/연결 ---------- */
async function loadAiStatus() {
  try {
    const s = await (await fetch("/api/ai/status")).json();
    if (s.url) el("cfgUrl").value = s.url;
    if (s.model) el("cfgModel").value = s.model;
    if (s.provider) el("cfgProvider").value = s.provider;
    setAiBadge(s.configured, s.configured ? "연결됨(설정 있음)" : "미설정");
  } catch(e){ setAiBadge(false, "상태 확인 실패"); }
}
function setAiBadge(on, text) {
  const b = el("aiState");
  b.textContent = text; b.className = "badge " + (on ? "on" : "off");
}
function cfgPayload() {
  return {
    base_url: el("cfgUrl").value.trim(),
    api_key: el("cfgKey").value.trim(),
    model: el("cfgModel").value.trim(),
    provider: el("cfgProvider").value,
    auth_header: el("cfgAuth").value.trim(),
  };
}
el("btnSave").addEventListener("click", async () => {
  const s = await (await fetch("/api/ai/config", {method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify(cfgPayload())})).json();
  el("cfgResult").textContent = "저장됨.";
  setAiBadge(s.configured, s.configured ? "설정 저장됨" : "URL/Key 필요");
});
el("btnTest").addEventListener("click", async () => {
  el("cfgResult").textContent = "🔌 연결 테스트 중…";
  setAiBadge(false, "테스트 중…");
  const r = await (await fetch("/api/ai/test", {method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify(cfgPayload())})).json();
  el("cfgResult").textContent = (r.ok ? "✅ " : "❌ ") + r.detail;
  setAiBadge(r.ok, r.ok ? "연결됨 ✅" : "연결 실패");
});
loadAiStatus();

/* ---------- util ---------- */
function num(v){const n=parseFloat(v);return isNaN(n)?NaN:n;}
function short(s,n){s=String(s);return s.length>n?s.slice(0,n-1)+"…":s;}
function esc(s){return String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}
