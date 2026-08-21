import type { Model } from "../lib/types";
import { ColumnChart, Donut, LineChart } from "./charts";

export function Trends({ model }: { model: Model }) {
  const { trends } = model;
  const cumulative = trends.cumulative_by_date.map((p) => ({ x: p.date, y: p.count }));
  const confirmations = trends.confirmations_by_month.map((p) => ({ label: p.month, value: p.count }));

  const staleSegments = [
    { label: "Fresh", value: trends.staleness.fresh, color: "var(--ok)" },
    { label: "Overdue", value: trends.staleness.overdue, color: "var(--warn)" },
  ];

  return (
    <div>
      <div className="card">
        <h3>Cumulative knowledge over time (by first-seen date)</h3>
        <LineChart points={cumulative} />
        <div className="legend" style={{ marginTop: 8 }}>
          <span>Each point is the total number of records the store held as of that date.</span>
        </div>
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Confirmations by month (last-confirmed)</h3>
          <ColumnChart data={confirmations} color="var(--accent)" />
        </div>
        <div className="card">
          <h3>Freshness vs. policy ({model.freshness_days}-day)</h3>
          <Donut segments={staleSegments} />
          <div className="note">
            "Overdue" means a record's last confirmation is older than the store's
            <code> freshness_days</code> policy, as of <code>{model.as_of}</code>. Overdue
            records are still served — the console surfaces them so a reader can
            discount or re-validate them, per the memory standard.
          </div>
        </div>
      </div>
    </div>
  );
}
