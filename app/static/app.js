/* Skeptic UI: vanilla JS, no build step. All model/user text is escaped before it touches the DOM. */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtP = (p) => (p === null || p === undefined ? "n/a" : Number(p).toFixed(4));
const bps = (v) => (v === null || v === undefined ? "n/a" : `${v > 0 ? "+" : ""}${v}`);

const S = {
  sid: null,
  config: null,
  hunch: "",
  spec: null,            // proposed or edited card (object)
  originalSpec: null,    // as proposed / as last approved, to detect edits
  approved: null,        // approve response
  attacks: null,         // attack response
  vault: null,           // vault result
  history: null,
  library: [],
  suggestions: [],       // layer 2
  ghost: "",
};

// ------------------------------------------------------------------ api
async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.body ? "POST" : "GET",
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
    signal: opts.signal,
  });
  let data = null;
  try { data = await res.json(); } catch { data = {}; }
  if (!res.ok) {
    const err = new Error(data.error || data.detail || `HTTP ${res.status}`);
    err.status = res.status; err.data = data;
    throw err;
  }
  return data;
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3200);
}

function loader(text) { return `<div class="loader"><div class="spinner"></div>${esc(text)}</div>`; }
function errorBox(e) { return `<div class="error-box">${esc(e.message || e)}</div>`; }
function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }

// ------------------------------------------------------------------ boot
async function boot() {
  try { S.sid = sessionStorage.getItem("skeptic_sid"); } catch { /* storage blocked */ }
  S.config = await api(`/api/config${S.sid ? `?session_id=${S.sid}` : ""}`);
  if (!S.sid) {
    S.sid = S.config.new_session_id;
    try { sessionStorage.setItem("skeptic_sid", S.sid); } catch { /* ignore */ }
  }
  $("#model-badge").textContent = S.config.models.reason;
  setChain(S.config.chain);
  try { S.library = (await api("/api/library")).hunches || []; } catch { S.library = []; }
  refreshHistory();
  wireTabs();
  wireHunch();
  $("#drawer-close").onclick = () => $("#drawer").classList.remove("open");
  $("#verify-btn").onclick = async () => { setChain(await api("/api/ledger/verify")); renderLog(); };
  $("#media").onchange = onMedia;
}

function setChain(v) {
  const b = $("#chain-badge");
  if (v && v.ok) { b.className = "badge ok"; b.textContent = `Log intact ✓ · ${v.entries}`; }
  else { b.className = "badge bad"; b.textContent = `Log tampered ✗ at #${v ? v.first_bad_seq : "?"}`; }
  b.title = v && !v.ok ? v.reason : "Hash chain verified from disk";
}
async function refreshChain() { try { setChain(await api("/api/ledger/verify")); } catch { /* offline */ } }

function wireTabs() {
  document.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => {
      document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
      ["test", "history", "log"].forEach((name) => $(`#tab-${name}`).classList.toggle("hidden", name !== t.dataset.tab));
      if (t.dataset.tab === "history") renderHistory();
      if (t.dataset.tab === "log") renderLog();
    };
  });
}

// ------------------------------------------------------------------ autocomplete (layer 1: local, layer 2: Flash-Lite)
const STOP = new Set("a an the of to after when if and or for on in is it by be at as with over its than more then".split(" "));
const tokens = (s) => new Set(String(s).toLowerCase().replace(/[^a-z0-9%.\- ]/g, " ").split(/\s+/).filter((w) => w && !STOP.has(w)));
function jaccard(a, b) {
  const A = tokens(a), B = tokens(b);
  if (!A.size || !B.size) return 0;
  let inter = 0; A.forEach((x) => { if (B.has(x)) inter++; });
  return inter / (A.size + B.size - inter);
}

function layer1(q) {
  const ql = q.trim().toLowerCase();
  if (ql.length < 2) return [];
  const past = (S.history?.hunches || []).map((h) => ({ text: h.text, src: "yours" }));
  const lib = S.library.map((t) => ({ text: t, src: "library" }));
  const seen = new Set();
  return [...past.reverse(), ...lib]
    .map((h) => {
      const t = h.text.toLowerCase();
      const score = t.startsWith(ql) ? 2 + ql.length / t.length : t.includes(ql) ? 1 : jaccard(ql, t);
      return { ...h, score };
    })
    .filter((h) => h.score > 0.34 && !seen.has(h.text) && seen.add(h.text) && h.text.toLowerCase() !== ql)
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
}

function variantWarning(q) {
  const pill = $("#variant-pill");
  const ideas = S.history?.ideas || [];
  let best = null;
  for (const idea of ideas) {
    const sim = jaccard(q, idea.hunch_text);
    if (idea.trials > 0 && sim >= 0.45 && (!best || sim > best.sim)) best = { ...idea, sim };
  }
  if (!best || q.trim().length < 12) { pill.classList.add("hidden"); return; }
  const n = best.trials;
  pill.innerHTML = `⚠ You've tested ${n} variant${n === 1 ? "" : "s"} of this idea. The bar is now <span class="mono">p &lt; 0.05/${n} = ${(0.05 / n).toPrecision(2)}</span>`;
  pill.title = `Similar to: "${best.hunch_text}" (token overlap ${(best.sim * 100).toFixed(0)}%, computed in code, not by the model)`;
  pill.classList.remove("hidden");
}

