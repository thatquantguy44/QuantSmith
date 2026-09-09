# Text-Intelligence Evidence Templates

These JSON templates document the provider-neutral contracts implemented by
`quantsmith.text_intelligence` for spec `0071`. Copy and complete them; do not
use template placeholders as production evidence.

The text-intelligence manifest is the domain index. Its `orchestration` field
must resolve to one spec-`0070` `run_envelope.json`. That envelope remains the
authoritative replay and audit record and must hash-reference the completed
text manifest, avoiding a circular hash dependency.

Committed, fully linked examples live in
[`examples/text_intelligence/`](../../examples/text_intelligence/README.md).
