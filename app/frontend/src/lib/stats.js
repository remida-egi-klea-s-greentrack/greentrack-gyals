// Pure helpers that turn the API responses into what the dashboard shows.
// Timestamps arrive as "YYYY-MM-DDTHH:MM:SS(.sss)" without a time zone, so they are
// handled as text (never through Date) to avoid shifting hours.
//
// Variables used across the helpers:
//   records     - /consumption records: timestamp, global_active_power_kwh, sub_metering_{1,2,3}_kwh
//   anomalies   - /anomalies items: timestamp, detector, consumption_kwh, severity
//   predictions - /forecast items: timestamp, predicted_kwh, actual_kwh (null for future hours)

const MONTHS = ["janar", "shkurt", "mars", "prill", "maj", "qershor", "korrik", "gusht", "shtator", "tetor", "nëntor", "dhjetor"];
const MONTHS_SHORT = ["Jan", "Shk", "Mar", "Pri", "Maj", "Qer", "Kor", "Gus", "Sht", "Tet", "Nën", "Dhj"];

/** "YYYY-MM-DDTHH" key, so the same hour matches across endpoints. */
export const hourKey = (ts) => String(ts).slice(0, 13);

const parts = (ts) => {
  const [date, time = ""] = String(ts).split("T");
  const [y, m, d] = date.split("-").map(Number);
  return { y, m, d, hh: time.slice(0, 5) };
};

/** "20 nëntor 2010" (withYear) or "20 nëntor". */
export function formatDay(ts, withYear = false) {
  const { y, m, d } = parts(ts);
  return `${d} ${MONTHS[m - 1]}${withYear ? ` ${y}` : ""}`;
}

/** "20 Nën" for chart ticks. */
export const formatTick = (ts) => {
  const { m, d } = parts(ts);
  return `${d} ${MONTHS_SHORT[m - 1]}`;
};

/** "18:00". */
export const formatHour = (ts) => parts(ts).hh;

/** "15–21 nëntor 2010", or "28 tetor – 3 nëntor 2010" across months. */
export function formatRange(startTs, endTs) {
  const a = parts(startTs);
  const b = parts(endTs);
  if (a.y === b.y && a.m === b.m) {
    return a.d === b.d ? `${a.d} ${MONTHS[a.m - 1]} ${a.y}` : `${a.d}–${b.d} ${MONTHS[a.m - 1]} ${a.y}`;
  }
  return `${formatDay(startTs, a.y !== b.y)} – ${formatDay(endTs, true)}`;
}

/** Hours with a measured value, oldest first. */
export function measuredHours(records) {
  return (records || [])
    .filter((r) => typeof r.global_active_power_kwh === "number")
    .slice()
    .sort((a, b) => (a.timestamp < b.timestamp ? -1 : 1));
}

export function totalKwh(hours) {
  return hours.reduce((sum, r) => sum + r.global_active_power_kwh, 0);
}

/** Hour with the highest consumption, or null. */
export function peakHour(hours) {
  return hours.reduce((best, r) => (!best || r.global_active_power_kwh > best.global_active_power_kwh ? r : best), null);
}

// Sub-meters of the UCI household dataset.
const SUB_METERS = [
  { key: "sub_metering_3_kwh", label: "Ngrohësi i ujit / Klima" },
  { key: "sub_metering_2_kwh", label: "Lavanderia" },
  { key: "sub_metering_1_kwh", label: "Kuzhina" },
];

/** kWh and share per sub-meter; "other" is what no sub-meter measures. Largest first. */
export function consumptionShares(hours) {
  const total = totalKwh(hours);
  if (total <= 0) return [];
  const rows = SUB_METERS.map(({ key, label }) => ({
    label,
    kwh: hours.reduce((sum, r) => sum + (r[key] || 0), 0),
  }));
  const metered = rows.reduce((sum, r) => sum + r.kwh, 0);
  rows.push({ label: "Të tjera (pa matës)", kwh: Math.max(total - metered, 0), other: true });
  return rows
    .map((r) => ({ ...r, share: r.kwh / total }))
    .sort((a, b) => b.kwh - a.kwh);
}

/** Anomalies whose hour lies in [startTs, endTs], newest first. */
export function anomaliesInRange(anomalies, startTs, endTs) {
  const lo = hourKey(startTs);
  const hi = hourKey(endTs);
  return (anomalies || [])
    .filter((a) => hourKey(a.timestamp) >= lo && hourKey(a.timestamp) <= hi)
    .sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
}

/** Number of distinct hours flagged (two detectors on one hour count once). */
export const flaggedHours = (anomalies) => new Set(anomalies.map((a) => hourKey(a.timestamp))).size;

/** Mean absolute error over hours that have both values, or null. */
export function forecastMae(predictions) {
  const pairs = (predictions || []).filter((p) => typeof p.predicted_kwh === "number" && typeof p.actual_kwh === "number");
  if (!pairs.length) return null;
  return { mae: pairs.reduce((s, p) => s + Math.abs(p.predicted_kwh - p.actual_kwh), 0) / pairs.length, hours: pairs.length };
}

/** "Title (https://url)" -> { title, url }; anything else -> { title }. */
export function parseCitation(text) {
  const match = /^(.*)\((https?:\/\/[^)\s]+)\)\s*$/.exec(String(text));
  return match ? { title: match[1].trim(), url: match[2] } : { title: String(text) };
}

export const SEVERITY_LABEL = { high: "E lartë", medium: "Mesatare", low: "E ulët" };
