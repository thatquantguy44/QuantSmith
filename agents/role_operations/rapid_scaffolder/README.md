# Rapid Scaffolder Agent

## Purpose

The Rapid Scaffolder Agent turns a new prototype idea into a running
skeleton — a repo/notebook structure, a data-contract stub, and a naive
baseline — so day one of a new idea starts at iterating, not at setting up.

## Use When

- A new prototype idea gets a green light and needs to go from zero to a
  runnable skeleton.
- A recurring project shape (data in → baseline → validation → report) is
  being rebuilt by hand every time.

## Inputs

- The idea or hypothesis to prototype, and its rough scope.
- Optionally, `role_context.yml` for the asset classes/domain in scope, so
  the scaffold points at the right `agents/asset_classes/` mechanics agent
  and the right spec/template starting points.

## Outputs

- A suggested repo/notebook structure, following this SDK's conventions
  (`specs/NNNN-slug/`, `templates/spec/`, `templates/data/data_contract.md`
  where a data contract applies).
- A data-contract stub with fields to fill in, not fabricated values.
- A naive baseline plan (what the simplest defensible first attempt looks
  like) — not a finished model.

## Example Requests

- "Scaffold a new prototype for [hypothesis] using this SDK's spec
  structure."
- "Give me a data-contract stub and a naive baseline plan to start from."

## Required Review Themes

- The scaffold points at the SDK's existing spec/template conventions rather
  than reinventing structure per prototype.
- No fabricated data-contract values (schema, source, cadence) — fields are
  left blank for the human to fill in from the real source.
- The baseline is explicitly naive: a floor to beat, not a claimed result.
