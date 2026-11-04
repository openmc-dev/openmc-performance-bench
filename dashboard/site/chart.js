// SVG charts: a line chart with crosshair tooltip and change markers, and a
// non-interactive sparkline for table rows.

import { h, s, clear } from "./dom.js";

const tooltip = () => document.getElementById("tooltip");

export function showTooltip(content, clientX, clientY) {
  const tt = tooltip();
  clear(tt).append(content);
  tt.hidden = false;
  const pad = 14;
  const { width, height } = tt.getBoundingClientRect();
  let x = clientX + pad;
  let y = clientY + pad;
  if (x + width > window.innerWidth - 8) x = clientX - width - pad;
  if (y + height > window.innerHeight - 8) y = clientY - height - pad;
  tt.style.left = `${Math.max(8, x)}px`;
  tt.style.top = `${Math.max(8, y)}px`;
}

export function hideTooltip() {
  tooltip().hidden = true;
}

/** Round tick values ("nice numbers") covering [min, max]. */
export function niceTicks(min, max, count = 4) {
  if (!(isFinite(min) && isFinite(max))) return [];
  if (min === max) {
    const d = Math.abs(min) * 0.05 || 1;
    min -= d;
    max += d;
  }
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((st) => st >= raw);
  const ticks = [];
  for (let t = Math.ceil(min / step) * step; t <= max + step * 1e-9; t += step) {
    ticks.push(Number(t.toPrecision(12)));
  }
  return ticks;
}

/**
 * Render a single-series line chart into `el`.
 *
 * opts:
 *   values      full value array aligned with commits (null = no result)
 *   range       [first, last] commit indices to show (inclusive)
 *   changes     [{commit_index, kind, change}] markers to draw
 *   levels      [{from, to, value}] optional baseline/after level segments
 *   format      value -> string (axis ticks use formatTick if given)
 *   formatTick  value -> short string for the y-axis
 *   xLabel      commit index -> short string for the x-axis
 *   tooltip     commit index -> DOM node
 *   onSelect    commit index -> void (click / Enter)
 *   height      plot height in px
 *   label       accessible name
 */
