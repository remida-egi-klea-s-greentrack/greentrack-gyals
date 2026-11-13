import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AssistantPanel from "./components/AssistantPanel.jsx";
import {
  anomaliesInRange,
  consumptionShares,
  flaggedHours,
  forecastMae,
  formatDay,
  formatHour,
  formatRange,
  formatTick,
  hourKey,
  measuredHours,
  peakHour,
  totalKwh,
} from "./lib/stats.js";
import { LANGS, SEVERITY, TEXT, saveLang, savedLang } from "./lib/i18n.js";
import "./App.css";

// VITE_API_URL vendoset në build (CI nga terraform output, lokalisht http://localhost:8080).
// Pa të, përdoret API-ja e production, si më parë.
const API =
  import.meta.env.VITE_API_URL ||
  "https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com";

// Colours shared by the charts (same values as the CSS variables).
const C = { cyan: "#17FCFF", green: "#34E89E", amber: "#FFB628", grid: "#073563", muted: "#93AECB", text: "#FDFFFF", card: "#032C57" };
const ANOMALIES_SHOWN = 5;

async function getJson(path, timeout = 15000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(`${API}${path}`, { signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

const kwh = (v, digits = 2) => (typeof v === "number" ? v.toFixed(digits) : "–");

const tooltipStyle = { background: C.card, border: `1px solid ${C.grid}`, borderRadius: 10, color: C.text };

// State per endpoint: { data, error } (error is a message when the call failed).
function useEndpoint(path) {
  const [state, setState] = useState({ data: null, error: "" });
  useEffect(() => {
    let alive = true;
    getJson(path)
      .then((data) => alive && setState({ data, error: "" }))
      .catch((err) => alive && setState({ data: null, error: err.name === "AbortError" ? "Timeout" : err.message }));
    return () => {
      alive = false;
    };
  }, [path]);
  return state;
}

function Section({ id, title, subtitle, aside, className = "", children }) {
  return (
    <section id={id} className={`card ${className}`}>
      <div className="card__head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="muted small">{subtitle}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

const Problem = ({ text }) => <p className="problem">{text}</p>;
const Loading = ({ text }) => <p className="muted">{text}</p>;

function App() {
  const consumption = useEndpoint("/consumption");
  const anomaliesRes = useEndpoint("/anomalies");
  const forecastRes = useEndpoint("/forecast?horizon_hours=24");
  const [tab, setTab] = useState("overview");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [showAllAnomalies, setShowAllAnomalies] = useState(false);
  const closeAssistant = useCallback(() => setAssistantOpen(false), []);
  // lang - interface language ("sq" or "en"), remembered in the browser; t - its text
  const [lang, setLang] = useState(savedLang);
  const t = TEXT[lang];
  useEffect(() => {
    saveLang(lang);
    document.documentElement.lang = lang;
  }, [lang]);
  const nextLang = LANGS[(LANGS.indexOf(lang) + 1) % LANGS.length];

  // hours  - measured hours shown in the charts; first/last - their period
  // flagged - anomalies inside that period; peak - highest hour; shares - breakdown by sub-meter
  const view = useMemo(() => {
    const hours = measuredHours(consumption.data?.records);
    if (!hours.length) return null;
    const first = hours[0].timestamp;
    const last = hours[hours.length - 1].timestamp;
    const flagged = anomaliesInRange(anomaliesRes.data?.anomalies, first, last);
    const flaggedKeys = new Set(flagged.map((a) => hourKey(a.timestamp)));
    return {
      first,
      last,
      total: totalKwh(hours),
      peak: peakHour(hours),
      shares: consumptionShares(hours, lang),
      flagged,
      chart: hours.map((r) => ({ hour: hourKey(r.timestamp), ts: r.timestamp, kwh: r.global_active_power_kwh, flagged: flaggedKeys.has(hourKey(r.timestamp)) })),
      dayTicks: hours.filter((r) => r.timestamp.slice(11, 13) === "00").map((r) => hourKey(r.timestamp)),
    };
  }, [consumption.data, anomaliesRes.data, lang]);

  const predictions = forecastRes.data?.predictions || [];
  const fcError = forecastMae(predictions);
  const fcTitle = predictions.length
    ? formatRange(predictions[0].timestamp, predictions[predictions.length - 1].timestamp, lang)
    : "";
  const allAnomalies = useMemo(
    () => (anomaliesRes.data?.anomalies || []).slice().sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1)),
    [anomaliesRes.data],
  );
  const listed = showAllAnomalies ? allAnomalies : allAnomalies.slice(0, ANOMALIES_SHOWN);

  const tabs = [
    ["overview", t.tabOverview],
    ["consumption", t.tabConsumption],
    ["anomalies", t.tabAnomalies],
  ];

  return (
    <div className="page">
      <header className="topbar">
        <div className="topbar__left">
          <a className="brand" href="#overview" onClick={() => setTab("overview")}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="url(#brandGrad)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <defs>
                <linearGradient id="brandGrad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0" stopColor={C.cyan} />
                  <stop offset="1" stopColor={C.green} />
                </linearGradient>
              </defs>
              <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
            GreenTrack
          </a>
          <nav aria-label={t.sections} className="tabs">
            {tabs.map(([id, label]) => (
              <a key={id} href={`#${id}`} className={`tab ${tab === id ? "is-active" : ""}`} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>
                {label}
              </a>
            ))}
          </nav>
        </div>
        <div className="topbar__actions">
          <button type="button" className="btn-outline lang-toggle" onClick={() => setLang(nextLang)} aria-label={t.switchLanguage} title={t.switchLanguage}>
            {nextLang.toUpperCase()}
          </button>
          <button type="button" className="btn-outline" onClick={() => setAssistantOpen(true)} aria-expanded={assistantOpen}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
            </svg>
            {t.askAssistant}
          </button>
        </div>
      </header>

      <main id="overview" className="main">
        <div className="title-row">
          <div>
            <h1>{t.title}</h1>
            <p className="muted">{t.historical}{consumption.data?.household_id ? ` · ${consumption.data.household_id}` : ""}</p>
          </div>
          {view && (
            <span className="period">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <rect x="3" y="4" width="18" height="18" rx="2" />
                <path d="M16 2v4M8 2v4M3 10h18" />
              </svg>
              {formatRange(view.first, view.last, lang)}
            </span>
          )}
        </div>

        {consumption.error && <Problem text={t.problem(t.whatConsumption, consumption.error)} />}
        {!consumption.error && !view && <Loading text={t.loading} />}

        {view && (
          <>
            <section aria-label={t.keyIndicators} className="kpis">
              <div className="card kpi">
                <svg className="kpi__icon" viewBox="0 0 24 24" fill="none" stroke={C.cyan} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" /></svg>
                <div>
                  <span className="kpi__label">{t.total}</span>
                  <span className="kpi__value kpi__value--grad">{kwh(view.total)} kWh</span>
                  <span className="kpi__sub">{t.hoursMeasured(view.chart.length)}</span>
                </div>
              </div>
              <div className="card kpi">
                <svg className="kpi__icon" viewBox="0 0 24 24" fill="none" stroke={C.green} strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M5 20v-4M10 20v-8M15 20V8M20 20V4" /></svg>
                <div>
                  <span className="kpi__label">{t.peak}</span>
                  <span className="kpi__value" style={{ color: C.cyan }}>{kwh(view.peak.global_active_power_kwh)} kWh</span>
                  <span className="kpi__sub">{formatDay(view.peak.timestamp, false, lang)} · {formatHour(view.peak.timestamp)}</span>
                </div>
              </div>
              <div className="card kpi">
                <svg className="kpi__icon" viewBox="0 0 24 24" fill="none" stroke={C.amber} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01" /></svg>
                <div>
                  <span className="kpi__label">{t.anomaliesKpi}</span>
                  <span className="kpi__value" style={{ color: C.amber }}>{anomaliesRes.error ? "–" : flaggedHours(view.flagged)}</span>
                  <span className="kpi__sub">
                    {anomaliesRes.error
                      ? t.anomaliesNotLoaded
                      : view.flagged.length === 0 && allAnomalies.length > 0
                        ? t.noneInPeriod(formatDay(allAnomalies[0].timestamp, false, lang), formatHour(allAnomalies[0].timestamp))
                        : t.flaggedInPeriod}
                  </span>
                </div>
              </div>
            </section>

            <Section
              id="consumption"
              title={t.hourly}
              subtitle={formatRange(view.first, view.last, lang)}
              aside={
                <span className="legend">
                  <span><i className="dot" style={{ background: C.cyan }} />{t.legendPeak}</span>
                  <span><i className="dot" style={{ background: C.amber }} />{t.legendAnomaly}</span>
                </span>
              }
            >
              <div className="chart" role="img" aria-label={t.hourlyAria(formatRange(view.first, view.last, lang))}>
                <ResponsiveContainer width="100%" height={260}>
                  <ComposedChart data={view.chart} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="wkLine" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0" stopColor={C.cyan} />
                        <stop offset="1" stopColor={C.green} />
                      </linearGradient>
                      <linearGradient id="wkFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stopColor={C.cyan} stopOpacity={0.26} />
                        <stop offset="0.6" stopColor={C.green} stopOpacity={0.1} />
                        <stop offset="1" stopColor={C.green} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke={C.grid} vertical={false} />
                    <XAxis dataKey="hour" ticks={view.dayTicks} tickFormatter={(h) => formatTick(h, lang)} stroke={C.muted} tickLine={false} axisLine={{ stroke: C.grid }} />
                    <YAxis stroke={C.muted} tickLine={false} axisLine={false} width={44} domain={[0, (max) => Math.max(1, Math.ceil(max))]} allowDecimals={false} label={{ value: "kWh", angle: -90, position: "insideLeft", fill: C.muted, fontSize: 12 }} />
                    <Tooltip contentStyle={tooltipStyle} labelFormatter={(h) => `${formatDay(h, false, lang)} · ${formatHour(`${h}:00`)}`} formatter={(v) => [`${kwh(v, 3)} kWh`, t.consumption]} />
                    <Area type="monotone" dataKey="kwh" stroke="url(#wkLine)" strokeWidth={2.2} fill="url(#wkFill)" isAnimationActive={false} />
                    {view.chart.filter((p) => p.flagged).map((p) => (
                      <ReferenceDot key={p.hour} x={p.hour} y={p.kwh} r={5} fill={C.amber} stroke={C.card} strokeWidth={2} />
                    ))}
                    <ReferenceDot x={hourKey(view.peak.timestamp)} y={view.peak.global_active_power_kwh} r={5} fill={C.cyan} stroke={C.card} strokeWidth={2} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </Section>
          </>
        )}

        <div className="two-col">
          <Section
            id="forecast"
            title={`${t.forecast}${fcTitle ? ` · ${fcTitle}` : ""}`}
            subtitle={fcError ? t.forecastError(kwh(fcError.mae, 3), fcError.hours) : t.forecastSub}
            aside={
              <span className="legend">
                <span><i className="line line--grad" />{t.actual}</span>
                <span><i className="line line--dash" />{t.predicted}</span>
              </span>
            }
          >
            {forecastRes.error && <Problem text={t.problem(t.whatForecast, forecastRes.error)} />}
            {!forecastRes.error && !forecastRes.data && <Loading text={t.loading} />}
            {predictions.length > 0 && (
              <div className="chart" role="img" aria-label={t.forecastAria(fcTitle)}>
                <ResponsiveContainer width="100%" height={230}>
                  <ComposedChart data={predictions} margin={{ top: 12, right: 12, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="fcLine" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0" stopColor={C.cyan} />
                        <stop offset="1" stopColor={C.green} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke={C.grid} vertical={false} />
                    <XAxis dataKey="timestamp" tickFormatter={formatHour} stroke={C.muted} tickLine={false} axisLine={{ stroke: C.grid }} minTickGap={40} />
                    <YAxis stroke={C.muted} tickLine={false} axisLine={false} width={44} domain={[0, (max) => Math.max(1, Math.ceil(max))]} allowDecimals={false} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelFormatter={(ts) => `${formatDay(ts, false, lang)} · ${formatHour(ts)}`}
                      formatter={(v, name) => [`${kwh(v, 3)} kWh`, name === "actual_kwh" ? t.tipActual : t.tipPredicted]}
                    />
                    <Line type="monotone" dataKey="predicted_kwh" stroke={C.text} strokeOpacity={0.85} strokeWidth={2} strokeDasharray="7 5" dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="actual_kwh" stroke="url(#fcLine)" strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </Section>

          <Section title={t.breakdown} subtitle={view ? t.breakdownSub : ""}>
            {view?.shares.length > 0 && (
              <ul className="shares">
                {view.shares.map((s, i) => (
                  <li key={s.label}>
                    <span>{s.label}</span>
                    <span className="bar">
                      <span className={`bar__fill bar__fill--${i}`} style={{ width: `${(s.share * 100).toFixed(1)}%` }} />
                    </span>
                    <span className="shares__value">
                      <b>{Math.round(s.share * 100)}%</b> <span className="muted">· {kwh(s.kwh, 1)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {!view && !consumption.error && <Loading text={t.loading} />}
          </Section>
        </div>

        <Section
          id="anomalies"
          title={t.recentAnomalies}
          aside={
            allAnomalies.length > ANOMALIES_SHOWN && (
              <button type="button" className="link-btn" onClick={() => setShowAllAnomalies((v) => !v)} aria-expanded={showAllAnomalies}>
                {showAllAnomalies ? t.showLess : t.showAll(allAnomalies.length)} ›
              </button>
            )
          }
        >
          {anomaliesRes.error && <Problem text={t.problem(t.whatAnomalies, anomaliesRes.error)} />}
          {!anomaliesRes.error && !anomaliesRes.data && <Loading text={t.loading} />}
          {anomaliesRes.data && allAnomalies.length === 0 && <p className="muted">{t.noAnomalies}</p>}
          <ul className="anomalies">
            {listed.map((a) => (
              <li key={`${a.timestamp}-${a.detector}`}>
                <span>{formatDay(a.timestamp, true, lang)} · {formatHour(a.timestamp)}</span>
                <span>{kwh(a.consumption_kwh, 3)} kWh</span>
                <span className="muted">{a.detector || "–"}</span>
                <span className={`badge badge--${a.severity}`}>{SEVERITY[lang][a.severity] || a.severity}</span>
              </li>
            ))}
          </ul>
        </Section>
      </main>

      <AssistantPanel api={API} open={assistantOpen} onClose={closeAssistant} t={t} />
    </div>
  );
}

export default App;
