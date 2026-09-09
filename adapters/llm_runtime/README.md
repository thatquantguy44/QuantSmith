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
