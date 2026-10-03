# Visualization story example

This fixed synthetic fixture runs three distinct domain stories through the real
0093 collector, story builder, and renderer: segment revenue/expense attribution,
a credit-exposure snapshot, and a macro policy-rate path. A fourth case rejects
a PD metric registered with sum aggregation before its reader runs.

```sh
PYTHONPATH=src python3 -m quantsmith.visualization_packs demo --output-dir /tmp/visualization-stories
```

Open the generated HTML files locally. They include executive findings, visible
caveats, actual SVG charts or a declared table fallback, the exact observations,
and expandable analyst evidence. JSON and Markdown express the same story.
Outputs are deterministic for `input.json`; they are generated artifacts, not
firm analysis. See the [disclosure](../../docs/0093_synthetic_data_disclosure.md)
and [integration guide](../../knowledge/visualization_packs/README.md).
