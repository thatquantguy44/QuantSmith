# Synthetic Data Disclosure

- **Artifact:** `examples/visualization_packs/input.json` and the HTML, JSON,
  and Markdown produced by `quantsmith.visualization_packs demo`.
- **Author:** Joshua Lutkemuller, CFA
- **Last updated:** 2026-10-03
- **Reviewer / sign-off:** Pending human domain-content review; feature scope
  approval does not certify any demonstration values or domain conventions.

## Priority Check

Actual firm data was not supplied and would be inappropriate to commit in this
public SDK. Fixed synthetic fixtures verify arithmetic boundaries and rendering;
they are not observations about a company, market, economy, or investment.

| Location (section / chart / field) | What's synthetic | Why real data wasn't used | Generation method | Real-data follow-up |
| --- | --- | --- | --- | --- |
| Finance story: revenue and expense charts, executive findings, analyst evidence, and source labels | Every number, segment label, and period | No authorized firm dataset supplied | Explicit fixed values in `input.json`; no randomness | Replace through an authorized Reader and governed definitions. |
| Credit story: exposure chart, executive finding, analyst evidence, and source label | Every exposure, portfolio label, and period | No authorized credit dataset supplied | Explicit fixed values in `input.json`; no randomness | Use governed exposure snapshots with approved measurement bases. |
| Macro story: policy-rate chart, executive finding, analyst evidence, and release-vintage description | Every policy rate and period | No point-in-time source requested for this software example | Explicit fixed values in `input.json`; no randomness | Use a vintage-aware Reader with dated source provenance. |
| Refused PD sum case | The intentionally invalid PD definition and proposed row | Negative software test, not a data analysis | Fixed invalid definition in `example.py`; row is not executed | None; rejection is the expected behavior. |

Every usable example story displays a synthetic-data caveat. JSON and Markdown
carry the same source and disclosure. Unit-test fixtures are independently
synthetic and never presented as financial findings.
