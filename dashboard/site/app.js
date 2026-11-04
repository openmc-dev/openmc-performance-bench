// OpenMC performance dashboard: overview, benchmark detail and commit views,
// rendered from data/perf.json (build_data.py) and data/regressions.json
// (regressions.py --json).

import { h, clear } from "./dom.js";
import { lineChart, sparkline } from "./chart.js";

const OPENMC = "https://github.com/openmc-dev/openmc";
const SERIAL = "(1, None)";
const BASELINE_WINDOW = 10;
// A confirmed change this many commits ago still sets a benchmark's status
// (matches Params.recent in regressions.py)
const RECENT_COMMITS = 10;

const METRIC_LABELS = {
  transport_time: "Transport time",
  elapsed_wall: "Wall time",
  total_time_elapsed: "Total time",
  initialization_time: "Initialization time",
  max_rss_kb: "Peak memory",
  parallel_efficiency: "Parallel efficiency",
  calc_rate_active: "Particle rate (active)",
  calc_rate_inactive: "Particle rate (inactive)",
  figure_of_merit: "Figure of merit",
};
const METRIC_ORDER = Object.keys(METRIC_LABELS);
// Metrics where a higher value is better (everything else: lower is better)
const HIGHER_IS_BETTER = new Set([
  "parallel_efficiency", "calc_rate_active", "calc_rate_inactive", "figure_of_merit",
]);

const STATUS = {
  failing: { label: "No result", rank: 0 },
  regression: { label: "Regression", rank: 1 },
  possible_regression: { label: "Possible regression", rank: 2 },
  improvement: { label: "Improvement", rank: 3 },
  possible_improvement: { label: "Possible improvement", rank: 4 },
  ok: { label: "OK", rank: 5 },
};

const state = {
  perf: null,
  reg: null,
  seriesIndex: new Map(),
  range: loadPref("range", "90"),
};

// ---------------------------------------------------------------- utilities

function loadPref(key, fallback) {
  try {
    return localStorage.getItem(`perfdash.${key}`) ?? fallback;
  } catch {
    return fallback;
  }
}

function savePref(key, value) {
  try {
    localStorage.setItem(`perfdash.${key}`, value);
  } catch {
    /* storage unavailable; preference lasts for this page only */
  }
}

const metricLabel = (m) =>
  METRIC_LABELS[m] || m.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function configLabel(config) {
  const [t, p] = config.replace(/[()\s]/g, "").split(",");
  const threads = `${t} thread${t === "1" ? "" : "s"}`;
  return p === "None" ? threads : `${p} MPI ranks × ${threads}`;
}

function formatValue(metric, v) {
  if (v === null || v === undefined) return "—";
  const unit = state.perf.units[metric] || "";
  if (unit === "seconds") {
    if (v < 1) return `${(v * 1000).toPrecision(3)} ms`;
    if (v < 100) return `${v.toPrecision(3)} s`;
    return `${Math.round(v)} s`;
  }
  if (unit === "KB") {
    const mib = v / 1024;
    return mib >= 1024 ? `${(mib / 1024).toFixed(2)} GiB` : `${mib.toFixed(mib < 100 ? 1 : 0)} MiB`;
  }
  if (unit === "fraction") return `${(v * 100).toFixed(0)}%`;
  if (unit === "particles / second") return `${compact(v)}/s`;
  return compact(v);
}

function compact(v) {
  const a = Math.abs(v);
  if (a >= 1e6) return `${(v / 1e6).toPrecision(3)}M`;
  if (a >= 1e4) return `${(v / 1e3).toPrecision(3)}K`;
  return Number(v.toPrecision(4)).toLocaleString();
}

function formatPct(x, digits = 1) {
  if (x === null || x === undefined || !isFinite(x)) return "—";
  const sign = x > 0 ? "+" : x < 0 ? "−" : "";
  return `${sign}${Math.abs(x * 100).toFixed(digits)}%`;
}

const shortDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const longDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

function median(xs) {
  if (!xs.length) return null;
  const a = [...xs].sort((p, q) => p - q);
  const mid = a.length >> 1;
  return a.length % 2 ? a[mid] : (a[mid - 1] + a[mid]) / 2;
}

