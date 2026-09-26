# NL Analytics Tasks

## Answer A Natural-Language Question

Input: a question in plain language, the semantic layer, the viewer's clearance, and
an as-of period.

Output: a typed chat response — on `answered`, a validated plan echo, a chart
(handed to `data_visualization`), grounded insights, a caveated narrative, and
citations; otherwise a `clarification_needed`, `masked`, `empty`, or `stale` status
with a reason.

## Clarify An Ambiguous Or Unknown Question

Input: a question that names an unknown term or matches more than one metric
candidate.

Output: a `clarification_needed` response listing the candidates the question could
mean, with existence masking preserved for any candidate the viewer cannot see.

## Publish An Answer's Insight

Input: an answered question, a loaded `writeback_contract.md`, and (if required) an
approval decision.

Output: a dry-run preview by default, or — once approved — an idempotent, append-only
write-back record with a run id it can later be reversed by.

## Reverse A Published Insight

Input: a run id for a previously committed write-back record.

Output: a tombstoned reversal of that record, visible to `prior_insights` as-of the
reversal, never a hard delete.

## Emit An Audit Envelope For A Run

Input: an answered (or write-back) request where the caller has opted into envelope
emission (`envelope_dir`/`run_id`).

Output: a `0070` run envelope — prompt/context manifests, assumption ledger, and
audit events per stage — with any non-deterministic step (an LLM interpreter) marked
honestly rather than hidden, and a byte-identical replay for the same inputs.
