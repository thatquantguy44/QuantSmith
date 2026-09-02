# Data Signal Intake Instructions

## Operating Rules

- Identify prediction time, decision time, holding period, and data availability.
- Require source provenance, data grain, refresh cadence, and owner for every input.
- Distinguish raw signal strength from allocation-ready expected return, risk, or constraint inputs.
- Name stale, missing, or low-confidence inputs and required fallbacks.

## Checks

- Are forecasts calibrated and aligned to the rebalance horizon?
- Are holdings, benchmark, risk, cost, and price data as-of the same decision time?
- Is the baseline portfolio decision defined if a signal is unavailable?

## Market Research Retrieval (spec 0056 T-012)

Pull governed sell-side notes, fund-manager letters, and firm research as signal
context before populating `Signal Evidence`. Use the market research MCP namespace:

```python
from quantsmith.adapters.mcp_servers.market_research_resources import dispatch_market_research

resp = dispatch_market_research(
    {"jsonrpc": "2.0", "method": "resources/list", "id": 1,
     "params": {"caller_clearance": "internal"}},
    catalog=catalog,
)
# Read individual items: knowledge://market_research/<asset_class>/<source_type>/<item_id>
```

Cite every item used in `Signal Evidence`; flag stale or superseded items.

## Output Contract

Use sections: `Input Inventory`, `Timing`, `Signal Evidence`, `Readiness`,
`Risks`, `Validation`, `Workflow Handoff`, and `Spec Updates`.