let suggestTimer = null, suggestAbort = null, activeIdx = -1;
function wireHunch() {
  const ta = $("#hunch");
  const autosize = () => { ta.style.height = "auto"; ta.style.height = ta.scrollHeight + "px"; };
  ta.addEventListener("input", () => {
    autosize();
    S.suggestions = []; S.ghost = ""; activeIdx = -1;
    renderSuggest(); renderGhost();
    variantWarning(ta.value);
    clearTimeout(suggestTimer);
    if (suggestAbort) suggestAbort.abort();
    if (ta.value.trim().length >= 15) suggestTimer = setTimeout(() => layer2(ta.value), 400);
  });
  ta.addEventListener("keydown", (e) => {
    const items = [...document.querySelectorAll("#suggest .item")];
    if (e.key === "Tab" && (S.ghost || items.length)) {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) accept(items[activeIdx].dataset.text);
      else if (S.ghost) accept(ta.value + S.ghost);
      else if (items[0]) accept(items[0].dataset.text);
    } else if (e.key === "ArrowDown" && items.length) { e.preventDefault(); activeIdx = (activeIdx + 1) % items.length; highlight(items); }
    else if (e.key === "ArrowUp" && items.length) { e.preventDefault(); activeIdx = (activeIdx - 1 + items.length) % items.length; highlight(items); }
    else if (e.key === "Escape") { hide("#suggest"); }
    else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) accept(items[activeIdx].dataset.text); else submitHunch();
    }
  });
  ta.addEventListener("focus", renderSuggest);
  ta.addEventListener("blur", () => setTimeout(() => hide("#suggest"), 150));
  $("#go").onclick = submitHunch;
}
function highlight(items) { items.forEach((it, i) => it.classList.toggle("active", i === activeIdx)); }
function accept(text) {
  const ta = $("#hunch");
  ta.value = text; ta.dispatchEvent(new Event("input")); ta.focus();
  ta.setSelectionRange(text.length, text.length);
}

async function layer2(q) {
  suggestAbort = new AbortController();
  try {
    const out = await api(`/api/suggest?q=${encodeURIComponent(q)}&session_id=${S.sid}`, { signal: suggestAbort.signal });
    if ($("#hunch").value !== q) return; // stale
    S.suggestions = out.completions || [];
    const first = S.suggestions.find((c) => c.toLowerCase().startsWith(q.toLowerCase()));
    S.ghost = first ? first.slice(q.length) : "";
    renderSuggest(); renderGhost();
  } catch (e) { if (e.name !== "AbortError") { S.suggestions = []; renderSuggest(); } }
}

function renderGhost() {
  const q = $("#hunch").value;
  $("#hunch-ghost").innerHTML = S.ghost ? `${esc(q)}<span class="rest">${esc(S.ghost)}</span>` : "";
}

function renderSuggest() {
  const q = $("#hunch").value;
  const box = $("#suggest");
  const l1 = layer1(q);
  const l2 = S.suggestions.filter((s) => s.toLowerCase() !== q.toLowerCase());
  if (!l1.length && !l2.length || document.activeElement !== $("#hunch")) { box.classList.add("hidden"); return; }
  let html = "";
  if (l2.length) html += `<div class="group"><div class="label">Gemini · ${esc(S.config.models.router)} · precise wording</div>${l2.map((t) => `<div class="item" data-text="${esc(t)}">${esc(t)}</div>`).join("")}</div>`;
  if (l1.length) html += `<div class="group"><div class="label">Instant · your hunches + library (no AI)</div>${l1.map((h) => `<div class="item" data-text="${esc(h.text)}">${esc(h.text)}<span class="hint">${h.src}</span></div>`).join("")}</div>`;
  box.innerHTML = html;
  box.classList.remove("hidden");
  box.querySelectorAll(".item").forEach((it) => it.addEventListener("mousedown", (e) => { e.preventDefault(); accept(it.dataset.text); }));
}

// ------------------------------------------------------------------ step 1-2: hunch -> questions -> rule card
function resetBelow(fromId) {
  const order = ["#sec-questions", "#sec-rule", "#sec-attacks", "#sec-vault", "#sec-verdict"];
  order.slice(order.indexOf(fromId)).forEach((id) => { hide(id); $(id).innerHTML = ""; });
}

async function submitHunch() {
  const text = $("#hunch").value.trim();
  if (!text) return;
  hide("#suggest");
  S.hunch = text; S.spec = null; S.approved = null; S.attacks = null; S.vault = null;
  resetBelow("#sec-questions");
  const sec = $("#sec-questions"); show("#sec-questions");
  sec.innerHTML = loader(`${S.config.models.reason} is reading your hunch…`);
  try {
    const out = await api("/api/hunch", { body: { session_id: S.sid, hunch: text } });
    handleTranslate(out);
  } catch (e) { sec.innerHTML = errorBox(e); }
  refreshChain(); refreshHistory();
}

function handleTranslate(out) {
  if (out.questions) return renderQuestions(out);
  hide("#sec-questions");
  S.spec = out.spec; S.originalSpec = JSON.parse(JSON.stringify(out.spec));
  renderRuleCard(out);
}

