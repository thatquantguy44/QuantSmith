"""Analytics domain packs — spec ``0081-analytics-domain-packs``.

An analytics domain pack tells a natural-language analytics run (spec ``0080``)
how to read one kind of financial-services data: the vocabulary people use for
its metrics, the unit and additivity of each metric, which insights are
meaningless for it, the caveats it always needs, how it should be charted, and
which agent reviews answers about it. Packs live as JSON under
``knowledge/analytics_packs/`` and are selected by the ``domain:`` tags already
declared on every ``sources/*.yml`` entry (spec ``0027``).

What this module guarantees, and what it does not:

* It validates **structure and internal consistency**: required fields, the
  unit and additivity vocabularies, that a rate-like unit is never declared
  additive without a written rationale, that every golden case agrees with the
  pack's own declarations and arithmetic, and that every reviewer agent and
  ``builds_on`` path actually exists in the repository.
* It does **not** certify that a convention is correct. A pack becomes usable
  for database write-back only when a named person marks it ``reviewed``
  (REQ-005). Until then ``0080`` may apply it in chat with a visible caveat.
* Packs only ever **restrict** interpretation (suppress insights, add caveats,
  force units). Nothing here can widen access or loosen ``0008`` governance.

Standard library only (NFR-001).
"""

from __future__ import annotations

import fnmatch
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = "0081.1"

FAMILIES = (
    "business_line",
    "markets",
    "risk",
    "finance_treasury",
    "control_compliance",
    "operations",
    "cross_cutting",
)

UNITS = (
    "currency", "currency_per_unit", "count", "quantity",
    "pct", "bps", "ratio", "multiple", "index", "score", "years", "days",
)

# Units whose values are rates, ratios, or levels. A metric in one of these
# units is non-additive unless it carries a written ``additivity_rationale``
# (e.g. single-period attribution effects, which sum by construction).
RATE_LIKE_UNITS = frozenset({"pct", "bps", "ratio", "multiple", "index", "score", "years", "days"})

ADDITIVITY = ("additive", "semi_additive", "non_additive")

# What each additivity class permits: (across dimensions, across time).
ADDITIVITY_RULES: Dict[str, Tuple[bool, bool]] = {
    "additive": (True, True),          # flows: P&L, volume, losses
    "semi_additive": (True, False),    # stocks: balances, exposures — period-end or average over time
    "non_additive": (False, False),    # rates, ratios, quantiles (VaR), prices
}

# The insight kinds spec 0080 computes (REQ-007).
INSIGHT_KINDS = ("level", "change", "contributor", "trend", "outlier", "concentration")

REVIEW_STATUSES = ("draft", "in_review", "reviewed")

GOLDEN_KINDS = ("bps_change", "additivity", "ratio")

