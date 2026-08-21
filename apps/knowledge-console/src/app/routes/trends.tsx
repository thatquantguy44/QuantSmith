import { useConsole } from "../../lib/store";
import { Panel } from "../../components/ui";
import { ColumnChart, Donut, LineChart } from "../../components/charts";

export function Trends() {
  const model = useConsole((s) => s.model)!;
  const { trends } = model;
  const cumulative = trends.cumulative_by_date.map((p) => ({ x: p.date, y: p.count }));
  const confirmations = trends.confirmations_by_month.map((p) => ({ label: p.month, value: p.count }));
  const staleSegments = [
    { label: "Fresh", value: trends.staleness.fresh, color: "#2ECC71" },
    { label: "Overdue", value: trends.staleness.overdue, color: "#FF3B3B" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <Panel title="Cumulative Knowledge Over Time (by first-seen)">
        <LineChart points={cumulative} />
        <div className="mt-2 text-2xs text-term-muted">
          Each point is the total number of records the store held as of that date.
        </div>
      </Panel>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Confirmations by Month (last-confirmed)">
          <ColumnChart data={confirmations} />
        </Panel>
        <Panel title={`Freshness vs Policy (${model.freshness_days}d)`}>
          <Donut segments={staleSegments} />
          <div className="mt-3 border-l-2 border-term-amber bg-term-amber/5 px-3 py-2 text-2xs text-term-dim">
            "Overdue" means last confirmation is older than the store's freshness policy as of {model.as_of}. Overdue
            records are still served — surfaced here so a reader can discount or re-validate them.
          </div>
        </Panel>
      </div>
    </div>
  );
}
