"""Spec 0080 T-024 / AC-028: provider-neutral LLM backends configured by ``llm-profiles/1``.

Every network call goes to a stub server on 127.0.0.1; no test reaches a real provider.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

from quantsmith.adapters import llm_runtime as L
from quantsmith.adapters.llm_runtime import errors as E

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "llm_profiles"
CONFORMANCE = json.loads((FIXTURES / "conformance.json").read_text(encoding="utf-8"))
SCHEMA = ROOT / "adapters" / "llm_runtime" / "llm-profiles.schema.json"
SECRET = "fake-credential-canary-7f3a"  # a unique value the leak checks look for


def _config(spec, enable=()):
    data = json.loads((FIXTURES / spec).read_text(encoding="utf-8")) if isinstance(spec, str) else copy.deepcopy(spec)
    for name in enable:
        data["profiles"][name]["enabled"] = True
    return L.parse_profiles(data)


# --- conformance: the same cases QuantMeridian's resolver must pass ----------------------------------

@pytest.mark.parametrize("case", CONFORMANCE["cases"], ids=lambda c: c["name"])
def test_ac028_conformance_resolution(case):
    config = _config(case["config"], case.get("enable", ()))
    call = case["call"]
    kwargs = {"use": call["use"], "data_classes": call.get("data_classes", ()), "requested": call.get("requested"),
              "env": case["env"]}
    expect = case["expect"]
    if "error" in expect:
        with pytest.raises(L.LLMRuntimeError) as info:
            L.resolve(config, **kwargs)
        assert info.value.code == expect["error"]
        return
    resolved = L.resolve(config, **kwargs)
    assert resolved.name == expect["profile"]
    assert resolved.model == expect.get("model")
    if "api_style" in expect:
        assert resolved.api_style == expect["api_style"]
    if expect.get("endpoint") is None:
        assert resolved.api_style == "none"
        return
    request = L.build_request(resolved, "hello")
    assert request.url == expect["endpoint"]
    auth_names = {"x-api-key", "authorization", (resolved.profile.auth.header_name or "").lower()}
    sent_auth = [k for k in request.header_names if k.lower() in auth_names]
    assert sent_auth == ([expect["auth_header"]] if expect["auth_header"] else [])
    assert [k for k, _ in resolved.extra_headers] == expect["extra_headers"]
    if "limits" in expect:
        limits = resolved.profile.limits
        assert {k: getattr(limits, k) for k in expect["limits"]} == expect["limits"]


@pytest.mark.parametrize("case", CONFORMANCE["invalid_configs"], ids=lambda c: c["name"])
def test_ac028_invalid_configs_fail_with_a_typed_error(case):
    with pytest.raises(L.LLMRuntimeError) as info:
        L.parse_profiles(case["config"])
    assert info.value.code == E.PROFILE_CONFIG_INVALID
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    rejected = not jsonschema.Draft7Validator(schema).is_valid(case["config"])
    assert rejected == case["schema_rejects"]   # the stdlib validator is never weaker than the schema


def test_ac028_quantmeridian_settings_parse_unchanged():
    config = L.load_profiles(FIXTURES / "quantmeridian_settings.json")
    assert config.default_profile == "anthropic-direct" and config.default_profile_env == "LLM_PROFILE_DEFAULT"
    assert {p.api_style for p in config.profiles.values()} == {"anthropic_messages", "openai_chat_completions", "none"}
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(json.loads((FIXTURES / "quantmeridian_settings.json").read_text()))


def test_vendored_schema_matches_its_recorded_digest():
    readme = (ROOT / "adapters" / "llm_runtime" / "README.md").read_text(encoding="utf-8")
    digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    assert digest in readme, "update the provenance digest in adapters/llm_runtime/README.md"


# --- stub provider servers -------------------------------------------------------------------------

class _Stub:
    """A local HTTP server that replays scripted (status, body, headers) responses and records requests."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                stub.requests.append({"path": self.path, "headers": dict(self.headers.items()), "body": json.loads(body)})
                status, payload, headers = stub.script.pop(0) if stub.script else (500, {}, {})
                data = json.dumps(payload).encode()
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # silence
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


