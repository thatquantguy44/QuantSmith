import type { ReactNode } from "react";
import { ACCESS_COLOR, CONFIDENCE_COLOR, SEVERITY_COLOR, STATUS_COLOR } from "../lib/format";

export function Badge({ color, children }: { color?: string; children: ReactNode }) {
  return (
    <span className="badge">
      {color && <span className="dot" style={{ background: color }} />}
      {children}
    </span>
  );
}

export function ConfidenceBadge({ value }: { value: string }) {
  return <Badge color={CONFIDENCE_COLOR[value] || "var(--muted)"}>{value}</Badge>;
}
export function StatusBadge({ value }: { value: string }) {
  return <Badge color={STATUS_COLOR[value] || "var(--muted)"}>{value}</Badge>;
}
export function AccessBadge({ value }: { value: string }) {
  return <Badge color={ACCESS_COLOR[value] || "var(--muted)"}>{value}</Badge>;
}
export function SeverityBadge({ value }: { value: string }) {
  return <Badge color={SEVERITY_COLOR[value] || "var(--muted)"}>{value}</Badge>;
}

export function Kpi({ value, label, sub }: { value: ReactNode; label: string; sub?: ReactNode }) {
  return (
    <div className="card kpi">
      <div className="kpi-val">{value}</div>
      <div className="kpi-label">{label}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
