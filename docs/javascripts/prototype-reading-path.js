// PROTOTYPE — throwaway. Lives only on branch prototype/reading-path-buttons.
// Question: what should the reading-path boxes look like instead of a table?
// Four variants redraw every .reading-path box from its generated table, so the
// generator (vultron/metadata/docs/threads/boxes.py) stays untouched.
// Switch: ?variant=A|B|C|D|off, the floating bar, or the ← / → keys.
// The choice is kept in localStorage so it survives Material's instant nav.
(function () {
  "use strict";

  const VARIANTS = {
    A: "Pill buttons",
    B: "Footer tiles",
    C: "Chevron stepper",
    D: "Compact rail",
    off: "Current table",
  };
  const KEYS = Object.keys(VARIANTS);
  const STORE = "prototype-reading-path-variant";

  function currentVariant() {
    const fromUrl = new URLSearchParams(location.search).get("variant");
    if (fromUrl && VARIANTS[fromUrl]) {
      localStorage.setItem(STORE, fromUrl);
      return fromUrl;
    }
    const stored = localStorage.getItem(STORE);
    return stored && VARIANTS[stored] ? stored : "B";
  }

  // ---- parse a generated box -------------------------------------------
  function parseCell(td) {
    if (!td) return [];
    return Array.from(td.querySelectorAll("li")).map((li) => {
      const a = li.querySelector("a");
      return { text: li.textContent.trim(), href: a ? a.getAttribute("href") : null };
    });
  }

  function parseBox(box) {
    const titleEl = box.querySelector(".admonition-title");
    const title = titleEl ? titleEl.textContent.replace(/^Reading path:\s*/, "").trim() : "";
    let segment = null;
    box.querySelectorAll(":scope > p").forEach((p) => {
      const m = p.textContent.match(/This page is part of (.+?)\.?$/);
      if (m) segment = m[1].trim();
    });
    const tds = box.querySelectorAll("table.reading-path-table tbody td");
    return {
      title,
      segment,
      start: parseCell(tds[0]),
      prev: parseCell(tds[1]),
      current: parseCell(tds[2]),
      next: parseCell(tds[3]),
    };
  }

  // ---- tiny helpers ----------------------------------------------------
  const esc = (s) =>
    s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const link = (item, cls, inner) =>
    item.href
      ? `<a class="${cls}" href="${esc(item.href)}" title="${esc(item.text)}">${inner}</a>`
      : `<span class="${cls} is-here" title="${esc(item.text)}">${inner}</span>`;
  const isStartPage = (d) => d.start.length && !d.start[0].href;

  // A cell with several pages becomes a dropdown (A, D) or a stacked list (B, C).
  function menu(items, cls, label) {
    return `<details class="rpp-menu ${cls}"><summary>${label}</summary><ul>${items
      .map((i) => `<li>${link(i, "rpp-menu-item", esc(i.text))}</li>`)
      .join("")}</ul></details>`;
  }

  // ---- Variant A: pill buttons -----------------------------------------
  function variantA(d) {
    const btn = (items, cls, arrowL, word, arrowR) => {
      if (!items.length) return `<span class="rpp-pill ${cls} is-empty">${arrowL}${word}${arrowR}</span>`;
      if (items.length === 1) {
        return link(items[0], `rpp-pill ${cls}`,
          `${arrowL}<span class="rpp-pill-word">${word}</span><span class="rpp-pill-label">${esc(items[0].text)}</span>${arrowR}`);
      }
      return menu(items, `rpp-pill ${cls}`,
        `${arrowL}<span class="rpp-pill-word">${word}</span><span class="rpp-pill-label">${items.length} choices ▾</span>${arrowR}`);
    };
    const start = isStartPage(d)
      ? ""
      : link(d.start[0], "rpp-pill rpp-home", `<span aria-hidden="true">⌂</span><span class="rpp-sr">Start</span>`);
    return `
      <div class="rpp-a-head">
        <span class="rpp-a-kicker">Reading path</span>
        <span class="rpp-a-title">${esc(d.title)}</span>
        ${d.segment ? `<span class="rpp-chip">${esc(d.segment)}</span>` : ""}
      </div>
      <nav class="rpp-a-bar">
        ${start}
        ${btn(d.prev, "rpp-prev", '<span class="rpp-arrow">‹</span>', "Previous", "")}
        <span class="rpp-pill rpp-here"><span class="rpp-dot">●</span>${esc(d.current[0] ? d.current[0].text : "")}</span>
        ${btn(d.next, "rpp-next", "", "Next", '<span class="rpp-arrow">›</span>')}
      </nav>`;
  }

  // ---- Variant B: footer tiles -----------------------------------------
  function variantB(d) {
    const tile = (items, side, word) => {
      if (!items.length) return `<div class="rpp-tile rpp-tile-${side} is-empty"></div>`;
      if (items.length === 1) {
        return link(items[0], `rpp-tile rpp-tile-${side}`,
          `<span class="rpp-tile-dir">${side === "prev" ? "← " + word : word + " →"}</span>
           <span class="rpp-tile-label">${esc(items[0].text)}</span>`);
      }
      return `<div class="rpp-tile rpp-tile-${side} is-multi">
          <span class="rpp-tile-dir">${side === "prev" ? "← " + word : word + " → pick one"}</span>
          <ul>${items.map((i) => `<li>${link(i, "rpp-tile-item", esc(i.text))}</li>`).join("")}</ul>
        </div>`;
    };
    const restart = isStartPage(d) ? "" : link(d.start[0], "rpp-b-restart", "↺ Path overview");
    return `
      <div class="rpp-b-head">
        <span class="rpp-b-title">📖 ${esc(d.title)}</span>
        ${d.segment ? `<span class="rpp-b-seg">· ${esc(d.segment)}</span>` : ""}
        ${restart}
      </div>
      <div class="rpp-b-tiles">
        ${tile(d.prev, "prev", "Previous")}
        ${tile(d.next, "next", "Next")}
      </div>`;
  }

  // ---- Variant C: chevron stepper --------------------------------------
  function variantC(d) {
    const step = (items, cls, word) => {
      if (!items.length) return "";
      const body = items.length === 1
        ? link(items[0], "rpp-step-link", esc(items[0].text))
        : `<ul>${items.map((i) => `<li>${link(i, "rpp-step-link", esc(i.text))}</li>`).join("")}</ul>`;
      return `<li class="rpp-step ${cls}${items.length > 1 ? " is-multi" : ""}">
          <span class="rpp-step-word">${word}</span>${body}</li>`;
    };
    const steps = [
      isStartPage(d) ? "" : step([{ text: "Path overview", href: d.start[0].href }], "rpp-step-start", "Start"),
      d.prev.length && !isStartPage(d) && d.prev[0].href !== (d.start[0] || {}).href
        ? `<li class="rpp-step rpp-step-gap" aria-hidden="true">…</li>` : "",
      step(d.prev.filter((p) => p.href !== (d.start[0] || {}).href), "rpp-step-prev", "Previous"),
      `<li class="rpp-step rpp-step-here"><span class="rpp-step-word">You are here</span>
         <span class="rpp-step-link">${esc(d.current[0] ? d.current[0].text : "")}</span></li>`,
      step(d.next, "rpp-step-next", d.next.length > 1 ? "Next — choose" : "Next"),
    ];
    return `
      <div class="rpp-c-head">${esc(d.title)}${d.segment ? ` <em>— ${esc(d.segment)}</em>` : ""}</div>
      <ol class="rpp-c-steps">${steps.join("")}</ol>`;
  }

  // ---- Variant D: compact rail -----------------------------------------
  function variantD(d) {
    const round = (items, cls, glyph, word) => {
      if (!items.length) return `<span class="rpp-round ${cls} is-empty" aria-hidden="true">${glyph}</span>`;
      if (items.length === 1) return link(items[0], `rpp-round ${cls}`, `${glyph}<span class="rpp-sr">${word}: ${esc(items[0].text)}</span>`);
      return menu(items, `rpp-round ${cls}`, `${glyph}<sup>${items.length}</sup>`);
    };
    const nextHint = d.next.length === 1 ? `<span class="rpp-d-hint">Next: ${esc(d.next[0].text)}</span>` : "";
    return `
      <div class="rpp-d-rail">
        <span class="rpp-d-label">
          ${isStartPage(d) ? "📖" : link(d.start[0], "rpp-d-home", "📖")}
          <strong>${esc(d.title)}</strong>${d.segment ? `<span class="rpp-d-seg">${esc(d.segment)}</span>` : ""}
        </span>
        ${nextHint}
        <span class="rpp-d-btns">
          ${round(d.prev, "rpp-prev", "◀", "Previous")}
          ${round(d.next, "rpp-next", "▶", "Next")}
        </span>
      </div>`;
  }

  const RENDER = { A: variantA, B: variantB, C: variantC, D: variantD };

  // ---- apply -----------------------------------------------------------
  function apply() {
    const v = currentVariant();
    document.querySelectorAll(".reading-path").forEach((box) => {
      let proto = box.nextElementSibling;
      if (!proto || !proto.classList.contains("rpp")) {
        proto = document.createElement("div");
        box.after(proto);
      }
      if (v === "off") {
        box.style.display = "";
        proto.style.display = "none";
        return;
      }
      box.style.display = "none";
      proto.style.display = "";
      proto.className = `rpp rpp-${v}`;
      proto.innerHTML = RENDER[v](parseBox(box));
    });
    renderSwitcher(v);
  }

  function renderSwitcher(v) {
    let bar = document.getElementById("rpp-switcher");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "rpp-switcher";
      document.body.appendChild(bar);
      bar.addEventListener("click", (e) => {
        const b = e.target.closest("button[data-step]");
        if (b) step(Number(b.dataset.step));
      });
    }
    const boxes = document.querySelectorAll(".reading-path").length;
    bar.innerHTML = `<button data-step="-1" aria-label="Previous variant">←</button>
      <span><b>PROTOTYPE</b> ${v} — ${VARIANTS[v]}
      <small>${boxes ? boxes + " box" + (boxes > 1 ? "es" : "") + " here" : "no box on this page"}</small></span>
      <button data-step="1" aria-label="Next variant">→</button>`;
  }

  function step(delta) {
    const i = KEYS.indexOf(currentVariant());
    const v = KEYS[(i + delta + KEYS.length) % KEYS.length];
    localStorage.setItem(STORE, v);
    const url = new URL(location.href);
    url.searchParams.set("variant", v);
    history.replaceState(history.state, "", url);
    apply();
  }

  document.addEventListener("keydown", (e) => {
    const t = e.target;
    if (t.closest && t.closest("input, textarea, [contenteditable]")) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === "ArrowLeft") step(-1);
    if (e.key === "ArrowRight") step(1);
  });

  // Material's instant navigation swaps the page without a reload.
  if (window.document$ && window.document$.subscribe) window.document$.subscribe(apply);
  else document.addEventListener("DOMContentLoaded", apply);
})();