function renderQuestions(out) {
  const sec = $("#sec-questions");
  const answers = {};
  sec.innerHTML = `
    <div class="section-head"><span class="step-no">02</span><h2>A few questions first</h2>
      <span class="muted small">Your hunch is ambiguous in ways that change the result. Gemini asks instead of guessing.</span></div>
    <div class="q-grid">${out.questions.map((q, i) => `
      <div class="q-card" data-q="${i}">
        <div class="q">${esc(q.text)}</div>
        <div class="opts">${q.options.map((o) => `<button class="pill-btn" data-opt="${esc(o)}">${esc(o)}</button>`).join("")}</div>
        <input class="other" placeholder="…or type your own answer">
      </div>`).join("")}
    </div>
    <div class="row" style="margin-top:16px"><button class="btn primary" id="answer-go" disabled>Continue</button>
      <span class="small muted mono">interaction ${esc(out.interaction_id.slice(0, 18))}…</span></div>`;
  const check = () => { $("#answer-go").disabled = Object.keys(answers).length < out.questions.length; };
  sec.querySelectorAll(".q-card").forEach((card) => {
    const q = out.questions[+card.dataset.q];
    card.querySelectorAll(".pill-btn").forEach((b) => b.onclick = () => {
      card.querySelectorAll(".pill-btn").forEach((x) => x.classList.toggle("selected", x === b));
      answers[q.text] = b.dataset.opt; $(".other", card).value = ""; check();
    });
    $(".other", card).oninput = (e) => {
      card.querySelectorAll(".pill-btn").forEach((x) => x.classList.remove("selected"));
      if (e.target.value.trim()) answers[q.text] = e.target.value.trim(); else delete answers[q.text];
      check();
    };
  });
  $("#answer-go").onclick = async () => {
    $("#answer-go").disabled = true;
    sec.insertAdjacentHTML("beforeend", loader("Turning your answers into exact rules…"));
    try { handleTranslate(await api("/api/hunch", { body: { session_id: S.sid, answers } })); }
    catch (e) { sec.insertAdjacentHTML("beforeend", errorBox(e)); }
    refreshChain();
  };
}

// ---- rule card with inline numeric editing
const PARAMS = ["lookback", "window", "fast", "slow"];
function condHTML(c, path) {
  const ps = PARAMS.filter((k) => c[k] !== undefined && c[k] !== null)
    .map((k) => `${k}=<input class="edit" data-path="${path}.${k}" data-int="1" value="${c[k]}">`).join(", ");
  return `${esc(c.feature)}(${ps}) ${esc(c.op)} <input class="edit" data-path="${path}.value" value="${c.value}">`;
}

function renderRuleCard(out) {
  const sp = S.spec;
  const sec = $("#sec-rule"); show("#sec-rule");
  const exits = [];
  if (sp.exit.hold_bars != null) exits.push(`held <input class="edit" data-path="exit.hold_bars" data-int="1" value="${sp.exit.hold_bars}"> bars`);
  if (sp.exit.take_profit != null) exits.push(`up <input class="edit" data-path="exit.take_profit" value="${sp.exit.take_profit}"> from entry`);
  if (sp.exit.stop_loss != null) exits.push(`down <input class="edit" data-path="exit.stop_loss" value="${sp.exit.stop_loss}"> from entry`);
  (sp.exit.any || []).forEach((c, i) => exits.push(condHTML(c, `exit.any.${i}`)));
  const trialsNow = S.approved?.idea_id ? S.approved.trials : 0;
  sec.innerHTML = `
    <div class="section-head"><span class="step-no">03</span><h2>Rule card</h2>
      <span class="muted small">Exactly what will be tested. Edit any number, then approve. Only you can approve.</span></div>
    <div class="rule-card">
      <div class="rule-head">
        <div><h3 class="rule-name">${esc(sp.name)}</h3><div class="small muted">“${esc(sp.hunch_text || S.hunch)}”</div></div>
        <div class="row"><span class="badge mono" id="fp-badge" title="SHA-256 of entry, exit and cooldown only">fp ${esc((out.fingerprint || "").slice(0, 12))}</span>
          <span class="badge" id="trial-badge"></span></div>
      </div>
      <div class="rule-lines">
        <div class="line"><span class="kw">ENTER</span> when ${sp.entry.all.map((c, i) => condHTML(c, `entry.all.${i}`)).join(" <span class='kw'>AND</span> ")}</div>
        <div class="line"><span class="kw">EXIT</span> when ${exits.join(" <span class='kw'>OR</span> ")}</div>
        ${sp.cooldown_bars ? `<div class="line"><span class="kw">WAIT</span> <input class="edit" data-path="cooldown_bars" data-int="1" value="${sp.cooldown_bars}"> bars after an exit</div>` : ""}
        <div class="line muted small" style="margin-top:12px">Long-only · all-in/all-out · decide on bar close, fill at the next bar · thresholds are fractions (−0.05 = −5%)</div>
      </div>
      <h3 style="margin-bottom:6px">Assumptions Gemini made</h3>
      <ul class="assumptions">${(sp.assumptions || []).map((a) => `<li>${esc(a)}</li>`).join("") || "<li class='muted'>none listed</li>"}</ul>
      <div class="row" style="margin-top:22px">
        <button class="btn primary" id="approve-btn">Approve rules</button>
        <span class="small muted" id="approve-note">Approval counts as one trial for this idea.</span>
      </div>
      <div id="rule-error"></div>
    </div>`;
  updateTrialBadge(trialsNow, false);
  sec.querySelectorAll("input.edit").forEach((inp) => inp.addEventListener("change", onEdit));
  $("#approve-btn").onclick = approve;
}

function updateTrialBadge(trials, edited) {
  const b = $("#trial-badge");
  if (!b) return;
  const next = edited || !S.approved ? trials + 1 : trials;
  b.className = next > 1 ? "badge warn" : "badge";
  b.innerHTML = `trial <span class="mono">${next}</span> · bar <span class="mono">p &lt; ${(0.05 / Math.max(1, next)).toPrecision(2)}</span>`;
}

function setPath(obj, path, val) {
  const parts = path.split(".");
  let o = obj;
  for (let i = 0; i < parts.length - 1; i++) o = o[isNaN(parts[i]) ? parts[i] : +parts[i]];
  o[parts[parts.length - 1]] = val;
}