export function lineChart(el, opts) {
  el.classList.add("chart");
  el.tabIndex = 0;
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", opts.label || "Line chart");
  let focusIndex = null;

  const render = () => {
    const width = Math.max(240, el.clientWidth);
    const height = opts.height || 180;
    const m = { top: 14, right: 14, bottom: 26, left: 58 };
    const [i0, i1] = opts.range;
    const n = Math.max(1, i1 - i0);
    const pts = [];
    for (let i = i0; i <= i1; i++) {
      const v = opts.values[i];
      if (v !== null && v !== undefined) pts.push([i, v]);
    }
    clear(el);
    if (!pts.length) {
      el.append(h("p", { class: "muted" }, "No results in this range."));
      return;
    }

    let lo = Math.min(...pts.map((p) => p[1]));
    let hi = Math.max(...pts.map((p) => p[1]));
    for (const lv of opts.levels || []) {
      lo = Math.min(lo, lv.value);
      hi = Math.max(hi, lv.value);
    }
    const ticks = niceTicks(lo, hi, 4);
    const yMin = Math.min(lo, ticks[0]);
    const yMax = Math.max(hi, ticks[ticks.length - 1]);
    const pw = width - m.left - m.right;
    const ph = height - m.top - m.bottom;
    const x = (i) => m.left + ((i - i0) / n) * pw;
    const y = (v) => m.top + (1 - (v - yMin) / (yMax - yMin || 1)) * ph;
    const fmtTick = opts.formatTick || opts.format;

    const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, height, "aria-hidden": "true" });

    // Gridlines and y ticks
    for (const t of ticks) {
      svg.append(
        s("line", { class: "grid-line", x1: m.left, x2: width - m.right, y1: y(t), y2: y(t) }),
        s("text", { class: "tick-label", x: m.left - 8, y: y(t) + 4, "text-anchor": "end" }, fmtTick(t)),
      );
    }
    svg.append(s("line", { class: "axis-line", x1: m.left, x2: width - m.right,
                           y1: m.top + ph, y2: m.top + ph }));

    // X ticks: evenly spaced commit indices
    const nx = Math.max(2, Math.min(6, Math.floor(pw / 110)));
    const seen = new Set();
    for (let k = 0; k <= nx; k++) {
      const i = Math.round(i0 + (k / nx) * (i1 - i0));
      if (seen.has(i)) continue;
      seen.add(i);
      const anchor = k === 0 ? "start" : k === nx ? "end" : "middle";
      svg.append(s("text", { class: "tick-label", x: x(i), y: height - 6, "text-anchor": anchor },
                   opts.xLabel(i)));
    }

    // Area wash + line, broken at missing values
    let d = "";
    let segStart = null;
    let prev = null;
    const washes = [];
    for (const [i, v] of pts) {
      if (prev === null || i !== prev + 1) {
        if (segStart !== null) washes.push([segStart, prev]);
        d += `M${x(i)},${y(v)}`;
        segStart = i;
      } else {
        d += `L${x(i)},${y(v)}`;
      }
      prev = i;
    }
    washes.push([segStart, prev]);
    for (const [a, b] of washes) {
      let w = `M${x(a)},${m.top + ph}`;
      for (let i = a; i <= b; i++) w += `L${x(i)},${y(opts.values[i])}`;
      w += `L${x(b)},${m.top + ph}Z`;
      svg.append(s("path", { class: "series-wash", d: w }));
    }
    // Change markers and levels: above the wash, below the line
    for (const c of opts.changes || []) {
      if (c.commit_index < i0 || c.commit_index > i1) continue;
      const cx = x(c.commit_index);
      svg.append(
        s("line", { class: `change-rule ${c.kind}`, x1: cx, x2: cx, y1: m.top, y2: m.top + ph }),
        s("path", { class: `change-flag ${c.kind}`,
                    d: `M${cx - 5},${m.top - 8} h10 l-5,7 z` }),
      );
    }

    // Baseline / after levels for the selected change
    for (const lv of opts.levels || []) {
      const a = Math.max(lv.from, i0);
      const b = Math.min(lv.to, i1);
      if (a > b) continue;
      svg.append(s("line", { class: "level-line", x1: x(a), x2: x(b), y1: y(lv.value), y2: y(lv.value) }));
    }

    svg.append(s("path", { class: "series-line", d }));

    // Missing results inside the plotted span: small marks on the baseline
    const first = pts[0][0];
    for (let i = Math.max(i0, first); i <= i1; i++) {
      const v = opts.values[i];
      if (v === null || v === undefined) {
        svg.append(s("rect", { class: "missing-mark", x: x(i) - 3, y: m.top + ph - 3, width: 6, height: 6, rx: 1 }));
      }
    }

    const [li, lv] = pts[pts.length - 1];
    svg.append(s("circle", { class: "end-dot", cx: x(li), cy: y(lv), r: 4 }));

    // Hover layer
    const cross = s("line", { class: "crosshair", y1: m.top, y2: m.top + ph, visibility: "hidden" });
    const dot = s("circle", { class: "hover-dot", r: 4, visibility: "hidden" });
    const hit = s("rect", { x: m.left - 6, y: 0, width: pw + 12, height, fill: "transparent" });
    svg.append(cross, dot, hit);

    const indexAt = (clientX) => {
      const r = svg.getBoundingClientRect();
      const px = ((clientX - r.left) / r.width) * width;
      return Math.max(i0, Math.min(i1, Math.round(i0 + ((px - m.left) / pw) * n)));
    };
    const highlight = (i, clientX, clientY) => {
      const cx = x(i);
      cross.setAttribute("x1", cx);
      cross.setAttribute("x2", cx);
      cross.setAttribute("visibility", "visible");
      const v = opts.values[i];
      if (v !== null && v !== undefined) {
        dot.setAttribute("cx", cx);
        dot.setAttribute("cy", y(v));
        dot.setAttribute("visibility", "visible");
      } else {
        dot.setAttribute("visibility", "hidden");
      }
      if (opts.tooltip) showTooltip(opts.tooltip(i), clientX, clientY);
    };
    const unhighlight = () => {
      cross.setAttribute("visibility", "hidden");
      dot.setAttribute("visibility", "hidden");
      hideTooltip();
    };

    hit.addEventListener("pointermove", (e) => highlight(indexAt(e.clientX), e.clientX, e.clientY));
    hit.addEventListener("pointerleave", unhighlight);
    hit.addEventListener("click", (e) => opts.onSelect && opts.onSelect(indexAt(e.clientX)));
    if (opts.onSelect) hit.style.cursor = "pointer";

    el.onkeydown = (e) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End", "Enter", "Escape"].includes(e.key)) return;
      e.preventDefault();
      if (e.key === "Escape") { unhighlight(); return; }
      if (focusIndex === null) focusIndex = li;
      if (e.key === "ArrowLeft") focusIndex = Math.max(i0, focusIndex - 1);
      if (e.key === "ArrowRight") focusIndex = Math.min(i1, focusIndex + 1);
      if (e.key === "Home") focusIndex = i0;
      if (e.key === "End") focusIndex = i1;
      if (e.key === "Enter" && opts.onSelect) { opts.onSelect(focusIndex); return; }
      const r = svg.getBoundingClientRect();
      highlight(focusIndex, r.left + (x(focusIndex) / width) * r.width, r.top + m.top);
    };
    el.onblur = unhighlight;

    el.append(svg);
  };

  render();
  let lastWidth = el.clientWidth;
  const ro = new ResizeObserver(() => {
    if (!el.isConnected) {
      ro.disconnect();
      return;
    }
    if (Math.abs(el.clientWidth - lastWidth) > 4) {
      lastWidth = el.clientWidth;
      render();
    }
  });
  ro.observe(el);
  return el;
}

/** Small trend line for table rows (values already sliced to the range). */
export function sparkline(values, { width = 110, height = 24 } = {}) {
  const pts = values.map((v, i) => [i, v]).filter((p) => p[1] !== null && p[1] !== undefined);
  const svg = s("svg", { class: "spark", width, height, viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true" });
  if (pts.length < 2) return svg;
  const lo = Math.min(...pts.map((p) => p[1]));
  const hi = Math.max(...pts.map((p) => p[1]));
  const n = values.length - 1 || 1;
  const x = (i) => 2 + (i / n) * (width - 8);
  const y = (v) => 3 + (1 - (v - lo) / (hi - lo || 1)) * (height - 6);
  let d = "";
  let prev = null;
  for (const [i, v] of pts) {
    d += `${prev === null || i !== prev + 1 ? "M" : "L"}${x(i)},${y(v)}`;
    prev = i;
  }
  const [li, lv] = pts[pts.length - 1];
  svg.append(s("path", { class: "series-line", d }), s("circle", { class: "end-dot", cx: x(li), cy: y(lv), r: 2.5 }));
  return svg;
}
