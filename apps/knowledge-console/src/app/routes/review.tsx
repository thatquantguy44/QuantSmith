import { useState } from "react";
import { useConsole } from "../../lib/store";
import { cn, titleCase, SEVERITY_CLASS, ACCESS_CLASS } from "../../lib/format";
import { Panel, Chip, Empty } from "../../components/ui";

const REASON_LABEL: Record<string, string> = {
  freshness: "Overdue for re-validation",
  validation: "Validation finding",
  unsupported_confidence: "Confidence not evidenced",
  thin_corroboration: "Thinly corroborated",
};

export function Review() {
  const model = useConsole((s) => s.model)!;
  const [sev, setSev] = useState("all");
  const queue = model.review_queue.filter((i) => sev === "all" || i.severity === sev);
  const counts: Record<string, number> = { error: 0, warn: 0, info: 0 };
  model.review_queue.forEach((i) => (counts[i.severity] = (counts[i.severity] || 0) + 1));

  return (
    <div className="flex flex-col gap-4">
      <div className="border-l-2 border-term-amber bg-term-amber/5 px-3 py-2 text-2xs text-term-dim">
        <span className="font-semibold uppercase tracking-wider text-term-amber">Read-only review queue.</span> It shows
        every record carrying a curation signal and why. Confirming/retiring a record (the approval action) needs a
        reviewer identity and audit trail — a deliberate follow-up (0049 write path). Nothing here mutates the store.
      </div>

      <div className="flex items-center gap-3">
        <span className="label">severity</span>
        <select
          className="border border-term-border-2 bg-term-bg px-2 py-1 text-2xs uppercase text-term-text focus:border-term-amber focus:outline-none"
          value={sev}
          onChange={(e) => setSev(e.target.value)}
        >
          <option value="all">ALL ({model.review_queue.length})</option>
          <option value="error">ERROR ({counts.error || 0})</option>
          <option value="warn">WARN ({counts.warn || 0})</option>
          <option value="info">INFO ({counts.info || 0})</option>
        </select>
      </div>

      {queue.length === 0 ? (
        <Empty>Nothing in the queue at this filter — the store is clean here.</Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {queue.map((item) => (
            <Panel
              key={item.record_id}
              title={item.record_id}
              right={
                <div className="flex items-center gap-2">
                  <Chip className={cn(SEVERITY_CLASS[item.severity])}>{item.severity}</Chip>
                  <Chip className="border-term-border-2 text-term-dim">{item.workflow}</Chip>
                  <Chip className="border-term-border-2 text-term-dim">{titleCase(item.type)}</Chip>
                  <Chip className={cn(ACCESS_CLASS[item.access_level])}>{item.access_level}</Chip>
                </div>
              }
            >
              <div className="mb-2 text-3xs text-term-muted">
                {item.scope} · last confirmed {item.last_confirmed}
              </div>
              <ul className="flex flex-col gap-1.5">
                {item.reasons.map((r, i) => (
                  <li key={i} className="flex items-baseline gap-2 text-2xs text-term-dim">
                    <Chip className={cn(SEVERITY_CLASS[r.severity])}>{r.severity}</Chip>
                    <span>
                      <span className="font-semibold text-term-text">{REASON_LABEL[r.kind] || r.kind}:</span> {r.detail}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