/** Median of up to BASELINE_WINDOW recorded values before commit i. */
function baselineAt(values, i) {
  const prior = [];
  for (let k = i - 1; k >= 0 && prior.length < BASELINE_WINDOW; k--) {
    if (values[k] !== null && values[k] !== undefined) prior.push(values[k]);
  }
  return prior.length >= 3 ? median(prior) : null;
}

function relChange(values, i) {
  const v = values[i];
  const b = baselineAt(values, i);
  return v === null || v === undefined || !b ? null : v / b - 1;
}

/** CSS class for a relative change: colored only when it exceeds the series' noise threshold. */
function deltaClass(metric, change, threshold) {
  if (change === null || threshold === null || threshold === undefined) return "delta-none";
  if (Math.abs(change) <= threshold) return "delta-none";
  const worse = HIGHER_IS_BETTER.has(metric) ? change < 0 : change > 0;
  return worse ? "delta-bad" : "delta-good";
}

const seriesKey = (b, m, c) => `${b}|${m}|${c}`;
const seriesInfo = (b, m, c) => state.seriesIndex.get(seriesKey(b, m, c));
const values = (b, m, c) => state.perf.benchmarks[b]?.[m]?.[c] || [];
const hasValues = (arr) => arr.some((v) => v !== null && v !== undefined);

/** The main time metric for a benchmark: transport time if reported, else wall time. */
function primaryMetric(bench) {
  const t = state.perf.benchmarks[bench].transport_time;
  return t && hasValues(Object.values(t).flat()) ? "transport_time" : "elapsed_wall";
}

function visibleRange() {
  const n = state.perf.commits.length;
  const keep = state.range === "all" ? n : Number(state.range);
  return [Math.max(0, n - keep), n - 1];
}

const commit = (i) => state.perf.commits[i];
const shaShort = (i) => commit(i).sha.slice(0, 8);

function commitLink(i, { withTitle = true } = {}) {
  const c = commit(i);
  const parts = [h("a", { href: `#/commit/${c.sha.slice(0, 8)}` }, c.sha.slice(0, 8))];
  if (c.pr) parts.push(" ", h("a", { href: `${OPENMC}/pull/${c.pr}` }, `#${c.pr}`));
  if (withTitle && c.title) parts.push(" ", h("span", { class: "secondary" }, c.title));
  return h("span", {}, parts);
}

function badge(status) {
  const info = STATUS[status] || { label: status };
  return h("span", { class: `badge ${status}` }, info.label);
}

// ------------------------------------------------------------------- views

