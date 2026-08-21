# Agentic Dictionary

This dictionary defines the core terms used by QuantSmith. The goal is to make agentic quant workflows easier to discuss, document, review, and automate.

## Agent

A durable role definition for an AI assistant or automation worker. An agent should have a clear purpose, scope, inputs, outputs, and behavioral rules.

Example: A Backtest Review Agent reviews a strategy simulation for lookahead bias, transaction cost assumptions, benchmark selection, fragility, and reproducibility.

## Agent Catalog

The set of available agents in the SDK. In this repository, the public catalog should live under `agents/`.

## Agent Prompt

The role prompt that tells an agent what it is, what it should optimize for, and what kind of work it should perform.

Recommended file: `prompt.md`.

## Agent Instructions

Rules and standards an agent must follow. Instructions should be more durable than one-off prompts.

Recommended file: `instructions.md`.

## Agent Tasks

A catalog of common requests an agent can handle, usually paired with expected output artifacts.

Recommended file: `tasks.md`.

## Agent Runtime

The system that executes or applies agent definitions. This may be a local coding assistant, a chat interface, a workflow engine, a CI job, or a future SDK CLI.

## Agentic Workflow

A multi-step workflow where agents, prompts, hooks, templates, and human review combine to produce a reliable artifact.

Example: hypothesis -> research plan -> data quality review -> model experiment -> backtest review -> risk review -> handoff memo.

## Hook

A local or remote automation checkpoint that runs before or after a workflow event. Git hooks are common examples.

Examples: `pre-commit`, `commit-msg`, `pre-push`, documentation freshness checks, notebook output checks, secret checks.

## Guardrail

A lightweight rule that prevents common mistakes or forces important risks into view. Good guardrails help reviewers without blocking legitimate exploration unnecessarily.

## Adapter

The boundary between an agent's decision and a provider-specific action. Agents decide what happened and what should be produced; adapters translate an already-approved payload into sending an email, posting to Slack, scheduling a job, writing an artifact, querying a warehouse, or invoking a model runtime. Adapters never decide severity, ownership, or workflow completion, and never own secrets directly.

Recommended location: `adapters/<group>/`. See `adapters/README.md` for the catalog and design rules.

## Instruction

A reusable standard or operating procedure for agents and humans.

Example: `instructions/backtesting.md` could define required checks for time alignment, benchmark choice, costs, slippage, and fragility.

## Prompt

A task-specific request template. Prompts should define the input context, expected output, review criteria, and assumptions to surface.

Example: "Draft a model card for this forecasting model using the attached experiment summary and validation results."

## Template

A reusable artifact structure. Templates are useful when outputs need consistency across teams.

Examples: research memo, model card, dataset card, experiment report, backtest report, production readiness checklist.

## Workflow Artifact

Any durable output created during research or model development.

Examples: research plan, notebook, feature spec, experiment summary, model card, dataset card, backtest review, PR, handoff memo.

## Handoff

A document that lets another qualified person continue work without reconstructing context from scratch. A good handoff states goals, current state, decisions, assumptions, risks, next steps, and validation status.

## Research Memo

A structured document that explains a hypothesis, motivation, data, method, results, limitations, decision, and next steps.

## Dataset Card

A document that describes a dataset's source, coverage, schema, lineage, refresh schedule, missingness, known caveats, permissions, and intended uses.

## Model Card

A document that describes a model's purpose, inputs, outputs, training data, methodology, validation results, limitations, risks, monitoring needs, and owner.

## Experiment Summary

A concise record of an experiment's goal, configuration, data window, code version, metrics, results, observations, and follow-up decisions.

## Backtest Report

A structured review of a strategy simulation, including assumptions, data windows, benchmarks, costs, slippage, constraints, performance, risk, robustness, and known weaknesses.

## Production Readiness Checklist

A checklist used before a model, signal, strategy, or data pipeline is promoted into a production-like workflow.

## Lineage

The documented path from raw data to derived artifact. In quant workflows, lineage should explain sources, transformations, joins, filters, time alignment, and versioning.

## Time Alignment

The discipline of ensuring every feature, label, signal, and decision uses only information that would have been available at the relevant time.

## Leakage

Any use of information during training, validation, or backtesting that would not have been available in a real decision setting.

## Lookahead Bias

A form of leakage where future information accidentally influences past decisions in research, modeling, or backtesting.

## Survivorship Bias

Bias caused by excluding entities that disappeared, failed, delisted, or otherwise left the dataset before the analysis period ended.

## Overfitting

When a model, signal, or strategy fits noise or idiosyncrasies in the development sample rather than a durable relationship.

## Data Snooping

Repeated testing or selection over many ideas, features, periods, or configurations without accounting for the search process.

## Transaction Costs

Costs incurred to trade or rebalance a strategy. These may include commissions, fees, bid-ask spread, market impact, borrow cost, and financing.

## Slippage

The difference between assumed execution price and realized or plausible execution price.

## Benchmark

The reference used to judge performance. A benchmark should match the strategy's opportunity set, constraints, and risk profile as closely as practical.

## Robustness Check

An analysis that tests whether a result survives reasonable changes to assumptions, windows, costs, universe definitions, model parameters, or evaluation metrics.