async function onEdit(e) {
  const inp = e.target;
  const v = inp.dataset.int ? parseInt(inp.value, 10) : parseFloat(inp.value);
  if (Number.isNaN(v)) { inp.value = ""; return; }
  setPath(S.spec, inp.dataset.path, v);
  inp.classList.add("changed");
  try {
    const out = await api("/api/spec/preview", { body: { session_id: S.sid, spec: S.spec } });
    $("#fp-badge").textContent = `fp ${out.fingerprint.slice(0, 12)} (edited)`;
    $("#rule-error").innerHTML = "";
    const edited = !S.approved || out.fingerprint !== S.approved.fingerprint;
    $("#approve-btn").textContent = S.approved && edited ? "Approve edited rules (new trial)" : "Approve rules";
    $("#approve-btn").disabled = !edited && !!S.approved;
    updateTrialBadge(S.approved ? S.approved.trials : 0, edited);
  } catch (err) { $("#rule-error").innerHTML = errorBox(err); }
}

async function approve() {
  const btn = $("#approve-btn"); btn.disabled = true;
  const parent = S.approved ? S.approved.fingerprint : null;
  try {
    const out = await api("/api/spec/approve", { body: { session_id: S.sid, spec: S.spec, parent_fingerprint: parent } });
    S.approved = out; S.spec = out.spec; S.attacks = null;
    $("#fp-badge").textContent = `fp ${out.fingerprint.slice(0, 12)} ✓ approved`;
    $("#approve-note").textContent = `Approved by you · idea ${out.idea_id} · ${out.trials} trial${out.trials === 1 ? "" : "s"} so far` + (out.contaminated ? " · ⚠ changed after this idea's vault was used" : "");
    btn.textContent = "Approved";
    updateTrialBadge(out.trials, false);
    document.querySelectorAll("#sec-rule input.edit").forEach((i) => i.classList.remove("changed"));
    refreshHistory(); refreshChain();
    if (S.vault && out.contaminated) { renderVaultAfterEdit(); return; }
    runAttacks();
  } catch (e) { $("#rule-error").innerHTML = errorBox(e); btn.disabled = false; }
}

// ------------------------------------------------------------------ step 3: attacks
async function runAttacks() {
  resetBelow("#sec-attacks");
  const sec = $("#sec-attacks"); show("#sec-attacks");
  sec.innerHTML = `<div class="section-head"><span class="step-no">04</span><h2>Attacks</h2></div>` +
    loader(`Baseline on 300 practice paths → ${S.config.models.reason} pre-registers alternative explanations → shuffled markets, wobble, cost stress, outliers, too-many-tries…`);
  try {
    S.attacks = await api("/api/attack", { body: { session_id: S.sid, fingerprint: S.approved.fingerprint } });
    renderAttacks(); renderVault(); explain();
  } catch (e) { sec.innerHTML += errorBox(e); }
  refreshChain(); refreshHistory();
}

function keyNumber(r) {
  const n = r.numbers;
  switch (r.id) {
    case "A1": return { v: bps(n.median_excess_bps), u: "bps median excess", sub: `95% CI [${n.median_excess_ci95_bps[0]}, ${n.median_excess_ci95_bps[1]}] · sign p ${fmtP(n.sign_p)} · ${n.wins}W/${n.losses}L` };
    case "A2": return { v: fmtP(n.p_perm), u: "p_perm", sub: `K=${n.K} shuffled markets · real ${n.observed_mean_excess_bps} vs shuffled ${n.perm_mean_excess_median_bps} bps` };
    case "A3": return { v: `${n.share_positive_pct}%`, u: "neighbours positive", sub: `${n.neighbours} neighbours · your rule ranks ${n.user_spec_rank}/${n.rank_out_of}` };
    case "A4": return { v: bps(n.median_excess_x2_bps), u: "bps at costs ×2", sub: `×1 ${bps(n.median_excess_x1_bps)} · ×3 ${bps(n.median_excess_x3_bps)} bps` };
    case "A5": return { v: bps(n.median_after_bps), u: "bps without top 5%", sub: `median ${bps(n.median_before_bps)} → ${bps(n.median_after_bps)} · mean ${bps(n.mean_before_bps)} → ${bps(n.mean_after_bps)}` };
    case "A6": return { v: fmtP(n.p_adj), u: "adjusted p", sub: `${n.trials} trial${n.trials === 1 ? "" : "s"} × p_perm ${fmtP(n.p_perm)} · bar p < ${n.bar}` };
    default: {
      if (n.table && n.table[0] && "bucket" in n.table[0]) return { v: `${n.positive_buckets}/${n.buckets}`, u: "groups positive", sub: n.table.map((t) => `${t.bucket} ${bps(t.median_excess_bps)}`).join(" · ") };
      if (n.fold_medians_bps) return { v: `${n.positive_folds}/${n.k}`, u: "folds positive", sub: n.fold_medians_bps.map(bps).join(" · ") + " bps" };
      if ("exposure_pct" in n) return { v: `${n.exposure_pct}%`, u: "time in market", sub: `corr with buy-and-hold ${n.return_correlation_with_bh}` };
      if (n.table && n.table[0] && "hold_bars" in n.table[0]) return { v: `${n.share_positive_pct}%`, u: "holding periods positive", sub: n.table.map((t) => `${t.hold_bars}b ${bps(t.median_excess_bps)}`).join(" · ") };
      if ("multiplier" in n) return { v: bps(n.median_excess_bps), u: `bps at costs ×${n.multiplier}`, sub: `${n.wins}W/${n.losses}L · sign p ${fmtP(n.sign_p)}` };
      if ("median_after_bps" in n) return { v: bps(n.median_after_bps), u: `bps without top ${n.pct}%`, sub: `dropped ${n.dropped_paths} paths` };
      return { v: "", u: "", sub: "" };
    }
  }
}