function renderOverview(app) {
  const benches = Object.keys(state.perf.benchmarks).sort();
  const n = state.perf.commits.length;
  const latest = n - 1;
  const rows = benches.map((b) => benchmarkSummary(b, latest));

  const count = (st) => rows.filter((r) => r.status === st).length;
  const lc = commit(latest);
  app.append(
    h("div", { class: "tiles" },
      tile("Benchmarks", benches.length, `${state.perf.machine}`),
      tile("Latest commit", shortDate(lc.date), lc.pr ? `PR #${lc.pr}` : lc.sha.slice(0, 8)),
      tile("Regressions", count("regression"), `confirmed in the last ${RECENT_COMMITS} commits`),
      tile("Possible regressions", count("possible_regression"), "not yet confirmed"),
      tile("Improvements", count("improvement"), `confirmed in the last ${RECENT_COMMITS} commits`),
      tile("Without a result", count("failing"), "at the latest commit"),
    ),
  );

  app.append(renderEvents());

  // Health table
  const search = h("input", { class: "search", type: "search", placeholder: "Filter benchmarks",
                              "aria-label": "Filter benchmarks" });
  const tbody = h("tbody");
  const [i0, i1] = visibleRange();
  const fillRows = () => {
    clear(tbody);
    const q = search.value.trim().toLowerCase();
    rows
      .filter((r) => !q || r.bench.toLowerCase().includes(q))
      .sort((a, b) => (STATUS[a.status].rank - STATUS[b.status].rank) || a.bench.localeCompare(b.bench))
      .forEach((r) => {
        const v = values(r.bench, r.metric, SERIAL);
        tbody.append(h("tr", {},
          h("td", {}, h("a", { href: `#/benchmark/${encodeURIComponent(r.bench)}` }, r.bench)),
          h("td", {}, badge(r.status),
            r.reason ? h("div", { class: "status-reason" }, r.reason) : null),
          h("td", { class: "secondary" }, metricLabel(r.metric)),
          h("td", { class: "num" }, formatValue(r.metric, v[latest])),
          h("td", { class: `num ${deltaClass(r.metric, r.change, r.threshold)}` }, formatPct(r.change)),
          h("td", {}, sparkline(v.slice(i0, i1 + 1))),
        ));
      });
  };
  search.addEventListener("input", fillRows);
  fillRows();

  const baselineTip = `Latest ÷ median of the previous ${BASELINE_WINDOW} commits − 1; ` +
    "grey when within the series' noise";
  app.append(h("section", { class: "card" },
    h("h2", {}, "All benchmarks"),
    h("p", { class: "subtitle" },
      "Metric is the 1-thread transport time, or wall time for benchmarks that don't report it. ",
      "“vs baseline” compares the latest result with the median of the previous ",
      `${BASELINE_WINDOW} commits; changes within a series' normal noise are grey.`),
    h("p", { class: "subtitle" },
      "Status is the most serious finding across all alerting metrics (including memory and other ",
      "thread counts), named under the badge. ",
      `Regression or Improvement is a confirmed change in the last ${RECENT_COMMITS} commits; `,
      "Possible means seen at the latest commits but not yet confirmed; ",
      "No result means the benchmark failed or is missing at the latest commit."),
    search,
    h("div", { class: "table-wrap" },
      h("table", { class: "data" },
        h("thead", {}, h("tr", {},
          h("th", {}, "Benchmark"),
          h("th", { title: "Most serious finding across all alerting metrics" }, "Status"),
          h("th", { title: "Transport time if reported, else wall time" }, "Metric"),
          h("th", { class: "num", title: "Value at the latest commit" }, "Latest"),
          h("th", { class: "num", title: baselineTip }, "vs baseline"),
          h("th", { title: "Metric over the selected commit range" }, "Trend"),
        )),
        tbody,
      ),
    ),
  ));
}

function tile(label, value, note) {
  return h("div", { class: "tile" },
    h("div", { class: "tile-label" }, label),
    h("div", { class: "tile-value" }, String(value)),
    h("div", { class: "tile-note" }, note));
}

function benchmarkSummary(bench, latest) {
  const metric = primaryMetric(bench);
  const v = values(bench, metric, SERIAL);
  const info = seriesInfo(bench, metric, SERIAL);
  // Status: confirmed changes only count when corroborated (as in the events
  // list); unconfirmed changes at the latest commits come from series status.
  let status = "ok";
  let reason = null;
  const consider = (st, why) => {
    if (STATUS[st].rank < STATUS[status].rank) {
      status = st;
      reason = why;
    }
  };
  const describe = (m, c) => (c === SERIAL ? metricLabel(m) : `${metricLabel(m)}, ${configLabel(c)}`);
  for (const g of state.reg.changes) {
    if (g.benchmark !== bench || g.role !== "alert" || !g.corroborated) continue;
    if (g.commit_index < latest + 1 - RECENT_COMMITS) continue;
    const main = g.series.find((sr) => sr.role === "alert") || g.series[0];
    consider(g.kind, describe(g.metric, main.config));
  }
  for (const r of state.reg.series) {
    if (r.benchmark !== bench || r.role !== "alert") continue;
    if (r.status === "possible_regression" || r.status === "possible_improvement") {
      consider(r.status, describe(r.metric, r.config));
    }
  }
  if (v[latest] === null || v[latest] === undefined) {
    consider("failing", metricLabel(metric));
  }

  return {
    bench, metric, status, reason,
    change: relChange(v, latest),
    threshold: info?.threshold ?? null,
  };
}

