# CLI Binary Profile

For a prebuilt model exposed as a command-line tool or batch job — common
for legacy or vendor solvers with no library or service interface.

## Registration

`invocation.type: cli_binary`; `invocation.reference` is a command template
in the local, gitignored `model_plugins.yml`. The committed template uses a
placeholder (`{binary} --input {problem_payload_uri} --output {solution_uri}`)
— never a real binary path or license-bearing invocation string.

## Invocation Notes

- The binary is expected to read `problem_payload_uri` and write
  `solution_uri` in the shapes declared by the manifest's schema URIs; exit
  code maps to `status` (`0` → `completed`, nonzero → `failed`, with the
  binary's own convention for `infeasible` documented per registration).
- stdout/stderr are captured but redacted before appearing in
  `error_message_redacted` — vendor CLIs often echo license or path detail
  that shouldn't leave the invoking process.
- `dry_run: true` should validate the binary exists and is executable
  without running a real problem through it.

## What This Adapter Does Not Do

- Does not vendor, wrap, or redistribute the binary.
- Does not parse vendor-specific solver logs beyond what the manifest's
  `output_schema_uri` declares as the expected result shape.
