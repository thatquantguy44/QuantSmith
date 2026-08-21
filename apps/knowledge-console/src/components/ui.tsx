import type { ReactNode } from "react";
import { cn } from "../lib/format";

export function Panel({
  title,
  right,
  children,
  className,
  bodyClass,
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
}) {
  return (
    <section className={cn("panel", className)}>
      <header className="panel-header">
        <span className="panel-title">{title}</span>
        {right}
      </header>
      <div className={cn("panel-body", bodyClass)}>{children}</div>
    </section>
  );
}

export function Chip({ className, children }: { className?: string; children: ReactNode }) {
  return <span className={cn("chip", className)}>{children}</span>;
}

export function Stat({
  value,
  label,
  hint,
  accent,
}: {
  value: ReactNode;
  label: string;
  hint?: ReactNode;
  accent?: "amber" | "up" | "down" | "info";
}) {
  const color =
    accent === "amber"
      ? "text-term-amber"
      : accent === "up"
        ? "text-term-up"
        : accent === "down"
          ? "text-term-down"
          : accent === "info"
            ? "text-term-info"
            : "text-term-text";
  return (
    <div className="panel">
      <div className="px-3 pt-2">
        <div className="label">{label}</div>
      </div>
      <div className="px-3 pb-2">
        <div className={cn("stat text-3xl font-bold leading-none", color)}>{value}</div>
        {hint && <div className="mt-1 text-2xs text-term-dim">{hint}</div>}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="border border-dashed border-term-border px-4 py-8 text-center text-xs text-term-muted">
      {children}
    </div>
  );
}
