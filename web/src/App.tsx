import { useEffect, useState } from "react";
import type { Model } from "./lib/types";
import { isEmbedded, loadModel } from "./lib/api";
import { Overview } from "./components/Overview";
import { Trends } from "./components/Trends";
import { Graph } from "./components/Graph";
import { Changes } from "./components/Changes";
import { Review } from "./components/Review";
import { Ask } from "./components/Ask";

type View = "overview" | "trends" | "graph" | "changes" | "review" | "ask";

const NAV: { id: View; label: string; ico: string }[] = [
  { id: "overview", label: "Overview", ico: "▦" },
  { id: "trends", label: "Trends", ico: "📈" },
  { id: "graph", label: "Knowledge Graph", ico: "🕸" },
  { id: "changes", label: "Recent Changes", ico: "🕑" },
  { id: "review", label: "Needed Review", ico: "✔" },
  { id: "ask", label: "Ask", ico: "💬" },
];

const TITLES: Record<View, string> = {
  overview: "Overview",
  trends: "Knowledge Trends",
  graph: "Knowledge Graph",
  changes: "Recent Changes",
  review: "Needed Review",
  ask: "Ask the Knowledge Base",
};

export default function App() {
  const [model, setModel] = useState<Model | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("overview");

  useEffect(() => {
    loadModel().then(setModel).catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="app">
        <div className="content">
          <div className="note warn">Could not load the knowledge model: {error}</div>
        </div>
      </div>
    );
  }
  if (!model) {
    return (
      <div className="app">
        <div className="content"><div className="empty">Loading knowledge base…</div></div>
      </div>
    );
  }

  const reviewCount = model.review_queue.length;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">Q</div>
          <div>
            <div className="brand-name">Knowledge Console</div>
            <div className="brand-sub">QuantSmith · memory store</div>
          </div>
        </div>
        {NAV.map((n) => (
          <div
            key={n.id}
            className={`nav-item ${view === n.id ? "active" : ""}`}
            onClick={() => setView(n.id)}
          >
            <span className="ico">{n.ico}</span>
            <span>{n.label}</span>
            {n.id === "review" && reviewCount > 0 && (
              <span className="nav-badge hot">{reviewCount}</span>
            )}
            {n.id === "overview" && <span className="nav-badge">{model.counts.total}</span>}
          </div>
        ))}
        <div className="sidebar-foot">
          As of {model.as_of}
          <br />
          {isEmbedded() ? "Static snapshot" : "Live server"}
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <h1>{TITLES[view]}</h1>
          <div className="spacer" />
          <span className="pill">{model.counts.total} records</span>
          <span className={`pill ${isEmbedded() ? "mode-embedded" : ""}`}>
            {isEmbedded() ? "snapshot" : "live"}
          </span>
        </div>
        <div className="content">
          {view === "overview" && <Overview model={model} onGoReview={() => setView("review")} />}
          {view === "trends" && <Trends model={model} />}
          {view === "graph" && <Graph model={model} />}
          {view === "changes" && <Changes model={model} />}
          {view === "review" && <Review model={model} />}
          {view === "ask" && <Ask model={model} />}
        </div>
      </main>
    </div>
  );
}
