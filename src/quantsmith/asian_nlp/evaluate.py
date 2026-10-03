"""Per-language evaluation for spec 0094.

Scores extractions against labelled cases and reports precision, recall, and
exact-match **per language and per extraction type**, always with the sample size.
``pooled_score`` refuses to publish one overall number while any language/type cell is
below ``min_n`` expected items, because a pooled figure would hide the weakest language.
Scores describe only the labelled (synthetic) cases they were computed on; they are not
a claim of general accuracy.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .extract import extract

MIN_CASES_PER_CELL = 6
DEFAULT_MIN_N = 6


class PooledScoreRefused(ValueError):
    """Raised when a pooled score would hide a language or type below the sample threshold."""


def _key(item: Mapping[str, Any]) -> Tuple[Any, ...]:
    value = item.get("value")
    return (item["type"], item["span"], json.dumps(value, sort_keys=True, ensure_ascii=False),
            item.get("currency"), bool(item.get("ambiguous")))


def score_case(case: Mapping[str, Any], predicted: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    exp = [_key(e) for e in case["expected"]]
    pred = [_key(p) for p in predicted]
    exp_left = list(exp)
    tp = 0
    for k in pred:
        if k in exp_left:
            exp_left.remove(k)
            tp += 1
    return {"tp": tp, "n_expected": len(exp), "n_predicted": len(pred), "exact": sorted(exp) == sorted(pred)}


def evaluate_cases(cases: Iterable[Mapping[str, Any]], predictions: Mapping[str, Sequence[Mapping[str, Any]]] = None
                   ) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Score ``cases``; ``predictions`` maps case id to items (computed with ``extract`` if omitted).

    Cases are grouped by their ``language`` and their extraction ``kind`` (``amount``,
    ``date``, ``era_year`` or ``fiscal_period``).
    """
    cells: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "n_expected": 0, "n_predicted": 0, "n_cases": 0, "exact_cases": 0})
    for case in cases:
        pred = predictions[case["id"]] if predictions is not None else extract(case["text"], case["language"])
        # Only items of the case's own kind are scored in its cell; cross-type extras are
        # still counted as predictions of their own type below.
        s = score_case(case, [p for p in pred if p["type"] == case["kind"]])
        cell = cells[(case["language"], case["kind"])]
        cell["tp"] += s["tp"]
        cell["n_expected"] += s["n_expected"]
        cell["n_predicted"] += s["n_predicted"]
        cell["n_cases"] += 1
        cell["exact_cases"] += 1 if s["exact"] else 0
    report: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for (lang, kind), c in sorted(cells.items()):
        report.setdefault(lang, {})[kind] = {
            "n_cases": c["n_cases"], "n_expected": c["n_expected"], "n_predicted": c["n_predicted"],
            "precision": (c["tp"] / c["n_predicted"]) if c["n_predicted"] else None,
            "recall": (c["tp"] / c["n_expected"]) if c["n_expected"] else None,
            "exact_match": c["exact_cases"] / c["n_cases"],
            "tp": c["tp"]}
    return report


def below_threshold(report: Mapping[str, Mapping[str, Mapping[str, Any]]], min_n: int = DEFAULT_MIN_N
                    ) -> List[Tuple[str, str, int]]:
    return [(lang, kind, cell["n_expected"]) for lang, kinds in report.items()
            for kind, cell in kinds.items() if cell["n_expected"] < min_n]


def pooled_score(report: Mapping[str, Mapping[str, Mapping[str, Any]]], min_n: int = DEFAULT_MIN_N) -> Dict[str, Any]:
    """One overall precision/recall, refused while any cell has fewer than ``min_n`` expected items."""
    low = below_threshold(report, min_n)
    if low:
        raise PooledScoreRefused(
            "pooled score refused; cells below n=%d: %s" % (min_n, ", ".join(f"{lang}/{kind} (n={n})" for lang, kind, n in low)))
    tp = sum(c["tp"] for kinds in report.values() for c in kinds.values())
    pred = sum(c["n_predicted"] for kinds in report.values() for c in kinds.values())
    exp = sum(c["n_expected"] for kinds in report.values() for c in kinds.values())
    return {"precision": tp / pred if pred else None, "recall": tp / exp if exp else None,
            "n_expected": exp, "note": "applies only to the labelled synthetic cases; see per-language report"}


def render_markdown(report: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> str:
    def f(v: Any) -> str:
        return "n/a" if v is None else f"{v:.3f}"
    rows = ["| Language | Type | Cases | Expected | Precision | Recall | Exact match |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for lang, kinds in report.items():
        for kind, c in kinds.items():
            rows.append(f"| {lang} | {kind} | {c['n_cases']} | {c['n_expected']} | {f(c['precision'])} | "
                        f"{f(c['recall'])} | {f(c['exact_match'])} |")
    return "\n".join(rows) + "\n"
