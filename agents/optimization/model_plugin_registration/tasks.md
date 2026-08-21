# Model Plugin Registration Tasks

## Ingest The Manifest Entry

Input: a `model_plugins.yml` entry.

Output: a capability summary, explicitly labeled "as declared by the
owner."

## Check Contract Compliance

Input: the same entry, plus `adapters/model_plugin/adapter_contract.md`.

Output: a list of required fields present vs. missing.

## Surface Unverifiable Claims

Input: the declared capability and any stated guarantees.

Output: a list of claims that cannot be confirmed from the manifest alone.

## Recommend Routing

Input: the compliance check and unverifiable-claims list.

Output: a named handoff to `problem_formulation`,
`solver_diagnostics_sensitivity`, and/or `risk`, plus a recommended (not
enacted) `review_status`.