/** Detected events (grouped like regressions.py's report), newest first. */
function renderEvents({ bench = null } = {}) {
  const [i0] = visibleRange();
  const groups = state.reg.changes.filter((g) =>
    g.role === "alert" && g.commit_index >= i0 && (!bench || g.benchmark === bench));
  const events = new Map();
  for (const g of groups) {
    const key = `${g.event_commits.join(",")}|${g.kind}|${g.metric}|${g.corroborated}`;
    if (!events.has(key)) events.set(key, { ...g, groups: [] });
    events.get(key).groups.push(g);
  }
  const all = [...events.values()].sort((a, b) => b.event_commits[0] - a.event_commits[0]);
  const strong = all.filter((e) => e.corroborated);
  const weak = all.filter((e) => !e.corroborated);

  const list = (evs) => h("ul", { class: "events" }, evs.map(eventItem));
  const card = h("section", { class: "card" },
    h("h2", {}, bench ? "Detected changes" : "Recent changes"),
    h("p", { class: "subtitle" },
      "Sustained changes confirmed over at least 3 commits and seen in more than one series ",
      "or benchmark. Times and memory are at 1 thread unless noted."),
    strong.length ? list(strong) : h("p", { class: "muted" }, "No confirmed changes in this range."),
  );
  if (weak.length) {
    card.append(h("details", { class: "disclosure" },
      h("summary", {}, `Low-confidence changes (${weak.length}): seen in only one series, often noise`),
      list(weak)));
  }

  const results = state.reg.results_changes.filter((g) =>
    g.commit_index >= i0 && (!bench || g.benchmark === bench));
  if (results.length) {
    card.append(h("details", { class: "disclosure" },
      h("summary", {}, `Results changed (${results.length}): deterministic tally values changed`),
      h("ul", { class: "events" }, results.map((g) => h("li", { class: "event" },
        h("div", { class: "event-head" },
          h("a", { href: `#/benchmark/${encodeURIComponent(g.benchmark)}` }, g.benchmark),
          h("span", { class: "event-meta" }, longDate(commit(g.commit_index).date))),
        h("div", { class: "event-commits" }, commitLink(g.commit_index)),
        h("div", { class: "event-benchmarks" },
          g.series.map((sr) => h("span", {}, `${metricLabel(sr.metric)} (${configLabel(sr.config)})`))),
      )))));
  }
  return card;
}

function eventItem(e) {
  const kindLabel = e.kind === "regression" ? "Regression" : "Improvement";
  const first = e.event_commits[0];
  return h("li", { class: "event" },
    h("div", { class: "event-head" },
      badge(e.kind),
      h("span", { class: "event-title" },
        `${metricLabel(e.metric)}, ${e.groups.length} benchmark${e.groups.length === 1 ? "" : "s"}`),
      h("span", { class: "event-meta" }, longDate(commit(first).date))),
    h("div", { class: "event-commits" },
      e.event_commits.length > 1 ? "Candidates: " : "",
      e.event_commits.map((ci, k) => [k ? h("br") : null, commitLink(ci)])),
    h("div", { class: "event-benchmarks" },
      e.groups.sort((a, b) => a.benchmark.localeCompare(b.benchmark)).map((g) => {
        const main = g.series.find((sr) => sr.role === "alert") || g.series[0];
        const extra = g.series.length > 1 ? ` (${g.series.length} series)` : "";
        const cfg = main.config === SERIAL ? "" : `, ${configLabel(main.config)}`;
        return h("span", {},
          h("a", { href: `#/benchmark/${encodeURIComponent(g.benchmark)}?metric=${e.metric}` }, g.benchmark),
          " ", h("span", { class: main.change > 0 === HIGHER_IS_BETTER.has(e.metric) ? "delta-good" : "delta-bad" },
            formatPct(main.change)),
          h("span", { class: "muted" }, `${cfg}${extra}`));
      })),
  );
}

