# Plan: Economists Agent Expansion

- **Spec:** 0033-economists-agents (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-10

## Approach

Reclaim `agents/economists/` (currently a stray, unwired placeholder) as a
real category folder with a group README plus seven four-file public
agents across four pillars (Indicators; Policy & Regime; Cross-Asset &
Scenario; Synthesis & Reporting). Add the backing instruction standard
`instructions/macro_economic_analysis.md` and one shared report template,
`templates/docs/macro_backdrop_report.md`. Update the agent catalog, spec
index, and top-level README so the group is discoverable and routable
alongside `trading_strategies/` and `portfolio_management/`.

## Architecture & Components

```text
sources/{fred,bls,bea,census,eia}.yml (0027)      # data foundation, already cataloged
  -> economists/macro_indicator_analyst            # indicator tracking, PIT/vintage
  -> economists/monetary_policy_analyst             # policy stance, rate path
       -> economists/macro_regime_classifier         # synthesizes into a regime label
            -> economists/cross_asset_macro_linkages   # regime -> cross-asset behavior
            -> economists/macro_scenario_analyst        # forward stress narratives
                 -> risk (stress testing), backtest_review
       -> economists/macro_backdrop_summarizer          # recurring brief (short cadence)
       -> economists/economic_outlook_report_writer      # periodic report (long cadence)
            -> trading_strategies/macro_multi_asset, portfolio_management/*,
               research_analyst (shared context at the start of a workflow)

Explicit non-duplication:
  economists/macro_regime_classifier  != monitoring/model_signal_monitoring
    (economic regime label            vs. a live model's regime-change detection)
  economists/cross_asset_macro_linkages != trading_strategies/macro_multi_asset
    (backdrop-to-market translation   vs. strategy design/sizing/review)
```

## Interfaces & Data Contracts

`templates/docs/macro_backdrop_report.md` is the one new schema: a shared
Markdown template with a `Cadence` field (`brief` | `outlook`) so
`macro_backdrop_summarizer` and `economic_outlook_report_writer` render the
same structure at different depth, rather than maintaining two templates
that would drift. All other agents produce free-form Markdown advisory
output, consistent with `asset_classes/`'s own precedent (no schema).

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P3 Point-in-time | yes | `macro_indicator_analyst`'s core job is vintage-aware indicator reads (first print vs. revised), backed by `instructions/point_in_time.md` and the already-shipped `instructions/data_ingestion.md`. |
| P10 Honest reporting | yes | Every agent flags an indicator/policy/forecast value absent from its input as a gap rather than inventing one, per `instructions/data_provenance.md`. |
| P4 Correct by construction | yes | Scope boundaries against `macro_multi_asset` and `model_signal_monitoring` prevent the group from making an unreviewed strategy or model-health call. |
| P5 Reversibility | yes | Docs/contracts-only change, isolated on a branch. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `agents/economists/README.md` | T-001 |
| REQ-002 | `agents/economists/{macro_indicator_analyst,monetary_policy_analyst,macro_regime_classifier,cross_asset_macro_linkages,macro_scenario_analyst,macro_backdrop_summarizer,economic_outlook_report_writer}/` | T-002 |
| REQ-003 | `instructions/macro_economic_analysis.md` | T-003 |
| REQ-004 | `templates/docs/macro_backdrop_report.md` | T-004 |
| REQ-005 | Named handoff in each agent's `instructions.md` | T-002 |
| REQ-006 | `agents/README.md`, `specs/README.md`, top-level `README.md` | T-005 |
| NFR-001 | Four-file contract + `Spec-Driven Role` per agent | T-002 |
| NFR-002 | Validation gates | T-006 |
| NFR-003 | "Never invent, flag as gap" operating rule per agent | T-002, T-003 |
| NFR-004 | Explicit boundary language against `macro_multi_asset`/`model_signal_monitoring` | T-001, T-002, T-003 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Reclaim vs. rename | Reuse the existing `agents/economists/` placeholder path | Create a new `agents/macro_research/` (or similar) group and leave the placeholder alone | The placeholder is unwired and contentless (a literal `"placeholder"` stub); reusing its path avoids two competing top-level groups for the same domain and matches the `sources/README.md` precedent from spec `0027`, where an equivalent stray stub was replaced outright rather than left alongside real content. |
| Roster size | Seven agents across four pillars | Fewer (e.g. 3-4, collapsing indicators/policy/regime into one agent) or more (e.g. per-region policy agents) | Seven mirrors this SDK's existing roster scale for a full category buildout (`asset_classes` = 5, a role_operations phase = 3-4) without collapsing genuinely distinct jobs (tracking a release vs. reading policy vs. classifying a regime) into one overloaded agent. |
| Report template | One shared template with a `Cadence` field | Two separate templates (`macro_brief.md`, `economic_outlook.md`) | The short brief and long outlook share the same underlying sections (regime read, indicator highlights, risks, watch list) at different depth; one template with a cadence field avoids the two copies drifting apart, the same reasoning already applied to `instructions/data_ingestion.md` replacing three duplicated agent-level copies (spec `0031`). |
| Runtime scope | Contracts, standard, and template only | Build an indicator-vintage runtime helper now | No concrete workflow yet needs one; matches `0022`'s own precedent of contracts-first, runtime only once a driving use case exists. |

## Validation Strategy

Run `hooks/stages/run-stage.sh spec agent-catalog docs-link spec-index`,
then the full `pytest tests/ -q` (expected unaffected — no runtime code in
this slice) and `git diff --check`. AC-001 is covered by direct inspection
of the group README. AC-002/AC-005 are covered by direct inspection of
each agent's `instructions.md`. AC-003/AC-004 are covered by direct
inspection of the new standard and template. AC-006 is covered by
`agent-catalog`/`spec-index`/`docs-link`. AC-007 is covered by the gate
run itself.

## Rollout, Observability & Rollback

Rollout is a branch commit (and push, if requested). Rollback is reverting
the single commit; no existing agent, gate, or template changes behavior
— `trading_strategies/macro_multi_asset` and `monitoring/
model_signal_monitoring` are unmodified. A future runtime spec can add an
indicator-vintage helper under `src/quantsmith/` once a concrete workflow
needs one, following the `0006`/`0007` pattern of promoting a
contract-only group into a tested runtime.

## Open Questions

- Does a per-region policy-agent variant become worth splitting out once
  this group sees real cross-region use, versus handling region as an
  input to the existing agents?
