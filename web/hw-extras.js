/* HarborWise site add-ons (loaded after the main bundle in index.html).
 *
 * Adds three things the bundled site does not show, using the API responses it already receives:
 *   1. Voyage Lab: forecast confidence (high for container/cruise, lower for tanker/bulk/general cargo)
 *   2. Voyage Lab: the ships alongside the destination berth and when each is expected to leave
 *   3. Model Results: the turnaround-at-arrival comparison (RF / HistGB / GB vs global and port medians)
 *
 * It watches fetch() for /recommendations and /experiments responses and renders panels in the
 * site's own styles. Nothing is shown in offline-sample mode, because there is no model output then.
 */
(function () {
  "use strict";

  const state = { rec: null, exp: null };
  let seq = 0;

  // ---- capture API responses -------------------------------------------------------------
  const prevFetch = window.fetch.bind(window);
  window.fetch = async function (input, options) {
    const res = await prevFetch(input, options);
    try {
      const url = typeof input === "string" ? input : input.url;
      const path = new URL(url, location.href).pathname;
      if (res.ok && (path.endsWith("/recommendations") || path.endsWith("/experiments"))) {
        const mine = ++seq;
        res.clone().json().then((body) => {
          if (body?.schema_version !== "1.0") return;
          if (path.endsWith("/recommendations")) { if (mine >= (state.recSeq || 0)) { state.rec = body; state.recSeq = mine; } }
          else state.exp = body;
          render();
        }).catch(() => {});
      }
    } catch (e) { /* never break the site */ }
    return res;
  };

  // ---- helpers --------------------------------------------------------------------------------
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v, d = 1) => (typeof v === "number" && isFinite(v) ? v.toFixed(d) : "—");
  const pct = (v) => (typeof v === "number" && isFinite(v) ? `${Math.round(v * 100)}%` : "—");
  const TYPE = { cont: "Container", crui: "Cruise", tank: "Tanker", bulk: "Bulk carrier", gcar: "General cargo" };
  const when = (iso) => {
    const d = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : iso + "Z");
    return isNaN(d) ? "—" : new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(d) + " UTC";
  };
  const liveMode = () => /LIVE/.test(document.getElementById("api-badge")?.textContent || "") ||
    /HarborWise API/.test(document.body.innerText.match(/API connection\n[^\n]*/)?.[0] || "");
  const headingSection = (text) => {
    const h = [...document.querySelectorAll(".analysis-root h2")].find((e) => e.textContent.trim() === text);
    return h ? h.closest("section") : null;
  };
  function place(id, anchor, html) {
    let el = document.getElementById(id);
    if (!anchor) { if (el) el.remove(); return; }
    if (!el) { el = document.createElement("section"); el.id = id; el.className = "panel lab-panel hw-extra"; }
    if (el.previousElementSibling !== anchor) anchor.after(el);
    if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; }
  }

  // ---- 1 + 2: confidence and ships alongside (Voyage Lab) -------------------------------------
  function alongsideHtml(r) {
    const c = r.clearance, b = r.berth || {}, prov = r.provenance || {};
    const occ = c.occupants || [];
    const high = c.confidence === "high";
    const conf = high
      ? `<span class="pill mint">HIGH CONFIDENCE</span><p>Every ship alongside is a container or cruise ship. They keep regular schedules, so these forecasts are the most reliable.</p>`
      : `<span class="pill amber">LOWER CONFIDENCE</span><p>At least one ship alongside is a tanker, bulk carrier or general cargo ship. How long they stay depends on cargo we cannot see, so treat this window as a rough guide.</p>`;
    const status = c.status === "free"
      ? `A slot is free now (${occ.length} of ${c.capacity} in use), so there is no queue to time the arrival against.`
      : `Berth full: ${occ.length} ship${occ.length === 1 ? "" : "s"} alongside, capacity ${c.capacity}. A slot frees ${occ.length - c.capacity + 1 === 1 ? "when the first ship leaves" : `once ${occ.length - c.capacity + 1} of them have left`}.`;
    const standIn = prov.stand_in_port ? `<p class="hw-note">⚓ ${esc(prov.stand_in_port)}.</p>` : "";
    const rows = occ.map((o) => {
      const p = o[Object.keys(o).find((k) => k.startsWith("p_leaves_within_"))];
      const q = o.remaining_h || {};
      return `<tr><td>${esc(TYPE[o.vessel_type] || o.vessel_type)}</td><td>${esc(when(o.arrival_time))}</td><td>${num(o.elapsed_h)}</td>` +
        `<td>${num(q.p25)} / <b>${num(q.p50)}</b> / ${num(q.p90)}</td><td>${pct(p)}</td>` +
        `<td><span class="pill ${o.confidence === "high" ? "mint" : "amber"}">${esc(o.confidence)}</span></td></tr>`;
    }).join("");
    const table = occ.length
      ? `<div class="lab-table-wrap"><table class="lab-table"><thead><tr><th>Ship</th><th>Arrived</th><th>Alongside (h)</th>` +
        `<th>Leaves in P25 / P50 / P90 (h)</th><th>Leaves within 6 h</th><th>Confidence</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<p class="hw-note">No commercial ship is alongside at the planning time.</p>`;
    return `<div class="panel-heading"><div><h2>Ships alongside the destination berth</h2>` +
      `<p>Berth ${esc(b.berth_id)} at ${esc(b.portname)}: who is using it now and when each ship is expected to leave</p></div>` +
      `<span class="lab-badge reference">LIVE · TRAINED MODEL</span></div>` +
      `<div class="hw-conf">${conf}</div>${standIn}<p class="hw-status">${esc(status)}</p>${table}` +
      `<p class="hw-foot">Each ship is scored by the model for its own type. “Leaves within 6 h” is a calibrated probability. Times are UTC, replaying 2019.</p>`;
  }

  // ---- 3: turnaround comparison (Model Results) ----------------------------------------------
  function turnaroundHtml(e) {
    const models = e.turnaround_models || [];
    if (!models.length) return null;
    const learned = models.filter((m) => !/median/i.test(m.name));
    const best = learned.reduce((a, m) => (m.mae_h < a.mae_h ? m : a), learned[0] || models[0]);
    const name = (m) => m.name.replace(/ \(stay predicted at arrival\)$/, "").replace(/ \(extra baseline\)$/, " (extra baseline)");
    const rows = models.map((m) => `<tr${m === best ? ' class="hw-best"' : ""}><td>${esc(name(m))}${m === best ? ' <span class="pill mint">best</span>' : ""}</td>` +
      `<td>${num(m.mae_h, 2)}</td><td>${num(m.rmse_h, 2)}</td><td>${num(m.medae_h, 2)}</td><td>${pct(m.within_1h)}</td></tr>`).join("");
    const gain = e.turnaround_improvement_vs_port_median_pct;
    return `<div class="panel-heading"><div><h2>Turnaround predicted at arrival</h2>` +
      `<p>How long a container or cruise ship will stay, predicted the moment it berths · test set · lower is better</p></div>` +
      `<span class="lab-badge reference">TEST SET · MEASURED</span></div>` +
      (typeof gain === "number" ? `<p class="hw-status">${esc(name(best))} is ${num(gain, 0)}% more accurate than the port median.</p>` : "") +
      `<div class="lab-table-wrap"><table class="lab-table"><thead><tr><th>Model</th><th>MAE (h)</th><th>RMSE (h)</th><th>Median error (h)</th><th>Within 1 h</th></tr></thead>` +
      `<tbody>${rows}</tbody></table></div>` +
      `<p class="hw-foot">Same Nov–Dec 2019 test set; models chosen on Sep–Oct validation. RMSE is larger than MAE because a few very long stays are hard to predict.</p>`;
  }

  // ---- render ------------------------------------------------------------------------------------
  function render() {
    const live = liveMode();
    const clearance = headingSection("Predicted clearance window");
    place("hw-alongside", live && state.rec && clearance ? clearance : null, state.rec ? alongsideHtml(state.rec) : "");
    const baselines = headingSection("Baselines vs. tuned XGBoost");
    const anchor = baselines ? (baselines.closest(".lab-two-col") || baselines) : null;
    const html = state.exp ? turnaroundHtml(state.exp) : null;
    place("hw-turnaround", live && html && anchor ? anchor : null, html || "");
  }

  const css = document.createElement("style");
  css.textContent = `
    .hw-extra .hw-conf{display:flex;gap:12px;align-items:flex-start;margin:4px 0 8px}
    .hw-extra .hw-conf .pill{flex:none;margin-top:2px}
    .hw-extra .hw-conf p,.hw-extra .hw-status,.hw-extra .hw-note,.hw-extra .hw-foot{margin:0 0 10px;color:var(--muted,#8c9baa);line-height:1.5}
    .hw-extra .hw-status{color:var(--text,#e7edf1)}
    .hw-extra .hw-note{color:var(--amber,#dfb478)}
    .hw-extra .hw-foot{font-size:.85em;margin-top:10px}
    .hw-extra tr.hw-best td{color:var(--mint,#94e3c2);font-weight:600}
    .hw-extra td,.hw-extra th{white-space:nowrap}
  `;
  document.head.appendChild(css);

  let queued = false;
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; render(); });
  }).observe(document.body, { childList: true, subtree: true });
})();
