import type { Model } from "../lib/types";
import { titleCase, CONFIDENCE_COLOR, categoryColor } from "../lib/format";
import { BarList, Donut } from "./charts";
import { AccessBadge, ConfidenceBadge, Kpi, StatusBadge } from "./common";

function toList(obj: Record<string, number>) {
  return Object.entries(obj)
    .map(([label, value]) => ({ label: titleCase(label), value }))
    .sort((a, b) => b.value - a.value);
}

export function Overview({ model, onGoReview }: { model: Model; onGoReview: () => void }) {
  const { counts, trends, review_queue } = model;
  const overdue = trends.staleness.overdue;
  const workflows = Object.keys(counts.by_workflow).length;

  const confidenceSegments = Object.entries(counts.by_confidence).map(([label, value]) => ({
    label: titleCase(label),
    value,
    color: CONFIDENCE_COLOR[label] || "var(--muted)",
  }));

  return (
    <div>
      <div className="grid cols-4">
        <Kpi value={counts.total} label="Knowledge records" sub={`${workflows} workflow(s)`} />
        <Kpi
          value={review_queue.length}
          label="Needing review"
          sub={<span style={{ color: "var(--warn)" }}>{overdue} overdue for re-validation</span>}
        />
        <Kpi
          value={`${counts.by_confidence.high || 0}`}
          label="High-confidence records"
          sub={`${counts.by_confidence.medium || 0} medium · ${counts.by_confidence.low || 0} low`}
        />
        <Kpi
          value={trends.staleness.fresh}
          label="Fresh records"
          sub={`policy: re-validate after ${model.freshness_days} days`}
        />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Records by type</h3>
          <BarList data={toList(counts.by_type)} />
        </div>
        <div className="card">
          <h3>Confidence mix</h3>
          <Donut segments={confidenceSegments} />
        </div>
      </div>

      <div className="grid cols-3" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>By workflow</h3>
          <BarList data={toList(counts.by_workflow)} colorFor={(l) => categoryColor(l)} />
        </div>
        <div className="card">
          <h3>By status</h3>
          <BarList data={toList(counts.by_status)} />
        </div>
        <div className="card">
          <h3>By access level</h3>
          <BarList data={toList(counts.by_access_level)} />
        </div>
      </div>

      <div className="section-title">Records</div>
      <div className="card" style={{ padding: 0, overflowX: "auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>ID</th>
              <th>Statement</th>
              <th>Type</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Access</th>
              <th>Confirmed</th>
            </tr>
          </thead>
          <tbody>
            {model.records.map((r) => (
              <tr key={r.id}>
                <td className="id">{r.id}</td>
                <td style={{ maxWidth: 420 }}>
                  <div className="stmt">{r.statement}</div>
                  <div className="prov">
                    {r.workflow} · {r.scope} · {r.source_file.split("/").slice(-2).join("/")}
                  </div>
                </td>
                <td>{titleCase(r.type)}</td>
                <td><ConfidenceBadge value={r.confidence} /></td>
                <td><StatusBadge value={r.status} /></td>
                <td><AccessBadge value={r.access_level} /></td>
                <td style={{ whiteSpace: "nowrap", color: r.overdue ? "var(--warn)" : "var(--fg-dim)" }}>
                  {r.last_confirmed}
                  {r.overdue && <div className="prov" style={{ color: "var(--warn)" }}>overdue</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {review_queue.length > 0 && (
        <div className="note warn">
          {review_queue.length} record(s) carry a curation signal.{" "}
          <a onClick={onGoReview} style={{ cursor: "pointer" }}>Open the review queue →</a>
        </div>
      )}
    </div>
  );
}
