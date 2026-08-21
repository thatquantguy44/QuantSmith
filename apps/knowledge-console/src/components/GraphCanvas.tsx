import { useEffect, useMemo, useRef, useState } from "react";
import type { Graph as GraphData, Model } from "../lib/types";

// Canvas force-directed graph, terminal-themed. Records link to their workflow,
// scope, and evidence runs. Deterministic seeding keeps layout stable.

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
  record: "#FF8C00",
  workflow: "#4F9CF9",
  scope: "#2ECC71",
  run: "#B36400",
};
const KIND_LABEL: Record<string, string> = {
  record: "RECORD",
  workflow: "WORKFLOW",
  scope: "SCOPE",
  run: "EVIDENCE RUN",
};

export function GraphCanvas({ model }: { model: Model }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const simRef = useRef<Sim[]>([]);
  const [workflow, setWorkflow] = useState("all");
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [tip, setTip] = useState<{ x: number; y: number; node: Sim } | null>(null);

  const workflows = useMemo(() => Object.keys(model.counts.by_workflow).sort(), [model]);

  const filtered: GraphData = useMemo(() => {
    let nodes = model.graph.nodes.filter((n) => !hidden[n.kind]);
    if (workflow !== "all") {
      const recs = new Set(model.records.filter((r) => r.workflow === workflow).map((r) => `rec:${r.id}`));
      const keep = new Set<string>([...recs, `wf:${workflow}`]);
      for (const e of model.graph.edges) if (recs.has(e.source)) keep.add(e.target);
      nodes = nodes.filter((n) => keep.has(n.id));
    }
    const ids = new Set(nodes.map((n) => n.id));
    return { nodes, edges: model.graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) };
  }, [model, workflow, hidden]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const dpr = window.devicePixelRatio || 1;
    const width = wrap.clientWidth;
    const height = 440;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);

    const n = filtered.nodes.length;
    const nodes: Sim[] = filtered.nodes.map((nd, i) => {
      const a = (i / Math.max(1, n)) * Math.PI * 2;
      const rc = Number(nd.meta.record_count || 0);
      return {
        ...nd,
        x: width / 2 + Math.cos(a) * Math.min(width, height) * 0.32,
        y: height / 2 + Math.sin(a) * Math.min(width, height) * 0.32,
        vx: 0,
        vy: 0,
        r: nd.kind === "record" ? 5.5 : nd.kind === "run" ? 4.5 : 8 + Math.min(9, rc * 1.5),
        color: KIND_COLOR[nd.kind] || "#5E5E66",
      };
    });
    simRef.current = nodes;
    const idx = new Map(nodes.map((nd) => [nd.id, nd]));
    const links = filtered.edges
      .map((e) => ({ s: idx.get(e.source), t: idx.get(e.target) }))
      .filter((l): l is { s: Sim; t: Sim } => !!l.s && !!l.t);

    let alpha = 1;
    let raf = 0;
    function tick() {
      for (let i = 0; i < nodes.length; i += 1)
        for (let j = i + 1; j < nodes.length; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 0.01) {
            d2 = 0.01;
            dx = Math.random();
            dy = Math.random();
          }
          const d = Math.sqrt(d2);
          const f = (2400 / d2) * alpha;
          a.vx += (dx / d) * f;
          a.vy += (dy / d) * f;
          b.vx -= (dx / d) * f;
          b.vy -= (dy / d) * f;
        }
      for (const l of links) {
        const dx = l.t.x - l.s.x;
        const dy = l.t.y - l.s.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = ((d - 88) * 0.02) * alpha;
        l.s.vx += (dx / d) * f;
        l.s.vy += (dy / d) * f;
        l.t.vx -= (dx / d) * f;
        l.t.vy -= (dy / d) * f;
      }
      for (const nd of nodes) {
        nd.vx += (width / 2 - nd.x) * 0.002 * alpha;
        nd.vy += (height / 2 - nd.y) * 0.002 * alpha;
        nd.vx *= 0.86;
        nd.vy *= 0.86;
        nd.x = Math.max(nd.r, Math.min(width - nd.r, nd.x + nd.vx));
        nd.y = Math.max(nd.r, Math.min(height - nd.r, nd.y + nd.vy));
      }
      alpha *= 0.985;

      ctx.clearRect(0, 0, width, height);
      ctx.strokeStyle = "#26262B";
      ctx.lineWidth = 1;
      for (const l of links) {
        ctx.beginPath();
        ctx.moveTo(l.s.x, l.s.y);
        ctx.lineTo(l.t.x, l.t.y);
        ctx.stroke();
      }
      for (const nd of nodes) {
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, nd.r, 0, Math.PI * 2);
        ctx.fillStyle = nd.color;
        ctx.fill();
        if (nd.kind !== "record") {
          ctx.fillStyle = nd.kind === "workflow" ? "#E6E6E6" : "#9A9AA3";
          ctx.font = "10px ui-monospace, monospace";
          ctx.textAlign = "center";
          ctx.fillText(nd.label.length > 20 ? `${nd.label.slice(0, 20)}…` : nd.label, nd.x, nd.y - nd.r - 4);
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
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <span className="label">workflow</span>
        <select
          className="border border-term-border-2 bg-term-bg px-2 py-1 text-2xs uppercase text-term-text focus:border-term-amber focus:outline-none"
          value={workflow}
          onChange={(e) => setWorkflow(e.target.value)}
        >
          <option value="all">ALL</option>
          {workflows.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
        <span className="flex-1" />
        <div className="flex flex-wrap gap-3">
          {kinds.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setHidden((h) => ({ ...h, [k]: !h[k] }))}
              className="flex items-center gap-1.5 text-2xs uppercase tracking-wide text-term-dim"
              style={{ opacity: hidden[k] ? 0.35 : 1 }}
            >
              <span className="inline-block h-2 w-2" style={{ background: KIND_COLOR[k] }} /> {KIND_LABEL[k]}
            </button>
          ))}
        </div>
      </div>
      <div ref={wrapRef} className="relative border border-term-border bg-term-bg">
        <canvas ref={canvasRef} onMouseMove={onMove} onMouseLeave={() => setTip(null)} />
        {tip && (
          <div
            className="pointer-events-none absolute z-10 max-w-[240px] border border-term-border-2 bg-term-panel-2 px-2 py-1.5 text-2xs"
            style={{ left: Math.min(tip.x + 12, 460), top: tip.y + 12 }}
          >
            <div className="font-semibold text-term-text">{tip.node.label}</div>
            <div className="text-term-muted">{KIND_LABEL[tip.node.kind] || tip.node.kind}</div>
            {Object.entries(tip.node.meta).map(([k, v]) => (
              <div key={k} className="text-term-dim">
                {k.replace(/_/g, " ")}: {String(v)}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="mt-2 text-2xs text-term-muted">
        {filtered.nodes.length} nodes · {filtered.edges.length} links · hover for detail, toggle a legend key to filter
      </div>
    </div>
  );
}
