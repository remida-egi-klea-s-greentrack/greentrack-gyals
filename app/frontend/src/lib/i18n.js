// Interface text in Albanian (sq) and English (en).
// Variables:
//   LANGS    - supported languages, in toggle order
//   TEXT     - text per language; functions take the values they insert
//   MONTHS   - month names per language (long for titles, short for chart ticks)
//   SEVERITY - anomaly severity labels per language
//   STORE    - localStorage key for the chosen language

export const LANGS = ["sq", "en"];
const STORE = "greentrack-lang";

export const MONTHS = {
  sq: {
    long: ["janar", "shkurt", "mars", "prill", "maj", "qershor", "korrik", "gusht", "shtator", "tetor", "nëntor", "dhjetor"],
    short: ["Jan", "Shk", "Mar", "Pri", "Maj", "Qer", "Kor", "Gus", "Sht", "Tet", "Nën", "Dhj"],
  },
  en: {
    long: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    short: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  },
};

export const SEVERITY = {
  sq: { high: "E lartë", medium: "Mesatare", low: "E ulët" },
  en: { high: "High", medium: "Medium", low: "Low" },
};

export const TEXT = {
  sq: {
    sections: "Seksionet",
    tabOverview: "Përmbledhje",
    tabConsumption: "Konsumi",
    tabAnomalies: "Anomalitë",
    askAssistant: "Pyet asistentin",
    switchLanguage: "Switch to English",
    title: "Përmbledhja e konsumit",
    historical: "Të dhëna historike",
    loading: "Po ngarkohet…",
    problem: (what, error) => `Nuk u ngarkua ${what}: ${error}`,
    whatConsumption: "konsumi",
    whatForecast: "parashikimi",
    whatAnomalies: "anomalitë",
    keyIndicators: "Treguesit kryesorë",
    total: "Konsumi total",
    hoursMeasured: (n) => `${n} orë të matura`,
    peak: "Piku i konsumit",
    anomaliesKpi: "Anomali",
    anomaliesNotLoaded: "Anomalitë nuk u ngarkuan",
    noneInPeriod: (day, hour) => `Asnjë në këtë periudhë · e fundit ${day}, ${hour}`,
    flaggedInPeriod: "Orë të shënuara gjatë periudhës",
    hourly: "Konsumi për orë",
    hourlyAria: (range) => `Konsumi për orë, ${range}`,
    legendPeak: "Piku",
    legendAnomaly: "Anomali",
    consumption: "Konsumi",
    forecast: "Parashikimi",
    forecastSub: "XGBoost në SageMaker",
    forecastError: (mae, hours) => `XGBoost në SageMaker · gabimi mesatar ${mae} kWh/orë (${hours} orë)`,
    actual: "Konsumi real",
    predicted: "Parashikimi",
    tipActual: "Real",
    tipPredicted: "Parashikuar",
    forecastAria: (range) => `Parashikimi kundrejt konsumit real, ${range}`,
    breakdown: "Ndarja e konsumit",
    breakdownSub: "kWh gjatë periudhës, sipas matësve",
    meterWaterAc: "Ngrohësi i ujit / Klima",
    meterLaundry: "Lavanderia",
    meterKitchen: "Kuzhina",
    meterOther: "Të tjera (pa matës)",
    recentAnomalies: "Anomalitë e fundit",
    showLess: "Shfaq më pak",
    showAll: (n) => `Shiko të gjitha (${n})`,
    noAnomalies: "Asnjë anomali.",
    assistant: "Asistenti i energjisë",
    closeAssistant: "Mbyll asistentin",
    assistantHint: "Pyet për konsumin, orët e pikut, anomalitë ose si të kursesh energji.",
    assistantError: (msg) => `Asistenti nuk u përgjigj (${msg}). Provo përsëri.`,
    thinking: "Po mendon…",
    yourQuestion: "Pyetja jote",
    askPlaceholder: "Pyet për konsumin…",
    send: "Dërgo",
  },
  en: {
    sections: "Sections",
    tabOverview: "Overview",
    tabConsumption: "Consumption",
    tabAnomalies: "Anomalies",
    askAssistant: "Ask the assistant",
    switchLanguage: "Kalo në shqip",
    title: "Consumption overview",
    historical: "Historical data",
    loading: "Loading…",
    problem: (what, error) => `Could not load ${what}: ${error}`,
    whatConsumption: "consumption",
    whatForecast: "the forecast",
    whatAnomalies: "anomalies",
    keyIndicators: "Key indicators",
    total: "Total consumption",
    hoursMeasured: (n) => `${n} hours measured`,
    peak: "Peak consumption",
    anomaliesKpi: "Anomalies",
    anomaliesNotLoaded: "Anomalies could not be loaded",
    noneInPeriod: (day, hour) => `None in this period · latest ${day}, ${hour}`,
    flaggedInPeriod: "Hours flagged in this period",
    hourly: "Hourly consumption",
    hourlyAria: (range) => `Hourly consumption, ${range}`,
    legendPeak: "Peak",
    legendAnomaly: "Anomaly",
    consumption: "Consumption",
    forecast: "Forecast",
    forecastSub: "XGBoost on SageMaker",
    forecastError: (mae, hours) => `XGBoost on SageMaker · mean error ${mae} kWh/hour (${hours} hours)`,
    actual: "Actual consumption",
    predicted: "Forecast",
    tipActual: "Actual",
    tipPredicted: "Forecast",
    forecastAria: (range) => `Forecast against actual consumption, ${range}`,
    breakdown: "Consumption breakdown",
    breakdownSub: "kWh in this period, by sub-meter",
    meterWaterAc: "Water heater / AC",
    meterLaundry: "Laundry",
    meterKitchen: "Kitchen",
    meterOther: "Other (not metered)",
    recentAnomalies: "Recent anomalies",
    showLess: "Show less",
    showAll: (n) => `Show all (${n})`,
    noAnomalies: "No anomalies.",
    assistant: "Energy assistant",
    closeAssistant: "Close the assistant",
    assistantHint: "Ask about consumption, peak hours, anomalies or how to save energy.",
    assistantError: (msg) => `The assistant did not answer (${msg}). Please try again.`,
    thinking: "Thinking…",
    yourQuestion: "Your question",
    askPlaceholder: "Ask about consumption…",
    send: "Send",
  },
};

/** Saved language, or Albanian. */
export function savedLang() {
  try {
    const value = window.localStorage.getItem(STORE);
    return LANGS.includes(value) ? value : "sq";
  } catch {
    return "sq";
  }
}

export function saveLang(lang) {
  try {
    window.localStorage.setItem(STORE, lang);
  } catch {
    // Storage can be unavailable (private mode); the choice then lasts for this visit only.
  }
}