_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_TRIGGER_RE = re.compile(r"^(always|metric:[a-z0-9_*]+|dimension:[a-z0-9_]+)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TOLERANCE = 1e-6

PACKS_DIR = Path("knowledge") / "analytics_packs"


class PackValidationError(ValueError):
    """Raised by :func:`load_packs` when ``strict`` and any pack is invalid."""


@dataclass(frozen=True)
class Finding:
    """One validation problem. ``severity`` is ``error`` or ``info``."""

    pack_id: str
    severity: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - formatting
        return f"[{self.severity}] {self.pack_id}: {self.message}"


@dataclass(frozen=True)
class Selection:
    """The packs selected for one dataset (REQ-004)."""

    packs: Tuple[dict, ...]
    unmatched_domains: Tuple[str, ...]
    synonym_conflicts: Tuple[Tuple[str, Tuple[str, ...]], ...] = field(default_factory=tuple)

    @property
    def pack_ids(self) -> Tuple[str, ...]:
        return tuple(p["pack_id"] for p in self.packs)

    @property
    def all_reviewed(self) -> bool:
        """True when every selected pack may drive database write-back (REQ-005)."""
        return bool(self.packs) and all(is_reviewed(p) for p in self.packs)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def pack_paths(root: str | Path = ".") -> List[Path]:
    """Every ``*.json`` pack file, sorted by name for determinism (NFR-001)."""
    d = Path(root) / PACKS_DIR
    return sorted(d.glob("*.json")) if d.is_dir() else []


def load_packs(root: str | Path = ".", *, strict: bool = False) -> List[dict]:
    """Load every pack; with ``strict`` raise if any error-severity finding exists."""
    packs = [json.loads(p.read_text(encoding="utf-8")) for p in pack_paths(root)]
    if strict:
        errors = [f for f in validate_catalog(packs, root) if f.severity == "error"]
        if errors:
            raise PackValidationError("; ".join(str(e) for e in errors))
    return packs


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_REQUIRED = (
    "schema_version", "pack_id", "name", "family", "description", "source_domains",
    "builds_on", "reviewer_agents", "dimensions", "metrics", "conventions",
    "insight_rules", "caveats", "chart_conventions", "golden_cases", "review",
)


def _metric_matches(pattern: str, metrics: Iterable[str]) -> List[str]:
    return [m for m in metrics if fnmatch.fnmatchcase(m, pattern)]


def validate_pack(pack: Mapping, root: str | Path = ".", *, file_stem: Optional[str] = None) -> List[Finding]:
    """Validate one pack's structure and internal consistency (REQ-001..REQ-008)."""
    pid = str(pack.get("pack_id", file_stem or "<unknown>"))
    out: List[Finding] = []

    def err(msg: str) -> None:
        out.append(Finding(pid, "error", msg))

    missing = [k for k in _REQUIRED if k not in pack]
    if missing:
        err(f"missing required field(s): {', '.join(missing)}")
        return out

    if pack["schema_version"] != SCHEMA_VERSION:
        err(f"schema_version {pack['schema_version']!r} != {SCHEMA_VERSION!r}")
    if not _ID_RE.match(pid):
        err("pack_id must be lower_snake_case")
    if file_stem is not None and file_stem != pid:
        err(f"file name {file_stem!r} does not match pack_id")
    if pack["family"] not in FAMILIES:
        err(f"family {pack['family']!r} not in {list(FAMILIES)}")
    if not pack["source_domains"]:
        err("source_domains is empty; a pack nothing can select is unreachable")
    for d in pack["source_domains"]:
        if not _ID_RE.match(d):
            err(f"source domain {d!r} must be lower_snake_case")

    root = Path(root)
    if not pack["reviewer_agents"]:
        err("reviewer_agents is empty (REQ-006)")
    for a in pack["reviewer_agents"]:
        if not (root / a / "prompt.md").is_file():
            err(f"reviewer agent {a!r} does not exist (no {a}/prompt.md)")
    for b in pack["builds_on"]:
        if not (root / b).exists():
            err(f"builds_on path {b!r} does not exist")

    # Dimensions and metrics -------------------------------------------------
    names: Dict[str, str] = {}
    for kind, items in (("dimension", pack["dimensions"]), ("metric", pack["metrics"])):
        for item in items:
            n = item.get("name", "")
            if not _ID_RE.match(n):
                err(f"{kind} name {n!r} must be lower_snake_case")
            if n in names:
                err(f"name {n!r} declared twice")
            names[n] = kind
    if not pack["metrics"]:
        err("a pack must declare at least one metric")

    vocab: Dict[str, str] = {}
    for item in list(pack["dimensions"]) + list(pack["metrics"]):
        for term in [item.get("name", "")] + list(item.get("synonyms", [])):
            key = term.strip().lower()
            if key in vocab and vocab[key] != item.get("name"):
                err(f"term {term!r} maps to both {vocab[key]!r} and {item.get('name')!r}")
            vocab[key] = item.get("name", "")

    metrics = {m["name"]: m for m in pack["metrics"] if "name" in m}
    for m in pack["metrics"]:
        unit, add = m.get("unit"), m.get("additivity")
        if unit not in UNITS:
            err(f"metric {m.get('name')!r}: unit {unit!r} not in {list(UNITS)}")
        if add not in ADDITIVITY:
            err(f"metric {m.get('name')!r}: additivity {add!r} not in {list(ADDITIVITY)}")
        if unit in RATE_LIKE_UNITS and add != "non_additive" and not m.get("additivity_rationale"):
            err(f"metric {m.get('name')!r}: rate-like unit {unit!r} declared {add!r} without an additivity_rationale")

    # Insight rules, caveats ------------------------------------------------
    for r in pack["insight_rules"]:
        pat = r.get("applies_to", "")
        if not _metric_matches(pat, metrics):
            err(f"insight rule {r.get('id')!r}: applies_to {pat!r} matches no metric")
        bad = [k for k in r.get("suppress_kinds", []) if k not in INSIGHT_KINDS]
        if bad or not r.get("suppress_kinds"):
            err(f"insight rule {r.get('id')!r}: suppress_kinds must be non-empty and within {list(INSIGHT_KINDS)}")
        if not r.get("reason"):
            err(f"insight rule {r.get('id')!r}: reason is required")
    for c in pack["caveats"]:
        trig = c.get("trigger", "")
        if not _TRIGGER_RE.match(trig):
            err(f"caveat {c.get('id')!r}: trigger {trig!r} must be always|metric:<name>|dimension:<name>")
        elif trig.startswith("metric:") and not _metric_matches(trig[7:], metrics):
            err(f"caveat {c.get('id')!r}: trigger metric {trig[7:]!r} not declared")
        elif trig.startswith("dimension:") and names.get(trig[10:]) != "dimension":
            err(f"caveat {c.get('id')!r}: trigger dimension {trig[10:]!r} not declared")
    for section in ("conventions", "chart_conventions"):
        ids = [x.get("id") for x in pack[section]]
        if len(ids) != len(set(ids)):
            err(f"{section} ids are not unique")
        if any(not x.get("rule") for x in pack[section]):
            err(f"{section}: every entry needs a rule")
    if not pack["conventions"]:
        err("a pack must state at least one convention")

    # Golden cases ----------------------------------------------------------
    if not pack["golden_cases"]:
        err("a pack must carry at least one golden case (REQ-008)")
    for g in pack["golden_cases"]:
        out.extend(_check_golden(pid, g, metrics))

    # Review ----------------------------------------------------------------
    rv = pack["review"]
    status = rv.get("status")
    if status not in REVIEW_STATUSES:
        err(f"review.status {status!r} not in {list(REVIEW_STATUSES)}")
    if status == "reviewed":
        if not rv.get("reviewer"):
            err("review.status is reviewed but no named reviewer is recorded (REQ-005)")
        if not _DATE_RE.match(str(rv.get("reviewed_on") or "")):
            err("review.status is reviewed but reviewed_on is not an ISO date (REQ-005)")
    return out


def _check_golden(pid: str, g: Mapping, metrics: Mapping[str, Mapping]) -> List[Finding]:
    gid = g.get("id", "<no id>")
    kind = g.get("kind")
    bad = lambda m: [Finding(pid, "error", f"golden case {gid!r}: {m}")]  # noqa: E731
    if kind not in GOLDEN_KINDS:
        return bad(f"kind {kind!r} not in {list(GOLDEN_KINDS)}")
    if kind == "bps_change":
        got = (g["to_pct"] - g["from_pct"]) * 100
        if not math.isclose(got, g["expected_bps"], abs_tol=TOLERANCE):
            return bad(f"{g['from_pct']}% -> {g['to_pct']}% is {got:.6f} bps, not {g['expected_bps']}")
    elif kind == "ratio":
        if g["denominator"] == 0:
            return bad("denominator is zero")
        got = g["numerator"] / g["denominator"] * g["scale"]
        if not math.isclose(got, g["expected"], abs_tol=TOLERANCE):
            return bad(f"{g['numerator']}/{g['denominator']}*{g['scale']} = {got:.6f}, not {g['expected']}")
    elif kind == "additivity":
        m = metrics.get(g.get("metric"))
        if m is None:
            return bad(f"metric {g.get('metric')!r} not declared")
        across = g.get("across")
        if across not in ("dimension", "time"):
            return bad(f"across must be dimension or time, not {across!r}")
        allowed = can_sum(m, across)
        if allowed != g.get("allowed"):
            return bad(f"{m['name']} is {m['additivity']}: summing across {across} is "
                       f"{'allowed' if allowed else 'not allowed'}, case says {g.get('allowed')}")
    return []


def validate_catalog(packs: Sequence[Mapping], root: str | Path = ".") -> List[Finding]:
    """Validate every pack plus catalog-level rules (REQ-002, REQ-009, REQ-010)."""
    out: List[Finding] = []
    seen: Dict[str, int] = {}
    for p in packs:
        out.extend(validate_pack(p, root, file_stem=p.get("pack_id")))
        seen[p.get("pack_id", "")] = seen.get(p.get("pack_id", ""), 0) + 1
    for pid, n in seen.items():
        if n > 1:
            out.append(Finding(pid, "error", "pack_id declared by more than one file"))
    families = {p.get("family") for p in packs}
    for fam in FAMILIES:
        if packs and fam not in families:
            out.append(Finding("<catalog>", "error", f"no pack covers family {fam!r} (REQ-002)"))
    readme = Path(root) / PACKS_DIR / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        for p in packs:
            if f"`{p.get('pack_id')}`" not in text:
                out.append(Finding(p.get("pack_id", ""), "error", "not listed in knowledge/analytics_packs/README.md"))
    elif packs:
        out.append(Finding("<catalog>", "error", "knowledge/analytics_packs/README.md is missing"))
    for dom in sorted(uncovered_source_domains(packs, root)):
        out.append(Finding("<catalog>", "info", f"source domain {dom!r} (sources/*.yml) selects no pack"))
    return out


# ---------------------------------------------------------------------------
# Semantics used by spec 0080
# ---------------------------------------------------------------------------


def can_sum(metric: Mapping, across: str) -> bool:
    """Whether a metric may be summed across ``dimension`` or ``time`` (REQ-003)."""
    dim_ok, time_ok = ADDITIVITY_RULES[metric["additivity"]]
    return dim_ok if across == "dimension" else time_ok


def suppressed_insights(pack: Mapping, metric_name: str) -> Tuple[str, ...]:
    """Insight kinds 0080 must not produce for ``metric_name`` under this pack.

    Derived rule first: a non-additive metric never gets a ``contributor``
    insight (contributions of a rate or quantile do not sum to its change).
    Declared insight rules add to that; they can only suppress, never enable.
    """
    kinds = set()
    metric = next((m for m in pack["metrics"] if m["name"] == metric_name), None)
    if metric is not None and metric["additivity"] == "non_additive":
        kinds.add("contributor")
    for r in pack["insight_rules"]:
        if fnmatch.fnmatchcase(metric_name, r["applies_to"]):
            kinds.update(r["suppress_kinds"])
    return tuple(k for k in INSIGHT_KINDS if k in kinds)


def is_reviewed(pack: Mapping) -> bool:
    return pack.get("review", {}).get("status") == "reviewed"


def select_packs(domains: Sequence[str], packs: Sequence[Mapping]) -> Selection:
    """Packs whose ``source_domains`` intersect a dataset's ``domain:`` tags (REQ-004).

    Order follows the pack list (sorted by file name), so selection is
    deterministic. Terms that map to different metrics in two selected packs
    are returned as conflicts; 0080 must ask a clarification rather than pick.
    """
    wanted = set(domains)
    chosen = [p for p in packs if wanted & set(p["source_domains"])]
    covered = set().union(*(set(p["source_domains"]) for p in chosen)) if chosen else set()
    owners: Dict[str, set] = {}
    for p in chosen:
        for item in p["metrics"]:
            for term in [item["name"]] + list(item.get("synonyms", [])):
                owners.setdefault(term.strip().lower(), set()).add(f"{p['pack_id']}.{item['name']}")
    conflicts = tuple(sorted((t, tuple(sorted(o))) for t, o in owners.items()
                             if len({x.split('.', 1)[1] for x in o}) > 1))
    return Selection(tuple(chosen), tuple(sorted(wanted - covered)), conflicts)


def source_domains_in_catalog(root: str | Path = ".") -> List[str]:
    """Every ``domain:`` tag declared in ``sources/*.yml`` (flow-list form)."""
    tags: set = set()
    for f in sorted((Path(root) / "sources").glob("*.yml")):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r'^domain:\s*\[(.*)\]\s*$', line)
            if m:
                tags.update(t.strip().strip('"\'') for t in m.group(1).split(",") if t.strip())
    return sorted(tags)