function chartSVG(c) {
  if (!c || !c.type) return "";
  const W = 300, H = 64;
  if (c.type === "hist" && c.counts?.length) {
    const max = Math.max(...c.counts, 1), bw = W / c.counts.length;
    const lo = c.edges[0], hi = c.edges[c.edges.length - 1];
    const x = (v) => Math.max(0, Math.min(W, ((v - lo) / (hi - lo)) * W));
    const zero = lo < 0 && hi > 0 ? `<line x1="${x(0)}" x2="${x(0)}" y1="0" y2="${H}" stroke="#9ca3af" stroke-dasharray="2 2"/>` : "";
    const marker = c.marker != null ? `<line x1="${x(c.marker)}" x2="${x(c.marker)}" y1="0" y2="${H}" stroke="#111" stroke-width="2"/>` : "";
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(c.label)}">${c.counts.map((n, i) =>
      `<rect x="${i * bw + 1}" y="${H - (n / max) * (H - 4)}" width="${bw - 2}" height="${(n / max) * (H - 4)}" rx="1.5" fill="#d1d5db"/>`).join("")}${zero}${marker}</svg>
      <div class="sub">${esc(c.label)} · <b>│</b> = this rule${zero ? " · ┊ = 0" : ""}</div>`;
  }
  if (c.type === "bars" && c.values?.length) {
    const vals = c.values.map(Number), max = Math.max(...vals.map(Math.abs), 1);
    const bw = W / vals.length, mid = H / 2;
    return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${vals.map((v, i) => {
      const h = (Math.abs(v) / max) * (mid - 4);
      return `<rect x="${i * bw + bw * 0.2}" y="${v >= 0 ? mid - h : mid}" width="${bw * 0.6}" height="${Math.max(1, h)}" rx="2" fill="${v >= 0 ? "#111" : "#ef4444"}"/>`;
    }).join("")}<line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="#d1d5db"/></svg>
      <div class="sub">${c.labels.map((l, i) => `${esc(l)} ${esc(vals[i])}`).join(" · ")}</div>`;
  }
  if (c.type === "wobble") {
    if (!c.joint) return `<div class="sub">one parameter only: no joint grid</div>`;
    const j = c.joint, color = (m) => (m == null ? "#eee" : m > 0 ? `rgba(16,185,129,${0.15 + Math.min(0.6, Math.abs(m) / 400)})` : `rgba(239,68,68,${0.15 + Math.min(0.6, Math.abs(m) / 400)})`);
    const lab = (s) => `${s > 0 ? "+" : ""}${Math.round(s * 100)}%`;
    let html = `<div class="wob-grid"><div class="hdr"></div>${j.steps.map((s) => `<div class="hdr">${lab(s)}</div>`).join("")}`;
    j.grid.forEach((row, i) => {
      html += `<div class="hdr" style="text-align:right">${lab(j.steps[i])}</div>`;
      row.forEach((cell) => {
        const m = cell ? cell.median_excess_bps : null;
        html += `<div class="cell" style="background:${color(m)};${cell?.is_user_spec ? "outline:2px solid #111" : ""}">${m == null ? "–" : m}</div>`;
      });
    });
    return html + `</div><div class="sub">rows: ${esc(j.params[0])} · cols: ${esc(j.params[1])} · median bps · outlined = your rule</div>`;
  }
  return "";
}

function attackCard(r) {
  const k = keyNumber(r);
  const prereg = r.kind === "diagnostic" ? `<div class="prereg"><b>Gemini's alternative explanation (logged before the test ran):</b> ${esc(r.hypothesis)}
      ${r.inputs?.supports_if ? `<div class="small muted" style="margin-top:6px">Supports it if: ${esc(r.inputs.supports_if)}<br>Refutes it if: ${esc(r.inputs.refutes_if)}</div>` : ""}</div>` : "";
  return `<div class="attack" id="card-${r.id}">
    <div class="top"><span class="aid">${r.id}</span><span class="name">${esc(r.name)}</span>
      ${r.kind === "diagnostic" ? `<span class="badge violet">agent-proposed</span>` : ""}
      <span class="badge ${r.passed ? "pass" : "fail"}">${r.passed ? "pass" : "fail"}</span></div>
    <div><span class="key">${esc(k.v)}<span class="unit">${esc(k.u)}</span></span><div class="sub">${esc(k.sub)}</div></div>
    ${chartSVG(r.chart)}
    ${prereg}
    <div class="summary">${esc(r.summary)}</div>
    <div class="foot"><span class="small muted">${esc(r.kind === "diagnostic" ? "diagnostic: " : "gate: ")}${esc(r.threshold)}</span>
      <button class="btn ghost small" data-trace="${r.id}">trace →</button></div>
  </div>`;
}

