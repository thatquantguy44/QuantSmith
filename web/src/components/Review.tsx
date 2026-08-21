import { useState } from "react";
import type { Model } from "../lib/types";
import { titleCase } from "../lib/format";
import { AccessBadge, EmptyState, SeverityBadge } from "./common";

const REASON_LABEL: Record<string, string> = {
  freshness: "Overdue for re-validation",
  validation: "Validation finding",
  unsupported_confidence: "Confidence not evidenced",
  thin_corroboration: "Thinly corroborated",
};

export function Review({ model }: { model: Model }) {
  const [sev, setSev] = useState("all");
  const queue = model.review_queue.filter((i) => sev === "all" || i.severity === sev);

  const counts = { error: 0, warn: 0, info: 0 } as Record<string, number>;
  model.review_queue.forEach((i) => { counts[i.severity] = (counts[i.severity] || 0) + 1; });

  return (
    <div>
      <div className="note">
        This is a <strong>read-only review queue</strong>: it shows every record carrying a
        curation signal and why. Confirming, retiring, or editing a record (the approval
        <em> action</em>) needs a reviewer identity and an audit trail — that write path is a
        deliberate follow-up (spec 0048/0057), so nothing here mutates the store.
      </div>

      <div className="controls" style={{ marginTop: 14 }}>
        <label style={{ color: "var(--muted)" }}>Severity</label>
        <select className="sel" value={sev} onChange={(e) => setSev(e.target.value)}>
          <option value="all">All ({model.review_queue.length})</option>
          <option value="error">Error ({counts.error || 0})</option>
          <option value="warn">Warn ({counts.warn || 0})</option>
          <option value="info">Info ({counts.info || 0})</option>
        </select>
      </div>

      {queue.length === 0 ? (
        <EmptyState>Nothing in the queue at this filter — the store is clean here.</EmptyState>
      ) : (
        <div className="grid" style={{ gap: 12 }}>
          {queue.map((item) => (
            <div className="card" key={item.record_id}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span className="id mono" style={{ fontWeight: 700, color: "var(--accent)" }}>{item.record_id}</span>
                <SeverityBadge value={item.severity} />
                <span className="badge">{item.workflow}</span>
                <span className="badge">{titleCase(item.type)}</span>
                <AccessBadge value={item.access_level} />
                <span style={{ flex: 1 }} />
                <span className="prov">last confirmed {item.last_confirmed}</span>
              </div>
              <div className="prov" style={{ marginTop: 6 }}>{item.scope}</div>
              <ul className="reasons">
                {item.reasons.map((r, idx) => (
                  <li key={idx}>
                    <SeverityBadge value={r.severity} />
                    <span><strong>{REASON_LABEL[r.kind] || r.kind}:</strong> {r.detail}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