def uncovered_source_domains(packs: Sequence[Mapping], root: str | Path = ".") -> List[str]:
    """Source-catalog domain tags no pack selects (REQ-010 coverage report)."""
    covered = {d for p in packs for d in p.get("source_domains", [])}
    return [d for d in source_domains_in_catalog(root) if d not in covered]


def coverage_report(packs: Sequence[Mapping], root: str | Path = ".") -> Dict[str, object]:
    """Deterministic summary for the catalog README and handoff (REQ-010)."""
    by_family: Dict[str, List[str]] = {f: [] for f in FAMILIES}
    for p in packs:
        by_family.setdefault(p["family"], []).append(p["pack_id"])
    statuses: Dict[str, int] = {s: 0 for s in REVIEW_STATUSES}
    for p in packs:
        statuses[p["review"]["status"]] = statuses.get(p["review"]["status"], 0) + 1
    return {
        "pack_count": len(packs),
        "metric_count": sum(len(p["metrics"]) for p in packs),
        "by_family": {k: sorted(v) for k, v in by_family.items()},
        "review_status": statuses,
        "uncovered_source_domains": uncovered_source_domains(packs, root),
    }


# ---------------------------------------------------------------------------
# Review workflow (REQ-012)
# ---------------------------------------------------------------------------

# Named reviewer for each family, recorded when the owner took review on
# (2026-09-24). A pack may still be reviewed by someone else; this is the
# assignment, not a permission.
FAMILY_REVIEWERS: Dict[str, str] = {fam: "Joshua Lutkemuller, CFA" for fam in FAMILIES}