## Stress Test

An analysis of behavior under adverse market, data, or operational conditions.

## Risk Review

A review of exposures, concentration, volatility, drawdown, liquidity, scenario behavior, capacity, and operational risk.

## Reproducibility

The ability to recreate an artifact from documented code, data versions, configuration, environment, and commands.

## Decision Log

A durable record of material decisions, alternatives considered, rationale, and consequences.

## Review Contract

The expected checks and outputs for a review step. Review contracts make agent output easier to verify.

Example: A Data Quality Agent must report data sources, row counts, date ranges, missingness, joins, timestamp assumptions, and leakage risks.

## Acceptance Criteria

The conditions that must be true before a task or artifact is considered complete.

## Human In The Loop

A workflow design where agents assist, draft, validate, or summarize, but important judgment calls remain visible to a human owner or reviewer.

## SDK Surface

A public area of the SDK that downstream users are expected to rely on. For this repository, the main surfaces are `agents/`, `hooks/`, `instructions/`, `prompts/`, `specs/`, `templates/`, and `docs/`, with `CLAUDE.md` activating the framework by default.

## Seed Template

An existing file that demonstrates a useful structure but is not yet final content. Seed templates are useful starting points, but they should be promoted into public SDK surfaces only after their purpose, inputs, outputs, and review contract are clear.

# Spec-Driven Development Vocabulary

## Spec-Driven Development (SDD)

The SDK's operating model: the specification is the source of truth, and every design decision, task, test, and release traces back to it. The flow is `Constitution → Specify → Plan → Tasks → Implement → Verify → Operate`. See `instructions/spec_driven_development.md`.

## Constitution

The non-negotiable engineering principles every change is checked against, defined in `instructions/engineering_principles.md` (P1–P10). Deviations require a recorded, approved exception.

## Spec / Plan / Tasks

The three per-feature artifacts under `specs/NNNN-slug/`: `spec.md` (WHAT and WHY — requirements and acceptance criteria), `plan.md` (HOW — architecture, data contracts, trade-offs), and `tasks.md` (ordered, traceable work). Templates live in `templates/spec/`.

## Identifier Scheme (REQ / NFR / AC / RISK / T)

Stable IDs that make traceability mechanical: `REQ-*` functional requirement, `NFR-*` non-functional requirement, `AC-*` acceptance criterion, `RISK-*` risk, `T-*` task. Once assigned, an ID is never reused.

## Traceability

The property that every task, test, and behavior links to a requirement, and every requirement is covered — no orphan code, no orphan requirements. Enforced by the `spec` gate.

## Gate (Quality Gate / Stage Gate)

A checkpoint a stage must pass before work advances. The SDK's gates live in `hooks/stages/` and run via `run-stage.sh`; advisory by default, blocking under `QF_STAGE_ENFORCE=1`. Examples: `spec`, `leakage`, `backtest`, `secret-scan`, `data-contract`.

## Stage

One of the six development-lifecycle steps — Planning/Requirements, Design, Implementation, Testing, Deployment, Maintenance — each with an owning agent and a companion gate.

## Orchestrator

The `workflow_orchestrator` agent, which drives a change through the SDD flow and enforces the gate between each stage. It routes to the owning stage and domain agents using `agents/README.md` as its routing table.

## Agent Group (Category Folder)

A directory under `agents/` that groups related agents (e.g. `data_ingestion/`, `secrets_management/`, `trading_strategies/`). The folder has its own `README.md` and is not itself an agent; a public agent is any directory containing `prompt.md`, at any depth.

## Spec-Driven Role

A section in each agent's `instructions.md` that ties it to the framework: which spec artifact it owns or feeds, which IDs its outputs become, and which gates and instructions apply.

## Run Card

A record that makes an experiment or job reproducible: code version, data snapshot/hash, config, seed, environment, and the command to reproduce. Template: `templates/docs/run_card.md`.

## Data Contract

A checkable declaration of what a dataset guarantees: grain, keys, schema, point-in-time rules, and missingness thresholds. Template: `templates/data/data_contract.md`; checked by the `data-contract` gate.

## Point-in-Time (PIT)

The discipline of using each input only as of when it was actually knowable, including publication and revision lags. See `instructions/point_in_time.md`; a primary leakage surface.

## Information Barrier

An access boundary (e.g. MNPI, restricted lists, Chinese walls) that knowledge and data must respect. Enforced by the knowledge and secrets agents so restricted material is never surfaced to an unauthorized party.

## Provenance

The recorded origin of a knowledge item or dataset — source, author, date, version, and access level — so an answer or result can be traced and reproduced.

## Formulaic Alpha

A tradable signal expressed as an explicit formula over market inputs, composed from an operator library (`rank`, `ts_rank`, `correlation`, `delta`, `decay_linear`, `indneutralize`, …). See `instructions/formulaic_alphas.md`.

## Financing-Aware Backtest

A backtest that nets the cost of borrowing and funding — borrow fee, short rebate, repo/funding, margin — from returns. Short and long-short backtests that ignore financing overstate their edge; checked by the `backtest` gate's financing theme.
