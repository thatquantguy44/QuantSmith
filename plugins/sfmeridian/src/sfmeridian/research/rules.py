"""Securities-finance rule pack, keyed by dataset kind.

Spec ``0121`` REQ-008. Each rule is declarative: a violation predicate and an
applicability predicate (rows whose inputs are present), pushed down as one
exact count. Rules refer to *logical* column names; the research context's
``column_map`` maps them to physical names, and a rule whose columns are not
in the dataset is ``skipped`` with that reason.

Thresholds are never assumed. A rule that needs a threshold the context does
not supply is skipped and says which threshold is missing. Each rule cites
the convention it encodes (``0063`` short-term-markets pack, ``0066``
securities-lending corrections) or says it is adopter-configurable.

Violations are observations about the filtered population. A violation of a
mechanic (on-loan above lendable) is a ``blocker``; a breach of an
adopter-supplied band or margin is ``material``. Neither is a repair.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .templates import Predicate as P

__all__ = ["RULES", "Rule", "rules_for"]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    kinds: tuple[str, ...]
    title: str
    columns: tuple[str, ...]                   # logical names
    severity: str                              # blocker | material
    convention: str
    thresholds: tuple[str, ...]
    build: Callable[[Callable[[str], str], dict[str, Any], Any], tuple[P, P]]
    viewpoints: tuple[str, ...] = ()           # empty: any viewpoint


def _present(col: Callable[[str], str], *names: str) -> P:
    return P("all", parts=[P("not_null", column=col(n)) for n in names])


def _range_rule(rule_id, kinds, title, column, op, value, severity, convention, viewpoints=()):
    return Rule(rule_id, kinds, title, (column,), severity, convention, (),
                lambda c, t, ctx: (P("cmp_value", column=c(column), op=op, value=value), _present(c, column)),
                viewpoints)


def _fee_band(c, t, ctx):
    band = t["fee_band_bps"]
    return (P("any", parts=[P("cmp_value", column=c("fee_bps"), op="<", value=band["min"]),
                            P("cmp_value", column=c("fee_bps"), op=">", value=band["max"])]),
            _present(c, "fee_bps"))


def _status(c, t, ctx):
    return P("not_in", column=c("status"), values=list(t["status_values"])), _present(c, "status")


def _category(c, t, ctx):
    th = t["category_thresholds_bps"]
    labels = {"gc": "GC", "warm": "WARM", "htb": "HTB", **(t.get("category_labels") or {})}
    fee, cat = c("fee_bps"), c("borrow_category")
    return (P("any", parts=[
        P("all", parts=[P("cmp_value", column=fee, op="<=", value=th["gc_max_bps"]),
                        P("cmp_value", column=cat, op="<>", value=labels["gc"])]),
        P("all", parts=[P("cmp_value", column=fee, op=">", value=th["gc_max_bps"]),
                        P("cmp_value", column=fee, op="<=", value=th["warm_max_bps"]),
                        P("cmp_value", column=cat, op="<>", value=labels["warm"])]),
        P("all", parts=[P("cmp_value", column=fee, op=">", value=th["warm_max_bps"]),
                        P("cmp_value", column=cat, op="<>", value=labels["htb"])]),
    ]), _present(c, "fee_bps", "borrow_category"))


def _margin(c, t, ctx):
    return (P("cmp_scaled", column=c("collateral_value"), op="<", other=c("on_loan_value"),
              value=t["collateral_margin"]), _present(c, "collateral_value", "on_loan_value"))


def _accrual(c, t, ctx):
    return (P("abs_diff_gt", column=c("fee_income"), other=c("on_loan_value"), third=c("fee_bps"),
              value=t["accrual_tolerance"]), _present(c, "fee_income", "on_loan_value", "fee_bps"))


def _split(c, t, ctx):
    return (P("any", parts=[P("cmp_value", column=c("owner_split"), op="<", value=0),
                            P("cmp_value", column=c("owner_split"), op=">", value=1)]), _present(c, "owner_split"))


def _on_loan_le_lendable(c, t, ctx):
    return (P("cmp_column", column=c("on_loan_qty"), op=">", other=c("lendable_qty")),
            _present(c, "on_loan_qty", "lendable_qty"))


RULES: list[Rule] = [
    _range_rule("lb.quantity_positive", ("loan_book",), "Loan quantity is positive", "quantity", "<=", 0,
                "blocker", "0063 securities-lending lifecycle: an open loan has a positive quantity"),
    _range_rule("lb.on_loan_value_nonnegative", ("loan_book", "collateral", "program_revenue"),
                "On-loan value is non-negative", "on_loan_value", "<", 0, "blocker",
                "0063 conventions: market value on loan is a non-negative amount"),
    _range_rule("lb.lender_fee_nonnegative", ("loan_book", "borrow_rates", "program_revenue"),
                "Lending fee is non-negative from the lender viewpoint", "fee_bps", "<", 0, "material",
                "0063 viewpoints: the lender receives the fee (negative only via rebate, a separate field)",
                ("lender", "beneficial_owner", "agent")),
    Rule("lb.fee_within_band", ("loan_book", "borrow_rates"), "Fee within the adopter's band", ("fee_bps",),
         "material", "adopter-configurable band (no universal fee limit)", ("fee_band_bps",), _fee_band),
    Rule("lb.status_enumerated", ("loan_book", "recalls"), "Status is one of the adopter's lifecycle states",
         ("status",), "material", "adopter-configurable; 0063 lifecycles name the states", ("status_values",),
         _status),
    Rule("li.on_loan_le_lendable", ("lendable_inventory",), "On-loan quantity does not exceed lendable quantity",
         ("on_loan_qty", "lendable_qty"), "blocker",
         "0063 utilization = on-loan / lendable, bounded by 1", (), _on_loan_le_lendable),
    _range_rule("li.lendable_nonnegative", ("lendable_inventory",), "Lendable quantity is non-negative",
                "lendable_qty", "<", 0, "blocker", "0063 inventory: lendable quantity is non-negative"),
    Rule("br.category_consistent", ("borrow_rates",), "Borrow category agrees with the fee thresholds",
         ("fee_bps", "borrow_category"), "material",
         "0066 configurable GC/WARM/HTB thresholds (labels configurable)", ("category_thresholds_bps",), _category),
    Rule("cl.coverage_at_margin", ("collateral",), "Collateral covers on-loan value at the required margin",
         ("collateral_value", "on_loan_value"), "material",
         "adopter-configurable margin (agreement-specific; 0063 haircut/margin vocabulary)",
         ("collateral_margin",), _margin),
    Rule("pr.owner_split_unit_interval", ("program_revenue",), "Beneficial-owner split is between 0 and 1",
         ("owner_split",), "blocker", "0063 roles: a revenue split is a fraction", (), _split),
    Rule("pr.accrual_act360", ("program_revenue",), "Daily fee income reconciles to value × fee / 10,000 / 360",
         ("fee_income", "on_loan_value", "fee_bps"), "material",
         "0066 ACT/360 daily accrual for fees and rebates", ("accrual_tolerance",), _accrual),
    _range_rule("rc.recall_qty_positive", ("recalls",), "Recall quantity is positive", "recall_qty", "<=", 0,
                "blocker", "0063 recall lifecycle: a recall names a positive quantity"),
]


def rules_for(kind: str) -> list[Rule]:
    return [r for r in RULES if kind in r.kinds]


def plan_rule(rule: Rule, context: Any, columns: Sequence[str]) -> tuple[tuple[P, P] | None, str | None]:
    """Build a rule's predicates for this dataset, or say why it is skipped."""
    physical = {c: context.column(c) for c in rule.columns}
    missing = [f"{c}→{p}" if p != c else c for c, p in physical.items() if p not in columns]
    if missing:
        return None, f"column(s) not in the dataset: {', '.join(missing)}"
    for name in rule.thresholds:
        if context.thresholds.get(name) in (None, {}, []):
            return None, f"threshold {name!r} not supplied in the research context"
    if rule.viewpoints and context.viewpoint not in rule.viewpoints:
        return None, (f"applies to the {'/'.join(rule.viewpoints)} viewpoint; context viewpoint is "
                      f"{context.viewpoint or 'not stated'}")
    return rule.build(context.column, context.thresholds, context), None
