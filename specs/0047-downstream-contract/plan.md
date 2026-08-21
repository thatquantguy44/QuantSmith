# Plan: Downstream Consumer Contract

- **Spec:** 0047-downstream-contract (`spec.md`)
- **Status:** Approved
- **Author:** Claude
- **Last updated:** 2026-08-12

## Approach

Three small, independent pieces serving one concern — a consumer in a
separate repository being able to tell whether it still understands
QuantSmith. Only one existing file changes, additively.

## Architecture & Components

```text
1. src/quantsmith/pipelines/dashboard_spec.py   (MODIFIED, additive)

   SCHEMA_VERSION = "1.0"        # MAJOR.MINOR of the rendering contract

   DashboardSpec:
       ... existing fields unchanged ...
       schema_version: str = SCHEMA_VERSION   # appended last, defaulted,
                                              # so positional construction
                                              # and all 7 renderers are
                                              # untouched (RISK-001)

   Compatibility(compatible, reason, payload_version, consumer_version)

   check_schema_compatibility(payload_version, consumer_version=SCHEMA_VERSION)
       parse "MAJOR.MINOR" both sides; unparseable -> incompatible (REQ-003)
       major differs            -> incompatible ("major 2 != 1")
       payload minor > consumer -> compatible, caveat: payload is newer,
                                   unknown fields should be ignored
       otherwise                -> compatible, no caveat

2. .github/workflows/release-notify.yml         (NEW)

   on: push tags 'v*'
   job:
     - skip unless secrets.DOWNSTREAM_DISPATCH_TOKEN and
       vars.DOWNSTREAM_REPOS are both set          (REQ-005, NFR-003)
     - for each repo in DOWNSTREAM_REPOS (comma-separated):
         POST /repos/<repo>/dispatches
           event_type: quantsmith-release
           client_payload: { version: <tag> }
   # notifies only; opening and merging the bump PR is the consumer's side

3. hooks/stages/quantsmith-version-check.sh      (NEW gate)

   declared = grep 'quantsmith' in requirements*.txt / pyproject.toml
   if none                  -> qf_info "not a consumer; skipped"  (REQ-007)
   if declared without '=='  -> qf_warn floating dependency        (REQ-006)
   if pinned:
       installed = python -c "import quantsmith; print(__version__)"
       pinned != installed  -> qf_warn naming both
   # offline and deterministic: compares against the INSTALLED package,
   # never a remote index (Non-Goals)
```

`quantsmith/__init__.py` gains `__version__` if absent, so the gate has
something to read.

## Interfaces & Data Contracts

`SCHEMA_VERSION` and `check_schema_compatibility` are the public surface a
consumer imports. The dispatch event (`quantsmith-release` with a
`version` payload) is the cross-repo interface. The gate's interface is
its exit code and findings, like every other `hooks/stages/*-check.sh`.

## Constitution Check

| Principle | Upheld? | Notes |
| --- | --- | --- |
| P5 Reversibility | yes | The only modified file gains one defaulted field and two new symbols; reverting is a clean subtraction. |
| P9 No credentials | yes | The token is read from repository secrets, never embedded, and its absence is a skip rather than a failure. |
| P10 Honest reporting | yes | RISK-002 is stated in the module itself: `schema_version` is a *declaration*, not a derivation — a breaking change shipped without a bump is undetectable from here, and the consumer-side contract test is the real guard. |
| P8 No silent trade-offs | yes | RISK-001–RISK-004 name the compatibility irony, the false-safety limit, the new credential, and the artifact-only consumer gap. |

## Traceability Matrix

| Requirement | Design element | Tasks |
| --- | --- | --- |
| REQ-001 | `schema_version` field, appended and defaulted | T-001 |
| REQ-002, REQ-003 | `check_schema_compatibility`, `Compatibility` | T-001 |
| REQ-004, REQ-005 | `release-notify.yml` | T-002 |
| REQ-006, REQ-007 | `quantsmith-version-check.sh` | T-003 |
| REQ-008 | `run-stage.sh`, `hooks/README.md`, root `README.md` | T-004 |
| NFR-001 | Existing renderer tests pass unchanged | T-005 |
| NFR-002, NFR-003 | Stdlib + POSIX sh; secrets-only token | T-001 – T-003 |
| NFR-004 | Validation gates | T-005 |

## Trade-offs & Alternatives

| Decision | Chosen | Rejected alternative | Why |
| --- | --- | --- | --- |
| Version granularity | `MAJOR.MINOR` | Full SemVer with patch | A patch cannot change payload shape by definition, so carrying it would imply a precision the contract does not have. |
| Newer-minor payload | Compatible, with a stated caveat | Reject anything newer | Same major means no breaking change; rejecting would make every SDK minor release break every client until it upgrades — the opposite of the goal. |
| Cross-repo mechanism | `repository_dispatch` notification | Auto-open-and-merge, or a scheduled poll | Notification plus a human merge is the safe default for a contract a shipped client depends on; polling adds a moving part with no benefit over an event. |
| Gate comparison basis | The installed package version | Query PyPI / GitHub releases | Gates here are offline and deterministic. A network call would make the gate flaky and CI-dependent, and RISK-004 records the resulting limitation honestly. |
| Where the field goes | Appended last with a default | A new wrapper type carrying version + spec | A wrapper would break all seven renderers to add a version — breaking compatibility to add compatibility. |

## Validation Strategy

Extend `tests/test_powerbi_profile.py`'s sibling coverage with a new
`tests/test_dashboard_contract.py` for AC-001 and AC-003 – AC-006, and
rely on the **existing** renderer test modules passing unchanged for
AC-002 — that is the real backward-compatibility evidence, and it is
evidence precisely because those tests were not touched. The gate is
verified by direct execution against temporary fixture repositories
(AC-007 – AC-009), as `0040` and `0043` were. AC-010 and AC-011 are
inspection and a full `run-stage.sh` run. Then the documentation gate
set, the full `pytest tests/ -q`, and `git diff --check`.

## Rollout, Observability & Rollback

Rollout is a branch commit and push. The workflow is inert until a
maintainer configures `DOWNSTREAM_REPOS` and the dispatch secret, so
merging it changes nothing operationally. Rollback is reverting the
commit.

## Open Questions

- Should `schema_version` extend to the run manifest, backtest report,
  and data contract payloads once a consumer exists for them? (Carried
  from `spec.md`.)
