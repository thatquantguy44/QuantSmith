# LLM Runtime Adapters

LLM runtime adapters normalize provider execution for workflows that use language
models. They do not own prompts, evaluation, policy, or final decisions.

## Files

| File | Purpose |
| --- | --- |
| `adapter_contract.md` | Provider-neutral model invocation and result schema. |
| `openai.md` | OpenAI model runtime profile. |
| `anthropic.md` | Anthropic model runtime profile. |
| `local_model.md` | Local or self-hosted model runtime profile. |
| `llm-profiles.schema.json` | Vendored copy of QuantMeridian's `llm-profiles/1` schema (provenance below). |

## Design Rule

Agents own task framing and review. Runtime adapters own provider selection,
request formatting, rate limits, retries, token accounting, and response metadata.

Spec `0071` consumes this boundary through versioned, provider-neutral capability
profiles in `src/quantsmith/text_intelligence/`. Those profiles declare model
revision/checksum, license, execution location, privacy classes, deterministic
settings, limits, fallbacks, fixture references, and replay class. Agents receive
typed task or signal artifacts and never provider credentials. The current `0071`
foundation is offline only; adding a live provider requires a separately approved
adapter and promotion policy.

## Executable backend: `quantsmith.adapters.llm_runtime` (spec `0080` T-024)

Profiles use QuantMeridian's `llm-profiles/1` format unchanged, so one
`settings/llm_profiles.json` serves both repositories. The package reads and
validates that file with the standard library, resolves a profile per call,
and sends one single-turn completion:

```python
from quantsmith.adapters import llm_runtime as llm

config = llm.load_profiles("settings/llm_profiles.json")
out = llm.complete("Which metric is 'funding cost'?", config=config, use="interpreter",
                   data_classes=["public_market_data"], system="Return a QueryPlan as JSON.")
out.output_text, out.usage, out.to_contract()
```

| `api_style` | Request | Covers |
| --- | --- | --- |
| `anthropic_messages` | `POST {base}/v1/messages`, `anthropic-version: 2023-06-01`; base defaults to `https://api.anthropic.com` | Anthropic direct and Anthropic-compatible gateways |
| `openai_chat_completions` | `POST {base}/chat/completions`; base defaults to `https://api.openai.com/v1` | OpenAI, Azure OpenAI v1 endpoints (`auth.scheme: header`, `api-key`), LiteLLM, OpenRouter, vLLM, Ollama, llama.cpp |
| `none` | no request; `complete()` returns `status: skipped` | the keyword interpreter and template narrative |

Base URLs follow the official SDKs: an Anthropic base URL has no `/v1`; an
OpenAI-compatible base URL ends in `/v1`.

- **Secrets:** endpoints, models, credentials, and header values come only
  from the environment variables a profile names. A literal URL or
  credential-looking string in another field fails validation. Errors name
  variables, never values, and provider error text is not echoed.
- **Resolution** (identical to QuantMeridian spec009): requested profile,
  then module default, then `default_profile_env`, then `default_profile`.
  Each check fails with a typed error: `LLM_PROFILE_UNKNOWN`,
  `LLM_PROFILE_NOT_ALLOWED` (disabled, use not in `uses`, or data class not
  in `data_classes`), or `LLM_PROFILE_UNAVAILABLE` (a named variable unset).
- **Calls:** retries 408, 409, 429, 5xx, and connection failures up to
  `limits.max_retries`, honoring `retry-after` (capped at 30 s). Then
  `fallback_profile` is tried once, on provider errors only.
  `TokenBudget` enforces `limits.per_job_token_cap` across one answer.
  Other failures are `LLM_OUTPUT_INVALID`, `LLM_REFUSAL`, and
  `LLM_TOKEN_CAP_EXCEEDED`.
- **Network boundary:** `transport.py` is the only module that opens a
  connection; pass `transport=` to use your own HTTP client.
  `quantsmith.nl_analytics` never imports this package: it receives a plain
  completion callable (`0080` AC-019).
- **Not in `llm-profiles/1` yet:** a generic HTTP/JSON shape, import-path
  callables (Bedrock, Vertex), and token-command credentials. These are
  proposed to QuantMeridian as an additive revision. Until then, inject a
  callable.

Shared conformance cases live in `tests/fixtures/llm_profiles/conformance.json`,
in the format QuantMeridian spec009's PLAN describes ("Conformance fixtures"),
so both resolvers can be checked against the same files.

### Provenance of the vendored schema

| File | Source | SHA-256 |
| --- | --- | --- |
| `llm-profiles.schema.json` | QuantMeridian `contracts/agent/llm-profiles.schema.json` at `main` `ad3d2d067040bd67b01bea20da59b94572b4113e` | `fb04b7e1089b5d2f705d30f665b7134b053b1afcf8c43891594ae55c1362da00` |
| `tests/fixtures/llm_profiles/quantmeridian_settings.json` | QuantMeridian `settings/llm_profiles.json`, same commit | `2a99ba4702673b288f258312257c195eea95a3e32c0f7512032e9b015b47fb8f` |

Re-copy both together when QuantMeridian revises the format, and update
the digests above (a test checks the schema digest).
