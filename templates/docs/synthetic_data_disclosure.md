# Synthetic Data Disclosure

Companion report for `{artifact_name}`. Required whenever any data point,
figure, or visual in that artifact uses synthetic, simulated, sampled-as-if-real,
or otherwise non-actual data. See `instructions/data_provenance.md` for the
priority stack and standards this report enforces.

- **Artifact:** `{path or name of the report/dashboard/deliverable this discloses for}`
- **Author:**
- **Last updated:**
- **Reviewer / sign-off:**

## Priority Check

- [ ] Actual, sourced data was the first option considered for every item below.
- [ ] Each item below used synthetic data only because actual data was
      unavailable, restricted, or not yet collected — not for convenience.

## Disclosure Table

One row per location synthetic data appears. Do not summarize — list every
occurrence; a missing row is an undisclosed use.

| Location (section / chart / field) | What's synthetic | Why real data wasn't used | Generation method | Real-data follow-up |
| --- | --- | --- | --- | --- |
| `{e.g. "Fig. 3, borrow-rate series"}` | `{e.g. "all 30 tickers"}` | `{e.g. "no live feed in this environment"}` | `{e.g. "numpy.random.default_rng(seed=42), normal(rate_base, 5%)"}` | `{e.g. "swap for live feed before production"}` |

## Traceability

- Every non-synthetic data point or visual in `{artifact_name}` carries its
  own source citation (system/dataset name, as-of date) at the point of use —
  this report does not restate those; it exists only for what's synthetic.
- If the artifact is regenerated with real data replacing any row above,
  update or remove that row in the same change.

## Open Items

- `{none yet}`
