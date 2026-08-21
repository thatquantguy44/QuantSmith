import { useEffect, useMemo, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { useConsole } from "../../lib/store";
import { cn, titleCase, ACCESS_CLASS, SEVERITY_CLASS } from "../../lib/format";
import { Panel, Chip, Stat, Empty } from "../../components/ui";
import { BarList } from "../../components/charts";
import type { ResearchItem } from "../../lib/types";

const REVIEW_CLASS: Record<string, string> = {
  approved: "text-term-up border-term-up/40",
  pending_review: "text-term-amber border-term-amber/40",
  quarantined: "text-term-down border-term-down/40",
  restricted: "text-term-down border-term-down/40",
  superseded: "text-term-muted border-term-border-2",
  deprecated: "text-term-muted border-term-border-2",
  deleted: "text-term-muted border-term-border-2",
  draft: "text-term-info border-term-info/40",
};

function toList(obj: Record<string, number>) {
  return Object.entries(obj).map(([label, value]) => ({ label: titleCase(label), value })).sort((a, b) => b.value - a.value);
}

export function Research() {
  const { research, researchLoading, researchError, loadResearch } = useConsole();
  const [sourceType, setSourceType] = useState("all");
  const [assetClass, setAssetClass] = useState("all");
  const [showHidden, setShowHidden] = useState(false);

  useEffect(() => {
    if (!research && !researchLoading) loadResearch();
  }, [research, researchLoading, loadResearch]);

  const filtered = useMemo(() => {
    if (!research) return [] as ResearchItem[];
    return research.items.filter((it) => {
      if (!showHidden && it.hidden_by_default) return false;
      if (sourceType !== "all" && it.source_type !== sourceType) return false;
      if (assetClass !== "all" && it.asset_class !== assetClass) return false;
      return true;
    });
  }, [research, sourceType, assetClass, showHidden]);

  if (researchError) {
    return <div className="border border-term-down/50 bg-term-down/10 p-4 text-xs text-term-down">Failed to load research store: {researchError}</div>;
  }
  if (!research) {
    return <div className="text-xs uppercase tracking-widest text-term-muted">loading research store…</div>;
  }

  const sourceTypes = Object.keys(research.counts.by_source_type).sort();
  const assetClasses = Object.keys(research.counts.by_asset_class).sort();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-3 border-l-2 border-term-amber bg-term-amber/5 px-3 py-2 text-2xs text-term-dim">
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-term-amber" />
        <span>{research.disclaimer}</span>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat value={research.counts.total} label="Research Items" hint={`${research.counts.visible} visible`} />
        <Stat
          value={research.counts.hidden}
          label="Hidden by Default"
          accent="amber"
          hint="quarantined / deleted"
        />
        <Stat value={research.counts.by_access_level.restricted || 0} label="Restricted / Entitled" accent="down" />
        <Stat value={research.counts.by_review_status.approved || 0} label="Approved" accent="up" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="By Source Type">
          <BarList data={toList(research.counts.by_source_type)} />
        </Panel>
        <Panel title="By Asset Class">
          <BarList data={toList(research.counts.by_asset_class)} />
        </Panel>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="label">source type</span>
        <select className="border border-term-border-2 bg-term-bg px-2 py-1 text-2xs uppercase text-term-text focus:border-term-amber focus:outline-none" value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
          <option value="all">ALL</option>
          {sourceTypes.map((s) => (
            <option key={s} value={s}>{titleCase(s)}</option>
          ))}
        </select>
        <span className="label">asset class</span>
        <select className="border border-term-border-2 bg-term-bg px-2 py-1 text-2xs uppercase text-term-text focus:border-term-amber focus:outline-none" value={assetClass} onChange={(e) => setAssetClass(e.target.value)}>
          <option value="all">ALL</option>
          {assetClasses.map((s) => (
            <option key={s} value={s}>{titleCase(s)}</option>
          ))}
        </select>
        <label className="ml-2 flex items-center gap-1.5 text-2xs uppercase tracking-wide text-term-dim">
          <input type="checkbox" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} className="accent-term-amber" />
          show quarantined/deleted
        </label>
        <span className="flex-1" />
        <span className="text-2xs text-term-muted">{filtered.length} item(s)</span>
      </div>

      {filtered.length === 0 ? (
        <Empty>No research items match this filter.</Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((it) => (
            <Panel
              key={it.id}
              title={it.id}
              right={
                <div className="flex flex-wrap items-center gap-2">
                  <Chip className="border-term-border-2 text-term-dim">{titleCase(it.source_type)}</Chip>
                  <Chip className="border-term-border-2 text-term-dim">{titleCase(it.asset_class)}</Chip>
                  <Chip className={cn(ACCESS_CLASS[it.access_level])}>{it.access_level}</Chip>
                  <Chip className={cn(REVIEW_CLASS[it.review_status] || SEVERITY_CLASS.info)}>{titleCase(it.review_status)}</Chip>
                </div>
              }
            >
              <div className="mb-1 text-sm font-semibold text-term-text">{it.title}</div>
              <div className="mb-2 text-3xs text-term-muted">
                {it.author_or_publisher} · {it.strategy_theme && `${titleCase(it.strategy_theme)} · `}
                {it.geography && `${it.geography} · `}
                published {it.publication_date} · ingested {it.ingestion_date}
                {it.entitlement_class && ` · ${it.entitlement_class}`}
              </div>
              <p className="text-xs leading-relaxed text-term-text">{it.summary}</p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-3xs text-term-muted">
                <span>cite: {it.citation}</span>
                {it.superseded_by && <span className="text-term-amber">superseded by {it.superseded_by}</span>}
                {it.overdue && <span className="text-term-down">overdue for re-validation</span>}
              </div>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
