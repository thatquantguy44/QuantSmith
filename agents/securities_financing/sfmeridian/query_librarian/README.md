# Query Librarian Agent

## Purpose

The Query Librarian keeps SFMeridian's query-repository index healthy. It
fetches and indexes the configured repositories, then hands people a cited
curation report: which files were rejected and why, which metric names have
conflicting definitions, which files need front-matter (with a drafted
starting point), and which candidates wait in the review inbox.

## Use When

- A query repository is onboarded or changes and needs (re)indexing.
- Analysts need to know which queries are unusable and how to fix them.
- Two queries define the same metric differently.
- The review inbox needs triage.

## Inputs

- The SFMeridian configuration (`sfmeridian.yml`): repositories, policies, inbox.
- Optionally, the repository IDs to index and whether to force a full rebuild.

## Outputs

- An index (exemplars, join graph, metric candidates, filter patterns), every
  entry cited to repository, ref, path, and line span.
- A curation report whose findings each cite evidence observed in the run.
- Drafted front-matter for unannotated files, always `review_status: draft`.
- A run record (status, trace, configuration hash) for audit.

## Example Requests

- "Index the desk query repository and tell me what's broken."
- "Which metrics are defined more than one way?"
- "What's waiting for review in the inbox?"

## Required Review Themes

- Every finding cites evidence from this run; no rejected file is omitted.
- Nothing is marked reviewed, promoted, or discarded by the agent.
- Conflicting metric definitions are surfaced, never resolved by the agent.

## Runtime

A tested loop agent (spec `0114`): `python -m sfmeridian agent run query_librarian`,
or `sfmeridian.librarian.run_librarian` from Python. Manifest:
`plugins/sfmeridian/src/sfmeridian/data/agents/query_librarian.json`.