function renderBenchmark(app, bench, params) {
  const metrics = state.perf.benchmarks[bench];
  if (!metrics) {
    app.append(h("p", {}, `Unknown benchmark “${bench}”. `, h("a", { href: "#/" }, "Back to overview")));
    return;
  }
  const available = Object.keys(metrics)
    .filter((m) => hasValues(Object.values(metrics[m]).flat()))
    .sort((a, b) => {
      const ia = METRIC_ORDER.indexOf(a);
      const ib = METRIC_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    });
  const metric = available.includes(params.get("metric")) ? params.get("metric") : primaryMetric(bench);
  const [i0, i1] = visibleRange();

  app.append(
    h("div", { class: "breadcrumb" }, h("a", { href: "#/" }, "Overview"), " / ", bench),
    h("h1", { class: "page-title" }, bench),
    h("p", { class: "page-subtitle" },
      "Each panel is one thread/MPI configuration with its own scale. Markers show detected ",
      "changes; click a point to see everything that changed at that commit."),
  );

  const tabs = h("div", { class: "tabs", role: "tablist", "aria-label": "Metric" },
    available.map((m) => h("button", {
      type: "button", role: "tab", "aria-selected": m === metric ? "true" : "false",
      onclick: () => { location.hash = `#/benchmark/${encodeURIComponent(bench)}?metric=${m}`; },
    }, metricLabel(m))));
  app.append(tabs);

  const configs = Object.keys(metrics[metric]).filter((c) => hasValues(metrics[metric][c]));
  const panels = h("div", { class: "panels" });
  app.append(panels);
  for (const config of configs) {
    panels.append(renderPanel(bench, metric, config, [i0, i1], config === configs[0]));
  }

  app.append(renderEvents({ bench }));
  app.append(renderValueTable(bench, metric, configs, [i0, i1]));
}

