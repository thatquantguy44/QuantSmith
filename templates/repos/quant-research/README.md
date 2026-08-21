# Shape: quant-research

**For:** signal research, feature exploration, hypothesis testing. Many cheap
experiments, most of which fail.

**Not for:** anything sizing a real position. When a signal graduates, it moves
to a `quant-models` repo — that transition is the point of keeping them apart.

## Structure

```text
notebooks/     exploration; never imported by src/
experiments/   one dir per experiment, each with a run_card.md
data/          raw/ interim/ processed/ -- all gitignored
sources/       per-source registry (.yml): quality, point-in-time, cred pointer
src/research/  code that graduated out of a notebook
specs/         only for work that outlives one experiment
```

## Why these gates

`secret-scan`, `docs-link`, and `handoff-sync` **block**. `leakage`, `repro`,
and `data-provenance` are **advisory**, and `spec` is advisory too.

That last one is deliberate. Requiring a spec per experiment stops people
running experiments, and the whole value of this shape is cheap iteration. The
spec chain becomes blocking when a signal graduates.

Leakage stays advisory because it is heuristic and will false-positive on
exploratory code — but you want it *reported* on every run, because a research
repo's characteristic failure is a result that was never real.
