"""Evidence-bound executive and analyst views, without a generative narrator."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace

from quantsmith.nl_analytics.chart import choose_chart
from quantsmith.pipelines.dashboard_spec import DashboardSpec, Panel

from .catalog import SCHEMA_VERSION, VisualizationError, resolve_metric, validate_pack
from .evidence import Claim, Evidence, bind_claim, validate_claim


@dataclass(frozen=True)
class Benchmark:
    policy_id: str
    evidence_id: str
    evidence_digest: str
    unit: str
    target: float
    direction: str  # higher | lower (caller policy, never inferred)


@dataclass(frozen=True)
class Section:
    section_id: str
    observation: str
    interpretation: str
    chart: object
    claims: tuple[Claim, ...]
    rule: str
    caveats: tuple[str, ...]
    assessment: dict | None = None


@dataclass(frozen=True)
class Story:
    status: str
    reason: str
    pack_id: str = ""
    recipe_id: str = ""
    decision: str = ""
    headline: str = ""
    supporting_findings: tuple[str, ...] = ()
    sections: tuple[Section, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    caveats: tuple[str, ...] = ()
    action: str = ""
    action_evidence_ids: tuple[str, ...] = ()
    pack_versions: tuple[tuple[str, str], ...] = ()
    conventions: tuple[str, ...] = ()

    def to_dict(self):
        payload = {k: v for k, v in asdict(self).items() if k != "evidence"}
        payload["schema_version"] = SCHEMA_VERSION
        payload["evidence"] = [dict(e.payload(), digest=e.digest) for e in self.evidence]
        return payload


def describe_claim(claim, evidence):
    plan = evidence.result.plan
    population = ", ".join(f"{name}={value}" for name, value in zip(plan.dimensions, claim.population))
    filters = ", ".join(f"{f.dimension}={','.join(sorted(f.values))}" for f in plan.filters)
    scope = "; ".join(s for s in (population, filters) if s) or "declared population"
    period = str(claim.period) if claim.period is not None else f"{plan.window.start_period}–{plan.window.end_period}"
    return f"{claim.metric}: {claim.value:,.6g} {claim.unit} ({scope}; {plan.window.grain} period {period}; as of {claim.as_of})."


def _comparable(current, baseline):
    a, b = current.result.plan, baseline.result.plan
    scope_a = tuple(sorted((f.dimension, f.op, tuple(sorted(f.values))) for f in a.filters if f.dimension != "scenario"))
    scope_b = tuple(sorted((f.dimension, f.op, tuple(sorted(f.values))) for f in b.filters if f.dimension != "scenario"))
    same_window = a.window == b.window
    prior_window = (b.window.end_period < a.window.start_period and
                    b.window.end_period - b.window.start_period == a.window.end_period - a.window.start_period)
    return (current.analytics_pack_id == baseline.analytics_pack_id and current.unit == baseline.unit
            and current.definition == baseline.definition and a.metric == b.metric
            and a.dimensions == b.dimensions and scope_a == scope_b
            and a.window.grain == b.window.grain and (same_window or prior_window)
            and current.result.as_of == baseline.result.as_of
            and (a.window != b.window or a.filters != b.filters))


def _assessment(benchmark, evidence):
    if not isinstance(benchmark, Benchmark) or not benchmark.policy_id.strip():
        raise VisualizationError("A supplied benchmark needs an identified policy.")
    if (benchmark.evidence_id != evidence.evidence_id or benchmark.evidence_digest != evidence.digest
            or benchmark.unit != evidence.unit or benchmark.direction not in ("higher", "lower")
            or isinstance(benchmark.target, bool) or not isinstance(benchmark.target, (int, float))
            or not math.isfinite(benchmark.target) or evidence.result.plan.dimensions):
        raise VisualizationError("Benchmark does not bind to this scalar evidence, unit, and scope.")
    value = bind_claim(evidence).value
    relation = "above" if value > benchmark.target else "below" if value < benchmark.target else "at"
    meets = value >= benchmark.target if benchmark.direction == "higher" else value <= benchmark.target
    return dict(asdict(benchmark), relation=relation, meets_policy=meets)


def build_story(catalog, pack_id, recipe_id, evidence, layer, *, benchmarks=()):
    """Compose a complete story or a typed refusal; never a partial positive answer."""
    def refuse(status, reason):
        return Story(status, reason)

    pack = catalog.packs.get(pack_id)
    if pack is None:
        return refuse("unavailable", "Unknown visualization pack.")
    errors = validate_pack(pack, catalog.analytics, catalog.root)
    if errors:
        return refuse("invalid", "; ".join(errors))
    recipe = next((r for r in pack["recipes"] if r["recipe_id"] == recipe_id), None)
    if recipe is None:
        return refuse("unavailable", "Unknown recipe for this pack.")
    by_id = {e.evidence_id: e for e in evidence}
    if len(by_id) != len(evidence):
        return refuse("clarification_needed", "Duplicate evidence identifiers; supply one result per required input.")
    required = [s["section_id"] for s in recipe["sections"]]
    required += [s["section_id"] + "_baseline" for s in recipe["sections"] if s["view"] == "comparison"]
    # Refusals take precedence over missing-input diagnostics, which might name
    # a private metric or source if the caller supplied mixed visible evidence.
    for eid in required:
        if eid in by_id and by_id[eid].status != "ready":
            e = by_id[eid]
            return refuse(e.status, e.reason)
    missing = sorted(set(required) - set(by_id))
    if missing:
        return refuse("unavailable", "Missing required evidence: " + ", ".join(missing))
    policies = {b.evidence_id: b for b in benchmarks}
    if len(policies) != len(benchmarks) or set(policies) - {s["section_id"] for s in recipe["sections"]}:
        return refuse("invalid", "Duplicate or unused benchmark evidence reference.")
    notes, sections = [], []
    if pack["review"]["status"] != "reviewed":
        notes.append(f"Unreviewed visualization pack: {pack_id} ({pack['review']['status']}).")
    used_evidence = tuple(by_id[eid] for eid in sorted(required))
    try:
        if len({e.result.as_of for e in used_evidence}) != 1:
            raise VisualizationError("All story evidence must share one as-of boundary.")
        for section in recipe["sections"]:
            eid = section["section_id"]
            e = by_id[eid]
            aid, metric = resolve_metric(pack["analytics_pack_ids"], section["metric"], catalog.analytics)
            plan = e.result.plan
            if (e.digest != e.fingerprint() or e.analytics_pack_id != aid or plan.metric != metric["name"]
                    or e.unit != metric["unit"] or plan.dimensions != tuple(section["dimensions"])
                    or e.view != section["view"]):
                raise VisualizationError(f"Evidence {eid!r} does not match the recipe's exact domain, metric, dimensions, and view.")
            # The registry cannot change between collection and presentation.
            from .evidence import canonical
            if canonical(asdict(layer.definition(plan.metric))) != e.definition:
                raise VisualizationError("Governed metric definition changed after evidence collection.")
            chart = choose_chart(e.result, layer, units=e.unit)
            key = sorted(e.result.values, key=lambda k: (-e.result.values[k], k))[0]
            claims = [bind_claim(e, key)]
            observation = describe_claim(claims[0], e)
            section_notes = list(e.caveats) + section["caveats"]
            rule = f"0080 shape rule → {chart.chart_type}"
            if section["view"] == "trend" and len(e.result.series) > 1:
                first = bind_claim(e, (), min(e.result.series))
                claims.append(first)
                observation += " Earlier observation: " + describe_claim(first, e)
            if section["view"] == "attribution":
                section_notes.append("Arithmetic attribution of observed amounts; not causal proof.")
            if section["view"] == "comparison":
                base = by_id[eid + "_baseline"]
                if base.digest != base.fingerprint() or base.view != "comparison" or not _comparable(e, base):
                    raise VisualizationError("Baseline evidence has an incompatible metric, unit, population, period, or as-of boundary.")
                claim = bind_claim(base)
                claims.append(claim)
                observation += " Declared baseline: " + describe_claim(claim, base)
                chart = replace(chart, chart_type="table", x="observation", y="value", series=None,
                                data=({"observation": "current", "value": claims[0].value},
                                      {"observation": "baseline", "value": claim.value}),
                                dimensions=(), zero_baseline=False)
                rule = "Comparable current/baseline observations → table; no implicit variance arithmetic"
                section_notes.extend(base.caveats)
            if section["chart_rule"] == "table":
                chart = replace(chart, chart_type="table")
                rule += "; declared domain table fallback"
                section_notes.append("Chart fallback: " + section["fallback_reason"])
            assessment = _assessment(policies[eid], e) if eid in policies else None
            if assessment is None:
                section_notes.append("No applicable benchmark or direction policy supplied; no performance verdict is inferred.")
            else:
                observation += (f" {assessment['relation'].capitalize()} supplied target {assessment['target']:,.6g} "
                                f"{e.unit}; policy {assessment['policy_id']} ({assessment['direction']} is preferred).")
            source_note = f"Source: {e.source}; as of {e.result.as_of}; evidence: {e.evidence_id} ({e.digest})."
            if section["view"] == "comparison":
                base = by_id[eid + "_baseline"]
                source_note += f" Baseline source: {base.source}; evidence: {base.evidence_id} ({base.digest})."
            chart = replace(chart, title=observation, alt_text=observation,
                            footnote=source_note + " " + " ".join(sorted(set(section_notes + notes))))
            for claim in claims:
                if validate_claim(claim, by_id[claim.evidence_id]):
                    raise VisualizationError("A generated claim failed its evidence binding.")
            sections.append(Section(eid, observation, section["interpretation"], chart, tuple(claims), rule,
                                    tuple(sorted(set(section_notes))), assessment))
            notes.extend(section_notes)
    except (VisualizationError, ValueError, KeyError) as exc:
        return refuse("invalid", str(exc))
    versions = [(pack_id, pack["schema_version"])]
    versions += [(aid, catalog.analytics[aid]["schema_version"]) for aid in sorted(pack["analytics_pack_ids"])]
    conventions = tuple(f"{aid}/{c['id']}: {c['rule']}" for aid in sorted(pack["analytics_pack_ids"])
                        for c in catalog.analytics[aid]["chart_conventions"])
    return Story("ready", "All required evidence validated.", pack_id, recipe_id, recipe["decision"],
                 sections[0].observation, tuple(s.observation for s in sections[1:4]), tuple(sections), used_evidence,
                 tuple(sorted(set(notes))), recipe["action"], tuple(e.evidence_id for e in used_evidence),
                 tuple(versions), conventions)


def dashboard_handoff(story, dataset):
    """The companion story is mandatory: bare DashboardSpec has no caveat field."""
    if story.status != "ready":
        raise VisualizationError("A refused story has no dashboard handoff.")
    spec = DashboardSpec(story.decision, dataset,
                         tuple(Panel(s.observation, s.chart.chart_type, s.chart.metric, s.chart.dimensions)
                               for s in story.sections))
    return {"dashboard_spec": asdict(spec), "story": story.to_dict()}