ANTHROPIC_OK = {"id": "msg_1", "type": "message", "model": "claude-stub", "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "Plan: "}, {"type": "text", "text": "level of SOFR"}],
                "usage": {"input_tokens": 11, "output_tokens": 7}}
OPENAI_OK = {"id": "c1", "model": "gpt-stub", "choices": [{"index": 0, "finish_reason": "stop",
             "message": {"role": "assistant", "content": "level of SOFR"}}],
             "usage": {"prompt_tokens": 9, "completion_tokens": 4}}


def _profiles(*, fallback=None, retries=2, cap=20000):
    limits = {"max_output_tokens": 800, "timeout_ms": 5000, "max_retries": retries, "per_job_token_cap": cap,
              "daily_token_budget": None}
    return L.parse_profiles({
        "schema_version": "llm-profiles/1", "default_profile": "claude-gw",
        "profiles": {
            "claude-gw": {"enabled": True, "label": "Anthropic-compatible stub", "api_style": "anthropic_messages",
                          "base_url_env": "STUB_A_URL", "model": "claude-stub",
                          "auth": {"scheme": "provider_default", "credential_env": "STUB_KEY"},
                          "header_envs": {"X-Desk": "STUB_DESK"}, "limits": limits,
                          "data_classes": ["public_market_data"], "uses": ["interpreter", "narrator"],
                          "fallback_profile": fallback},
            "openai-gw": {"enabled": True, "label": "OpenAI-compatible stub", "api_style": "openai_chat_completions",
                          "base_url_env": "STUB_O_URL", "model": "gpt-stub",
                          "auth": {"scheme": "bearer", "credential_env": "STUB_KEY"}, "limits": limits,
                          "data_classes": ["public_market_data"], "uses": ["interpreter", "narrator"]},
            "deterministic": {"enabled": True, "label": "No LLM", "api_style": "none",
                              "data_classes": ["public_market_data"], "uses": ["interpreter", "narrator"]},
        }})


