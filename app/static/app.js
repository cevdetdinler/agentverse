/* Skeptic UI: vanilla JS, no build step. All model/user text is escaped before it touches the DOM. */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtP = (p) => (p === null || p === undefined ? "n/a" : Number(p).toFixed(4));
// numbers arrive in basis points (hundredths of a percent); the UI always shows percent
const bps = (v) => (v === null || v === undefined ? "n/a" : `${v > 0 ? "+" : ""}${(v / 100).toFixed(2)}%`);
const pctAbs = (v) => (v === null || v === undefined ? "n/a" : `${(v / 100).toFixed(2)}%`);

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
  market: "real",        // "real" (Binance Vision) or "synthetic" (generated, planted pattern)
};

// ------------------------------------------------------------------ api
async function api(path, opts = {}) {
  if (opts.body instanceof FormData) opts.body.append("market", S.market);
  else if (opts.body) opts.body = { ...opts.body, market: S.market };
  else if (path.startsWith("/api/") && !path.startsWith("/api/library")) path += (path.includes("?") ? "&" : "?") + `market=${S.market}`;
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
  try { S.market = sessionStorage.getItem("skeptic_market") === "synthetic" ? "synthetic" : "real"; } catch { /* ignore */ }
  S.config = await api(`/api/config${S.sid ? `?session_id=${S.sid}` : ""}`);
  if (!S.sid) {
    S.sid = S.config.new_session_id;
    try { sessionStorage.setItem("skeptic_sid", S.sid); } catch { /* ignore */ }
  }
  $("#model-badge").textContent = S.config.models.reason;
  setChain(S.config.chain);
  try { S.library = (await api("/api/library")).hunches || []; } catch { S.library = []; }
  loadToday();
  setInterval(loadToday, 5 * 60 * 1000);
  refreshHistory();
  wireTabs();
  wireHunch();
  $("#drawer-close").onclick = () => $("#drawer").classList.remove("open");
  $("#verify-btn").onclick = async () => { setChain(await api("/api/ledger/verify")); renderLog(); };
  $("#media").onchange = onMedia;
  wireMarket();
}

// ------------------------------------------------------------------ market switch (real vs synthetic)
function renderMarket() {
  document.querySelectorAll(".mkt").forEach((b) => b.classList.toggle("active", b.dataset.market === S.market));
  const synth = S.market === "synthetic";
  $("#lede-data").textContent = synth
    ? "tests them on a made-up market with a known hidden pattern, with real fees,"
    : "tests them on real past prices with real fees,";
  const note = $("#market-note");
  note.classList.toggle("hidden", !synth);
  if (synth) note.innerHTML = `<b>Synthetic market.</b> Made-up prices with a hidden “dip, then bounce back” pattern, so there is a real pattern to find. Separate log, try counts and final exam. Not real market data.`;
}

function wireMarket() {
  renderMarket();
  document.querySelectorAll(".mkt").forEach((b) => (b.onclick = async () => {
    if (b.dataset.market === S.market) return;
    S.market = b.dataset.market;
    try { sessionStorage.setItem("skeptic_market", S.market); } catch { /* ignore */ }
    S.spec = null; S.approved = null; S.attacks = null; S.vault = null; S.history = null;
    resetBelow("#sec-questions");
    renderMarket();
    S.config = await api(`/api/config?session_id=${S.sid}`);
    setChain(S.config.chain);
    refreshHistory();
    const active = document.querySelector(".tab[data-tab].active")?.dataset.tab;
    if (active === "log") renderLog(); else if (active === "history") renderHistory();
  }));
}

function setChain(v) {
  const b = $("#chain-badge");
  if (v && v.ok) { b.className = "badge ok"; b.textContent = `Log intact ✓ · ${v.entries}`; }
  else { b.className = "badge bad"; b.textContent = `Log tampered ✗ at #${v ? v.first_bad_seq : "?"}`; }
  b.title = v && !v.ok ? v.reason : "Hash chain verified from disk";
}
async function refreshChain() { try { setChain(await api("/api/ledger/verify")); } catch { /* offline */ } }

