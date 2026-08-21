# Tasks: Downstream Consumer Contract

- **Spec:** 0047-downstream-contract (`spec.md`, `plan.md`)
- **Last updated:** 2026-08-12

## Definition of Done (applies to every task)

- Backward compatible: every existing `DashboardSpec` call site and all
  seven renderers pass with their tests **unchanged**.
- Standard library only; the gate is POSIX `sh` and makes no network call.
- No credential is embedded; an absent token is a skip, not a failure.
- The declaration-not-derivation limit of `schema_version` is stated in
  the code, not just the spec.

## Task List

| ID | Task | Covers | Status | Notes |
| --- | --- | --- | --- | --- |
| T-001 | Add `SCHEMA_VERSION`, the `schema_version` field, `Compatibility`, and `check_schema_compatibility` to `dashboard_spec.py`; add `__version__` to the package. | REQ-001, REQ-002, REQ-003, NFR-001, NFR-002 | done | Field appended last with a default so positional construction is unaffected (RISK-001). |
| T-002 | Add `.github/workflows/release-notify.yml`. | REQ-004, REQ-005, NFR-003 | done | Dispatches `quantsmith-release` on a `v*` tag; skips cleanly when the token or repo list is unset. |
| T-003 | Add `hooks/stages/quantsmith-version-check.sh`. | REQ-006, REQ-007, NFR-002 | done | Flags a missing pin, a floating dependency, or a pin that differs from the installed version; skips in a non-consumer repo. |
| T-004 | Wire `run-stage.sh`, `hooks/README.md`, root `README.md`, and the gate counts. | REQ-008 | done | Adding a gate moves the documented count 27 → 28; `doc-counts` enforces this. |
| T-005 | Write `tests/test_dashboard_contract.py` and run validation gates. | NFR-001, NFR-004 | done | Existing renderer tests are deliberately left untouched — that is the backward-compatibility evidence. |

Status values: `todo` | `in-progress` | `blocked` | `done`.

## Test Coverage Map

| Acceptance criterion | Verification | Status |
| --- | --- | --- |
| AC-001 | `test_existing_construction_unchanged_AC_001` | done |
| AC-002 | Existing renderer test modules passing **unmodified** | done |
| AC-003 | `test_major_mismatch_incompatible_AC_003` | done |
| AC-004 | `test_newer_minor_compatible_with_caveat_AC_004` | done |
| AC-005 | `test_same_or_older_minor_compatible_AC_005` | done |
| AC-006 | `test_malformed_version_incompatible_AC_006` | done |
| AC-007 | Gate run against a fixture pinning another version | done |
| AC-008 | Gate run against a fixture with an unpinned dependency | done |
| AC-009 | Gate run in a repository declaring no dependency (QuantSmith itself) | done |
| AC-010 | Direct inspection of `.github/workflows/release-notify.yml` | done |
| AC-011 | `hooks/stages/run-stage.sh` (no args) includes `quantsmith-version` | done |

## Follow-ups

- Extend `schema_version` to the run manifest, backtest report, and data
  contract payloads once a consumer exists for them (carried as an open
  question in `spec.md`).
- **Consumer-side pieces**, which belong in the consuming repository, not here:
  a pip entry in its Dependabot config, and the contract test that
  decodes a `DashboardSpec` from the installed `quantsmith` — the latter
  being the real guard that `schema_version` alone cannot provide
  (RISK-002).
- Decide whether to publish `quantsmith` to PyPI; `docs/packaging.md`
  tracks that, and a second consuming repository is the demand it was
  waiting for.
