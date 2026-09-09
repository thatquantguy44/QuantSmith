# Spec 0071 Text-Intelligence Evidence

These two offline examples exercise the provider-neutral spec-`0071`
contracts. Each has one `text_intelligence_manifest.json` and one authoritative
spec-`0070` `run_envelope.json`; the envelope hash-references the text manifest,
and the text replay command delegates verification to the `0070` replay engine.

| Example | Execution | Replay behavior |
| --- | --- | --- |
| `deterministic_lexical_signal/` | Deterministic normalization, untrusted-text quarantine, lexical tasks, and a fixture-only text signal | Replays without external substitution |
| `fixture_backed_retrieval_generation/` | Deterministic hash-vector/index fixtures plus a recorded provider-shaped response | Replays with `--fixture-mode`; performs no network request |

```sh
PYTHONPATH=src python3 -m quantsmith.text_intelligence validate --discover examples/text_intelligence
PYTHONPATH=src python3 -m quantsmith.text_intelligence replay \
  --manifest examples/text_intelligence/deterministic_lexical_signal/text_intelligence_manifest.json
PYTHONPATH=src python3 -m quantsmith.text_intelligence replay \
  --manifest examples/text_intelligence/fixture_backed_retrieval_generation/text_intelligence_manifest.json \
  --fixture-mode
```

Regenerate both bundles with
`generate_reference_examples("examples/text_intelligence")`. They contain only
fictional data; see the
[`0071` synthetic-data disclosure](../../docs/0071_synthetic_data_disclosure.md).
