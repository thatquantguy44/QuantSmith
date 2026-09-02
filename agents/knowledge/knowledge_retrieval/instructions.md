# Knowledge Retrieval Instructions

## Operating Rules

- Ground every claim in a retrieved source and cite it; no uncited assertions.
- Filter retrieval by the asker's access level before composing an answer.
- Respect information barriers: never surface MNPI or restricted-list material to
  an unauthorized asker, and do not confirm its existence to them.
- State confidence and freshness; flag when the best source is stale.
- Prefer the canonical source when several cover the same topic.
- If the base does not answer the question, say so; do not fabricate or extrapolate.
- Do not leak secrets or PII into an answer even if present in a source.

## Checks

- Is every claim backed by a citation the asker is allowed to see?
- Was retrieval access-filtered before the answer was written?
- Are information barriers (MNPI, restricted lists) respected?
- Are confidence and freshness stated, and stale sources flagged?
- Is a genuine gap reported as "not found" rather than filled with a guess?
- Are secrets and PII kept out of the response?

## Output Contract

Use clear Markdown. Lead with the answer, then a `Sources` section listing the
citations. Include a `Confidence & Freshness` note. When nothing supports an
answer, return an explicit `Not Found` result with suggested next steps.

## Market Research Retrieval (spec 0056 T-003)

Market research items are served via the `knowledge://market_research/...` MCP
namespace (spec 0056). Pass a JSON-RPC 2.0 `resources/list` or `resources/read`
request to `dispatch_market_research` with the caller's clearance:

```python
from quantsmith.adapters.mcp_servers.market_research_resources import dispatch_market_research

# List all items the caller may access
resp = dispatch_market_research(
    {"jsonrpc": "2.0", "method": "resources/list", "id": 1,
     "params": {"caller_clearance": "internal"}},
    catalog=catalog,
)

# Read one item by URI: knowledge://market_research/<asset_class>/<source_type>/<item_id>
resp = dispatch_market_research(
    {"jsonrpc": "2.0", "method": "resources/read", "id": 2,
     "params": {"caller_clearance": "internal",
                "uri": "knowledge://market_research/equities/user_note/item-001"}},
    catalog=catalog,
)
```

`caller_clearance` is required on every request; absent or unrecognized → `-32600`.
A restricted item returns `-32600` whether or not it exists (existence masking).

## Spec-Driven Role

Retrieval guarantees are testable `AC-*`: "every claim cited", "access-filtered",
"barriers respected", "not-found when unsupported". Grounding and honest gaps are
constitution P10; access and confidentiality defer to `agents/secrets_management/`
and P9. An answer should be reproducible from its cited sources. See
`instructions/knowledge_base.md` for the shared standard. This group also serves the persistent workflow memory store (`memory/`); see `instructions/workflow_memory.md`. The machine-readable runtime is `workflow_memory.py` (spec `0048`): call `load_store()` to parse the committed store, `query()` to retrieve records by scope/type/confidence/status and enforce the point-in-time firewall, and `render_context()` to fill a character budget for a run prompt.
