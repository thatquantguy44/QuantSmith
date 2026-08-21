# Run Card: <experiment / run name>

- **Run ID:**
- **Spec:** NNNN-short-slug (if applicable)
- **Author:**
- **Date:** YYYY-MM-DD
- **Status:** exploratory | candidate | archived

> A run card makes a result reproducible. Anyone with this card and the repo
> should be able to reproduce the numbers below. Reproducibility is a
> requirement, not a nicety (constitution P4).

## What Was Run

One or two sentences: the hypothesis, model, or job this run executed.

## Code Version

- Commit: `<git sha>`
- Branch / tag:
- Dirty working tree at run time? yes/no (if yes, why)

## Data Snapshot

- Source(s):
- Snapshot identifier / hash:
- Date range and frequency:
- Point-in-time / vintage notes:

## Configuration

- Config file / hash:
- Key parameters (only those that affect the result):
- Random seed(s):

## Environment

- Lockfile: `poetry.lock` | `requirements.txt` | `environment.yml` | …
- Python / runtime version:
- Hardware notes (if results are hardware-sensitive):

## Workflow Memory

- Memory version / snapshot used: (so the run is reproducible as memory evolves)
- Point-in-time scope applied to primed records: (research/backtest runs only)
- Memory proposed: (candidate id(s) this run staged to `memory/inbox/`, if any —
  see `specs/0049-workflow-memory-write-path/`; none proposed is a valid answer)

## Results

| Metric | Value | Notes |
| --- | --- | --- |
| … | … | … |

- Output artifact location:

## Reproduction

Exact command(s) to reproduce:

```sh
# e.g.
# python -m project.run --config configs/run.yaml --seed 42
```

## Notes & Caveats

- Known limitations, non-determinism sources, or follow-ups.