function wireTabs() {
  document.querySelectorAll(".tab[data-tab]").forEach((t) => {
    t.onclick = () => {
      document.querySelectorAll(".tab[data-tab]").forEach((x) => x.classList.toggle("active", x === t));
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

// ideas from today's real markets (live 24-hour summary, turned into testable ideas by plain code on the server)
async function loadToday() {
  try {
    const out = await api("/api/today");
    S.today = out.ok ? out.ideas || [] : [];
  } catch { S.today = []; }
  if (document.activeElement === $("#hunch") && !$("#hunch").value.trim()) renderSuggest();
}

function layer1(q) {
  const ql = q.trim().toLowerCase();
  if (ql.length < 2) return [];
  const past = (S.history?.hunches || []).map((h) => ({ text: h.text, src: "yours" }));
  const today = (S.today || []).map((i) => ({ text: i.hunch, src: "today: " + i.fact }));
  const lib = S.library.map((t) => ({ text: t, src: "example" }));
  const seen = new Set();
  return [...past.reverse(), ...today, ...lib]
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
  pill.innerHTML = `⚠ You've tested ${n} version${n === 1 ? "" : "s"} of this idea. Each extra try makes the luck check stricter: the next one needs a luck score below <span class="mono">${(0.05 / (n + 1)).toPrecision(2)}</span>`;
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
  const item = (text, hint) => `<div class="item" data-text="${esc(text)}">${esc(text)}${hint ? `<span class="hint">${esc(hint)}</span>` : ""}</div>`;
  if (!q.trim() && document.activeElement === $("#hunch")) {  // empty box: start from today's real markets
    const today = (S.today || []).slice(0, 5);
    const examples = S.library.slice(0, today.length ? 3 : 6);
    let html = "";
    if (today.length) html += `<div class="group"><div class="label">Today’s markets · live from Binance · ideas you could test</div>${today.map((i) => item(i.hunch, i.fact)).join("")}</div>`;
    if (examples.length) html += `<div class="group"><div class="label">Ideas people often post</div>${examples.map((t) => item(t)).join("")}</div>`;
    if (!html) { box.classList.add("hidden"); return; }
    box.innerHTML = html;
    box.classList.remove("hidden");
    box.querySelectorAll(".item").forEach((it) => it.addEventListener("mousedown", (e) => { e.preventDefault(); accept(it.dataset.text); }));
    return;
  }
  if (!l1.length && !l2.length || document.activeElement !== $("#hunch")) { box.classList.add("hidden"); return; }
  let html = "";
  if (l2.length) html += `<div class="group"><div class="label">Gemini · ${esc(S.config.models.router)} · precise wording</div>${l2.map((t) => `<div class="item" data-text="${esc(t)}">${esc(t)}</div>`).join("")}</div>`;
  if (l1.length) html += `<div class="group"><div class="label">Instant · your ideas + examples (no AI)</div>${l1.map((h) => `<div class="item" data-text="${esc(h.text)}">${esc(h.text)}<span class="hint">${h.src}</span></div>`).join("")}</div>`;
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
  clearTimeout(suggestTimer);
  if (suggestAbort) suggestAbort.abort();
  S.suggestions = []; S.ghost = ""; renderGhost();
  S.hunch = text; S.spec = null; S.approved = null; S.attacks = null; S.vault = null;
  resetBelow("#sec-questions");
  const sec = $("#sec-questions"); show("#sec-questions");
  sec.innerHTML = loader(`${S.config.models.reason} is reading your idea…`);
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
      <span class="muted small">Your idea could mean a few different things, and each gives a different result. Gemini asks instead of guessing.</span></div>
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
    catch (e) {
      sec.querySelectorAll(".loader").forEach((l) => l.remove());
      sec.insertAdjacentHTML("beforeend", errorBox(e));
      $("#answer-go").disabled = false;
    }
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
    <div class="section-head"><span class="step-no">03</span><h2>Your rules</h2>
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
        <div class="line muted small" style="margin-top:12px">Exact rules (edit any number) · 1 bar = 1 hour · −0.05 means −5%</div>
      </div>
      <p class="plain-rules">${esc(plainRules(sp))}</p>
      <h3 style="margin-bottom:6px">Assumptions Gemini made</h3>
      <ul class="assumptions">${(sp.assumptions || []).map((a) => `<li>${esc(a)}</li>`).join("") || "<li class='muted'>none listed</li>"}</ul>
      <div class="row" style="margin-top:22px">
        <button class="btn primary" id="approve-btn">Approve rules</button>
        <span class="small muted" id="approve-note">Approving counts as one try for this idea.</span>
      </div>
      <div id="rule-error"></div>
    </div>`;
  updateTrialBadge(trialsNow, false);
  sec.querySelectorAll("input.edit").forEach((inp) => inp.addEventListener("change", onEdit));
  $("#approve-btn").onclick = approve;
}

// ---- the rules in plain words (display only; the exact rules above are what gets tested)
const OP_WORDS = { "<": "is below", "<=": "is at most", ">": "is above", ">=": "is at least",
  crosses_above: "rises above", crosses_below: "drops below" };
const pctWord = (x) => `${(Math.abs(x) * 100).toFixed(2).replace(/\.?0+$/, "")}%`;
function plainCond(c) {
  const L = c.lookback, W = c.window, v = Number(c.value), op = c.op;
  const down = op === "<" || op === "<=" || op === "crosses_below";
  if (c.feature === "return" && v < 0 && down) return `the price has fallen ${pctWord(v)} or more over the last ${L} hours`;
  if (c.feature === "return" && v > 0 && !down) return `the price has risen ${pctWord(v)} or more over the last ${L} hours`;
  if (c.feature === "drawdown_from_high" && down) return `the price is ${pctWord(v)} or more below its highest point of the last ${L} hours`;
  if (c.feature === "rise_from_low" && !down) return `the price is ${pctWord(v)} or more above its lowest point of the last ${L} hours`;
  if (c.feature === "down_streak") return `the price has fallen ${v} times in a row`;
  const signed = `${v > 0 ? "+" : v < 0 ? "−" : ""}${pctWord(v)}`;
  const names = {
    return: [`the price change over the last ${L} hours`, signed],
    price_vs_sma: [`the price compared with its ${W}-hour average`, signed],
    sma_ratio: [`the ${c.fast}-hour average compared with the ${c.slow}-hour average`, signed],
    rsi: [`the ${W}-hour RSI (a 0–100 gauge of recent rises vs falls)`, String(v)],
    drawdown_from_high: [`the price compared with its ${L}-hour high`, signed],
    rise_from_low: [`the price compared with its ${L}-hour low`, signed],
    breakout: [`the price compared with the previous ${L}-hour high`, signed],
    volatility: [`how jumpy the price has been over ${L} hours`, pctWord(v)],
  };
  const [what, val] = names[c.feature] || [c.feature, String(v)];
  return `${what} ${OP_WORDS[op] || op} ${val}`;
}
function plainRules(sp) {
  const buy = sp.entry.all.map(plainCond).join(", and ");
  const sells = [];
  if (sp.exit.hold_bars != null) sells.push(`after ${sp.exit.hold_bars} hours`);
  if (sp.exit.take_profit != null) sells.push(`once it is up ${pctWord(sp.exit.take_profit)}`);
  if (sp.exit.stop_loss != null) sells.push(`once it is down ${pctWord(sp.exit.stop_loss)}`);
  (sp.exit.any || []).forEach((c) => sells.push(`when ${plainCond(c)}`));
  let text = `In plain words: buy when ${buy}. Sell ${sells.join(", or ")}.`;
  if (sp.cooldown_bars) text += ` After selling, wait ${sp.cooldown_bars} hours before buying again.`;
  return text;
}

function updateTrialBadge(trials, edited) {
  const b = $("#trial-badge");
  if (!b) return;
  const next = edited || !S.approved ? trials + 1 : trials;
  b.className = next > 1 ? "badge warn" : "badge";
  b.innerHTML = `try <span class="mono">${next}</span> · luck bar <span class="mono">p &lt; ${(0.05 / Math.max(1, next)).toPrecision(2)}</span>`;
  b.title = "Every extra try at the same idea makes a lucky result more likely, so the bar gets stricter.";
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
    $("#approve-btn").textContent = S.approved && edited ? "Approve edited rules (new try)" : "Approve rules";
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
    $("#approve-note").textContent = `Approved by you · ${out.trials} tr${out.trials === 1 ? "y" : "ies"} at this idea so far` + (out.contaminated ? " · ⚠ changed after this idea's final exam" : "");
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
  sec.innerHTML = `<div class="section-head"><span class="step-no">04</span><h2>Trying to break it</h2></div>` +
    loader(`Testing on ${S.config.practice_paths || 300} past price histories → ${S.config.models.reason} picks extra checks for this idea → luck check, fragility, higher fees, lucky streaks, too many tries…`);
  try {
    S.attacks = await api("/api/attack", { body: { session_id: S.sid, fingerprint: S.approved.fingerprint } });
    renderAttacks(); renderVault(); explain();
  } catch (e) { sec.innerHTML += errorBox(e); }
  refreshChain(); refreshHistory();
}

function keyNumber(r) {
  const n = r.numbers;
  switch (r.id) {
    case "A1": return { v: bps(n.median_excess_bps), u: "typical result vs holding", sub: `likely range ${bps(n.median_excess_ci95_bps[0])} to ${bps(n.median_excess_ci95_bps[1])} · beat holding ${n.wins} of ${n.paths} · luck score ${fmtP(n.sign_p)}` };
    case "A2": return { v: fmtP(n.p_perm), u: "luck score (needs < 0.05)", sub: `${n.perm_at_or_above_observed} of ${n.K} scrambled markets did as well · yours ${bps(n.observed_mean_excess_bps)} vs scrambled ${bps(n.perm_mean_excess_median_bps)}` };
    case "A3": return { v: `${n.share_positive_pct}%`, u: "of variations still beat holding", sub: `${n.neighbours} slightly different versions · yours ranks ${n.user_spec_rank} of ${n.rank_out_of}` };
    case "A4": return { v: bps(n.median_excess_x2_bps), u: "typical result at 2× fees", sub: `normal fees ${bps(n.median_excess_x1_bps)} · 3× fees ${bps(n.median_excess_x3_bps)}` };
    case "A5": return { v: bps(n.median_after_bps), u: "without the luckiest 5%", sub: `typical ${bps(n.median_before_bps)} → ${bps(n.median_after_bps)} · average ${bps(n.mean_before_bps)} → ${bps(n.mean_after_bps)}` };
    case "A6": return { v: fmtP(n.p_adj), u: "luck score after your tries", sub: `${n.trials} tr${n.trials === 1 ? "y" : "ies"} at this idea · bar p < ${n.bar}` };
    default: {
      if (n.table && n.table[0] && "bucket" in n.table[0]) return { v: `${n.positive_buckets}/${n.buckets}`, u: "kinds of market where it beat holding", sub: n.table.map((t) => `${t.bucket} ${bps(t.median_excess_bps)}`).join(" · ") };
      if (n.fold_medians_bps) return { v: `${n.positive_folds}/${n.k}`, u: "groups where it beat holding", sub: n.fold_medians_bps.map(bps).join(" · ") };
      if ("exposure_pct" in n) return { v: `${n.exposure_pct}%`, u: "of the time invested", sub: `moves with plain holding: ${n.return_correlation_with_bh} (1 = identical)` };
      if (n.table && n.table[0] && "hold_bars" in n.table[0]) return { v: `${n.share_positive_pct}%`, u: "of holding times beat holding", sub: n.table.map((t) => `${t.hold_bars}h ${bps(t.median_excess_bps)}`).join(" · ") };
      if ("multiplier" in n) return { v: bps(n.median_excess_bps), u: `typical result at ${n.multiplier}× fees`, sub: `beat holding ${n.wins}, lost ${n.losses} · luck score ${fmtP(n.sign_p)}` };
      if ("median_after_bps" in n) return { v: bps(n.median_after_bps), u: `without the luckiest ${n.pct}%`, sub: `left out ${n.dropped_paths} price histories` };
      return { v: "", u: "", sub: "" };
    }
  }
}

// ---- the same results for three audiences: simple (why it matters), standard, technical (method + raw numbers)
const WHY = {
  A1: "The first question anyone asks: did it do better than simply buying at the start and holding? Winning a bit more than half the time can still be a coin flip, so we add a luck score.",
  A2: "Random buying and selling wins sometimes. We scramble the order of each price history so no pattern can exist, then rerun your exact rule. If the scrambled markets do as well, your pattern isn’t what made the money.",
  A3: "A real pattern shouldn’t vanish if you change “24 hours” to “22 hours”. If only your exact numbers work, they were probably tuned to the past.",
  A4: "Fees and price gaps eat small gains. If paying double fees wipes the result out, it won’t survive real trading.",
  A5: "If a handful of lucky price histories carry the whole result, it’s a lottery win, not a strategy.",
  A6: "Try enough versions of an idea and one will look good by pure chance. Each extra try raises the bar.",
};
const VIEWS = { simple: "Simple", standard: "Standard", technical: "Technical" };
function currentView() {
  try { const v = localStorage.getItem("skeptic_view"); if (v in VIEWS) return v; } catch { /* storage blocked */ }
  return "standard";
}

function techLine(r) {
  const n = r.numbers || {};
  const p = (x) => (x == null ? "n/a" : Number(x).toFixed(4));
  switch (r.id) {
    case "A1": return `Exact two-sided sign test vs buy-and-hold (ties excluded), n = ${n.paths}: ${n.wins}W/${n.losses}L, p = ${p(n.sign_p)}. Median excess ${n.median_excess_bps} bps of starting capital, bootstrap 95% CI [${n.median_excess_ci95_bps?.join(", ")}] (2,000 path resamples); mean ${n.mean_excess_bps} bps; ${n.total_trades} trades; exposure ${n.exposure_pct}%; mean max drawdown ${n.mean_max_drawdown_bps} bps.`;
    case "A2": return `Surrogate permutation test: one-bar log returns shuffled within each path, K = ${n.K}; statistic = mean excess across paths; p_perm = (1 + #{surrogate ≥ observed}) / (1 + K) = ${p(n.p_perm)}. Observed ${n.observed_mean_excess_bps} bps vs surrogate median ${n.perm_mean_excess_median_bps} bps (95th pct ${n.perm_mean_excess_p95_bps}).`;
    case "A3": return `Parameter sensitivity: one-at-a-time ±10/20/30% on every numeric parameter plus a 3×3 joint grid on the two most sensitive; ${n.share_positive_pct}% of ${n.neighbours} neighbours with median excess > 0 (threshold 60%); spec rank ${n.user_spec_rank}/${n.rank_out_of}; neighbour medians ${n.worst_neighbour_median_bps} to ${n.best_neighbour_median_bps} bps. No neighbour is ever substituted.`;
    case "A4": return `Cost stress: strategy pays fee and slippage ×2 / ×3 while the buy-and-hold benchmark keeps ×1 (conservative). Median excess ${n.median_excess_x1_bps} / ${n.median_excess_x2_bps} / ${n.median_excess_x3_bps} bps at ×1 / ×2 / ×3; gate at ×2 > 0.`;
    case "A5": return `Outlier dependence: drop top ${n.pct}% of paths by excess (${n.dropped_paths} paths). Median ${n.median_before_bps} → ${n.median_after_bps} bps; mean ${n.mean_before_bps} → ${n.mean_after_bps} bps; gate: median after > 0.`;
    case "A6": return `Multiple-testing (Bonferroni): p_adj = min(1, p_perm × trials) = min(1, ${p(n.p_perm)} × ${n.trials}) = ${p(n.p_adj)}; equivalent per-trial α = ${n.bar}. Trials = distinct rule fingerprints approved in this idea’s lineage.`;
    default: {
      const tool = r.inputs?.tool || "diagnostic";
      const params = Object.entries(r.inputs || {}).filter(([k]) => !["tool", "fingerprint", "alternative_explanation", "supports_if", "refutes_if"].includes(k))
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
      const nums = Object.entries(n).filter(([k, v]) => k !== "table" && typeof v !== "object").map(([k, v]) => `${k} = ${v}`).join("; ");
      const table = Array.isArray(n.table) ? " · per group: " + n.table.map((t) => `${t.bucket ?? t.hold_bars ?? ""} ${t.median_excess_bps} bps`).join(", ") : "";
      return `Pre-registered diagnostic ${tool}(${params}). ${nums}${table}.`;
    }
  }
}

function contextCard(a) {
  const sp = S.approved.spec;
  const a1 = (a.results || []).find((r) => r.id === "A1")?.numbers || {};
  const synth = S.market === "synthetic";
  const data = synth
    ? `${a1.paths} made-up price histories with a hidden “dip, then bounce back” pattern (so there is something real to find)`
    : `${a1.paths} real crypto price histories from Binance (hourly or 4-hourly, 2 to 10 days each). Coin names and dates are hidden, and half are flipped upside down, so “crypto went up” can’t make a rule look good on its own`;
  return `
    <div class="context-card">
      <div class="ctx-row"><div class="ctx-k">Your idea</div><div class="ctx-v"><b>“${esc(sp.hunch_text || S.hunch || sp.name)}”</b></div></div>
      <div class="ctx-row"><div class="ctx-k">As exact rules</div><div class="ctx-v">${esc(plainRules(sp).replace(/^In plain words: (.)/, (_, ch) => ch.toUpperCase()))}</div></div>
      <div class="ctx-row"><div class="ctx-k">Tested on</div><div class="ctx-v">${esc(data)}. Each history uses its own real trading fee and price gap.</div></div>
      <div class="ctx-row"><div class="ctx-k">Compared with</div><div class="ctx-v">Simply buying at the start and holding to the end (“just holding”). A rule only counts as good if it does better than that.</div></div>
      <div class="ctx-row"><div class="ctx-k">At a glance</div><div class="ctx-v">The rule made <b>${a1.total_trades}</b> trades and had money invested <b>${a1.exposure_pct}%</b> of the time. It beat just holding in <b>${a1.wins} of ${a1.paths}</b> histories; its typical result was <b>${bps(a1.median_excess_bps)}</b> and its average <b>${bps(a1.mean_excess_bps)}</b>.</div></div>
    </div>`;
}

function niceParam(label) {
  return String(label).replace(/^entry\[\d+\]\./, "buy rule ").replace(/^exit\[\d+\]\./, "sell rule ")
    .replace("exit.hold_bars", "hours held").replace("exit.take_profit", "profit target").replace("exit.stop_loss", "loss limit")
    .replace("cooldown_bars", "wait after selling").replace(".lookback", " hours back").replace(".window", " window")
    .replace(".value", " threshold").replace(".fast", " short average").replace(".slow", " long average");
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
    }).join("")}<line x1="0" x2="${W}" y1="${mid}" y2="${mid}" stroke="#d1d5db"/></svg>`;
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
        html += `<div class="cell" style="background:${color(m)};${cell?.is_user_spec ? "outline:2px solid #111" : ""}">${m == null ? "–" : bps(m)}</div>`;
      });
    });
    return html + `</div><div class="sub">rows: ${esc(niceParam(j.params[0]))} · columns: ${esc(niceParam(j.params[1]))} · typical result · outlined = yours</div>`;
  }
  return "";
}