function renderPanel(bench, metric, config, range, primary) {
  const v = values(bench, metric, config);
  const info = seriesInfo(bench, metric, config);
  const latestIdx = range[1];
  const changes = info?.changes || [];

  // Show the baseline and new level around the most recent visible change
  const levels = [];
  const lastChange = [...changes].reverse().find((c) => c.commit_index >= range[0]);
  if (lastChange) {
    const ci = lastChange.commit_index;
    levels.push({ from: Math.max(range[0], ci - BASELINE_WINDOW), to: ci - 1, value: lastChange.baseline },
                { from: ci, to: Math.min(range[1], ci + 2), value: lastChange.after });
  }

  const statusText = (() => {
    if (!info) return "Not analyzed for regressions";
    const role = { alert: "Alerting", support: "Supporting evidence", dashboard: "Shown only",
                   results: "Deterministic result" }[info.role] || info.role;
    const notes = {
      noisy: "too noisy to analyze", too_small: "too short to analyze reliably",
      stale: "no recent results", insufficient_data: "not enough results yet",
      nondeterministic: "varies between runs",
    };
    const st = notes[info.status] || (STATUS[info.status]?.label ?? info.status).toLowerCase();
    const noise = info.noise !== null && info.noise !== undefined ? ` · noise ±${(info.noise * 100).toFixed(1)}%` : "";
    return `${role} · ${st}${noise}`;
  })();

  const chartEl = h("div");
  const panel = h("div", { class: `panel${primary ? " primary" : ""}` },
    h("div", { class: "panel-head" },
      h("span", { class: "panel-title" }, configLabel(config)),
      h("span", { class: "panel-latest" }, `Latest ${formatValue(metric, v[latestIdx])}`)),
    h("div", { class: "panel-status" }, statusText),
    chartEl,
  );

  requestAnimationFrame(() => lineChart(chartEl, {
    values: v,
    range,
    changes,
    levels,
    height: primary ? 220 : 170,
    format: (x) => formatValue(metric, x),
    formatTick: (x) => formatValue(metric, x),
    xLabel: (i) => shortDate(commit(i).date),
    label: `${metricLabel(metric)} for ${bench}, ${configLabel(config)}, over ${range[1] - range[0] + 1} commits`,
    onSelect: (i) => { location.hash = `#/commit/${shaShort(i)}`; },
    tooltip: (i) => {
      const c = commit(i);
      const val = v[i];
      const ch = relChange(v, i);
      const change = changes.find((x) => x.commit_index === i);
      return h("div", {},
        h("div", { class: "tt-value" }, val === null || val === undefined ? "No result" : formatValue(metric, val)),
        h("div", { class: "tt-row" }, h("span", { class: "tt-key" }),
          `${metricLabel(metric)}, ${configLabel(config)}`),
        ch !== null ? h("div", { class: "tt-row" }, `${formatPct(ch)} vs previous ${BASELINE_WINDOW} commits`) : null,
        change ? h("div", { class: "tt-row" },
          `Detected ${change.kind} starting here: ${formatPct(change.change)}`) : null,
        h("div", { class: "tt-commit" },
          `${longDate(c.date)} · ${c.sha.slice(0, 8)}${c.pr ? ` · #${c.pr}` : ""}`),
        c.title ? h("div", { class: "tt-row" }, c.title) : null,
      );
    },
  }));
  return panel;
}

function renderValueTable(bench, metric, configs, [i0, i1]) {
  const tbody = h("tbody");
  for (let i = i1; i >= i0; i--) {
    tbody.append(h("tr", {},
      h("td", {}, h("a", { href: `#/commit/${shaShort(i)}` }, shaShort(i))),
      h("td", { class: "secondary" }, shortDate(commit(i).date)),
      configs.map((c) => h("td", { class: "num" }, formatValue(metric, values(bench, metric, c)[i]))),
    ));
  }
  return h("section", { class: "card" },
    h("details", {},
      h("summary", {}, h("strong", {}, "Table of values")),
      h("div", { class: "table-wrap" },
        h("table", { class: "data" },
          h("thead", {}, h("tr", {}, h("th", {}, "Commit"), h("th", {}, "Date"),
            configs.map((c) => h("th", { class: "num" }, configLabel(c))))),
          tbody))));
}

function renderCommit(app, sha) {
  const idx = state.perf.commits.findIndex((c) => c.sha.startsWith(sha));
  if (idx < 0) {
    app.append(h("p", {}, `Commit ${sha} has no benchmark results. `, h("a", { href: "#/" }, "Back to overview")));
    return;
  }
  const c = commit(idx);
  const n = state.perf.commits.length;
  app.append(
    h("div", { class: "breadcrumb" }, h("a", { href: "#/" }, "Overview"), " / commit"),
    h("h1", { class: "page-title" }, c.title || c.sha.slice(0, 8)),
    h("p", { class: "page-subtitle" },
      h("a", { href: `${OPENMC}/commit/${c.sha}` }, c.sha.slice(0, 8)),
      c.pr ? [" · ", h("a", { href: `${OPENMC}/pull/${c.pr}` }, `PR #${c.pr}`)] : null,
      c.author ? ` · ${c.author}` : null, ` · ${longDate(c.date)}`),
    h("div", { class: "pager" },
      idx > 0 ? h("a", { href: `#/commit/${shaShort(idx - 1)}` }, "← Previous commit") : null,
      idx < n - 1 ? h("a", { href: `#/commit/${shaShort(idx + 1)}` }, "Next commit →") : null),
  );

  // Detected changes attributed to (or near) this commit
  const here = state.reg.changes.filter((g) => g.role === "alert" && g.event_commits.includes(idx));
  if (here.length) {
    app.append(h("section", { class: "card" },
      h("h2", {}, "Detected changes at this commit"),
      h("ul", { class: "events" }, here.map((g) => h("li", { class: "event" },
        h("div", { class: "event-head" }, badge(g.kind),
          h("a", { href: `#/benchmark/${encodeURIComponent(g.benchmark)}?metric=${g.metric}` }, g.benchmark),
          h("span", { class: "secondary" }, metricLabel(g.metric)),
          g.corroborated ? null : h("span", { class: "muted" }, "low confidence"),
          g.event_commits.length > 1 ? h("span", { class: "muted" }, "· also attributed to an adjacent commit") : null),
        h("div", { class: "event-benchmarks" }, g.series.map((sr) =>
          h("span", {}, `${configLabel(sr.config)} ${formatPct(sr.change)}`))),
      )))));
  }

  const rows = Object.keys(state.perf.benchmarks).sort().map((b) => {
    const m = primaryMetric(b);
    const v = values(b, m, SERIAL);
    const info = seriesInfo(b, m, SERIAL);
    const ch = relChange(v, idx);
    const memCh = relChange(values(b, "max_rss_kb", SERIAL), idx);
    const memInfo = seriesInfo(b, "max_rss_kb", SERIAL);
    const sig = (x, t) => (x === null || !t ? 0 : Math.abs(x) / t);
    return { b, m, v, info, ch, memCh, memInfo,
             score: Math.max(sig(ch, info?.threshold), sig(memCh, memInfo?.threshold)) };
  }).sort((a, b) => b.score - a.score);

  app.append(h("section", { class: "card" },
    h("h2", {}, "All benchmarks at this commit"),
    h("p", { class: "subtitle" },
      `1-thread results compared with the median of the previous ${BASELINE_WINDOW} commits, `,
      "largest changes relative to each series' noise first. A single commit can move by chance; ",
      "detected changes above require the shift to persist."),
    h("div", { class: "table-wrap" }, h("table", { class: "data" },
      h("thead", {}, h("tr", {},
        h("th", {}, "Benchmark"), h("th", {}, "Metric"), h("th", { class: "num" }, "Value"),
        h("th", { class: "num" }, "Baseline"), h("th", { class: "num" }, "Change"),
        h("th", { class: "num" }, "Memory change"))),
      h("tbody", {}, rows.map((r) => h("tr", { class: r.score <= 1 ? "dim" : "" },
        h("td", {}, h("a", { href: `#/benchmark/${encodeURIComponent(r.b)}?metric=${r.m}` }, r.b)),
        h("td", {}, metricLabel(r.m)),
        h("td", { class: "num" }, r.v[idx] === null || r.v[idx] === undefined ? "No result" : formatValue(r.m, r.v[idx])),
        h("td", { class: "num" }, formatValue(r.m, baselineAt(r.v, idx))),
        h("td", { class: `num ${deltaClass(r.m, r.ch, r.info?.threshold)}` }, formatPct(r.ch)),
        h("td", { class: `num ${deltaClass("max_rss_kb", r.memCh, r.memInfo?.threshold)}` }, formatPct(r.memCh)),
      ))))),
  ));
}

// ------------------------------------------------------------------ router

function route() {
  const app = clear(document.getElementById("app"));
  const [path, query = ""] = location.hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(query);
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "benchmark" && parts[1]) {
    renderBenchmark(app, decodeURIComponent(parts[1]), params);
    document.title = `${decodeURIComponent(parts[1])} · OpenMC Performance`;
  } else if (parts[0] === "commit" && parts[1]) {
    renderCommit(app, parts[1]);
    document.title = `Commit ${parts[1]} · OpenMC Performance`;
  } else {
    renderOverview(app);
    document.title = "OpenMC Performance";
  }
}

