# Text Intelligence Runtime (Spec 0071)

This standard-library package provides the offline foundation for governed NLP,
LLM, and quant text workflows:

- immutable corpus, document, source-span, revision, split, access, entitlement,
  license, transformation, and quarantine evidence;
- provider-neutral model capabilities, embedding artifacts, access-tier index
  snapshots, and training/adaptation evidence contracts;
- evidence-bearing task and text-signal schemas with point-in-time validation,
  evaluation coverage, review state, and fail-closed publication metadata;
- deterministic lexical and fixture-backed retrieval/generation producers; and
- replay that validates the domain artifacts and then invokes the authoritative
  spec-`0070` envelope replay engine.

The foundation performs no live model, data-source, MCP, or vector-store call.
Spec `0054` remains the owner of live cited semantic retrieval. Provider adapters
remain behind `adapters/llm_runtime/`; agents consume typed artifacts, not keys or
provider-specific payloads.

```python
from quantsmith.text_intelligence import (
    build_agent_consumption_view,
    emit_lexical_signal_evidence,
    replay_text_intelligence_manifest_file,
)
```

Use `python -m quantsmith.text_intelligence --help` for validation and replay.