function attackCard(r) {
  const k = keyNumber(r);
  const prereg = r.kind === "diagnostic" ? `<div class="prereg"><b>Gemini’s worry about this idea (written down before the check ran):</b> ${esc(r.hypothesis)}
      ${r.inputs?.supports_if ? `<div class="small muted" style="margin-top:6px">Worry confirmed if: ${esc(r.inputs.supports_if)}<br>Worry ruled out if: ${esc(r.inputs.refutes_if)}</div>` : ""}</div>` : "";
  const why = r.kind === "diagnostic"
    ? `Gemini worried about this specific idea: ${r.hypothesis}`
    : WHY[r.id] || r.hypothesis;
  return `<div class="attack" id="card-${r.id}">
    <div class="top"><span class="aid">${r.id}</span><span class="name">${esc(r.name)}</span>
      ${r.kind === "diagnostic" ? `<span class="badge violet">Gemini’s idea</span>` : ""}
      <span class="badge ${r.passed ? "pass" : "fail"}">${r.passed ? "pass" : "fail"}</span></div>
    <div><span class="key">${esc(k.v)}<span class="unit">${esc(k.u)}</span></span><div class="sub v-detail">${esc(k.sub)}</div></div>
    <p class="why v-why ${r.kind === "diagnostic" ? "v-simple" : ""}"><b>Why this check:</b> ${esc(why)}</p>
    <div class="v-detail">${chartSVG(r.chart)}</div>
    <div class="v-detail">${prereg}</div>
    <div class="summary v-detail">${esc(r.summary)}</div>
    <p class="tech v-tech">${esc(techLine(r))}</p>
    <div class="foot"><span class="small muted v-detail">${esc(r.kind === "diagnostic" ? "Extra check · " : "")}${esc(r.threshold)}</span>
      <button class="btn ghost small nowrap" data-trace="${r.id}">trace&nbsp;→</button></div>
  </div>`;
}