function renderAttacks() {
  const a = S.attacks, g = a.gate;
  const sec = $("#sec-attacks");
  const tone = g.status === "ELIGIBLE" ? "ok" : g.status === "INCONCLUSIVE" ? "warn" : "bad";
  sec.innerHTML = `
    <div class="section-head"><span class="step-no">04</span><h2>Attacks</h2>
      <span class="muted small">Fixed battery A1–A6 decides the practice gate. D-cards are Gemini's idea-specific challenges, pre-registered before they ran.</span></div>
    <div class="gate"><span class="badge ${tone}">${esc(g.status === "ELIGIBLE" ? "practice: passed" : "practice: " + g.status.toLowerCase())}</span>
      <div><b style="color:var(--ink)">${esc(g.headline)}</b>${g.failing.length ? `<ul>${g.failing.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}
      ${a.plan_error ? `<div class="small muted">Gemini planning unavailable (${esc(a.plan_error)}); the fixed battery still ran.</div>` : ""}</div></div>
    <div class="attack-grid">${[...a.results, ...a.diagnostics].map(attackCard).join("")}</div>`;
  sec.querySelectorAll("[data-trace]").forEach((b) => (b.onclick = () => openTrace(b.dataset.trace)));
}

// ------------------------------------------------------------------ step 4: vault
function renderVault() {
  const sec = $("#sec-vault"); show("#sec-vault");
  const v = S.attacks.vault;
  const opened = S.vault;
  const canTry = v.can_open || v.state === "contaminated";
  sec.innerHTML = `
    <div class="vault">
      <div class="row" style="gap:16px;align-items:flex-start">
        <div class="lock">${opened ? "🔓" : "🔒"}</div>
        <div style="flex:1">
          <h2>The vault</h2>
          <div class="reason">150 price paths this idea has never touched. One shot per idea: the pass mark is written to the log before it opens, and only a human click opens it.</div>
        </div>
      </div>
      <div id="vault-body" style="margin-top:20px">
        ${opened ? vaultTable(opened) : `
        <div class="row"><button class="btn vault-btn" id="vault-btn" ${canTry ? "" : "disabled"}>Open vault (one shot)</button>
        <span class="reason">${esc(v.reason)}</span></div>`}
      </div>
    </div>`;
  const b = $("#vault-btn");
  if (b) b.onclick = openVault;
}

function vaultTable(r) {
  const p = r.practice || {}, v = r.vault;
  const row = (label, a, b) => `<tr><td>${label}</td><td>${a}</td><td>${b}</td></tr>`;
  return `
    <table>
      <tr><th></th><th>Practice (300 paths)</th><th>Vault (${v.paths} paths)</th></tr>
      ${row("Median excess vs buy-and-hold", `${bps(p.median_excess_bps)} bps`, `${bps(v.median_excess_bps)} bps`)}
      ${row("95% CI of median", p.median_excess_ci95_bps ? `[${p.median_excess_ci95_bps.join(", ")}]` : "–", `[${v.median_excess_ci95_bps.join(", ")}]`)}
      ${row("Wins / losses vs B&H", `${p.wins}/${p.losses}`, `${v.wins}/${v.losses}`)}
      ${row("Sign-test p", fmtP(p.sign_p), fmtP(v.sign_p))}
      ${row("Mean max drawdown", `${p.mean_max_drawdown_bps} bps`, `${v.mean_max_drawdown_bps} bps`)}
      ${row("Trades", p.total_trades, v.total_trades)}
    </table>
    <div class="precommit">${r.edge_retained_pct != null ? `Edge retained on unseen data: ${r.edge_retained_pct}% of the practice median. ` : ""}${r.replayed ? "Stored result replayed (never re-run). " : ""}Pass mark pre-committed in the log: median > 0 and sign-test p < 0.05.</div>`;
}

async function openVault() {
  const b = $("#vault-btn"); b.disabled = true;
  try {
    S.vault = await api("/api/vault/open", { body: { session_id: S.sid, fingerprint: S.approved.fingerprint } });
    $("#vault-body").innerHTML = vaultTable(S.vault);
    explain();
  } catch (e) {
    if (e.status === 409) {
      $("#vault-body").insertAdjacentHTML("beforeend", `<div class="block"><b>Blocked.</b> ${esc(e.message)}<div class="small" style="margin-top:6px">Recorded in the audit log as <span class="mono">${e.data.code === "vault_blocked" ? "vault_blocked" : esc(e.data.code)}</span>. Open the Log tab to see it.</div></div>`);
    } else $("#vault-body").insertAdjacentHTML("beforeend", errorBox(e));
  }
  refreshChain(); refreshHistory();
}

function renderVaultAfterEdit() {
  // the edited card belongs to an idea that already used its vault: show the vault so the user can try (and be refused)
  S.attacks = { ...(S.attacks || {}), vault: { state: "contaminated", can_open: false, reason: "This version was changed after the idea's vault was opened." } };
  const prev = S.vault; S.vault = null;
  renderVault();
  S.vault = prev;
  $("#sec-vault").scrollIntoView({ behavior: "smooth", block: "center" });
}

// ------------------------------------------------------------------ step 5: verdict + explanation
async function explain() {
  const sec = $("#sec-verdict"); show("#sec-verdict");
  sec.innerHTML = `<div class="section-head"><span class="step-no">05</span><h2>Verdict</h2></div>` + loader(`${S.config.models.reason} is explaining the verdict (numbers checked by the number guard)…`);
  try {
    const out = await api("/api/explain", { body: { session_id: S.sid, fingerprint: S.approved.fingerprint } });
    renderVerdict(out);
  } catch (e) { sec.innerHTML += errorBox(e); }
  refreshChain();
}

function renderVerdict(out) {
  const v = out.verdict;
  const label = v.label;
  const text = esc(out.text).replace(/\[((?:[AD]\d+)(?:\s*,\s*[AD]\d+)*)\]/g, (_, ids) =>
    ids.split(/\s*,\s*/).map((id) => `<a class="cite" data-cite="${id}">${id}</a>`).join(" "));
  const sec = $("#sec-verdict");
  const isFinal = v.stage === "final";
  sec.innerHTML = `
    <div class="section-head"><span class="step-no">05</span><h2>Verdict</h2>
      <span class="muted small">${isFinal ? "Final: decided by pre-registered rules on the vault." : "Practice stage: decided by the practice gate."} The label comes from code; Gemini only explains it.</span></div>
    <div class="card verdict">
      <div><div class="verdict-badge ${label}">${label}</div>
        <div class="small muted" style="margin-top:10px">${isFinal ? "after the vault" : "before the vault"}</div></div>
      <div>
        <div class="explain">${text}</div>
        ${out.removed_count ? `<div class="guard-note">⚑ ${out.removed_count} claim${out.removed_count > 1 ? "s" : ""} removed by the number guard (a number not produced by the tools).</div>` : ""}
        <ul class="reasons">${v.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        <div class="row small muted" style="margin-top:14px">
          <span class="mono">${esc(out.model)} · ${out.interaction_ids.map((i) => esc(i.slice(0, 14)) + "…").join(", ")}</span>
          <div class="spacer"></div>
          ${label !== "SURVIVED" && !S.vault ? `<button class="btn small" id="rewrite-btn">Suggest one cleaner hypothesis</button>` : ""}
        </div>
        <div id="rewrite-out"></div>
      </div>
    </div>`;
  sec.querySelectorAll("a.cite").forEach((a) => (a.onclick = () => {
    const card = $(`#card-${a.dataset.cite}`);
    if (card) { card.scrollIntoView({ behavior: "smooth", block: "center" }); card.classList.add("flash"); setTimeout(() => card.classList.remove("flash"), 1600); }
  }));
  const rb = $("#rewrite-btn");
  if (rb) rb.onclick = suggestRewrite;
}

