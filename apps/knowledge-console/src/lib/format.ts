import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

export function titleCase(s: string): string {
  return s.replace(/[_:]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).trim();
}

// term.* semantic colors as class fragments.
export const CONFIDENCE_CLASS: Record<string, string> = {
  high: "text-term-up border-term-up/40",
  medium: "text-term-amber border-term-amber/40",
  low: "text-term-muted border-term-border-2",
};

export const STATUS_CLASS: Record<string, string> = {
  active: "text-term-up border-term-up/40",
  stale: "text-term-amber border-term-amber/40",
  superseded: "text-term-muted border-term-border-2",
  retired: "text-term-muted border-term-border-2",
};

export const SEVERITY_CLASS: Record<string, string> = {
  error: "text-term-down border-term-down/40",
  warn: "text-term-amber border-term-amber/40",
  info: "text-term-info border-term-info/40",
};

export const ACCESS_CLASS: Record<string, string> = {
  public: "text-term-up border-term-up/40",
  internal: "text-term-info border-term-info/40",
  restricted: "text-term-down border-term-down/40",
};

const KIND_HEX = ["#FF8C00", "#2ECC71", "#4F9CF9", "#E879A6", "#B36400", "#14B8A6"];
export function categoryHex(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i += 1) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return KIND_HEX[h % KIND_HEX.length];
}