function renderAttacks() {
  const a = S.attacks, g = a.gate;
  const sec = $("#sec-attacks");
  const tone = g.status === "ELIGIBLE" ? "ok" : g.status === "INCONCLUSIVE" ? "warn" : "bad";
  const view = currentView();
  sec.dataset.view = view;
  sec.innerHTML = `
    <div class="section-head"><span class="step-no">04</span><h2>Trying to break it</h2>
      <span class="muted small">Six standard checks (A1–A6) decide pass or fail. Purple cards are extra checks Gemini chose for this idea, written down before they ran.</span>
      <div class="spacer"></div>
      <nav class="tabs view-switch" aria-label="How much detail">${Object.entries(VIEWS).map(([k, label]) =>
        `<button class="tab vw ${k === view ? "active" : ""}" data-view="${k}">${label}</button>`).join("")}</nav></div>
    ${contextCard(a)}
    <details class="howto">
      <summary>How to read these cards</summary>
      <ul>
        <li><b>pass / fail</b>: whether your rule survived that check. One fail on A1–A6 is enough to reject the idea.</li>
        <li><b>Typical result</b>: how your rule did compared with just holding, on a typical price history (half did better, half worse).</li>
        <li><b>Luck score</b>: how easily luck alone could produce a result this good. Below 0.05 means luck is an unlikely explanation.</li>
        <li><b>Purple cards</b>: checks Gemini suggested for this particular idea. Its worry was written down before the check ran, so it can’t be changed afterwards.</li>
        <li><b>trace →</b>: shows exactly where a number came from. No AI calculates any number on this page.</li>
      </ul>
    </details>
    <div class="gate"><span class="badge ${tone}">${esc(g.status === "ELIGIBLE" ? "checks: passed" : "checks: " + g.status.toLowerCase())}</span>
      <div><b style="color:var(--ink)">${esc(g.headline)}</b>${g.failing.length ? `<ul>${g.failing.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}
      ${a.plan_error ? `<div class="small muted">Gemini couldn’t suggest extra checks this time (${esc(a.plan_error)}); the six standard checks still ran.</div>` : ""}</div></div>
    <div class="attack-grid">${[...a.results, ...a.diagnostics].map(attackCard).join("")}</div>`;
  sec.querySelectorAll("[data-trace]").forEach((b) => (b.onclick = () => openTrace(b.dataset.trace)));
  sec.querySelectorAll(".vw").forEach((b) => (b.onclick = () => {
    sec.dataset.view = b.dataset.view;
    sec.querySelectorAll(".vw").forEach((x) => x.classList.toggle("active", x === b));
    try { localStorage.setItem("skeptic_view", b.dataset.view); } catch { /* storage blocked: still switches */ }
  }));
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
          <h2>The final exam</h2>
          <div class="reason">150 past price histories this idea has never seen. One attempt per idea: the pass mark is written down before it opens, and only you can open it.</div>
        </div>
      </div>
      <div id="vault-body" style="margin-top:20px">
        ${opened ? vaultTable(opened) : `
        <div class="row"><button class="btn vault-btn" id="vault-btn" ${canTry ? "" : "disabled"}>Take the final exam (one attempt)</button>
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
      <tr><th></th><th>Practice (${p.paths || 300} histories)</th><th>Final exam (${v.paths} histories)</th></tr>
      ${row("Typical result vs just holding", bps(p.median_excess_bps), bps(v.median_excess_bps))}
      ${row("Likely range", p.median_excess_ci95_bps ? `${bps(p.median_excess_ci95_bps[0])} to ${bps(p.median_excess_ci95_bps[1])}` : "–", `${bps(v.median_excess_ci95_bps[0])} to ${bps(v.median_excess_ci95_bps[1])}`)}
      ${row("Beat holding / lost to holding", `${p.wins} / ${p.losses}`, `${v.wins} / ${v.losses}`)}
      ${row("Luck score (needs below 0.05)", fmtP(p.sign_p), fmtP(v.sign_p))}
      ${row("Average worst drop", pctAbs(p.mean_max_drawdown_bps), pctAbs(v.mean_max_drawdown_bps))}
      ${row("Trades", p.total_trades, v.total_trades)}
    </table>
    <div class="precommit">${r.edge_retained_pct != null ? `On prices it had never seen, it kept ${r.edge_retained_pct}% of its practice result. ` : ""}${r.replayed ? "Showing the saved result (an exam is never re-run). " : ""}Pass mark, written down before opening: typical result above 0% and luck score below 0.05.</div>`;
}

async function openVault() {
  const b = $("#vault-btn"); b.disabled = true;
  try {
    S.vault = await api("/api/vault/open", { body: { session_id: S.sid, fingerprint: S.approved.fingerprint } });
    $("#vault-body").innerHTML = vaultTable(S.vault);
    $("#sec-vault .lock").textContent = "🔓";
    explain();
  } catch (e) {
    if (e.status === 409) {
      $("#vault-body").insertAdjacentHTML("beforeend", `<div class="block"><b>Blocked.</b> ${esc(e.message)}<div class="small" style="margin-top:6px">Recorded in the tamper-proof log as <span class="mono">${e.data.code === "vault_blocked" ? "vault_blocked" : esc(e.data.code)}</span>. Open the Log tab to see it.</div></div>`);
    } else $("#vault-body").insertAdjacentHTML("beforeend", errorBox(e));
  }
  refreshChain(); refreshHistory();
}

function renderVaultAfterEdit() {
  // the edited card belongs to an idea that already used its vault: show the vault so the user can try (and be refused)
  S.attacks = { ...(S.attacks || {}), vault: { state: "contaminated", can_open: false, reason: "These rules were changed after this idea took its final exam." } };
  const prev = S.vault; S.vault = null;
  renderVault();
  S.vault = prev;
  $("#sec-vault").scrollIntoView({ behavior: "smooth", block: "center" });
}

// ------------------------------------------------------------------ step 5: verdict + explanation
async function explain() {
  const sec = $("#sec-verdict"); show("#sec-verdict");
  sec.innerHTML = `<div class="section-head"><span class="step-no">05</span><h2>Verdict</h2></div>` + loader(`${S.config.models.reason} is explaining the verdict (every number it uses gets checked)…`);
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
      <span class="muted small">${isFinal ? "Final: decided by the final exam, using a pass mark written down in advance." : "Decided by the standard checks."} The verdict comes from code; Gemini only explains it.</span></div>
    <div class="card verdict">
      <div><div class="verdict-badge ${label}">${label}</div>
        <div class="small muted" style="margin-top:10px">${isFinal ? "after the final exam" : "before the final exam"}</div></div>
      <div>
        <div class="explain">${text}</div>
        ${out.removed_count ? `<div class="guard-note">⚑ ${out.removed_count} sentence${out.removed_count > 1 ? "s" : ""} removed: Gemini used a number our maths didn’t produce.</div>` : ""}
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
      <span class="small muted">You still approve it. It counts as try ${S.approved.trials + 1}.</span></div></div>`;
    $("#use-rewrite").onclick = () => {
      S.spec = out.spec;
      renderRuleCard({ fingerprint: out.fingerprint });
      $("#approve-btn").textContent = "Approve suggested rules (new try)";
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
    $("#hunch").blur(); hide("#suggest");  // keep the extracted quotes visible
  } catch (err) { box.innerHTML = errorBox(err); }
  e.target.value = "";
}

boot().catch((e) => { document.body.insertAdjacentHTML("afterbegin", `<div class="error-box" style="margin:16px">${esc(e.message)}</div>`); });
