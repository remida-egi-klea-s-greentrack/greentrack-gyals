import { useEffect, useRef, useState } from "react";
import { parseCitation } from "../lib/stats.js";

// Side panel for the energy assistant (POST /chat, contracts/chat.json).
// Props: api - base URL of the API; open - whether the panel is shown; onClose - closes it;
//        t - interface text in the chosen language (lib/i18n.js).
// State: history - list of { role, content, citations }; input - text being typed; busy - waiting for /chat.
export default function AssistantPanel({ api, open, onClose, t }) {
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    inputRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [history, busy]);

  const send = async (e) => {
    e.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    setHistory((h) => [...h, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch(`${api}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: "web-session-1" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setHistory((h) => [...h, { role: "assistant", content: data.answer, citations: data.citations || [] }]);
    } catch (err) {
      setHistory((h) => [...h, { role: "assistant", content: t.assistantError(err.message), citations: [], error: true }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className={`assistant ${open ? "is-open" : ""}`} aria-label={t.assistant} aria-hidden={!open} inert={!open}>
      <header className="assistant__head">
        <h2>{t.assistant}</h2>
        <button type="button" className="icon-btn" onClick={onClose} aria-label={t.closeAssistant}>✕</button>
      </header>

      <div className="assistant__list" ref={listRef} aria-live="polite">
        {history.length === 0 && (
          <p className="muted">{t.assistantHint}</p>
        )}
        {history.map((m, i) => (
          <div key={i} className={`bubble bubble--${m.role} ${m.error ? "bubble--error" : ""}`}>
            <p>{m.content}</p>
            {m.citations?.length > 0 && (
              <div className="citations">
                {m.citations.map((c, j) => {
                  const { title, url } = parseCitation(c);
                  return url ? (
                    <a key={j} className="chip" href={url} target="_blank" rel="noreferrer">{title}</a>
                  ) : (
                    <span key={j} className="chip">{title}</span>
                  );
                })}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="bubble bubble--assistant muted">{t.thinking}</div>}
      </div>

      <form className="assistant__form" onSubmit={send}>
        <label htmlFor="ask" className="sr-only">{t.yourQuestion}</label>
        <input id="ask" ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} placeholder={t.askPlaceholder} disabled={busy} />
        <button type="submit" className="btn-primary" disabled={busy || !input.trim()}>{t.send}</button>
      </form>
    </aside>
  );
}
