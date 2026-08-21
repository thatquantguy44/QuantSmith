// Small presentation helpers shared across views.

export function titleCase(s: string): string {
  return s
    .replace(/[_:]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

export const CONFIDENCE_COLOR: Record<string, string> = {
  high: "var(--ok)",
  medium: "var(--warn)",
  low: "var(--muted)",
};

export const STATUS_COLOR: Record<string, string> = {
  active: "var(--ok)",
  stale: "var(--warn)",
  superseded: "var(--muted)",
  retired: "var(--muted)",
};

export const SEVERITY_COLOR: Record<string, string> = {
  error: "var(--err)",
  warn: "var(--warn)",
  info: "var(--accent)",
};

export const ACCESS_COLOR: Record<string, string> = {
  public: "var(--ok)",
  internal: "var(--accent)",
  restricted: "var(--err)",
};

// A stable, distinct color per node kind / category, drawn from the palette.
const PALETTE = [
  "#4f9cf9", "#22c55e", "#f59e0b", "#ef4444", "#a855f7",
  "#14b8a6", "#e879a6", "#84cc16", "#38bdf8", "#fb923c",
];

export function categoryColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i += 1) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function shortDate(iso: string): string {
  return iso ? iso.slice(0, 10) : "";
}

export function relDays(days: number): string {
  if (days <= 0) return "today";
  if (days === 1) return "1 day ago";
  if (days < 45) return `${days} days ago`;
  const months = Math.round(days / 30);
  return `${months} mo ago`;
}
