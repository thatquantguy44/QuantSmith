# Run Card: Venture intelligence pack validation

- **Run ID:** 0083-pack-validation-2026-10-03-r4 (supersedes r3, recorded at `ca508df`, r2 at `dab341c`, and the first run at `9477e9f`)
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
consistency, and recomputes every golden case; then the eight venture, Asian-language, and fund-analytics
test modules and the full repository test suite. This fourth run follows the `0092`
change, which added product-rule and retrieval-contract conventions, two built agents, workflow
entries, gap entries, and a fix for `None` being read as a name in the pack's sign-off checks. There is no model, no training, and no external
data in this run; it validates committed knowledge records and synthetic golden cases.

## Code Version

- Commit: `8f356e105a3b3ea46246097ff2979872908f9eb3`
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
  | `coverage.json` | `cf8c583cddfa` |
  | `gaps.json` | `9bee36fec8c5` |
  | `glossary.json` | `7e5bc6476aea` |
  | `golden_cases.json` | `32e6d1f35aeb` |
  | `models.json` | `f07557a6c5b9` |
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
| Records reviewed / draft | 0 / 210 | No record has named human review yet |
| Records citing `unverified` | 183 of 210 | Recorded honestly; not a failure |
| Golden cases recomputed | 24 | All match expected values |
| Venture, Asian-language, fund-analytics, and knowledge-integration test modules | 336 passed | nine modules, including 220 in `tests/test_asian_nlp.py`, 25 in `tests/test_venture_fund_analytics.py`, and 24 in `tests/test_venture_knowledge.py` |
| Full repository suite | 1129 passed | Python 3.11.17 (the 3.13.9 run of the earlier card also passed) |
| Validator output digest, two runs | `8feb9d24ac95` = `8feb9d24ac95` | Byte-identical output |

- Output artifact location: none written; results are printed to the terminal.

## Reproduction

Exact command(s) to reproduce:

```sh
uv sync --frozen --all-extras --python 3.11
PYTHONPATH=src .venv/bin/python -m quantsmith.pipelines.venture_pack
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_venture_pack.py tests/test_venture_ingestion.py tests/test_venture_regions.py \
  tests/test_venture_central_asia.py tests/test_venture_signals.py tests/test_venture_tradecraft.py \
  tests/test_asian_nlp.py tests/test_venture_fund_analytics.py tests/test_venture_knowledge.py -q
PYTHONPATH=src .venv/bin/python -m pytest -q
```

## Notes & Caveats

- "0 errors" means the pack is internally consistent, not that its content is
  correct. Every record is `draft` and 108 cite `unverified`; a named person must
  review them before any is relied on.
- This card covers the pack, its helpers, the `0094` baseline, and the `0091` fund
  analytics, and the `0092` retrieval reference and product validators. The baseline's scores apply only to the 240 synthetic cases and the fund
  functions are checked on synthetic flows with hand-computed answers; neither is a
  claim of accuracy on real documents or real funds. No live data adapter is built.
- If the pack files change, the hashes above change; re-run and record a new card.