def review_sheet(packs: Sequence[Mapping], family: str) -> str:
    """A Markdown sheet for reviewing one family, pack by pack.

    Everything a reviewer must judge is on the sheet: each metric's unit and
    additivity (with what that permits), every convention, insight rule,
    caveat, and chart convention, and the golden cases. Deterministic: packs
    in file-name order, sections in contract order.
    """
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}; use one of {list(FAMILIES)}")
    chosen = [p for p in packs if p["family"] == family]
    yes_no = lambda b: "yes" if b else "no"  # noqa: E731
    lines = [f"# Review sheet — `{family}` ({len(chosen)} packs)", "",
             f"Assigned reviewer: {FAMILY_REVIEWERS.get(family, '—')}", "",
             "For each pack, check every line below. When a pack is right, mark it:", "",
             "```sh",
             "PYTHONPATH=src python3 -m quantsmith.pipelines.analytics_packs \\",
             "  --mark-reviewed <pack_id> --reviewer \"<your name>\" --date YYYY-MM-DD",
             "```", "",
             "To change content, edit `knowledge/analytics_packs/<pack_id>.json` first, then mark it.", ""]
    for p in chosen:
        rv = p["review"]
        lines += [f"## `{p['pack_id']}` — {p['name']}", "",
                  f"{p['description']}", "",
                  f"- Status: **{rv['status']}**" + (f" ({rv['reviewer']}, {rv['reviewed_on']})" if rv.get("reviewer") else ""),
                  f"- Selected by source domains: {', '.join(p['source_domains'])}",
                  f"- Reviewer agents: {', '.join(p['reviewer_agents'])}",
                  f"- Builds on: {', '.join(p['builds_on']) or '—'}", "",
                  "| Metric | Unit | Additivity | Sum across dims? | Sum across time? | Synonyms |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for m in p["metrics"]:
            add = m["additivity"] + (f" — {m['additivity_rationale']}" if m.get("additivity_rationale") else "")
            lines.append(f"| `{m['name']}` — {m['description']} | {m['unit']} | {add} | "
                         f"{yes_no(can_sum(m, 'dimension'))} | {yes_no(can_sum(m, 'time'))} | "
                         f"{', '.join(m['synonyms']) or '—'} |")
        lines += ["", "Dimensions: " + "; ".join(f"`{d['name']}` ({d['description']})" for d in p["dimensions"]), ""]
        for title, key, fmt in (
            ("Conventions", "conventions", lambda x: f"`{x['id']}` {x['rule']}"),
            ("Insight rules (suppress only)", "insight_rules",
             lambda x: f"`{x['id']}` on `{x['applies_to']}` suppress {', '.join(x['suppress_kinds'])} — {x['reason']}"),
            ("Caveats", "caveats", lambda x: f"`{x['id']}` [{x['trigger']}] {x['text']}"),
            ("Chart conventions", "chart_conventions", lambda x: f"`{x['id']}` {x['rule']}"),
            ("Golden cases (machine-checked)", "golden_cases", _describe_golden),
        ):
            lines.append(f"**{title}**")
            lines += [f"- [ ] {fmt(x)}" for x in p[key]] or ["- (none)"]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _describe_golden(g: Mapping) -> str:
    if g["kind"] == "bps_change":
        return f"`{g['id']}` {g['from_pct']}% → {g['to_pct']}% = {g['expected_bps']} bp"
    if g["kind"] == "ratio":
        return f"`{g['id']}` {g['numerator']} / {g['denominator']} × {g['scale']} = {g['expected']}"
    return f"`{g['id']}` `{g['metric']}` summed across {g['across']}: {'allowed' if g['allowed'] else 'not allowed'}"


def mark_reviewed(root: str | Path, pack_id: str, reviewer: str, reviewed_on: str,
                  notes: Optional[str] = None) -> dict:
    """Record a named review on one pack file (REQ-005, REQ-012).

    Refuses an empty reviewer, a non-ISO date, an unknown pack, or a pack that
    has any validation error — a review cannot certify a pack that does not
    validate. One pack per call, on purpose: a family is reviewed pack by pack.
    """
    reviewer = (reviewer or "").strip()
    if not reviewer:
        raise PackValidationError("a named reviewer is required")
    if not _DATE_RE.match(reviewed_on or ""):
        raise PackValidationError(f"reviewed_on {reviewed_on!r} is not an ISO date (YYYY-MM-DD)")
    path = Path(root) / PACKS_DIR / f"{pack_id}.json"
    if not path.is_file():
        raise PackValidationError(f"no pack named {pack_id!r}")
    pack = json.loads(path.read_text(encoding="utf-8"))
    pack["review"] = {
        "status": "reviewed",
        "reviewer": reviewer,
        "reviewed_on": reviewed_on,
        "notes": notes if notes is not None else "Conventions, rules, and golden cases confirmed by the named reviewer.",
    }
    errors = [f for f in validate_pack(pack, root, file_stem=pack_id) if f.severity == "error"]
    if errors:
        raise PackValidationError("; ".join(str(e) for e in errors))
    path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    return pack


def main(argv: Optional[Sequence[str]] = None) -> int:  # pragma: no cover - thin CLI
    import argparse

    ap = argparse.ArgumentParser(description="Validate and review analytics domain packs (spec 0081).")
    ap.add_argument("--root", default=".")
    ap.add_argument("--report", action="store_true", help="print the coverage report as JSON")
    ap.add_argument("--review-sheet", metavar="FAMILY", help="print a Markdown review sheet for one family")
    ap.add_argument("--mark-reviewed", metavar="PACK_ID", help="record a named review on one pack")
    ap.add_argument("--reviewer", help="reviewer name for --mark-reviewed")
    ap.add_argument("--date", help="review date (YYYY-MM-DD) for --mark-reviewed")
    ap.add_argument("--notes", help="optional review notes for --mark-reviewed")
    args = ap.parse_args(argv)
    if args.mark_reviewed:
        try:
            mark_reviewed(args.root, args.mark_reviewed, args.reviewer or "", args.date or "", args.notes)
        except PackValidationError as exc:
            print(f"refused: {exc}")
            return 1
        print(f"{args.mark_reviewed}: reviewed by {args.reviewer} on {args.date}")
        return 0
    packs = load_packs(args.root)
    if args.review_sheet:
        print(review_sheet(packs, args.review_sheet), end="")
        return 0
    findings = validate_catalog(packs, args.root)
    for f in findings:
        print(f)
    if args.report:
        print(json.dumps(coverage_report(packs, args.root), indent=2))
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
