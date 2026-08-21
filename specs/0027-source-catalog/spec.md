# Spec: Data Source Catalog

- **ID:** 0027-source-catalog
- **Status:** Approved
- **Author:** Claude
- **Approver:** Josh
- **Last updated:** 2026-08-10

## Problem & Context

`templates/data/data_contract.md` describes a specific dataset (schema,
keys, point-in-time rules) once it's already being pulled, and
`adapters/data_access/external_apis/*.md` documents the generic technical
mechanics of known public APIs. Nothing in the SDK centrally answers, for
any source a workflow might use — an API, a database, a vendor feed, a
website — three basic questions in one place: what is it, how good is it,
and how do you connect to it. Ingestion agents
(`agents/data_ingestion/*`) and quality review
(`instructions/data_quality.md`) each implicitly assume this information
exists somewhere; nowhere did it have a home.

## Goals

- Add `sources/`, a directory-per-source catalog (one YAML file per
  source), matching this SDK's existing pattern for many independently
  reviewable entities (`specs/NNNN-slug/`, `agents/*/`) rather than a
  single growing manifest.
- Add `templates/data/source_catalog_entry.yml`, the schema: identity,
  description, quality assessment, point-in-time characteristics, and a
  connection block whose credential field is a *pointer*, never a value.
- Add `sources/README.md` as the index, with one filled-in reference entry
  (`fred.yml`, a public source already documented in
  `adapters/data_access/external_apis/fred.md`) — the same role
  `specs/0001-daily-momentum-signal/` plays for the spec format.
- Add a gate, `source-catalog`, verifying every entry declares the required
  fields, every entry is indexed, and `credential_ref` doesn't contain a
  real secret value (reusing `secret-scan`'s token-format patterns).
- Wire the catalog to what already exists: `data_contract.md` (a dataset
  names the `source_id` it came from), `credential_access` (resolves what
  `credential_ref` points to), and `agents/data_ingestion/*` (checks the
  catalog before wiring a new connection).

## Non-Goals

- No requirement that `sources/*.yml` be gitignored. Unlike
  `role_context.yml` (spec `0024`) or `model_plugins.yml` (spec `0026`),
  which are personal/proprietary local configuration, a source catalog is
  meant to be a shared, version-controlled team artifact — that's the
  point of centralizing it. The gate protects against a pasted *credential
  value*, not against the file being tracked.
- No automated data-quality scoring; `quality.completeness`/`timeliness`
  are stated by whoever registers the source, reviewed like any other
  claim in this repo, not computed.
- No duplication of `adapters/data_access/external_apis/*.md`'s technical
  delivery-rules content; a source entry references that doc rather than
  restating pagination/vintage/metadata rules already documented there.
- No new agent in this slice (template, index, gate, and wiring only, as
  requested); a dedicated "source registration reviewer" agent (mirroring
  `model_plugin_registration/`) is a candidate follow-up if a concrete
  workflow needs one.

## Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| REQ-001 | The system shall provide a per-source YAML schema (`templates/data/source_catalog_entry.yml`) covering identity, description, quality, point-in-time characteristics, and a connection block with a credential pointer field. | must |
| REQ-002 | The system shall provide `sources/README.md` as a maintained index, with one filled-in reference entry. | must |
| REQ-003 | The system shall provide a gate verifying every `sources/*.yml` declares the required fields, is listed in the index, and has no token-shaped value in place of a credential pointer. | must |
| REQ-004 | `templates/data/data_contract.md`, `agents/secrets_management/credential_access/`, and `agents/data_ingestion/*` shall reference the catalog as their source of truth for connection/quality/point-in-time metadata. | must |

## Non-Functional Requirements

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-001 | Gate hygiene | Degrades gracefully (skips cleanly) when `sources/` doesn't exist; each check is independently testable. |
| NFR-002 | Repository hygiene | `spec`, `agent-catalog`, `docs-link`, `spec-index`, `secret-scan`, `source-catalog` gates and the full pytest suite pass. |
| NFR-003 | Credential safety | No committed entry contains a token-shaped credential value; `credential_ref` names a pointer in every entry. |

## Acceptance Criteria

| ID | Given / When / Then | Covers |
| --- | --- | --- |
| AC-001 | Given `sources/fred.yml`, when the `source-catalog` gate runs, then every required field is reported declared and it is found in the index. | REQ-001, REQ-002, REQ-003 |
| AC-002 | Given a `sources/*.yml` entry missing a required field, when the gate runs, then that specific field is flagged. | REQ-003 |
| AC-003 | Given a `sources/*.yml` entry not listed in `sources/README.md`, when the gate runs, then it is flagged by id. | REQ-003 |
| AC-004 | Given a `sources/*.yml` entry with a token-shaped value (e.g. an `AKIA...` pattern) in place of a credential pointer, when the gate runs, then it is flagged. | REQ-003, NFR-003 |
| AC-005 | Given `templates/data/data_contract.md`, `credential_access/instructions.md`, and `agents/data_ingestion/*/instructions.md`, when inspected, then each references `sources/` by path. | REQ-004 |

## Data & Dependencies

No data dependencies, no runtime code. The gate is a POSIX shell script
consistent with `hooks/stages/`, reusing `secret-scan`'s existing
token-pattern regex rather than inventing a new one.

## Risks

| ID | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| RISK-001 | A registered source's `description`/`name` names something genuinely too sensitive to put in a shared, tracked file (an internal system whose existence itself is confidential). | Company-specific detail enters the repository despite the catalog's intent. | `sources/README.md`'s Data Safety section states the fallback explicitly: register with a generic name/description and keep identifying detail behind whatever `credential_ref` points at instead. |
| RISK-002 | `quality`/`last_assessed` goes stale and nobody notices, so a reviewer trusts an outdated assessment. | A decision relies on quality information that's no longer true. | Documented as a Common Failure Mode in `instructions/data_source_catalog.md`; no automated staleness gate in this slice (see Non-Goals) — a candidate follow-up if it becomes a real problem. |
| RISK-003 | The token-pattern heuristic misses a credential value in a format it doesn't recognize. | A non-standard secret format ships undetected. | Reuses `secret-scan`'s same patterns and the same honestly-scoped limitation already documented there; `secret-scan` itself still runs over the same files as a second check. |

## Assumptions & Open Questions

- Assumption: one file per source is the right granularity even for a small
  catalog (one or two sources); the pattern scales without a migration
  later, unlike starting with a single manifest and needing to split it.
- Assumption: FRED is a safe, genuinely public reference example — no
  proprietary or company-specific content is needed to demonstrate the
  schema.
- Open question: does a dedicated `model_plugin_registration`-style review
  agent for source registrations become worth building once there are
  enough sources that manual review doesn't scale?

## Exceptions

None.