function setupControls() {
  const buttons = document.querySelectorAll("#range-filter button");
  const sync = () => buttons.forEach((b) =>
    b.setAttribute("aria-pressed", b.dataset.range === state.range ? "true" : "false"));
  buttons.forEach((b) => b.addEventListener("click", () => {
    state.range = b.dataset.range;
    savePref("range", state.range);
    sync();
    route();
  }));
  sync();

  const toggle = document.getElementById("theme-toggle");
  const themes = ["auto", "light", "dark"];
  const apply = (t) => {
    if (t === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t;
    toggle.textContent = `Theme: ${t}`;
  };
  let theme = loadPref("theme", "auto");
  apply(theme);
  toggle.addEventListener("click", () => {
    theme = themes[(themes.indexOf(theme) + 1) % themes.length];
    savePref("theme", theme);
    apply(theme);
  });
}

async function main() {
  setupControls();
  try {
    const [perf, reg] = await Promise.all([
      fetch("data/perf.json").then((r) => { if (!r.ok) throw new Error(`perf.json: ${r.status}`); return r.json(); }),
      fetch("data/regressions.json").then((r) => { if (!r.ok) throw new Error(`regressions.json: ${r.status}`); return r.json(); }),
    ]);
    state.perf = perf;
    state.reg = reg;
    for (const r of reg.series) state.seriesIndex.set(seriesKey(r.benchmark, r.metric, r.config), r);
  } catch (err) {
    clear(document.getElementById("app")).append(
      h("p", {}, "Could not load the benchmark data (", String(err.message || err), "). ",
        "If you opened this file directly, serve the directory instead, e.g. ",
        h("code", {}, "python -m http.server"), "."));
    return;
  }
  const n = state.perf.commits.length;
  document.getElementById("data-meta").textContent =
    `${n} commits · updated ${longDate(state.perf.generated_at)}`;
  window.addEventListener("hashchange", () => { route(); window.scrollTo(0, 0); });
  route();
}

main();
