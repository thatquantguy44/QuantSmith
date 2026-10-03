"""Reproducible three-domain demonstration using explicitly synthetic fixtures."""
import json
from pathlib import Path

from quantsmith.nl_analytics.plan import QueryPlan, TimeWindow
from quantsmith.pipelines.metrics_semantic_layer import Fact, SemanticLayer

from .catalog import load_catalog
from .evidence import collect_evidence
from .story import build_story


def run_example(root="."):
    root = Path(root)
    catalog = load_catalog(root)
    fixture = json.loads((root / "examples/visualization_packs/input.json").read_text())
    if fixture.get("synthetic") is not True:
        raise ValueError("This demonstration requires explicitly synthetic input.")
    stories = {}
    for case in fixture["examples"]:
        layer = SemanticLayer()
        for definition in case["definitions"]:
            layer.define(**dict(definition, dimensions=tuple(definition["dimensions"])))
        rows = [Fact(**row) for row in case["rows"]]
        evidence = []
        for request in case["evidence"]:
            plan = QueryPlan(request["metric"], tuple(request["dimensions"]), (),
                             TimeWindow(request["start"], request["end"], "month"),
                             None, None, (), "visualization-example/0093.1")
            evidence.append(collect_evidence(request["id"], case["pack_id"], plan, request["view"],
                            catalog=catalog, layer=layer, reader=lambda _, rows=rows: rows,
                            source=case["source"], as_of=case["as_of"], synthetic=True))
        stories[case["pack_id"]] = build_story(catalog, case["pack_id"], case["recipe_id"], evidence, layer)
    layer = SemanticLayer()
    layer.define(name="pd", owner="example-negative-case", grain="month", dimensions=("stage",), source="pd", agg="sum")
    plan = QueryPlan("pd", ("stage",), (), TimeWindow(12, 12, "month"), None, None, (), "example-invalid-sum")
    refused = collect_evidence("probability", "credit_risk", plan, "breakdown", catalog=catalog,
                               layer=layer, reader=lambda _: [Fact(12, {"stage": "performing"}, {"pd": 0.02})],
                               source="Synthetic invalid-aggregation fixture", as_of=12, synthetic=True)
    stories["refused_pd_sum"] = build_story(catalog, "credit_risk", "loss_quality", [refused], layer)
    return stories