@pytest.fixture(autouse=True)
def _no_proxy_for_localhost(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


def _env(a=None, o=None):
    env = {"STUB_KEY": SECRET, "STUB_DESK": "desk-7"}
    if a:
        env["STUB_A_URL"] = a
    if o:
        env["STUB_O_URL"] = o
    return env


def _no_secret(*objects):
    for obj in objects:
        assert SECRET not in (obj if isinstance(obj, str) else repr(obj))


def test_ac028_anthropic_wire_format_and_usage():
    with _Stub([(200, ANTHROPIC_OK, {})]) as stub:
        out = L.complete("What is SOFR?", config=_profiles(), use="interpreter", system="Return a plan.",
                         data_classes=["public_market_data"], env=_env(a=stub.url))
    sent = stub.requests[0]
    assert sent["path"] == "/v1/messages"
    headers = {k.lower(): v for k, v in sent["headers"].items()}
    assert headers["x-api-key"] == SECRET and headers["anthropic-version"] == "2023-06-01"
    assert headers["x-desk"] == "desk-7" and "authorization" not in headers
    assert sent["body"] == {"model": "claude-stub", "max_tokens": 800, "system": "Return a plan.",
                            "messages": [{"role": "user", "content": "What is SOFR?"}]}
    assert out.output_text == "Plan: level of SOFR" and out.status == "completed"
    assert (out.usage.input_tokens, out.usage.output_tokens) == (11, 7) and out.model == "claude-stub"
    contract = out.to_contract()
    assert contract["provider_style"] == "anthropic_messages" and contract["model_profile"] == "claude-gw"
    _no_secret(out, contract)


def test_ac028_openai_wire_format():
    with _Stub([(200, OPENAI_OK, {})]) as stub:
        out = L.complete("What is SOFR?", config=_profiles(), use="narrator", requested="openai-gw",
                         system="Be brief.", env=_env(o=stub.url + "/v1"))
    sent = stub.requests[0]
    assert sent["path"] == "/v1/chat/completions"
    assert {k.lower(): v for k, v in sent["headers"].items()}["authorization"] == f"Bearer {SECRET}"
    assert sent["body"]["messages"][0] == {"role": "system", "content": "Be brief."}
    assert out.output_text == "level of SOFR" and out.usage.total == 13 and out.stop_reason == "stop"


def test_ac028_retries_honor_retry_after_then_succeed():
    waits = []
    script = [(529, {"type": "error", "error": {"type": "overloaded_error", "message": "busy " + SECRET}}, {"retry-after": "3"}),
              (500, {}, {}), (200, ANTHROPIC_OK, {})]
    with _Stub(script) as stub:
        out = L.complete("q", config=_profiles(retries=2), use="interpreter", env=_env(a=stub.url), sleep=waits.append)
    assert out.attempts == 3 and waits == [3.0, 1.0]


def test_ac028_non_retryable_status_fails_at_once_without_echoing_provider_text():
    bad_request = (400, {"type": "error", "error": {"type": "invalid_request_error", "message": SECRET}}, {})
    with _Stub([bad_request]) as stub, pytest.raises(L.LLMRuntimeError) as info:
        L.complete("q", config=_profiles(), use="interpreter", env=_env(a=stub.url), sleep=lambda s: None)
    err = info.value
    assert err.code == E.PROVIDER_ERROR and err.status == 400 and not err.retryable
    assert len(stub.requests) == 1 and "invalid_request_error" in str(err)
    _no_secret(str(err), err.args)


def test_ac028_fallback_profile_after_retries_records_fallback_from():
    with _Stub([(503, {}, {})] * 3) as bad, _Stub([(200, OPENAI_OK, {})]) as good:
        out = L.complete("q", config=_profiles(fallback="openai-gw"), use="interpreter",
                         env=_env(a=bad.url, o=good.url + "/v1"), sleep=lambda s: None)
    assert len(bad.requests) == 3 and out.profile == "openai-gw" and out.fallback_from == "claude-gw"


def test_ac028_refusal_is_typed_and_never_falls_back():
    refusal = {**ANTHROPIC_OK, "stop_reason": "refusal", "content": []}
    with _Stub([(200, refusal, {})]) as stub, _Stub([(200, OPENAI_OK, {})]) as other, \
            pytest.raises(L.LLMRuntimeError) as info:
        L.complete("q", config=_profiles(fallback="openai-gw"), use="interpreter",
                   env=_env(a=stub.url, o=other.url + "/v1"))
    assert info.value.code == E.REFUSAL and other.requests == []


def test_ac028_bad_response_shape_is_output_invalid():
    with _Stub([(200, {"content": [{"type": "image"}]}, {})]) as stub, pytest.raises(L.LLMRuntimeError) as info:
        L.complete("q", config=_profiles(), use="interpreter", env=_env(a=stub.url))
    assert info.value.code == E.OUTPUT_INVALID


def test_ac028_connection_failure_is_a_retryable_provider_error():
    with _Stub([]) as stub:
        dead = stub.url
    with pytest.raises(L.LLMRuntimeError) as info:
        L.complete("q", config=_profiles(retries=1), use="interpreter", env=_env(a=dead), sleep=lambda s: None)
    assert info.value.code == E.PROVIDER_ERROR and info.value.retryable


def test_ac028_token_cap_across_one_answer():
    budget = L.TokenBudget()
    with _Stub([(200, ANTHROPIC_OK, {})] * 2) as stub:
        config = _profiles(cap=810)
        L.complete("q", config=config, use="interpreter", env=_env(a=stub.url), budget=budget)
        assert budget.spent == 18
        with pytest.raises(L.LLMRuntimeError) as info:
            L.complete("q", config=config, use="interpreter", env=_env(a=stub.url), budget=budget)
    assert info.value.code == E.TOKEN_CAP_EXCEEDED and len(stub.requests) == 1


def test_ac028_none_profile_is_skipped_without_a_request():
    out = L.complete("q", config=_profiles(), use="interpreter", requested="deterministic", env={})
    assert out.status == "skipped" and out.output_text is None and out.api_style == "none"


def test_ac028_credentials_never_appear_in_repr_or_errors():
    resolved = L.resolve(_profiles(), use="interpreter", env=_env(a="http://127.0.0.1:9"))
    request = L.build_request(resolved, "q")
    _no_secret(resolved, request, request.url)
    with pytest.raises(L.LLMRuntimeError) as info:
        L.resolve(_profiles(), use="interpreter", env={"STUB_A_URL": "http://x", "STUB_DESK": "d"})
    assert "STUB_KEY" in str(info.value)      # names the variable, never a value


def test_ac019_nl_analytics_never_imports_the_network_adapter():
    for path in sorted((ROOT / "src" / "quantsmith" / "nl_analytics").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any("llm_runtime" in n for n in names), path


def test_only_transport_opens_connections():
    pkg = ROOT / "src" / "quantsmith" / "adapters" / "llm_runtime"
    for path in sorted(pkg.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if path.name != "transport.py":
            assert "urllib.request" not in source and "socket" not in source and "http.client" not in source, path


# --- end to end: llm_runtime -> nl_analytics (0080 T-025) ------------------------------------------

def _nl_layer_and_rows():
    from quantsmith.pipelines.metrics_semantic_layer import Fact, SemanticLayer
    layer = SemanticLayer()
    layer.define(name="funding_cost", owner="treasury", grain="day", dimensions=("desk",), source="cost", agg="sum")
    rows = [Fact(period=p, dims={"desk": d}, measures={"cost": float(p)}) for p in range(6, 11) for d in ("rates", "fx")]
    return layer, rows


def test_end_to_end_profile_backed_interpreter_and_narrator():
    from quantsmith.nl_analytics.interpret import (
        InterpretContext,
        KeywordInterpreter,
        LLMInterpreter,
    )
    from quantsmith.nl_analytics.narrate import LLMNarrator
    from quantsmith.nl_analytics.respond import AnswerContext, answer

    plan = {"metric": "funding_cost", "dimensions": ["desk"], "filters": [],
            "window": {"start_period": 6, "end_period": 10, "grain": "day"}, "comparison": None, "rank": None}
    reply_plan = {**ANTHROPIC_OK, "content": [{"type": "text", "text": json.dumps(plan)}]}
    reply_text = {**ANTHROPIC_OK, "content": [{"type": "text", "text": "Funding cost was reported by desk."}]}
    seen = []
    with _Stub([(200, reply_plan, {}), (200, reply_text, {})]) as stub:
        budget = L.TokenBudget()
        common = {"config": _profiles(), "data_classes": ["public_market_data"], "budget": budget,
                  "env": _env(a=stub.url), "on_completion": seen.append}
        layer, rows = _nl_layer_and_rows()
        ctx = AnswerContext(
            layer=layer, reader=lambda p: rows, as_of=10,
            interpret_context=InterpretContext(today_period=10, default_window_periods=5),
            interpreter=LLMInterpreter(L.as_callable(use="interpreter", **common), fallback=KeywordInterpreter()),
            narrator=LLMNarrator(L.as_callable(use="narrator", **common)),
        )
        response = answer("how did funding cost move by desk", ctx)
    assert response.status == "answered" and "by desk" in response.plan_echo
    assert response.narrative == "Funding cost was reported by desk." and response.narrative_mode == "llm/1"
    assert [c.profile for c in seen] == ["claude-gw", "claude-gw"] and budget.spent == 36
    assert len(stub.requests) == 2


def test_end_to_end_no_llm_profile_falls_back_to_keyword_and_template():
    from quantsmith.nl_analytics.interpret import (
        InterpretContext,
        KeywordInterpreter,
        LLMInterpreter,
    )
    from quantsmith.nl_analytics.narrate import LLMNarrator
    from quantsmith.nl_analytics.respond import AnswerContext, answer

    common = {"config": _profiles(), "requested": "deterministic", "env": {}}
    layer, rows = _nl_layer_and_rows()
    ctx = AnswerContext(
        layer=layer, reader=lambda p: rows, as_of=10,
        interpret_context=InterpretContext(today_period=10, default_window_periods=5),
        interpreter=LLMInterpreter(L.as_callable(use="interpreter", **common), fallback=KeywordInterpreter()),
        narrator=LLMNarrator(L.as_callable(use="narrator", **common)),
    )
    response = answer("funding cost by desk", ctx)
    assert response.status == "answered" and response.narrative_mode == "template"
    assert any("unavailable" in c for c in response.caveats)