async function suggestRewrite() {
  const box = $("#rewrite-out");
  box.innerHTML = loader("Gemini is proposing one simpler hypothesis (testing it will count as a new trial)…");
  try {
    const out = await api("/api/rewrite", { body: { session_id: S.sid, fingerprint: S.approved.fingerprint } });
    box.innerHTML = `<div class="card soft" style="margin-top:12px;padding:18px">
      <div class="small muted">Gemini suggests:</div><div style="color:var(--ink);margin:4px 0 8px">${esc(out.rationale)}</div>
      <div class="mono small">${out.rules_text.map(esc).join("<br>")}</div>
      <div class="row" style="margin-top:12px"><button class="btn small" id="use-rewrite">Load into the rule card</button>
      <span class="small muted">You still approve it. It counts as trial ${S.approved.trials + 1}.</span></div></div>`;
    $("#use-rewrite").onclick = () => {
      S.spec = out.spec;
      renderRuleCard({ fingerprint: out.fingerprint });
      $("#approve-btn").textContent = "Approve suggested rules (new trial)";
      updateTrialBadge(S.approved.trials, true);
      $("#sec-rule").scrollIntoView({ behavior: "smooth" });
    };
  } catch (e) { box.innerHTML = errorBox(e); }
}

// ------------------------------------------------------------------ trace drawer
async function openTrace(attackId) {
  const d = $("#drawer"), body = $("#drawer-body");
  d.classList.add("open");
  body.innerHTML = loader("Following the number back to the raw data…");
  try {
    const t = await api(`/api/trace?fingerprint=${S.approved.fingerprint}&attack=${attackId}`);
    body.innerHTML = `<div class="small muted" style="margin-bottom:16px">Every number on screen traces to raw data, a fixed rule card, a named function and a hash-chained log entry. No model computed it.</div>` +
      t.steps.map((s) => `<div class="trace-step"><span class="dot"></span><div class="t">${esc(s.step)}</div><div class="d">${esc(s.detail)}</div>
        ${s.sha256 ? `<pre>sha256 ${esc(s.sha256)}\npaths ${esc(s.paths)}</pre>` : ""}
        ${s.fingerprint ? `<pre>fingerprint ${esc(s.fingerprint)}</pre>` : ""}
        ${s.inputs ? `<pre>${esc(JSON.stringify(s.inputs, null, 1))}</pre>` : ""}
        ${s.numbers ? `<pre>${esc(JSON.stringify(s.numbers, null, 1))}</pre>` : ""}
        ${s.hash ? `<pre>ledger seq ${esc(s.seq)} · hash ${esc(s.hash.slice(0, 32))}…</pre>` : s.seq != null ? `<pre>ledger seq ${esc(s.seq)}</pre>` : ""}
      </div>`).join("") +
      `<h3 style="margin:20px 0 8px">Live Gemini calls in this session</h3>
      <table class="table"><tr><th>seq</th><th>purpose</th><th>interaction id</th></tr>
      ${t.llm_calls.map((c) => `<tr><td class="mono">${c.seq}</td><td>${esc(c.purpose)}<div class="small muted mono">${esc(c.model)}</div></td><td class="mono small" style="word-break:break-all">${esc(c.interaction_id || "–")}</td></tr>`).join("")}</table>`;
  } catch (e) { body.innerHTML = errorBox(e); }
}

// ------------------------------------------------------------------ history + log tabs
async function refreshHistory() {
  try { S.history = await api("/api/history"); } catch { /* ignore */ }
}

async function renderHistory() {
  await refreshHistory();
  const box = $("#history");
  const ideas = S.history?.ideas || [];
  if (!ideas.length) { box.innerHTML = `<div class="card soft muted">No approved ideas yet.</div>`; return; }
  box.innerHTML = ideas.map((i) => `
    <div class="idea">
      <div class="row" style="justify-content:space-between"><h3>“${esc(i.hunch_text || "(no text)")}”</h3>
        <span class="badge ${i.trials > 1 ? "warn" : ""}">${i.trials} trial${i.trials === 1 ? "" : "s"} · bar p &lt; ${(0.05 / Math.max(1, i.trials)).toPrecision(2)}</span></div>
      <table class="table" style="margin-top:10px">
        <tr><th>version</th><th>rules</th><th>verdict</th><th>vault</th></tr>
        ${i.specs.map((s) => `<tr><td class="mono">${esc(s.fingerprint.slice(0, 10))}</td><td class="mono small">${s.rules_text.map(esc).join("<br>")}</td>
          <td>${s.verdict ? `<span class="badge ${s.verdict === "SURVIVED" ? "pass" : s.verdict === "REJECTED" ? "fail" : "warn"}">${s.verdict}</span> <span class="small muted">${esc(s.stage || "")}</span>` : "–"}</td>
          <td class="small">${esc(s.vault)}</td></tr>`).join("")}
      </table>
    </div>`).join("");
}

