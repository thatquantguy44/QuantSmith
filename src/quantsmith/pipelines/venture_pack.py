"""Validation helpers for spec 0083's venture & non-traditional intelligence pack.

Validates the committed knowledge contracts under
``knowledge/venture_intelligence`` (referential integrity, governance
invariants, citation discipline) and runs the small golden-case operations
later runtimes must reproduce. It exposes no investment, scoring, screening, or
attribution API: nothing here decides anything about a company or a person.

Standard library only (NFR-001).
"""

from __future__ import annotations

from datetime import date
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

PACK_DIR = Path("knowledge/venture_intelligence")
FILES = ("taxonomy", "conventions", "channels", "models", "workflows",
         "coverage", "gaps", "glossary", "golden_cases")
SCHEMA_VERSION = "0083.1"

DECISION_CLASSES = {"analytic_support", "person_adjacent", "sovereign_adjacent"}
REQUIRED_CHANNELS = {"patents", "publications", "open_source", "hiring_labour",
                     "grants_procurement", "regulatory_filings", "trade_customs",
                     "web_app_telemetry", "narrative_news", "satellite_geospatial"}
REQUIRED_MODELS = {"entity_resolution", "round_progression", "technology_emergence",
                   "network_link", "funding_anomaly", "sector_nowcast", "fund_simulation"}
REQUIRED_WORKFLOWS = {"workflow.deal_to_memo", "workflow.signal_to_thesis",
                      "workflow.technology_landscape", "workflow.portfolio_fund_review",
                      "workflow.counter_diligence"}
REQUIRED_CONTRACTS = {"contract.survivorship", "contract.backfill",
                      "contract.reporting_lag", "contract.stealth_omission"}
CHANNEL_FIELDS = ("lead_time", "coverage", "biases", "deception_risks", "licensing", "point_in_time")
MODEL_FIELDS = ("target", "pit_feature_rule", "baseline", "validation", "failure_modes")
FACT_FIELDS = ("entity_id", "value", "unit", "source_id", "source_grade", "event_time",
               "announced_time", "filed_time", "ingested_time", "known_at", "language",
               "derived", "confidence")
MIN_CHILD_SPEC = 84
REVIEW_STATUSES = {"draft", "reviewed", "superseded", "retired"}
# Pack sections whose list records carry review_status / review (REQ-020).
REVIEWABLE = (("taxonomy", "entity_types"), ("taxonomy", "relationship_types"),
              ("channels", "channels"), ("models", "models"),
              ("workflows", "workflows"), ("glossary", "terms"))


class VenturePackError(ValueError):
    """Raised by ``validate_or_raise`` when the pack has errors."""


