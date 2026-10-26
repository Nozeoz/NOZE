// NOZE Studio dashboard — vanilla JS, no build step. All server text goes in via textContent.
(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const COLUMNS = [
    ["In production", ["planning", "rendering", "reviewing", "revising", "approval", "approved"]],
    ["Needs you", ["awaiting_human", "escalated"]],
    ["Delivered", ["delivered"]],
    ["Rejected / failed", ["rejected", "failed", "cancelled"]],
    ["Sources", null],
  ];
  let current = null;

  function el(tag, props = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid != null) n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return n;
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).detail || msg; } catch (_) { /* not JSON */ }
      throw new Error(msg);
    }
    return res.json();
  }
  const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

  function ago(ts) {
    const d = Date.now() / 1000 - ts;
    if (d < 60) return "just now";
    if (d < 3600) return `${Math.floor(d / 60)}m ago`;
    if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
    return `${Math.floor(d / 86400)}d ago`;
  }

  // -- board ---------------------------------------------------------------------------------
  async function loadBoard() {
    const s = await api("/api/agency/status");
    const strip = $("#strip");
    strip.replaceChildren(
      el("span", { class: "st-pill", text: s.llm.available ? `Claude: ${s.llm.model}` : `Claude off — ${s.llm.reason}` }),
      el("span", { class: "st-pill", text: `LLM spend 24h: $${s.spend_24h}` }),
      el("span", { class: "st-pill", text: s.auto_approve ? "manager auto-approves" : "you approve every clip" }),
      el("span", { class: "st-pill", text: s.runner ? "runner: on" : "runner: off (noze agency run, or AGENCY_AUTORUN=1)" }),
      s.runner ? null : el("button", { class: "st-btn", text: "Advance queue", onclick: async (e) => {
        e.target.disabled = true; try { await post("/api/agency/tick"); } finally { e.target.disabled = false; loadBoard(); }
      } }),
    );
    $("#alerts").replaceChildren(...s.alerts.slice(0, 6).map((a) => el("div", { class: "st-alert", text: `[${a.level}] ${a.message}` })));
    const board = $("#board");
    board.replaceChildren(...COLUMNS.map(([name, states]) => {
      const jobs = s.jobs.filter((j) => (states ? j.kind === "clip" && states.includes(j.state) : j.kind === "source"));
      return el("div", { class: "st-col" }, el("h2", {}, el("span", { text: name }), el("span", { text: String(jobs.length) })),
        ...jobs.slice(0, 40).map((j) => el("div", { class: "st-card", onclick: () => openJob(j.id) },
          el("div", { class: "t", text: `#${j.id} ${j.title}` }),
          el("div", { class: "m" }, el("span", { class: "st-state", text: j.state + (j.round ? ` · r${j.round}` : "") }),
            ` ${j.campaign || "own"} · ${ago(j.updated_at)}${j.canary ? " · trial lessons" : ""}`),
          j.error ? el("div", { class: "m", text: `⚠ ${j.error.slice(0, 120)}` }) : null)));
    }));
  }

  // -- job panel ------------------------------------------------------------------------------
  async function openJob(id) {
    current = id;
    const j = await api(`/api/agency/jobs/${id}`);
    const p = $("#panel");
    const kids = [el("div", { class: "st-row" }, el("b", { text: `#${j.id} ${j.title}` }),
      el("span", { class: "st-state", text: j.state }), el("button", { class: "st-btn", style: "margin-left:auto", text: "Close", onclick: () => p.classList.remove("open") }))];
    kids.push(el("div", { class: "muted", text: `${j.kind} · ${j.campaign || "own content"} · round ${j.round} · LLM $${j.spend}` }));
    if (j.has_video) kids.push(el("video", { src: `/api/agency/jobs/${id}/video?ts=${j.updated_at}`, controls: "", playsinline: "" }));
    if (j.render) kids.push(el("div", { class: "muted", text: `${(j.render.duration || 0).toFixed(1)}s · ${j.render.loudness?.integrated} LUFS · ${j.render.captions} captions · font ${j.render.font}` }));
    if (j.kind === "clip" && ["awaiting_human", "escalated", "approval", "approved"].includes(j.state)) {
      const notes = el("textarea", { placeholder: "What should change? (one note per line)" });
      kids.push(el("h3", { text: "Your call" }), notes, el("div", { class: "st-row" },
        el("button", { class: "st-btn primary", text: "Approve", onclick: () => decide(id, "approve", notes) }),
        el("button", { class: "st-btn", text: "Request changes", onclick: () => decide(id, "changes", notes) }),
        el("button", { class: "st-btn danger", text: "Reject", onclick: () => decide(id, "reject", notes) })));
    }
    if (["failed", "rejected", "awaiting_human"].includes(j.state) || (j.kind === "source" && j.state === "done")) {
      kids.push(el("div", { class: "st-row" }, el("button", { class: "st-btn", text: "Retry", onclick: () => retry(id) })));
    }
    if (j.error) kids.push(el("div", { class: "st-alert", text: j.error }));
    if (j.plan?.post) {
      kids.push(el("h3", { text: "Post copy" }), el("pre", { style: "white-space:pre-wrap", text: `${j.plan.post.caption || ""}\n${(j.plan.post.hashtags || []).join(" ")}` }));
    }
    if (j.reviews.length) {
      kids.push(el("h3", { text: "Reviews" }));
      for (const r of j.reviews) {
        kids.push(el("div", {}, el("b", { text: `Round ${r.round} · ${r.reviewer}: ${r.verdict}${r.score != null ? ` (${r.score})` : ""}` }),
          el("div", { class: "muted", text: r.summary })));
        for (const i of r.issues || []) {
          kids.push(el("div", { class: `st-issue ${i.severity}` },
            el("div", { text: `[${i.severity}] ${i.timecode_s != null ? `@${i.timecode_s}s ` : ""}${i.description}` }),
            el("div", { class: "fix", text: `→ ${i.fix}` })));
        }
      }
    }
    if (j.data?.fix_log?.length) {
      kids.push(el("h3", { text: "Editor fixes" }));
      for (const round of j.data.fix_log) for (const f of round.fixes || []) kids.push(el("div", { class: "st-ev", text: `${f.issue_id} → ${f.change}` }));
    }
    if (j.children.length) {
      kids.push(el("h3", { text: "Clips from this source" }));
      for (const c of j.children) kids.push(el("div", { class: "st-card", onclick: () => openJob(c.id) }, el("div", { class: "t", text: `#${c.id} ${c.title}` }), el("div", { class: "m", text: c.state })));
    }
    kids.push(el("h3", { text: "Timeline" }));
    for (const e of j.events.slice().reverse()) {
      kids.push(el("div", { class: "st-ev" }, el("b", { text: e.role }), ` ${new Date(e.ts * 1000).toLocaleString()} — ${e.message}`));
    }
    p.replaceChildren(...kids);
    p.classList.add("open");
  }

  async function decide(id, decision, notesEl) {
    const notes = notesEl.value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (decision === "changes" && !notes.length) { notesEl.focus(); return; }
    try { await post(`/api/agency/jobs/${id}/decision`, { decision, notes }); } catch (e) { alert(e.message); }
    openJob(id); loadBoard();
  }
  async function retry(id) {
    try { await post(`/api/agency/jobs/${id}/retry`); } catch (e) { alert(e.message); }
    openJob(id); loadBoard();
  }

  // -- team report ---------------------------------------------------------------------------------
  async function loadTeam() {
    const m = await api("/api/agency/report?days=7");
    const pct = (v) => (v == null ? "—" : `${v}%`);
    const kpis = [
      ["Delivered (7d)", m.throughput.delivered], ["In progress", m.throughput.in_progress],
      ["Editor first-pass", pct(m.editor.first_pass_rate_pct)], ["Avg review rounds", m.editor.avg_review_rounds ?? "—"],
      ["Escalations", pct(m.editor.escalation_rate_pct)], ["Reviewer misses", m.reviewer.misses_caught_later],
      ["Moment hit rate", pct(m.analyst.moment_hit_rate_pct)], ["Leads found", m.manager.leads_found],
      ["Avg views", m.audience.avg_views ?? "—"], ["LLM spend", `$${m.spend_usd}`],
      ["Playbook version", m.playbook.version], ["Active lessons", `${m.playbook.active} (+${m.playbook.candidates} trial)`],
    ];
    $("#kpis").replaceChildren(...kpis.map(([l, v]) => el("div", { class: "st-kpi" }, el("div", { class: "v", text: String(v) }), el("div", { class: "l", text: l }))));
    $("#issues").replaceChildren(...(m.top_issues.length ? m.top_issues.map(([id, n]) => el("div", { class: "st-ev", text: `${id} × ${n}` })) : [el("div", { class: "muted", text: "none yet" })]));
  }

  // -- playbook --------------------------------------------------------------------------------------
  async function loadPlaybook() {
    const pb = await api("/api/agency/playbook");
    const rows = pb.lessons.map((l) => el("tr", {},
      el("td", { text: l.id }), el("td", { text: `${l.role} / ${l.section}` }), el("td", { text: l.text }),
      el("td", { text: `${l.status}${l.protected ? " · yours" : ""}` }), el("td", { text: `+${l.helpful} −${l.harmful} · ${l.uses} uses` }),
      el("td", {}, el("button", { class: "st-btn", text: l.status === "active" ? "Retire" : "Activate", onclick: async () => {
        await post(`/api/agency/playbook/${l.id}/status`, { status: l.status === "active" ? "archived" : "active" }); loadPlaybook();
      } }))));
    $("#lessons").replaceChildren(el("div", { class: "muted", text: `Playbook v${pb.version} — lessons are added after every finished clip, tried on a share of jobs, promoted when they prove helpful and quarantined automatically if quality drops.` }),
      el("table", { class: "st-table" }, el("tr", {}, ...["id", "role", "lesson", "status", "evidence", ""].map((h) => el("th", { text: h }))), ...rows));
  }

  // -- leads & campaigns --------------------------------------------------------------------------------
  async function loadWork() {
    const d = await api("/api/agency/leads");
    $("#leads").replaceChildren(el("tr", {}, ...["#", "lead", "decision", "score", ""].map((h) => el("th", { text: h }))),
      ...d.leads.map((l) => el("tr", {}, el("td", { text: l.id }),
        el("td", {}, /^https?:\/\//i.test(l.url) ? el("a", { href: l.url, target: "_blank", rel: "noopener noreferrer", text: l.title || l.url }) : el("span", { text: l.title || l.url }), el("div", { class: "muted", text: (l.reasons || []).join(" · ") })),
        el("td", { text: `${l.decision || "—"} (${l.status})` }), el("td", { text: l.score == null ? "—" : Math.round(l.score) }),
        el("td", {}, l.status === "qualified" ? el("button", { class: "st-btn", text: "Accept", onclick: async () => {
          try { await post(`/api/agency/leads/${l.id}/accept`); } catch (e) { alert(e.message); } loadWork();
        } }) : null))));
    $("#campaigns").replaceChildren(el("tr", {}, ...["#", "campaign", "permission", "rules"].map((h) => el("th", { text: h }))),
      ...d.campaigns.map((c) => el("tr", {}, el("td", { text: c.id }), el("td", { text: c.name }),
        el("td", { text: c.permission?.granted ? "granted" : "NOT recorded" }),
        el("td", { text: [...(c.brief?.requirements?.hashtags || []), ...(c.brief?.requirements?.mentions || [])].join(" ") }))));
    $("#campaign-select").replaceChildren(el("option", { value: "", text: "— campaign —" }), ...d.campaigns.map((c) => el("option", { value: c.name, text: c.name })));
  }

  $("#lesson-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try { await post("/api/agency/playbook", { role: f.get("role"), section: f.get("section") || "general", text: f.get("text") }); e.target.reset(); }
    catch (err) { alert(err.message); }
    loadPlaybook();
  });
  $("#lead-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try { const q = await post("/api/agency/leads", { url: f.get("url"), terms: f.get("terms") }); alert(`Lead #${q.id}: ${q.decision} (score ${Math.round(q.score)})`); e.target.reset(); }
    catch (err) { alert(err.message); }
    loadWork();
  });
  $("#submit-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const clips = parseInt(f.get("clips"), 10);
    try { const r = await post("/api/agency/submit", { source: f.get("source"), campaign: f.get("campaign") || null, clips: Number.isFinite(clips) ? clips : null, own: f.get("own") === "on" }); alert(`Source job #${r.id} queued`); e.target.reset(); }
    catch (err) { alert(err.message); }
  });

  const loaders = { board: loadBoard, team: loadTeam, playbook: loadPlaybook, work: loadWork };
  let tab = "board";
  $("#tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-tab]");
    if (!b) return;
    tab = b.dataset.tab;
    for (const x of document.querySelectorAll("#tabs button")) x.classList.toggle("on", x === b);
    for (const name of Object.keys(loaders)) $(`#tab-${name}`).classList.toggle("hidden", name !== tab);
    loaders[tab]().catch((err) => console.error(err));
  });
  loadBoard().catch((err) => console.error(err));
  setInterval(() => { if (tab === "board" && !document.hidden) loadBoard().catch(() => {}); }, 10000);
})();
