import { Link } from "react-router-dom";
import { useConsole } from "../../lib/store";
import { cn, titleCase, CONFIDENCE_CLASS, STATUS_CLASS, ACCESS_CLASS, categoryHex } from "../../lib/format";
import { Panel, Stat, Chip } from "../../components/ui";
import { BarList, Donut } from "../../components/charts";

function toList(obj: Record<string, number>) {
  return Object.entries(obj).map(([label, value]) => ({ label: titleCase(label), value })).sort((a, b) => b.value - a.value);
}

export function Overview() {
  const model = useConsole((s) => s.model)!;
  const { counts, trends, review_queue } = model;

  const confidenceSegments = Object.entries(counts.by_confidence).map(([label, value]) => ({
    label: titleCase(label),
    value,
    color: label === "high" ? "#2ECC71" : label === "medium" ? "#FF8C00" : "#5E5E66",
  }));

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat value={counts.total} label="Knowledge Records" hint={`${Object.keys(counts.by_workflow).length} workflow(s)`} />
        <Stat value={review_queue.length} label="Needing Review" accent="amber" hint={`${trends.staleness.overdue} overdue`} />
        <Stat value={counts.by_confidence.high || 0} label="High Confidence" accent="up" hint={`${counts.by_confidence.medium || 0} med · ${counts.by_confidence.low || 0} low`} />
        <Stat value={trends.staleness.fresh} label="Fresh Records" accent="info" hint={`policy ${model.freshness_days}d`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Records by Type">
          <BarList data={toList(counts.by_type)} colorFor={(l) => categoryHex(l)} />
        </Panel>
        <Panel title="Confidence Mix">
          <Donut segments={confidenceSegments} />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel title="By Workflow">
          <BarList data={toList(counts.by_workflow)} colorFor={(l) => categoryHex(l)} />
        </Panel>
        <Panel title="By Status">
          <BarList data={toList(counts.by_status)} />
        </Panel>
        <Panel title="By Access Level">
          <BarList data={toList(counts.by_access_level)} />
        </Panel>
      </div>

      <Panel
        title="Records"
        right={
          review_queue.length > 0 ? (
            <Link to="/review" className="text-2xs uppercase tracking-wider text-term-amber hover:underline">
              {review_queue.length} need review →
            </Link>
          ) : undefined
        }
        bodyClass="p-0"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-term-border text-3xs uppercase tracking-widest text-term-muted">
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Statement</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Conf</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Access</th>
                <th className="px-3 py-2 text-left">Confirmed</th>
              </tr>
            </thead>
            <tbody>
              {model.records.map((r) => (
                <tr key={r.id} className="row-hover border-b border-term-border/60 align-top">
                  <td className="whitespace-nowrap px-3 py-2 font-semibold text-term-amber">{r.id}</td>
                  <td className="max-w-[420px] px-3 py-2">
                    <div className="text-term-text">{r.statement}</div>
                    <div className="mt-0.5 text-3xs text-term-muted">
                      {r.workflow} · {r.scope} · {r.source_file.split("/").slice(-2).join("/")}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-term-dim">{titleCase(r.type)}</td>
                  <td className="px-3 py-2">
                    <Chip className={cn(CONFIDENCE_CLASS[r.confidence])}>{r.confidence}</Chip>
                  </td>
                  <td className="px-3 py-2">
                    <Chip className={cn(STATUS_CLASS[r.status])}>{r.status}</Chip>
                  </td>
                  <td className="px-3 py-2">
                    <Chip className={cn(ACCESS_CLASS[r.access_level])}>{r.access_level}</Chip>
                  </td>
                  <td className={cn("whitespace-nowrap px-3 py-2 stat", r.overdue ? "text-term-down" : "text-term-dim")}>
                    {r.last_confirmed}
                    {r.overdue && <div className="text-3xs text-term-down">overdue</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
