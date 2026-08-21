// Dependency-free SVG charts (spec NFR-002: no chart library, no CDN).

import { categoryColor } from "../lib/format";

export function BarList({
  data,
  colorFor,
}: {
  data: { label: string; value: number }[];
  colorFor?: (label: string) => string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (data.length === 0) return <div className="empty">No data</div>;
  return (
    <div>
      {data.map((d) => (
        <div className="bar-row" key={d.label}>
          <span title={d.label} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {d.label}
          </span>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{
                width: `${(d.value / max) * 100}%`,
                background: colorFor ? colorFor(d.label) : categoryColor(d.label),
              }}
            />
          </div>
          <span className="bar-val">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

export function LineChart({
  points,
  height = 200,
  color = "var(--accent)",
}: {
  points: { x: string; y: number }[];
  height?: number;
  color?: string;
}) {
  const width = 640;
  const pad = { top: 14, right: 16, bottom: 26, left: 30 };
  if (points.length === 0) return <div className="empty">No data</div>;
  const maxY = Math.max(1, ...points.map((p) => p.y));
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const n = points.length;
  const xAt = (i: number) => pad.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const yAt = (v: number) => pad.top + innerH - (v / maxY) * innerH;

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(p.y)}`).join(" ");
  const area = `${line} L${xAt(n - 1)},${pad.top + innerH} L${xAt(0)},${pad.top + innerH} Z`;
  const ticks = [0, Math.ceil(maxY / 2), maxY];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="trend line chart">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.left} x2={width - pad.right} y1={yAt(t)} y2={yAt(t)} stroke="var(--border)" strokeWidth={1} />
          <text x={pad.left - 6} y={yAt(t) + 3} fontSize={10} fill="var(--muted)" textAnchor="end">{t}</text>
        </g>
      ))}
      <path d={area} fill={color} opacity={0.14} />
      <path d={line} fill="none" stroke={color} strokeWidth={2} />
      {points.map((p, i) => (
        <circle key={p.x} cx={xAt(i)} cy={yAt(p.y)} r={2.8} fill={color}>
          <title>{`${p.x}: ${p.y}`}</title>
        </circle>
      ))}
      {points.map((p, i) =>
        i % Math.ceil(n / 6 || 1) === 0 || i === n - 1 ? (
          <text key={`lbl-${p.x}`} x={xAt(i)} y={height - 8} fontSize={9} fill="var(--muted)" textAnchor="middle">
            {p.x.slice(2)}
          </text>
        ) : null,
      )}
    </svg>
  );
}

export function ColumnChart({
  data,
  height = 180,
  color = "var(--accent)",
}: {
  data: { label: string; value: number }[];
  height?: number;
  color?: string;
}) {
  const width = 640;
  const pad = { top: 12, right: 12, bottom: 26, left: 28 };
  if (data.length === 0) return <div className="empty">No data</div>;
  const maxY = Math.max(1, ...data.map((d) => d.value));
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const bw = innerW / data.length;
  const yAt = (v: number) => pad.top + innerH - (v / maxY) * innerH;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="column chart">
      {data.map((d, i) => {
        const x = pad.left + i * bw + bw * 0.15;
        const w = bw * 0.7;
        const y = yAt(d.value);
        return (
          <g key={d.label}>
            <rect x={x} y={y} width={w} height={pad.top + innerH - y} rx={3} fill={color}>
              <title>{`${d.label}: ${d.value}`}</title>
            </rect>
            <text x={x + w / 2} y={height - 8} fontSize={9} fill="var(--muted)" textAnchor="middle">
              {d.label.slice(2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function Donut({
  segments,
  size = 150,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = size / 2;
  const stroke = 20;
  const rad = r - stroke / 2 - 2;
  const c = 2 * Math.PI * rad;
  let offset = 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={r} cy={r} r={rad} fill="none" stroke="var(--bg-elev-2)" strokeWidth={stroke} />
        {total > 0 &&
          segments.map((s) => {
            const frac = s.value / total;
            const dash = frac * c;
            const el = (
              <circle
                key={s.label}
                cx={r}
                cy={r}
                r={rad}
                fill="none"
                stroke={s.color}
                strokeWidth={stroke}
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={-offset}
                transform={`rotate(-90 ${r} ${r})`}
              >
                <title>{`${s.label}: ${s.value}`}</title>
              </circle>
            );
            offset += dash;
            return el;
          })}
        <text x={r} y={r - 2} fontSize={22} fontWeight={700} fill="var(--fg)" textAnchor="middle">{total}</text>
        <text x={r} y={r + 16} fontSize={10} fill="var(--muted)" textAnchor="middle">total</text>
      </svg>
      <div className="legend" style={{ flexDirection: "column", gap: 6 }}>
        {segments.map((s) => (
          <span key={s.label}>
            <span className="dot" style={{ background: s.color }} /> {s.label} · {s.value}
          </span>
        ))}
      </div>
    </div>
  );
}
