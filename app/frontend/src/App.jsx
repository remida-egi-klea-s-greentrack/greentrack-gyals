import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from "recharts";
import "./App.css";

const API = "";

function App() {
  const [consumption, setConsumption] = useState({ records: [] });
  const [anomalies, setAnomalies] = useState({ anomalies: [] });
  const [forecast, setForecast] = useState({ predictions: [] });
  const [chatHistory, setChatHistory] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Ngarko të dhënat kur hapet faqja
  useEffect(() => {
    const fetchWithTimeout = (url, timeout = 10000) => {
      return Promise.race([
        fetch(url).then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        }),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("Timeout")), timeout)
        ),
      ]);
    };

    Promise.all([
      fetchWithTimeout(`${API}/consumption`),
      fetchWithTimeout(`${API}/anomalies`),
      fetchWithTimeout(`${API}/forecast?horizon_hours=24`),
    ])
      .then(([cons, anom, fore]) => {
        setConsumption(cons);
        setAnomalies(anom);
        setForecast(fore);
        setLoading(false);
      })
      .catch((err) => {
        console.error("API Error:", err);
        setError(
          `Gabim në lidhjen me API: ${err.message}. Backend duhet të jetë në port 8080.`
        );
        setLoading(false);
      });
  }, []);

  // Dërgon pyetje te chat
  const sendChatMessage = async () => {
    if (!chatInput.trim()) return;

    const userMessage = { role: "user", content: chatInput };
    setChatHistory([...chatHistory, userMessage]);
    setChatInput("");
    setChatLoading(true);

    try {
      const response = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: chatInput,
          session_id: "web-session-1",
        }),
      });

      const data = await response.json();
      const assistantMessage = {
        role: "assistant",
        content: data.answer,
        citations: data.citations || [],
        tools: data.tools_used || [],
      };

      setChatHistory((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setChatHistory((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Gabim në lidhje me asistentin.",
          citations: [],
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  // Llogarit statistikat për kartelat
  const totalConsumption = consumption.records
    .reduce((sum, r) => sum + (r.global_active_power_kwh || 0), 0)
    .toFixed(2);

  const peakHour = consumption.records.reduce((max, r) =>
    (r.global_active_power_kwh || 0) > (max.global_active_power_kwh || 0) ? r : max
  , { timestamp: "—", global_active_power_kwh: 0 });

  const anomalyCount = anomalies.anomalies?.length || 0;

  // Përgatit të dhënat për grafikun e pajisjeve (sub-metering)
  const subMeteringData = [
    {
      name: "Kuzhina",
      kwh: consumption.records.reduce((sum, r) => sum + (r.sub_metering_1_kwh || 0), 0),
    },
    {
      name: "Lavanderia",
      kwh: consumption.records.reduce((sum, r) => sum + (r.sub_metering_2_kwh || 0), 0),
    },
    {
      name: "Ngrohësi/Klima",
      kwh: consumption.records.reduce((sum, r) => sum + (r.sub_metering_3_kwh || 0), 0),
    },
  ];

  if (loading) {
    return (
      <div className="container">
        <div className="loading">Po ngarkon të dhënat...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <div className="error-box">{error}</div>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="header">
        <h1>🌱 GreenTrack Dashboard</h1>
        <p className="subtitle">Monitorimi i konsumit të energjisë elektrike</p>
      </header>

      {/* Kartela përmbledhëse */}
      <div className="summary-cards">
        <div className="card">
          <div className="card-label">Konsumi Total</div>
          <div className="card-value">{totalConsumption} kWh</div>
        </div>
        <div className="card">
          <div className="card-label">Ora e Pikut</div>
          <div className="card-value">
            {peakHour.timestamp.split("T")[1]?.slice(0, 5) || "—"}
          </div>
          <div className="card-detail">
            {peakHour.global_active_power_kwh.toFixed(2)} kWh
          </div>
        </div>
        <div className="card">
          <div className="card-label">Anomali të Zbuluara</div>
          <div className="card-value">{anomalyCount}</div>
        </div>
      </div>

      {/* Grafiku i konsumit total */}
      <section className="chart-section">
        <h2>📊 Konsumi Orar (kWh)</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={consumption.records}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(t) => t.split("T")[1]?.slice(0, 5)}
              stroke="#666"
            />
            <YAxis stroke="#666" />
            <Tooltip
              contentStyle={{
                background: "#fff",
                border: "1px solid #ddd",
                borderRadius: "8px",
              }}
              labelFormatter={(t) => `Ora: ${t.split("T")[1]?.slice(0, 5)}`}
            />
            <Line
              type="monotone"
              dataKey="global_active_power_kwh"
              stroke="#2e7d4f"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Konsumi (kWh)"
            />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* Grafiku i konsumit sipas pajisjeve */}
      <section className="chart-section">
        <h2>🔌 Konsumi sipas Pajisjeve</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={subMeteringData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis dataKey="name" stroke="#666" />
            <YAxis stroke="#666" label={{ value: "kWh", angle: -90, position: "insideLeft" }} />
            <Tooltip
              contentStyle={{
                background: "#fff",
                border: "1px solid #ddd",
                borderRadius: "8px",
              }}
            />
            <Bar dataKey="kwh" fill="#3b9e68" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Grafiku i parashikimit */}
      <section className="chart-section">
        <h2>🔮 Parashikimi i Konsumit (24 orë)</h2>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={forecast.predictions}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(t) => t.split("T")[1]?.slice(0, 5)}
              stroke="#666"
            />
            <YAxis stroke="#666" />
            <Tooltip
              contentStyle={{
                background: "#fff",
                border: "1px solid #ddd",
                borderRadius: "8px",
              }}
              labelFormatter={(t) => `Ora: ${t.split("T")[1]?.slice(0, 5)}`}
            />
            {forecast.predictions.some((p) => p.lower_bound !== undefined) && (
              <Area
                type="monotone"
                dataKey="lower_bound"
                stroke="none"
                fill="#d4edda"
                fillOpacity={0.3}
              />
            )}
            {forecast.predictions.some((p) => p.upper_bound !== undefined) && (
              <Area
                type="monotone"
                dataKey="upper_bound"
                stroke="none"
                fill="#d4edda"
                fillOpacity={0.3}
              />
            )}
            <Line
              type="monotone"
              dataKey="predicted_kwh"
              stroke="#1976d2"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Parashikuar (kWh)"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </section>

      {/* Lista e anomalive */}
      {anomalyCount > 0 && (
        <section className="chart-section">
          <h2>⚠️ Anomali të Zbuluara</h2>
          <div className="anomaly-list">
            {anomalies.anomalies.map((a, i) => (
              <div key={i} className={`anomaly-item severity-${a.severity}`}>
                <div className="anomaly-time">
                  {a.timestamp.split("T")[0]} • {a.timestamp.split("T")[1]?.slice(0, 5)}
                </div>
                <div className="anomaly-value">{a.consumption_kwh} kWh</div>
                <div className="anomaly-severity">{a.severity.toUpperCase()}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Chat Panel */}
      <section className="chart-section chat-section">
        <h2>💬 Asistenti i Energjisë</h2>
        <div className="chat-container">
          <div className="chat-messages">
            {chatHistory.length === 0 && (
              <div className="chat-placeholder">
                Pyet mua për konsumin, orët e pikut, apo për të dhënat e energjisë...
              </div>
            )}
            {chatHistory.map((msg, i) => (
              <div key={i} className={`chat-message ${msg.role}`}>
                <div className="message-content">{msg.content}</div>
                {msg.citations && msg.citations.length > 0 && (
                  <div className="message-citations">
                    <strong>Burimet:</strong> {msg.citations.join(", ")}
                  </div>
                )}
              </div>
            ))}
            {chatLoading && (
              <div className="chat-message assistant">
                <div className="message-content typing">Po mendoj...</div>
              </div>
            )}
          </div>
          <div className="chat-input-area">
            <input
              type="text"
              className="chat-input"
              placeholder="Shkruaj pyetjen tënde..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendChatMessage()}
              disabled={chatLoading}
            />
            <button
              className="chat-send-btn"
              onClick={sendChatMessage}
              disabled={chatLoading || !chatInput.trim()}
            >
              Dërgo
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

export default App;