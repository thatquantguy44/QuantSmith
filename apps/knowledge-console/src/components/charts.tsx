import { categoryHex } from "../lib/format";

// Dependency-free SVG charts themed for the terminal (no chart library).

export function BarList({
  data,
  colorFor,
}: {
  data: { label: string; value: number }[];
  colorFor?: (label: string) => string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (!data.length) return <div className="text-2xs text-term-muted">no data</div>;
  return (
    <div className="flex flex-col gap-1.5">
      {data.map((d) => (
        <div key={d.label} className="grid grid-cols-[110px_1fr_36px] items-center gap-2">
          <span className="truncate text-2xs uppercase tracking-wide text-term-dim" title={d.label}>
            {d.label}
          </span>
          <div className="h-3 bg-term-panel-2">
            <div
              className="h-full"
              style={{ width: `${(d.value / max) * 100}%`, background: colorFor ? colorFor(d.label) : "#FF8C00" }}
            />
          </div>
          <span className="stat text-right text-2xs text-term-text">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

export function LineChart({ points, height = 210 }: { points: { x: string; y: number }[]; height?: number }) {
  const width = 640;
  const pad = { top: 14, right: 16, bottom: 24, left: 30 };
  if (!points.length) return <div className="text-2xs text-term-muted">no data</div>;
  const maxY = Math.max(1, ...points.map((p) => p.y));
  const iw = width - pad.left - pad.right;
  const ih = height - pad.top - pad.bottom;
  const n = points.length;
  const xAt = (i: number) => pad.left + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);
  const yAt = (v: number) => pad.top + ih - (v / maxY) * ih;
  const line = points.map((p, i) => `${i ? "L" : "M"}${xAt(i)},${yAt(p.y)}`).join(" ");
  const area = `${line} L${xAt(n - 1)},${pad.top + ih} L${xAt(0)},${pad.top + ih} Z`;
  const ticks = [0, Math.ceil(maxY / 2), maxY];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="line chart">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.left} x2={width - pad.right} y1={yAt(t)} y2={yAt(t)} stroke="#26262B" />
          <text x={pad.left - 6} y={yAt(t) + 3} fontSize={9} fill="#5E5E66" textAnchor="end" fontFamily="monospace">
            {t}
          </text>
        </g>
      ))}
      <path d={area} fill="#FF8C00" opacity={0.1} />
      <path d={line} fill="none" stroke="#FF8C00" strokeWidth={1.5} />
      {points.map((p, i) => (
        <circle key={p.x} cx={xAt(i)} cy={yAt(p.y)} r={2.4} fill="#FF8C00">
          <title>{`${p.x}: ${p.y}`}</title>
        </circle>
      ))}
      {points.map((p, i) =>
        i % Math.ceil(n / 6 || 1) === 0 || i === n - 1 ? (
          <text key={`l${p.x}`} x={xAt(i)} y={height - 7} fontSize={8} fill="#5E5E66" textAnchor="middle" fontFamily="monospace">
            {p.x.slice(2)}
          </text>
        ) : null,
      )}
    </svg>
  );
}

export function ColumnChart({ data, height = 190 }: { data: { label: string; value: number }[]; height?: number }) {
  const width = 640;
  const pad = { top: 12, right: 12, bottom: 24, left: 26 };
  if (!data.length) return <div className="text-2xs text-term-muted">no data</div>;
  const maxY = Math.max(1, ...data.map((d) => d.value));
  const iw = width - pad.left - pad.right;
  const ih = height - pad.top - pad.bottom;
  const bw = iw / data.length;
  const yAt = (v: number) => pad.top + ih - (v / maxY) * ih;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="column chart">
      {data.map((d, i) => {
        const x = pad.left + i * bw + bw * 0.18;
        const w = bw * 0.64;
        const y = yAt(d.value);
        return (
          <g key={d.label}>
            <rect x={x} y={y} width={w} height={pad.top + ih - y} fill="#4F9CF9">
              <title>{`${d.label}: ${d.value}`}</title>
            </rect>
            <text x={x + w / 2} y={height - 7} fontSize={8} fill="#5E5E66" textAnchor="middle" fontFamily="monospace">
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
  size = 132,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = size / 2;
  const stroke = 18;
  const rad = r - stroke / 2 - 2;
  const c = 2 * Math.PI * rad;
  let off = 0;
  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={r} cy={r} r={rad} fill="none" stroke="#161619" strokeWidth={stroke} />
        {total > 0 &&
          segments.map((s) => {
            const dash = (s.value / total) * c;
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
                strokeDashoffset={-off}
                transform={`rotate(-90 ${r} ${r})`}
              >
                <title>{`${s.label}: ${s.value}`}</title>
              </circle>
            );
            off += dash;
            return el;
          })}
        <text x={r} y={r - 1} fontSize={20} fontWeight={700} fill="#E6E6E6" textAnchor="middle" fontFamily="monospace">
          {total}
        </text>
        <text x={r} y={r + 14} fontSize={8} fill="#5E5E66" textAnchor="middle" fontFamily="monospace">
          TOTAL
        </text>
      </svg>
      <div className="flex flex-col gap-1.5">
        {segments.map((s) => (
          <span key={s.label} className="flex items-center gap-2 text-2xs uppercase tracking-wide text-term-dim">
            <span className="inline-block h-2 w-2" style={{ background: s.color }} /> {s.label} · {s.value}
          </span>
        ))}
      </div>
    </div>
  );
}

export { categoryHex };
