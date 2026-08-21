# Spec: Downstream Consumer Contract — Schema Version, Release Notify, Version Gate

- **ID:** 0047-downstream-contract
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-12

## Problem & Context

A client in a **separate repository** consumes QuantSmith. That turns three latent weaknesses into real ones:

1. **`DashboardSpec` carries no schema version.** It is the contract a
   client renders, and seven profiles already build on it. A downstream
   consumer has no way to detect a breaking change except by breaking —
   and for a client shipped through App Store review, "detect by
   breaking" means days without a fix.
2. **Nothing tells a downstream repo that a new release exists.**
   Dependabot covers `github-actions` only (`.github/dependabot.yml`),
   and there is no signal when `quantsmith` itself moves.
3. **Nothing checks a consumer's pin.** This SDK's gates are designed to
   be copied into adopting repositories, but none of them covers "are you
   still on a version of QuantSmith whose contract you understand".

The version is `0.1.0` and the consumed contract is unversioned, so
SemVer is presently a documentation claim rather than something a
consumer can rely on. This spec makes it real, before a second repository
depends on it.

## Goals

- Add a `schema_version` to `DashboardSpec` and a
  `check_schema_compatibility` helper, so a consumer can refuse a payload
  it does not understand and show stale data rather than crash.
- Add a release-notify workflow: on a version tag, dispatch an event to
  configured downstream repositories so a bump PR can be opened and
  tested — automatic *notification*, human merge.
- Add `hooks/stages/quantsmith-version-check.sh`, a copyable gate that
  flags a downstream repo whose `quantsmith` pin is missing, floating, or
  behind the installed version.
- Keep every change backward compatible: existing `DashboardSpec`
  construction and all seven renderers keep working untouched.

## Non-Goals

- **No auto-merge of dependency bumps.** The workflow opens a signal, not
  a merge. Auto-updating the contract a UI is built on is the failure
  mode this spec exists to prevent.
- **No PyPI publication.** `docs/packaging.md` already tracks that
  decision; this spec makes a consumer *safe*, it does not choose a
  distribution channel.
- **No network calls from the gate.** It compares a declared pin against
  the installed package, not against a remote index — gates in this SDK
  stay offline and deterministic.
- **No versioning of other payloads** (run manifests, backtest reports,
  data contracts). `DashboardSpec` is the contract a downstream client consumes;
  extending the scheme elsewhere is a later decision, not an assumption.
- **No change to the SemVer policy itself.** `CHANGELOG.md` owns that;
  this spec supplies the mechanism the policy needs.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | `DashboardSpec` shall carry a `schema_version` defaulting to the module's `SCHEMA_VERSION`, added so existing positional construction and all seven renderers are unaffected. | must |
