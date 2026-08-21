import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  GitBranch,
  LayoutGrid,
  MessageSquare,
  Network,
  Newspaper,
  TrendingUp,
  CircleAlert,
  RefreshCw,
} from "lucide-react";
import { useConsole } from "../lib/store";
import { cn } from "../lib/format";

const NAV = [
  { to: "/", key: "F1", label: "Overview", icon: LayoutGrid, end: true },
  { to: "/trends", key: "F2", label: "Trends", icon: TrendingUp },
  { to: "/graph", key: "F3", label: "Graph", icon: Network },
  { to: "/changes", key: "F4", label: "Changes", icon: GitBranch },
  { to: "/review", key: "F5", label: "Review", icon: CircleAlert },
  { to: "/research", key: "F6", label: "Research", icon: Newspaper },
  { to: "/ask", key: "F7", label: "Ask", icon: MessageSquare },
];

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span className="stat text-2xs text-term-dim">
      {now.toISOString().slice(11, 19)} UTC
    </span>
  );
}

function Ticker() {
  const model = useConsole((s) => s.model);
  if (!model) return null;
  const c = model.counts;
  const items = [
    { k: "RECORDS", v: c.total, cls: "text-term-text" },
    { k: "HIGH CONF", v: c.by_confidence.high || 0, cls: "text-term-up" },
    { k: "OVERDUE", v: model.trends.staleness.overdue, cls: "text-term-down" },
    { k: "REVIEW QUEUE", v: model.review_queue.length, cls: "text-term-amber" },
    { k: "WORKFLOWS", v: Object.keys(c.by_workflow).length, cls: "text-term-info" },
    { k: "GRAPH NODES", v: model.graph.nodes.length, cls: "text-term-dim" },
    { k: "CHANGES", v: model.changes.length, cls: "text-term-dim" },
  ];
  return (
    <div className="flex flex-1 items-center gap-5 overflow-x-auto border-l border-term-border pl-4">
      {items.map((it) => (
        <span key={it.k} className="flex shrink-0 items-center gap-2 text-2xs uppercase tracking-wider">
          <span className="text-term-muted">{it.k}</span>
          <span className={cn("stat font-semibold", it.cls)}>{it.v}</span>
        </span>
      ))}
    </div>
  );
}

export function Layout() {
  const { load, loading, model, error, lastLoaded, research, loadResearch } = useConsole();
  useEffect(() => {
    load();
    loadResearch();
  }, [load, loadResearch]);

  const researchNeedsAttention =
    (research?.counts.by_review_status.pending_review || 0) + (research?.counts.by_review_status.quarantined || 0);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex items-center gap-4 border-b border-term-border bg-term-panel px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="grid h-6 w-6 place-items-center bg-term-amber text-xs font-bold text-term-bg">Q</span>
          <span className="text-sm font-bold uppercase tracking-widest text-term-text">
            QuantSmith<span className="text-term-amber"> // </span>Knowledge Terminal
          </span>
        </div>
        <Ticker />
        <Clock />
        <span className="flex items-center gap-1.5 text-2xs uppercase tracking-wider text-term-up">
          <span className="inline-block h-2 w-2 animate-blink rounded-full bg-term-up" /> live
        </span>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Sidebar */}
        <nav className="flex w-44 shrink-0 flex-col border-r border-term-border bg-term-panel py-2">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => cn("navkey", isActive && "navkey-active")}>
              <n.icon size={14} strokeWidth={1.75} />
              <span className="flex-1">{n.label}</span>
              {n.to === "/review" && model && model.review_queue.length > 0 && (
                <span className="chip border-term-amber/50 text-term-amber">{model.review_queue.length}</span>
              )}
              {n.to === "/research" && researchNeedsAttention > 0 && (
                <span className="chip border-term-amber/50 text-term-amber">{researchNeedsAttention}</span>
              )}
              <span className="kbd">{n.key}</span>
            </NavLink>
          ))}
          <div className="mt-auto px-3 pt-3">
            <button
              type="button"
              onClick={() => load(true)}
              className="flex items-center gap-1.5 text-2xs uppercase tracking-wider text-term-dim hover:text-term-amber"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> refresh
            </button>
          </div>
        </nav>

        {/* Main */}
        <main className="min-w-0 flex-1 overflow-y-auto bg-term-bg">
          {error ? (
            <div className="m-4 border border-term-down/50 bg-term-down/10 p-4 text-xs text-term-down">
              Failed to load model: {error}
            </div>
          ) : !model ? (
            <div className="flex h-full items-center justify-center text-xs uppercase tracking-widest text-term-muted">
              <Activity className="mr-2 animate-pulse" size={14} /> loading knowledge base…
            </div>
          ) : (
            <div className="p-4">
              <Outlet />
            </div>
          )}
        </main>
      </div>

      {/* Status bar */}
      <footer className="flex items-center gap-4 border-t border-term-border bg-term-panel px-4 py-1 text-3xs uppercase tracking-wider text-term-muted">
        <span>
          as-of <span className="text-term-dim">{model?.as_of ?? "—"}</span>
        </span>
        <span>
          freshness <span className="text-term-dim">{model?.freshness_days ?? "—"}d</span>
        </span>
        <span>
          engine <span className="text-term-dim">keyword · pluggable</span>
        </span>
        <span className="flex-1" />
        <span>src: memory/ store · 0048 runtime</span>
        <span>{lastLoaded ? `synced ${new Date(lastLoaded).toISOString().slice(11, 19)}` : ""}</span>
      </footer>
    </div>
  );
}