def load_pack(root: Path = Path(".")) -> Dict[str, Any]:
    pack: Dict[str, Any] = {}
    for name in FILES:
        pack[name] = json.loads((Path(root) / PACK_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return pack


# ---------------------------------------------------------------- operations
def post_money(pre_money: float, new_money: float) -> float:
    return pre_money + new_money


def new_ownership(pre_money: float, new_money: float) -> float:
    return new_money / post_money(pre_money, new_money)


def ownership_after(before: float, pre_money: float, new_money: float) -> float:
    """Existing holder's ownership after a round with no option-pool change."""
    return before * pre_money / post_money(pre_money, new_money)


def fund_metrics(paid_in: float, distributions: float, nav: float) -> Dict[str, float]:
    if paid_in <= 0:
        raise ValueError("paid_in must be positive")
    dpi, rvpi = distributions / paid_in, nav / paid_in
    return {"dpi": dpi, "rvpi": rvpi, "tvpi": dpi + rvpi}


def irr(cashflows: Sequence[Sequence[float]], lo: float = -0.99, hi: float = 10.0) -> float:
    """IRR by bisection; cashflows are (years_from_start, amount)."""
    def npv(r: float) -> float:
        return sum(a / (1.0 + r) ** t for t, a in cashflows)
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        raise ValueError("IRR not bracketed: cash flows need a sign change")
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def confidence_label(probability: float, bands: Sequence[Mapping[str, Any]]) -> str:
    for band in bands:
        if band["low"] <= probability < band["high"] or (
                probability == band["high"] == bands[-1]["high"]):
            return band["label"]
    raise ValueError(f"probability {probability} is outside the confidence bands")


def source_grade_valid(grade: str, conventions: Mapping[str, Any]) -> bool:
    sg = conventions["source_grade"]
    return (len(grade) == 2 and grade[0] in sg["reliability_scale"]
            and grade[1] in sg["credibility_scale"])


_UNIT_SYMBOLS = {"万": 10**4, "萬": 10**4, "亿": 10**8, "億": 10**8,
                 "만": 10**4, "억": 10**8, "조": 10**12}
_UNIT_WORDS = {"lakh": 10**5, "crore": 10**7}


def cn_number(text: str) -> float:
    """Parse a figure with an East or South Asian unit: 3.5亿, 2.5億, 350억, 1.2조, 5.2 lakh.

    Raises ``ValueError`` for an unknown or ambiguous unit (for example 兆),
    because a guessed multiplier is worse than a flagged one.
    """
    t = text.strip().replace(",", "").replace("，", "")
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([^0-9\s.]+)?", t)
    if not m:
        raise ValueError(f"cannot parse figure {text!r}; flag as ambiguous")
    number, unit = float(m.group(1)), m.group(2)
    if unit is None:
        mult = 1
    elif unit in _UNIT_SYMBOLS:
        mult = _UNIT_SYMBOLS[unit]
    elif unit.lower() in _UNIT_WORDS:
        mult = _UNIT_WORDS[unit.lower()]
    else:
        raise ValueError(f"unknown or ambiguous unit {unit!r} in {text!r}; flag, never guess")
    value = round(number * mult, 6)
    return int(value) if value == int(value) else value


def era_to_gregorian(era_id: str, year: int, conventions: Mapping[str, Any]) -> int:
    for rule in conventions["normalization"]["calendar_offsets"]:
        if rule["id"] == era_id:
            return year + rule["offset"]
    raise ValueError(f"unknown era {era_id!r}")


def buddhist_to_gregorian(year: int) -> int:
    return year - 543


def roc_to_gregorian(year: int) -> int:
    return year + 1911


def localized_number(text: str, locale: str, conventions: Mapping[str, Any]) -> float:
    for rule in conventions["normalization"]["number_locales"]:
        if locale in rule["locales"]:
            thousands = rule["thousands"]
            t = text.strip()
            if thousands == " ":
                t = re.sub(r"[\s\u00a0\u202f]", "", t)
            else:
                t = t.replace(thousands, "")
            t = t.replace(rule["decimal"], ".")
            value = float(t)
            return int(value) if value == int(value) else value
    raise ValueError(f"no number-locale rule for {locale!r}; flag as ambiguous")


def survivorship_rates(true_cohort: int, true_hits: int, db_listed: int, db_hits: int) -> Dict[str, float]:
    return {"biased_rate": db_hits / db_listed, "corrected_rate": true_hits / true_cohort}


def validate_fact_record(record: Mapping[str, Any]) -> List[str]:
    errors = [f"fact missing field: {f}" for f in FACT_FIELDS if f not in record]
    if "known_at" in record and not record["known_at"]:
        errors.append("fact has empty known_at")
    return errors


def validate_overlay(overlay: Mapping[str, Any], conventions: Mapping[str, Any]) -> List[str]:
    """An adopter-local overlay may never enable a prohibited source class."""
    prohibited = set(conventions["prohibited_source_classes"])
    enabled = set(overlay.get("enabled_source_classes", []))
    errors = [f"overlay enables prohibited source class: {c}" for c in sorted(enabled & prohibited)]
    for key in overlay:
        if re.search(r"(secret|password|token|api_key)", key, re.I) and overlay[key]:
            errors.append(f"overlay holds a secret-like value in {key!r}; use a credential reference")
    return errors


# ---------------------------------------------------------------- review
def reviewable_records(pack: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []
    for name, key in REVIEWABLE:
        out.extend(pack[name][key])
    conv = pack["conventions"]
    for key in ("valuation", "fund_metrics"):
        out.extend(conv[key])
    out.extend(conv["data_time"]["contracts"])
    norm = conv["normalization"]
    for key in ("numeral_units", "calendar_offsets", "number_locales"):
        out.extend(norm[key])
    return out


def validate_review(rec: Mapping[str, Any]) -> List[str]:
    """A record is `reviewed` only with a named reviewer, a date, and a scope."""
    rid, status = rec.get("id", "?"), rec.get("review_status")
    if status not in REVIEW_STATUSES:
        return [f"review: {rid} has invalid review_status {status!r}"]
    review = rec.get("review")
    if status == "draft":
        return [f"review: {rid} is draft but carries a review record"] if review else []
    if not isinstance(review, Mapping):
        return [f"review: {rid} is {status} without a review record"]
    errors = [f"review: {rid} review lacks {f}" for f in ("reviewer", "review_date", "scope")
              if not str(review.get(f, "")).strip()]
    try:
        date.fromisoformat(str(review.get("review_date", "")))
    except ValueError:
        errors.append(f"review: {rid} review_date is not an ISO date")
    if status == "reviewed" and str(rec.get("citation", "")).strip().lower() == "unverified" \
            and not review.get("accepts_unverified"):
        errors.append(f"review: {rid} is reviewed but still cites 'unverified' "
                      "(cite a source or set review.accepts_unverified)")
    return errors


def review_summary(pack: Mapping[str, Any]) -> Dict[str, int]:
    counts = {s: 0 for s in sorted(REVIEW_STATUSES)}
    unverified = 0
    for rec in reviewable_records(pack):
        counts[rec.get("review_status", "draft")] = counts.get(rec.get("review_status", "draft"), 0) + 1
        if str(rec.get("citation", "")).strip().lower() == "unverified":
            unverified += 1
    counts["total"] = sum(counts.values())
    counts["unverified_citations"] = unverified
    return counts


# ---------------------------------------------------------------- golden cases
def run_golden_cases(pack: Mapping[str, Any]) -> List[str]:
    conv, errors = pack["conventions"], []
    bands = conv["confidence_language"]["bands"]
    for case in pack["golden_cases"]["cases"]:
        k, exp, got = case["kind"], case["expect"], None
        try:
            if k == "post_money":
                got = {"post_money": post_money(case["pre_money"], case["new_money"]),
                       "new_ownership": new_ownership(case["pre_money"], case["new_money"]),
                       "existing_ownership_after": ownership_after(
                           case["existing_ownership_before"], case["pre_money"], case["new_money"])}
            elif k == "fund_metrics":
                got = fund_metrics(case["paid_in"], case["distributions"], case["nav"])
            elif k == "irr":
                got = {"irr": irr(case["cashflows"])}
            elif k == "confidence_label":
                got = {"label": confidence_label(case["probability"], bands)}
            elif k == "source_grade":
                got = {"valid": source_grade_valid(case["grade"], conv)}
            elif k == "cn_number":
                got = {"value": cn_number(case["text"])}
            elif k == "era_year":
                got = {"gregorian": era_to_gregorian(case["era"], case["year"], conv)}
            elif k == "buddhist_year":
                got = {"gregorian": buddhist_to_gregorian(case["year"])}
            elif k == "roc_year":
                got = {"gregorian": roc_to_gregorian(case["year"])}
            elif k == "localized_number":
                got = {"value": localized_number(case["text"], case["locale"], conv)}
            elif k == "survivorship":
                got = survivorship_rates(case["true_cohort"], case["true_reached_b"],
                                         case["db_listed"], case["db_reached_b"])
            elif k == "fact_record":
                got = {"valid": not validate_fact_record(case["record"])}
            else:
                errors.append(f"{case['id']}: unknown golden-case kind {k!r}")
                continue
        except ValueError as exc:
            errors.append(f"{case['id']}: raised {exc}")
            continue
        for key, want in exp.items():
            have = got[key]
            ok = (math.isclose(have, want, rel_tol=1e-9, abs_tol=1e-9)
                  if isinstance(want, float) and not isinstance(have, bool) else have == want)
            if not ok:
                errors.append(f"{case['id']}: {key} expected {want!r}, got {have!r}")
    return errors


# ---------------------------------------------------------------- validation
def _dupes(ids: Sequence[str]) -> List[str]:
    seen, dup = set(), []
    for i in ids:
        if i in seen:
            dup.append(i)
        seen.add(i)
    return dup


def _cited(rec: Mapping[str, Any]) -> bool:
    return bool(str(rec.get("citation", "")).strip())


def validate_pack(pack: Mapping[str, Any], root: Path = Path(".")) -> List[str]:
    root, errors = Path(root), []
    for name in FILES:
        if pack[name].get("schema_version") != SCHEMA_VERSION:
            errors.append(f"{name}: schema_version must be {SCHEMA_VERSION}")

    # taxonomy (REQ-002)
    tax = pack["taxonomy"]
    ent_ids = [e["id"] for e in tax["entity_types"]]
    errors += [f"taxonomy: duplicate id {d}" for d in _dupes(ent_ids)]
    for e in tax["entity_types"]:
        if not _cited(e):
            errors.append(f"taxonomy: {e['id']} lacks citation")
        if e["id"] != "entity.professional_role" and e.get("is_person_derived"):
            errors.append(f"taxonomy: {e['id']} models a person but is not the professional role")
    errors += [f"taxonomy: no entity type may be a person profile ({e['id']})"
               for e in tax["entity_types"] if "person" in e["id"] or "founder" in e["id"]]
    for r in tax["relationship_types"]:
        for end in ("from", "to"):
            if r[end] not in ent_ids:
                errors.append(f"taxonomy: {r['id']} {end} endpoint {r[end]} does not resolve")

    # conventions (REQ-003/004/005)
    conv = pack["conventions"]
    got = {c["id"] for c in conv["data_time"]["contracts"]}
    errors += [f"conventions: missing {c}" for c in sorted(REQUIRED_CONTRACTS - got)]
    for group in ("valuation", "fund_metrics"):
        for rec in conv[group]:
            if not _cited(rec):
                errors.append(f"conventions: {rec['id']} lacks citation")
    for f in ("known_at",):
        if f not in conv["data_time"]["fields"]:
            errors.append(f"conventions: data_time lacks {f}")
    if "known_at" not in conv["fact_record"]["required_fields"]:
        errors.append("conventions: fact_record must require known_at")
    bands = conv["confidence_language"]["bands"]
    for a, b in zip(bands, bands[1:]):
        if a["high"] != b["low"]:
            errors.append(f"conventions: confidence bands not contiguous at {a['label']}")
    if set(conv["analytic_product"]["required_sections"]) < {"Evidence", "Assumptions", "Judgement"}:
        errors.append("conventions: analytic product must separate evidence, assumptions, judgement")

    # channels (REQ-006)
    chans = pack["channels"]["channels"]
    errors += [f"channels: missing family {c}" for c in
               sorted(REQUIRED_CHANNELS - {c["id"].split(".", 1)[1] for c in chans})]
    for c in chans:
        errors += [f"channels: {c['id']} lacks {f}" for f in CHANNEL_FIELDS if not str(c.get(f, "")).strip()]
        if not _cited(c):
            errors.append(f"channels: {c['id']} lacks citation")

    # models (REQ-009)
    models = pack["models"]["models"]
    errors += [f"models: missing family {m}" for m in
               sorted(REQUIRED_MODELS - {m["id"].split(".", 1)[1] for m in models})]
    for m in models:
        errors += [f"models: {m['id']} lacks {f}" for f in MODEL_FIELDS if not str(m.get(f, "")).strip()]

    # coverage (REQ-008/016/019)
    cov = pack["coverage"]
    agents = cov["agents"]
    errors += [f"coverage: duplicate id {d}" for d in _dupes([a["id"] for a in agents])]
    wf = [a["workflow"].strip().lower() for a in agents]
    errors += [f"coverage: duplicate workflow {d!r}" for d in _dupes(wf)]
    spec_ids = {r["spec"] for r in cov["roadmap"]}
    for a in agents:
        if not a["never"].strip():
            errors.append(f"coverage: {a['id']} lacks a never-boundary")
        if a["creating_spec"] not in spec_ids:
            errors.append(f"coverage: {a['id']} creating_spec {a['creating_spec']} not in roadmap")
        if a["status"] == "built" and not (root / a.get("path", "") / "prompt.md").is_file():
            errors.append(f"coverage: built agent {a['id']} has no prompt.md at {a.get('path')}")
    agent_ids = {a["id"] for a in agents}
    closed: List[str] = []
    for r in cov["roadmap"]:
        if int(r["spec"]) < MIN_CHILD_SPEC:
            errors.append(f"roadmap: {r['spec']} precedes the first child spec")
        for c in r["closes"]:
            closed.append(c)
            if c not in agent_ids:
                errors.append(f"roadmap: {r['spec']} closes unknown agent {c}")
    errors += [f"roadmap: agent {a} closed by more than one spec" for a in _dupes(closed)]
    errors += [f"roadmap: agent {a} not closed by any spec" for a in sorted(agent_ids - set(closed))]

    # workflows (REQ-010/011/017)
    wfs = pack["workflows"]["workflows"]
    errors += [f"workflows: missing {w}" for w in sorted(REQUIRED_WORKFLOWS - {w["id"] for w in wfs})]
    for w in wfs:
        if w["decision_path_class"] not in DECISION_CLASSES:
            errors.append(f"workflows: {w['id']} has invalid class")
        if w["decision_path_class"] != "analytic_support":
            if not w["decision_support_only"]:
                errors.append(f"workflows: {w['id']} must be decision_support_only")
            if not w["human_review"]:
                errors.append(f"workflows: {w['id']} requires named human review")
        for ag in w["agents"]:
            if "(planned)" in ag:
                continue
            if not (root / "agents/venture_intelligence" / ag / "prompt.md").is_file():
                errors.append(f"workflows: {w['id']} names agent {ag} that does not exist")

    # workflow class must cover the strictest class among its agents
    by_key: Dict[str, str] = {}
    for a in agents:
        cls = a.get("decision_path_class", "analytic_support")
        by_key[a["id"]] = cls
        if a.get("path"):
            by_key[a["path"].replace("agents/venture_intelligence/", "")] = cls
    for w in wfs:
        classes = {by_key.get(ag.replace(" (planned)", "").strip()) for ag in w["agents"]}
        classes.discard(None)
        non_analytic = classes - {"analytic_support"}
        if non_analytic:
            need = "sovereign_adjacent" if "sovereign_adjacent" in non_analytic else "person_adjacent"
            if w["decision_path_class"] != need:
                errors.append(f"workflows: {w['id']} class {w['decision_path_class']} must be {need} "
                              "because it includes a stricter-class agent")

    # gaps (REQ-012)
    for g in pack["gaps"]["gaps"]:
        if g["severity"] not in ("low", "medium", "high"):
            errors.append(f"gaps: {g['id']} invalid severity")
        if g["owner_spec"] not in spec_ids:
            errors.append(f"gaps: {g['id']} owner_spec {g['owner_spec']} not in roadmap")

    # glossary (REQ-007)
    terms = pack["glossary"]["terms"]
    errors += [f"glossary: duplicate term {d}" for d in _dupes([t["term"].lower() for t in terms])]
    for t in terms:
        if not _cited(t):
            errors.append(f"glossary: {t['term']} lacks citation")
        if not (root / t["owner_doc"]).is_file():
            errors.append(f"glossary: {t['term']} owner_doc {t['owner_doc']} does not exist")

    # review sign-off (REQ-020)
    for rec in reviewable_records(pack):
        errors += validate_review(rec)

    # golden cases (REQ-012, AC-018)
    if pack["golden_cases"].get("synthetic") is not True:
        errors.append("golden_cases: must be flagged synthetic")
    errors += run_golden_cases(pack)
    return errors


def validate_or_raise(pack: Mapping[str, Any], root: Path = Path(".")) -> None:
    errors = validate_pack(pack, root)
    if errors:
        raise VenturePackError("; ".join(errors))


def main() -> int:  # pragma: no cover - thin CLI
    pack = load_pack()
    errors = validate_pack(pack)
    for e in errors:
        print("ERROR:", e)
    print("review:", ", ".join(f"{k}={v}" for k, v in review_summary(pack).items()))
    print(f"venture pack: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