| REQ-002 | `check_schema_compatibility` shall report a payload version as compatible or not against a consumer version, treating a differing major version as incompatible and a newer minor as compatible-with-caveat. | must |
| REQ-003 | A malformed or empty version string shall be reported as incompatible with a clear reason, never silently accepted. | must |
| REQ-004 | A release-notify workflow shall, on a version tag, dispatch a `repository_dispatch` event carrying the released version to each configured downstream repository. | must |
| REQ-005 | The release-notify workflow shall skip cleanly when no downstream repositories or no dispatch token are configured, rather than failing the release. | must |
| REQ-006 | `quantsmith-version-check.sh` shall detect a declared `quantsmith` dependency in a consuming repository and flag it when unpinned, or when pinned to a version other than the installed one. | must |
| REQ-007 | The gate shall report "not a consumer; skipped" in a repository that declares no `quantsmith` dependency — including QuantSmith itself. | must |
| REQ-008 | `hooks/stages/run-stage.sh`, `hooks/README.md`, and root `README.md`'s gate table shall document the new gate and workflow. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Backward compatibility | Every existing `DashboardSpec` call site and all seven renderers pass unchanged. |
| NFR-002 | Dependency isolation | Standard library only; the gate is POSIX `sh` with no network access. |
| NFR-003 | No credentials | The workflow reads a token from repository secrets and never embeds one; absence is handled as a skip. |
| NFR-004 | Repository hygiene | `spec`, `docs-link`, `spec-index`, `readme-sync`, `doc-counts`, `secret-scan`, `quantsmith-version` gates and the full pytest suite pass. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given a `DashboardSpec` built exactly as before this change, when constructed, then it succeeds and its `schema_version` equals `SCHEMA_VERSION`. | REQ-001, NFR-001 |
| AC-002 | Given the seven existing renderers, when run against a spec, then they behave as before (their tests pass unchanged). | NFR-001 |
| AC-003 | Given a payload whose major version differs from the consumer's, when checked, then it is incompatible with a reason naming the major mismatch. | REQ-002 |
| AC-004 | Given a payload whose minor version exceeds the consumer's within the same major, when checked, then it is compatible and the caveat is stated. | REQ-002 |
| AC-005 | Given a payload at or below the consumer's minor within the same major, when checked, then it is compatible with no caveat. | REQ-002 |
| AC-006 | Given a malformed or empty version string, when checked, then it is incompatible with a reason. | REQ-003 |
| AC-007 | Given a fixture repository declaring `quantsmith==<other>`, when the gate runs, then it flags the mismatch naming both versions. | REQ-006 |
| AC-008 | Given a fixture declaring `quantsmith` with no pin, when the gate runs, then it flags the floating dependency. | REQ-006 |
| AC-009 | Given a repository declaring no `quantsmith` dependency, when the gate runs, then it reports "skipped" and exits cleanly. | REQ-007 |
| AC-010 | Given `.github/workflows/release-notify.yml`, when inspected, then it dispatches on a version tag, carries the version, and guards on the token and repository list being present. | REQ-004, REQ-005, NFR-003 |
| AC-011 | Given `run-stage.sh` with no arguments, when run, then the `quantsmith-version` gate executes. | REQ-008 |

## Data & Dependencies

No data dependencies. Standard library; POSIX shell; a GitHub Actions
workflow using only `actions/github-script` or `curl` against the GitHub
API with a repository-provided token.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | Adding a field to a frozen dataclass could break a call site that constructs `DashboardSpec` positionally with trailing arguments. | Downstream breakage from a change meant to prevent it. | The field is appended last with a default, and AC-001/AC-002 verify existing construction and all seven renderers unchanged. The irony of breaking compatibility with a compatibility spec is exactly why this is tested rather than assumed. |
| RISK-002 | `schema_version` gives a *false* sense of safety: bumping it is a manual act, so a breaking change shipped without a bump is undetectable. | A consumer trusts a version that did not move. | Stated plainly in the module docstring: the version is a declaration, not a derivation. The honest guard is the consumer-side contract test, which this spec enables but cannot enforce from here. |
| RISK-003 | The dispatch workflow needs a token with permission on another repository, which is a credential this project has never held. | A new secret to manage, and a new blast radius. | Scoped to `repository_dispatch` only, read from repository secrets, never embedded, and the workflow skips when absent (REQ-005). It notifies; it cannot merge. |
| RISK-004 | The version gate compares against the *installed* package, so a consumer that never installs `quantsmith` gets no signal. | A silent pass in a repo that only reads JSON artifacts. | Documented as a limitation: the gate covers code consumers. A pure-artifact consumer is guarded by `schema_version` on the payload instead, which is the layer that actually applies to it. |

## Assumptions & Open Questions

- Assumption: `MAJOR.MINOR` is sufficient for a rendering contract; patch
  changes cannot alter payload shape by definition.
- Assumption: notification plus a tested bump PR is the right default,
  and "always latest" without a human merge is not wanted for a client
  shipped through review.
- Open question: should `schema_version` extend to the run manifest,
  backtest report, and data contract payloads once a consumer exists for
  them?

## Exceptions

None.