let logFilter = "all", lastSeq = -1;
function summarisePayload(e) {
  const p = e.payload || {};
  switch (e.type) {
    case "hunch_submitted": return `“${p.text}”`;
    case "llm_call": return `${p.purpose} · ${p.model} · ${p.ok ? "ok" : "FAILED " + (p.error || "")} · ${p.interaction_id || ""}`;
    case "spec_proposed": case "spec_approved": return `${(p.fingerprint || "").slice(0, 12)} · ${p.spec?.name || ""}${p.idea_id ? " · " + p.idea_id : ""}`;
    case "trial_counted": return `${p.idea_id} · trial ${p.trials_after} · ${(p.fingerprint || "").slice(0, 12)}`;
    case "attack_planned": return `${p.id} ${p.tool}: ${p.alternative_explanation}`;
    case "attack_run": return `${p.id} ${p.name}: ${p.passed ? "pass" : "fail"} · ${p.summary}`;
    case "verdict": return `${p.stage}: ${p.label} · ${(p.fingerprint || "").slice(0, 12)}`;
    case "vault_precommit": return `pass mark ${JSON.stringify(p.pass_mark)} · ${(p.fingerprint || "").slice(0, 12)} · ${p.vault_paths} paths`;
    case "vault_result": return `${p.verdict?.label} · vault median ${p.vault?.median_excess_bps} bps · p ${fmtP(p.vault?.sign_p)}`;
    case "vault_blocked": return `${(p.fingerprint || "").slice(0, 12)} · ${p.message}`;
    case "limit_hit": return `${p.limit}: ${p.message}`;
    case "number_guard_violation": return `removed ${p.removed_sentences?.length} sentence(s): ${(p.violations || []).join(", ")}`;
    case "suggestion_shown": return `${p.completions?.length} completions${p.cached ? " (cached)" : ""}`;
    case "questions_asked": return (p.questions || []).map((q) => q.text).join(" | ");
    case "explanation": return `${p.label} · ${p.text?.slice(0, 120)}…`;
    default: return JSON.stringify(p).slice(0, 160);
  }
}

async function renderLog() {
  const data = await api("/api/ledger?limit=500");
  setChain(data.verify);
  $("#log-verify").innerHTML = data.verify.ok
    ? `<span class="badge ok">✓ chain intact: ${data.verify.entries} entries · head ${esc(data.verify.head.slice(0, 16))}…</span>`
    : `<span class="badge bad">✗ chain broken at entry #${data.verify.first_bad_seq}: ${esc(data.verify.reason)}</span>`;
  const types = ["all", ...new Set(data.entries.map((e) => e.type))];
  $("#log-filters").innerHTML = types.map((t) => `<button class="pill-btn ${t === logFilter ? "selected" : ""}" data-t="${t}">${t}</button>`).join("");
  $("#log-filters").querySelectorAll("button").forEach((b) => (b.onclick = () => { logFilter = b.dataset.t; renderLog(); }));
  const rows = data.entries.filter((e) => logFilter === "all" || e.type === logFilter).reverse();
  $("#log-table").innerHTML = `<tr><th>#</th><th>time (UTC)</th><th>type</th><th>what</th><th>hash</th></tr>` +
    rows.map((e) => `<tr class="log-row ${e.seq > lastSeq && lastSeq >= 0 ? "new" : ""}"><td class="mono">${e.seq}</td><td class="mono small">${esc((e.ts || "").slice(11, 23))}</td>
      <td><span class="log-type ${esc(e.type)}">${esc(e.type)}</span></td><td class="small">${esc(summarisePayload(e))}</td>
      <td class="mono small" title="prev ${esc(e.prev_hash)}">${esc((e.hash || "").slice(0, 10))}</td></tr>`).join("");
  lastSeq = Math.max(lastSeq, ...data.entries.map((e) => e.seq));
}

// ------------------------------------------------------------------ stretch: media -> hunch
async function onMedia(e) {
  const f = e.target.files[0];
  if (!f) return;
  const box = $("#ingest-out");
  box.innerHTML = loader(`Uploading ${f.name} · ${S.config.models.reason} is watching for the claimed strategy…`);
  const fd = new FormData();
  fd.append("session_id", S.sid); fd.append("file", f);
  try {
    const out = await api("/api/ingest", { body: fd });
    if (!out.is_trading_strategy) { box.innerHTML = `<div class="card soft" style="margin-top:14px">No testable trading strategy found. ${esc(out.notes || "")}</div>`; return; }
    box.innerHTML = `<div class="card soft" style="margin-top:14px;padding:18px"><div class="small muted">Claims found (${esc(out.model)}):</div>
      ${out.claims.map((c) => `<div style="margin-top:6px">“${esc(c.quote)}” ${c.timestamp ? `<span class="mono small muted">@${esc(c.timestamp)}</span>` : ""}</div>`).join("")}
      <div class="small muted" style="margin-top:10px">Extracted hunch placed in the box above. You still approve the rule card.</div></div>`;
    accept(out.hunch);
  } catch (err) { box.innerHTML = errorBox(err); }
  e.target.value = "";
}

boot().catch((e) => { document.body.insertAdjacentHTML("afterbegin", `<div class="error-box" style="margin:16px">${esc(e.message)}</div>`); });
