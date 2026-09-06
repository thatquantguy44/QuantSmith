# Short-Term Markets Gap Register

This register is the required 0063 disposition log for current short-term
markets weaknesses. A row is not evidence of a runtime fix; it is evidence that
the issue is visible, scoped, and owned.

| ID | Gap | Evidence | Severity | Disposition | Owning spec |
| --- | --- | --- | --- | --- | --- |
| D-0063-001 | Repo-special versus stock-loan-special sign and viewpoint ambiguity. | `instructions/securities_financing.md` currently says to distinguish GC from specials in both stock loan and repo without a role/sign conversion; `agents/securities_financing/repo_financing/instructions.md` asks for GC vs specials but does not define the repo-rate axis; `agents/securities_financing/securities_lending/instructions.md` treats specials through the higher borrow-cost lens. | high | Corrected at the 0063 contract layer by `concept.repo_special`, `concept.stock_loan_special`, `convention.repo.specialness_bps`, and `golden.repo.specialness_sign`. No existing runtime output changed. | 0064 for repo runtime compatibility; 0066 for securities-lending compatibility |
| D-0063-002 | Hard-coded securities-lending GC/WARM/HTB classification cutoffs can look like universal market rules. | `src/quantsmith/quant/agentic_quant/sec_lending.py:103` and `:104` define `_GC_THRESHOLD = 50` and `_WARM_THRESHOLD = 200`; `_classify()` applies them globally. | high | Recorded as `convention.seclend.demo_classification_thresholds`, a draft parameterized model assumption, not sourced market truth. No runtime behavior changed under 0063. | 0066 |
| D-0063-003 | Mixed accrual bases: existing securities-lending runtime uses ACT/252-style daily fee approximations while financing-cost analysis uses ACT/360. | `src/quantsmith/quant/agentic_quant/sec_lending.py:258`, `:427`, and `:589` divide fee calculations/annualization by 252; `src/quantsmith/pipelines/financing_cost_analysis.py:40` sets `_DAY_COUNT_BASIS = 360.0` and `:118` uses it for all legs. | high | 0063 registers ACT/360 conventions and golden cases, and records the existing ACT/252 assumptions as incompatible unless explicitly declared. No runtime behavior changed. | 0066, with product-specific extensions from 0064 and 0065 where needed |
| D-0063-004 | Securities-lending allocation declares counterparty concentration but does not enforce it inside the optimizer. | `src/quantsmith/quant/agentic_quant/sec_lending.py:380` through `:390` document a counterparty constraint, but `_optimize()` builds only a balance-sheet `A_ub` at `:435` through `:437`; risk concentration is checked later at `:528` through `:565`. | medium | Kept as a visible compatibility gap. 0063 lifecycle/coverage names the counterparty and collateral states, but allocation correction is out of scope. | 0066 |
| D-0063-005 | Financing-cost point-in-time check can miss rates learned during a holding period and applied retroactively to earlier days. | `src/quantsmith/pipelines/financing_cost_analysis.py:235` through `:245` flags only a `rate_asof` after `period_end`; a rate known after `period_start` but before `period_end` can still be applied to the whole period by the caller. | high | 0063 adds dual-time semantics and `golden.temporal.asof_excludes_later_known_rate`; segmenting financing legs or requiring rate windows is deferred. | 0066 |
| D-0063-006 | Financing-cost analysis uses fixed notional and one universal day-count basis for every leg. | `src/quantsmith/pipelines/financing_cost_analysis.py:78` through `:84` define one notional and period per position; `:40` and `:118` apply ACT/360 to every leg. | medium | 0063 makes notional, day count, settlement, and convention IDs explicit in the domain contract. Variable notional, product-specific day count, and cashflow scheduling stay out of this spec. | 0064, 0065, and 0066 |

## Review Notes

- All six mandatory discrepancies from REQ-012 are retained here.
- No issue above is represented as runtime-corrected unless the affected runtime
  and tests change in a later spec.
- Records affected by unresolved severity-high gaps must remain `draft` until
  the owning spec supplies implementation and validation evidence, or a named
  reviewer explicitly scopes the record around the gap.
