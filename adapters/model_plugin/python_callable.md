# Python Callable Profile

For a prebuilt model exposed as a local Python function or class — the most
common case for an in-house solver already living in the adopter's codebase.

## Registration

`invocation.type: python_callable`; `invocation.reference` is an import path
(e.g. `internal_pkg.optimizers.collateral:solve`) in the local, gitignored
`model_plugins.yml`. The committed template uses a placeholder
(`{module.path:callable_name}`) — never a real internal import path.

## Invocation Notes

- The callable is expected to accept the payload described by
  `input_schema_uri` and return the shape described by `output_schema_uri`;
  this adapter does not impose a specific function signature beyond that.
- Exceptions raised by the callable are caught and redacted into
  `error_message_redacted` — a raw internal stack trace is not surfaced to
  an artifact this SDK would track.
- `dry_run: true` should import-check the callable exists and is callable
  without executing it.

## What This Adapter Does Not Do

- Does not install, vendor, or read the callable's source into this
  repository.
- Does not infer the callable's behavior beyond what the manifest declares —
  see `agents/optimization/model_plugin_registration/` for the review step.
