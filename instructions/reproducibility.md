# Reproducibility Standard

What constitution P4 ("reproducible by default") requires in practice, and
how the `repro` gate (`hooks/stages/repro-check.sh`) and
`templates/docs/run_card.md` check and capture it. This is the standard
behind the `implementation` and `testing_validation` lifecycle agents.

## Why This Standard

"It worked when I ran it" is not a result — it's an anecdote until someone
else (or the same person, months later) can reproduce it. Every other
correctness property in this SDK (leakage-free, point-in-time, honestly
reported) is worth little if the number behind it can't be regenerated from
a known input, config, and code version. P4 states reproducibility is a
requirement, not a nicety; this standard makes that concrete.

## What Reproducibility Requires

| Element | What "reproducible" means for it |
| --- | --- |
| Code | The exact commit/version is recorded; the working tree was clean at run time, or the dirty state is disclosed and explained. |
| Data | A snapshot identifier or content hash is recorded, not "whatever was live when it ran." See `instructions/data_ingestion.md`. |
| Configuration | Every parameter that affects the result is recorded — a config file/hash, not tribal knowledge of what flags were used. |
| Randomness | Every source of randomness is seeded and the seed is recorded; an unseeded run is not reproducible even with everything else pinned. |
| Environment | Dependencies are pinned (a lockfile), and the runtime/hardware is noted when results are hardware-sensitive. |
| Reproduction path | An exact command (or short sequence) exists that regenerates the result from the above — not a description of roughly how it was done. |

## Rules

1. **No hidden state.** A notebook cell run out of order, a global mutated
   between cells, or a value pulled from an untracked local file all break
   reproducibility even when the code "looks" reproducible.
2. **Pin, don't assume.** Data snapshot, config, dependencies, and random
   seed are each recorded explicitly; "it should be the same" is not a
   substitute for recording the actual value used.
3. **Record a run card for anything a decision depends on.** Use
   `templates/docs/run_card.md` for a result that informs a real decision
   (a promoted signal, a reported backtest, a governance artifact) — not
   for every throwaway exploratory run.
4. **A dirty working tree at run time is disclosed, not hidden.** The run
   card's `Dirty working tree at run time?` field exists because it
   happens; state it and why, rather than re-running clean just to look
   tidy and losing the actual provenance.
5. **State the gate's real limits honestly.** The `repro` gate is a
   heuristic, not a reproducibility verifier — see below. Do not treat a
   clean gate run as proof a result is actually reproducible; it only means
   the gate's narrow signals were present.

## What The `repro` Gate Actually Checks

Advisory by default (`QF_STAGE_ENFORCE=1` makes findings blocking). It
checks three narrow, deterministic signals, not the result itself:

- **A run manifest artifact** — a `run_card*.md`/`run_manifest*.md` file
  present somewhere in the repo (excluding `templates/`/`prompts/`
  scaffolding, so the template that *defines* a run card isn't mistaken
  for a real one).
- **A dependency lockfile** — any of `poetry.lock`, `uv.lock`,
  `Pipfile.lock`, `conda-lock.yml`, `requirements*.txt`,
  `environment.yml`.
- **Seeded randomness in changed code** — a heuristic grep over changed
  `.py`/`.ipynb` files: if a file uses randomness
  (`np.random`/`random.`/`torch.`/`tf.random`/`sample(`) but sets no seed
  (`seed(`/`random_state=`/`manual_seed(`), it's flagged.

This is honestly narrow: it cannot verify a result actually reproduces,
only that the *signals* of reproducibility (a manifest, a lockfile, a seed
call) are present — the same class of limitation the `leakage` and
`secret-scan` gates already disclose about themselves.

## Checklist

- [ ] Code version (commit, clean/dirty state) is recorded for any
      decision-informing run.
- [ ] Data is snapshotted (identifier/hash), not read as "latest."
- [ ] Configuration (all result-affecting parameters) is recorded.
- [ ] Randomness is seeded, and the seed is recorded.
- [ ] Dependencies are pinned via a lockfile.
- [ ] A run card (`templates/docs/run_card.md`) exists for any run a
      decision depends on, with an exact reproduction command.
- [ ] No hidden state: no out-of-order notebook execution, no untracked
      local inputs passed off as part of the pipeline.

## Runtime & Spec

- Gate: `hooks/stages/repro-check.sh` (`repro` in `run-stage.sh`).
- Template: `templates/docs/run_card.md`.
- Backs: `agents/implementation/` (the coding step's reproducibility rules)
  and `agents/testing_validation/` (verifying determinism as part of the
  definition of done).
- Related: `instructions/data_ingestion.md` (snapshot capture at the
  ingestion boundary), `instructions/model_development.md` (the run card in
  the modeling workflow specifically), `instructions/point_in_time.md`
  (a different, leakage-focused correctness property that reproducibility
  does not by itself guarantee).
