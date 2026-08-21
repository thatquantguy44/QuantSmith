import { useEffect, useMemo, useRef, useState } from "react";
import type { Graph as GraphData, Model } from "../lib/types";

// A dependency-free force-directed graph on <canvas> (spec NFR-002).
// Records link to their workflow, scope, and evidence runs. Deterministic
// seeding keeps the layout stable across reloads for a fixed store.

interface Sim {
  id: string;
  label: string;
  kind: string;
  meta: Record<string, string | number>;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  color: string;
}

const KIND_COLOR: Record<string, string> = {
  record: "#4f9cf9",
  workflow: "#a855f7",
  scope: "#22c55e",
  run: "#f59e0b",
};

const KIND_LABEL: Record<string, string> = {
  record: "Record",
  workflow: "Workflow",
  scope: "Scope / dataset",
  run: "Evidence run",
};

function seededPos(i: number, n: number, w: number, h: number) {
  const angle = (i / Math.max(1, n)) * Math.PI * 2;
  const radius = Math.min(w, h) * 0.32;
  return { x: w / 2 + Math.cos(angle) * radius, y: h / 2 + Math.sin(angle) * radius };
}

export function Graph({ model }: { model: Model }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [workflow, setWorkflow] = useState<string>("all");
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [tip, setTip] = useState<{ x: number; y: number; node: Sim } | null>(null);

  const workflows = useMemo(
    () => Object.keys(model.counts.by_workflow).sort(),
    [model],
  );

  const filtered: GraphData = useMemo(() => {
    let nodes = model.graph.nodes.filter((n) => !hidden[n.kind]);
    if (workflow !== "all") {
      const keepRecords = new Set(
        model.records.filter((r) => r.workflow === workflow).map((r) => `rec:${r.id}`),
      );
      const keepWf = new Set([`wf:${workflow}`]);
      // keep records of this workflow, plus scope/run/workflow nodes they touch
      const neighbors = new Set<string>([...keepRecords, ...keepWf]);
      for (const e of model.graph.edges) {
        if (keepRecords.has(e.source)) neighbors.add(e.target);
      }
      nodes = nodes.filter((n) => neighbors.has(n.id));
    }
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = model.graph.edges.filter(
      (e) => nodeIds.has(e.source) && nodeIds.has(e.target),
    );
    return { nodes, edges };
  }, [model, workflow, hidden]);

  const simRef = useRef<Sim[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const dpr = window.devicePixelRatio || 1;
    const width = wrap.clientWidth;
    const height = 460;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);

    const n = filtered.nodes.length;
    const nodes: Sim[] = filtered.nodes.map((nd, i) => {
      const p = seededPos(i, n, width, height);
      const rc = Number(nd.meta.record_count || 0);
      const r =
        nd.kind === "record" ? 6 : nd.kind === "run" ? 5 : 8 + Math.min(10, rc * 1.6);
      return {
        ...nd,
        x: p.x,
        y: p.y,
        vx: 0,
        vy: 0,
        r,
        color: KIND_COLOR[nd.kind] || "#7d8792",
      };
    });
    simRef.current = nodes;
    const index = new Map(nodes.map((nd) => [nd.id, nd]));
    const links = filtered.edges
      .map((e) => ({ s: index.get(e.source), t: index.get(e.target) }))
      .filter((l): l is { s: Sim; t: Sim } => !!l.s && !!l.t);

    let alpha = 1;
    let raf = 0;
    const cssVar = (name: string) =>
      getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
    const edgeColor = cssVar("--border-strong");
    const fg = cssVar("--fg");
    const muted = cssVar("--muted");

    function tick() {
      // repulsion
      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 0.01) { d2 = 0.01; dx = Math.random(); dy = Math.random(); }
          const d = Math.sqrt(d2);
          const force = (2600 / d2) * alpha;
          const fx = (dx / d) * force;
          const fy = (dy / d) * force;
          a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
        }
      }
      // springs
      for (const l of links) {
        const dx = l.t.x - l.s.x;
        const dy = l.t.y - l.s.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = ((d - 90) * 0.02) * alpha;
        const fx = (dx / d) * force;
        const fy = (dy / d) * force;
        l.s.vx += fx; l.s.vy += fy; l.t.vx -= fx; l.t.vy -= fy;
      }
      // gravity + integrate
      for (const nd of nodes) {
        nd.vx += (width / 2 - nd.x) * 0.002 * alpha;
        nd.vy += (height / 2 - nd.y) * 0.002 * alpha;
        nd.vx *= 0.86; nd.vy *= 0.86;
        nd.x += nd.vx; nd.y += nd.vy;
        nd.x = Math.max(nd.r, Math.min(width - nd.r, nd.x));
        nd.y = Math.max(nd.r, Math.min(height - nd.r, nd.y));
      }
      alpha *= 0.985;

      // draw
      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = edgeColor;
      ctx.globalAlpha = 0.5;
      ctx.lineWidth = 1;
      for (const l of links) {
        ctx.beginPath();
        ctx.moveTo(l.s.x, l.s.y);
        ctx.lineTo(l.t.x, l.t.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      for (const nd of nodes) {
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, nd.r, 0, Math.PI * 2);
        ctx.fillStyle = nd.color;
        ctx.fill();
        if (nd.kind !== "record") {
          ctx.fillStyle = nd.kind === "workflow" ? fg : muted;
          ctx.font = "11px system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(nd.label.length > 22 ? `${nd.label.slice(0, 22)}…` : nd.label, nd.x, nd.y - nd.r - 4);
        }
      }
      if (alpha > 0.02) raf = requestAnimationFrame(tick);
    }
    tick();
    return () => cancelAnimationFrame(raf);
  }, [filtered]);

  function onMove(ev: React.MouseEvent<HTMLCanvasElement>) {
    const rect = ev.currentTarget.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;
    let hit: Sim | null = null;
    for (const nd of simRef.current) {
      const dx = nd.x - mx;
      const dy = nd.y - my;
      if (dx * dx + dy * dy <= (nd.r + 3) ** 2) hit = nd;
    }
    setTip(hit ? { x: mx, y: my, node: hit } : null);
  }

  const kinds = ["record", "workflow", "scope", "run"];

  return (
    <div>
      <div className="controls">
        <label style={{ color: "var(--muted)" }}>Workflow</label>
        <select className="sel" value={workflow} onChange={(e) => setWorkflow(e.target.value)}>
          <option value="all">All</option>
          {workflows.map((w) => (
            <option key={w} value={w}>{w}</option>
          ))}
        </select>
        <span style={{ flex: 1 }} />
        <div className="legend">
          {kinds.map((k) => (
            <span
              key={k}
              onClick={() => setHidden((h) => ({ ...h, [k]: !h[k] }))}
              style={{ cursor: "pointer", opacity: hidden[k] ? 0.35 : 1 }}
              title="click to toggle"
            >
              <span className="dot" style={{ background: KIND_COLOR[k] }} /> {KIND_LABEL[k]}
            </span>
          ))}
        </div>
      </div>
      <div className="graph-wrap" ref={wrapRef}>
        <canvas ref={canvasRef} onMouseMove={onMove} onMouseLeave={() => setTip(null)} />
        {tip && (
          <div className="graph-tip" style={{ left: Math.min(tip.x + 12, 520), top: tip.y + 12 }}>
            <div style={{ fontWeight: 600 }}>{tip.node.label}</div>
            <div style={{ color: "var(--muted)" }}>{KIND_LABEL[tip.node.kind] || tip.node.kind}</div>
            {Object.entries(tip.node.meta).map(([kk, vv]) => (
              <div key={kk} style={{ color: "var(--fg-dim)" }}>{kk.replace(/_/g, " ")}: {String(vv)}</div>
            ))}
          </div>
        )}
      </div>
      <div className="note">
        Nodes: {filtered.nodes.length} · Links: {filtered.edges.length}. Hover a node for detail;
        click a legend item to hide that kind. Records link to the workflow that learned them, the
        scope they describe, and each evidence run that supports them.
      </div>
    </div>
  );
}
