# LLM Runtime Adapter Contract

## Input

```yaml
workflow_id: string
run_id: string
model_profile: string
task_type: research | extraction | drafting | review | classification | planning
prompt_uri: string
input_artifact_uris:
  - string
temperature: number
max_output_tokens: integer
tools_allowed:
  - string
privacy:
  contains_pii: boolean
  contains_mnpi: boolean
  contains_restricted_positions: boolean
correlation_id: string
dry_run: boolean
```

## Output

```yaml
adapter_name: string
provider: string
model: string
status: completed | skipped | failed
output_artifact_uri: string | null
usage:
  input_tokens: integer | null
  output_tokens: integer | null
  cost_estimate: number | null
correlation_id: string
timestamp_utc: string
retryable: boolean
error_code: string | null
error_message_redacted: string | null
```

## Required Behavior

- Record provider, model, prompt URI, input artifacts, and usage metadata.
- Support dry-run validation of profile and privacy constraints.
- Do not send restricted fields to providers unless a workflow explicitly permits
  the model profile.
- Return outputs as artifacts rather than relying only on chat transcripts.

## Executable Callable (spec `0080` T-024)

`quantsmith.adapters.llm_runtime.complete(prompt, *, config, use, data_classes,
system=None, requested=None, module_default=None, max_output_tokens=None,
budget=None, transport=None, env=None) -> Completion` implements this contract for
`llm-profiles/1` profiles. `Completion.to_contract()` returns the output fields
above, plus `provider_style`, `model_profile`, `stop_reason`, `latency_ms`,
`attempts`, and `fallback_from`. Failures raise `LLMRuntimeError` with `code`,
`retryable`, `profile`, and `status`; no credential or provider free text appears in
them. Consumers that must stay network-free, such as `quantsmith.nl_analytics`,
receive a `Callable[[str], str]` built from it rather than importing the package.
