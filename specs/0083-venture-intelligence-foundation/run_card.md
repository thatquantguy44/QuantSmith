# Run Card: Venture intelligence pack validation

- **Run ID:** 0083-pack-validation-2026-10-03-r6 (supersedes r5, recorded at `0ba173c`, r4 at `8f356e1`, r3 at `ca508df`, r2 at `dab341c`, and the first run at `9477e9f`)
- **Spec:** 0083-venture-intelligence-foundation
- **Author:** Joshua Lutkemuller, CFA (accountable owner); executed in a Claude Code session
- **Date:** 2026-10-03
- **Status:** candidate

> A run card makes a result reproducible. Anyone with this card and the repo
> should be able to reproduce the numbers below. Reproducibility is a
> requirement, not a nicety (constitution P4).

## What Was Run

The standard-library validator for the `knowledge/venture_intelligence/` pack
(`quantsmith.pipelines.venture_pack`), which checks referential integrity,
decision-path class rules, citation discipline, review sign-off, workflow-class
consistency, and recomputes every golden case; then the eight venture, multilingual-NLP, and fund-analytics
test modules and the full repository test suite. This sixth run follows the `0096`
change, which added `routing.json` (request-routing rules), a validator block checking every routing
reference, the `venture_orchestrator` agent, and glossary and roadmap entries. There is no model, no training, and no external
data in this run; it validates committed knowledge records and synthetic golden cases.

## Code Version

- Commit: `02fea832f97c748f91d6cfa19a2e4e1630118756` (the `0096` commit after rebasing onto `main` at `06588e4`; tested before the rebase at `4a271f4` with identical content)
- Branch / tag: `claude/venture-intelligence-sea-0083`
- Dirty working tree at run time? no. This card is committed after the run; it does
  not change any validated file.

## Data Snapshot

- Source(s): the pack's own JSON files in `knowledge/venture_intelligence/`; the 24
  golden cases are synthetic (disclosed in `golden_cases.json` per spec `0025`).
  No external or real data.
- Snapshot identifier / hash (SHA-256, first 12 characters):

  | File | Hash |
  | --- | --- |
  | `channels.json` | `196fc2889a67` |
  | `conventions.json` | `b481ff974f8f` |
  | `coverage.json` | `5f99ec3563c2` |
  | `gaps.json` | `3b6b8e1796d1` |
  | `glossary.json` | `cf4033077fdc` |
  | `golden_cases.json` | `32e6d1f35aeb` |
  | `routing.json` | `ee0e0ee2b019` |
  | `models.json` | `1c6ed93a0168` |
  | `taxonomy.json` | `47bea5b30d2f` |
  | `workflows.json` | `a1677faa793f` |
  | `asian_nlp/fixtures/extraction_cases.json` | `57a9da51cf22` |
  | `asian_nlp/fixtures/identification_cases.json` | `b2040ff4ed19` |

- Date range and frequency: not applicable (no time series).
- Point-in-time / vintage notes: not applicable to this run; the pack itself defines
  the `known_at` rules that later data runs must follow.

## Configuration

- Config file / hash: none; the validator takes no configuration.
- Key parameters (only those that affect the result): none.
- Random seed(s): none. The run is fully deterministic (no randomness is used).

## Environment

- Lockfile: `uv.lock` (SHA-256 `dc2ce2f3025b9611…`)
- Python / runtime version: CPython 3.11.17 (the CI version) for the recorded results;
  the full suite also passed on CPython 3.13.9 (802 tests). `uv` 0.12.22.
- Hardware notes (if results are hardware-sensitive): not sensitive; run on an Apple
  silicon laptop (aarch64, macOS).

## Workflow Memory

- Memory version / snapshot used: none read.
- Point-in-time scope applied to primed records: not applicable.
- Memory proposed: none.

## Results

| Metric | Value | Notes |
| --- | --- | --- |
| Validator errors | 0 | `venture pack: 0 error(s)` |
| Records reviewed / draft | 0 / 239 | No record has named human review yet |
| Records citing `unverified` | 212 of 239 | Recorded honestly; not a failure |
| Golden cases recomputed | 24 | All match expected values |
| Venture-family test modules | 408 passed | eleven modules, including 39 in `tests/test_venture_routing.py` |
| Full repository suite | 1201 passed | Python 3.11.17 (the 3.13.9 run of the earlier card also passed) |
| Validator output digest, two runs | `fcc4fa0aa0af` = `fcc4fa0aa0af` | Byte-identical output |

- Output artifact location: none written; results are printed to the terminal.

## Reproduction

Exact command(s) to reproduce:

```sh
uv sync --frozen --all-extras --python 3.11
PYTHONPATH=src .venv/bin/python -m quantsmith.pipelines.venture_pack
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_venture_pack.py tests/test_venture_ingestion.py tests/test_venture_regions.py \
  tests/test_venture_signals.py tests/test_venture_tradecraft.py \
  tests/test_asian_nlp.py tests/test_venture_fund_analytics.py tests/test_venture_knowledge.py tests/test_venture_models.py tests/test_venture_routing.py -q
PYTHONPATH=src .venv/bin/python -m pytest -q
```

## Notes & Caveats

- "0 errors" means the pack is internally consistent, not that its content is
  correct. Every record is `draft` and 108 cite `unverified`; a named person must
  review them before any is relied on.
- This card covers the pack, its helpers, the `0094` baseline, and the `0091` fund
  analytics, the `0092` retrieval reference and product validators, and the `0095` predictive-model baselines. The
  `0095` baselines are validated on synthetic data only and the catalog marks every model not usable for
  decisions. The baseline's scores apply only to the 240 synthetic cases and the fund
  functions are checked on synthetic flows with hand-computed answers; neither is a
  claim of accuracy on real documents or real funds. No live data adapter is built.
- If the pack files change, the hashes above change; re-run and record a new card.
