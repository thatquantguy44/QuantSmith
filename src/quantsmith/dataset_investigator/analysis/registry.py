"""The analysis tool registry. Spec ``0099`` (REQ-004, REQ-005).

Only functions registered here can run, and only with parameters that validate
against the tool's Pydantic parameter model and whose column parameters name
columns of an eligible role. Every execution is recorded as a
:class:`~.models.ToolExecution` whose id is a hash of the tool, version,
parameters, input fingerprint, and sample size — identical calls share an id,
so reruns line up exactly (NFR-001).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Type,
)

import pandas as pd
from pydantic import BaseModel, ConfigDict, ValidationError

from .models import ToolExecution
from .utils import jsonable, sha256_json


class ToolError(ValueError):
    """An unregistered tool, invalid parameters, or an ineligible column."""


class Params(BaseModel):
    """Base class for tool parameter models (unknown fields are rejected)."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolContext:
    """What a tool may know besides the data: roles, PII flags, and limits."""

    roles: Mapping[str, str]
    pii: FrozenSet[str] = frozenset()
    min_cell: int = 10
    min_n: int = 30
    alpha: float = 0.05
    seed: int = 42
    as_of: Optional[str] = None
    positive: Optional[str] = None
    near_constant: float = 0.99
    max_numeric_columns: int = 30

    def columns(self, roles: Iterable[str], *, allow_pii: bool = False) -> List[str]:
        wanted = set(roles)
        return [c for c, r in self.roles.items() if r in wanted and (allow_pii or c not in self.pii)]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    category: str
    version: str
    module: str
    function: str
    params_model: Type[Params]
    columns: Mapping[str, FrozenSet[str]]
    reveals_values: bool
    expensive: bool
    description: str
    fn: Callable[..., Dict[str, Any]] = field(compare=False, repr=False)

    def catalog_entry(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "description": self.description,
            "params_schema": self.params_model.model_json_schema(),
            "column_params": {k: sorted(v) for k, v in sorted(self.columns.items())},
        }


TOOL_REGISTRY: Dict[str, ToolSpec] = {}


def analysis_tool(
    *,
    name: str,
    category: str,
    version: str,
    params: Type[Params],
    columns: Optional[Mapping[str, Iterable[str]]] = None,
    reveals_values: bool = False,
    expensive: bool = False,
) -> Callable[[Callable[..., Dict[str, Any]]], Callable[..., Dict[str, Any]]]:
    """Register ``fn(df, params, ctx) -> dict`` as an analysis tool.

    ``columns`` maps each parameter that names a column (or a list of columns)
    to the roles it accepts. ``reveals_values`` marks tools whose output names
    a column's values (group labels), which therefore refuse PII columns.
    """

    def wrap(fn: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
        if name in TOOL_REGISTRY:
            raise ToolError(f"tool {name!r} registered twice")
        TOOL_REGISTRY[name] = ToolSpec(
            name=name, category=category, version=version,
            module=fn.__module__.rsplit(".", 1)[-1], function=fn.__name__,
            params_model=params,
            columns={k: frozenset(v) for k, v in (columns or {}).items()},
            reveals_values=reveals_values, expensive=expensive,
            description=(fn.__doc__ or "").strip().split("\n\n")[0].replace("\n", " "),
            fn=fn,
        )
        return fn

    return wrap


def spec(name: str) -> ToolSpec:
    if name not in TOOL_REGISTRY:
        raise ToolError(f"unregistered tool {name!r}; registered: {sorted(TOOL_REGISTRY)}")
    return TOOL_REGISTRY[name]


def validate_params(name: str, params: Mapping[str, Any], ctx: ToolContext) -> Params:
    """Validate ``params`` for tool ``name`` against its model, roles, and PII flags."""
    s = spec(name)
    try:
        p = s.params_model.model_validate(dict(params))
    except ValidationError as exc:
        raise ToolError(f"invalid parameters for {name}: {exc.errors(include_url=False)}") from exc
    for pname, allowed in s.columns.items():
        value = getattr(p, pname, None)
        if value is None:
            continue
        for col in ([value] if isinstance(value, str) else list(value)):
            if col not in ctx.roles:
                raise ToolError(f"{name}: column {col!r} does not exist")
            role = ctx.roles[col]
            if role not in allowed:
                raise ToolError(f"{name}: column {col!r} has role {role!r}; {pname} accepts {sorted(allowed)}")
            if s.reveals_values and col in ctx.pii:
                raise ToolError(f"{name}: column {col!r} is flagged PII and this tool reports its values")
    return p


def sample_for(s: ToolSpec, df: pd.DataFrame, *, threshold: int, n: int, seed: int) -> Tuple[pd.DataFrame, Optional[int]]:
    """Rows an expensive tool runs on: all of them, or a seeded sample above ``threshold``."""
    if not s.expensive or len(df) <= threshold:
        return df, None
    sampled = df.sample(n=min(n, len(df)), random_state=seed).sort_index()
    return sampled, len(sampled)


def execution_id_for(name: str, p: Params, input_fingerprint: str, sampled: Optional[int]) -> str:
    s = spec(name)
    return "E" + sha256_json({
        "tool": s.name, "version": s.version, "params": p.model_dump(mode="json"),
        "input": input_fingerprint, "sampled_rows": sampled,
    })[:12]


def planned_execution_id(name: str, df: pd.DataFrame, params: Mapping[str, Any], ctx: ToolContext, *,
                         input_fingerprint: str, sample_threshold: int = 200_000,
                         expensive_sample: int = 50_000) -> str:
    """The id :func:`execute` would give this call, without running it."""
    s = spec(name)
    p = validate_params(name, params, ctx)
    sampled = None if (not s.expensive or len(df) <= sample_threshold) else min(expensive_sample, len(df))
    return execution_id_for(name, p, input_fingerprint, sampled)


def execute(
    name: str,
    df: pd.DataFrame,
    params: Mapping[str, Any],
    ctx: ToolContext,
    *,
    input_fingerprint: str,
    origin: str = "plan",
    sample_threshold: int = 200_000,
    expensive_sample: int = 50_000,
) -> Tuple[ToolExecution, Dict[str, Any]]:
    """Validate and run one registered tool; return its execution record and JSON-safe result."""
    s = spec(name)
    p = validate_params(name, params, ctx)
    data, sampled = sample_for(s, df, threshold=sample_threshold, n=expensive_sample, seed=ctx.seed)
    started = time.perf_counter()
    result = jsonable(s.fn(data, p, ctx))
    duration = time.perf_counter() - started
    if not isinstance(result, dict):
        raise ToolError(f"{name} returned {type(result).__name__}, not a dict")
    result.setdefault("tests", [])
    normalized = p.model_dump(mode="json")
    execution_id = execution_id_for(name, p, input_fingerprint, sampled)
    record = ToolExecution(
        execution_id=execution_id, tool=s.name, version=s.version, module=s.module, category=s.category,
        params=normalized, input_fingerprint=input_fingerprint, sampled_rows=sampled,
        result_sha256=sha256_json(result), duration_s=round(duration, 6), origin=origin,
    )
    return record, result


def catalog() -> List[Dict[str, Any]]:
    return [TOOL_REGISTRY[k].catalog_entry() for k in sorted(TOOL_REGISTRY)]
