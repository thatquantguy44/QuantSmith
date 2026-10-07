"""Pydantic models for one investigation. Spec ``0099``.

Everything an investigation records is one of these models, so the whole state
round-trips through JSON (``InvestigationState.model_dump_json``) and the
command-line steps can hand it from one call to the next.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

SPEC_VERSION = "0099.1"

ROLES = (
    "identifier", "entity_identifier", "timestamp", "continuous_numeric", "discrete_numeric",
    "categorical", "boolean", "binary_target", "multiclass_target", "free_text", "constant",
)
STATUSES = ("VALIDATED", "WEAK_EVIDENCE", "INCONCLUSIVE", "REJECTED")
HYPOTHESIS_STATUSES = ("untested", "supported", "rejected", "inconclusive", "invalid")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Weights(_Model):
    M: float = 0.35
    S: float = 0.30
    P: float = 0.15
    A: float = 0.20


class Config(_Model):
    """What a run is configured with; saved with the run so a rerun matches."""

    target: Optional[str] = None
    timestamp: Optional[str] = None
    roles: Dict[str, str] = Field(default_factory=dict)
    pii: List[str] = Field(default_factory=list)
    positive: Optional[str] = None
    seed: int = 42
    as_of: Optional[str] = None
    min_cell: int = 10
    min_n: int = 30
    alpha: float = 0.05
    top_n: int = 10
    weights: Weights = Field(default_factory=Weights)
    sample_threshold: int = 200_000
    expensive_sample: int = 20_000
    max_rounds: int = 3
    max_tool_calls: int = 25
    max_numeric_columns: int = 30
    near_constant: float = 0.99
    missing_warn: float = 0.05

    @field_validator("top_n")
    @classmethod
    def _top_n_bounded(cls, v: int) -> int:
        if not 5 <= v <= 15:
            raise ValueError("top_n must be between 5 and 15")
        return v

    @field_validator("roles")
    @classmethod
    def _roles_known(cls, v: Dict[str, str]) -> Dict[str, str]:
        bad = {c: r for c, r in v.items() if r not in ROLES}
        if bad:
            raise ValueError(f"unknown role(s): {bad}; use one of {list(ROLES)}")
        return v


class DatasetInfo(_Model):
    source: str
    format: str
    file_sha256: Optional[str] = None
    content_sha256: str
    rows: int
    columns: int
    column_names: List[str]


class ColumnProfile(_Model):
    name: str
    dtype: str
    role: str
    pii: bool = False
    overridden: bool = False
    n_unique: int
    unique_ratio: float
    missing_pct: float
    evidence: Dict[str, Any] = Field(default_factory=dict)


class PlannedAnalysis(_Model):
    analysis: str
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)
    reason: str


class SkippedAnalysis(_Model):
    analysis: str
    reason: str


class Plan(_Model):
    source: Literal["rules", "model"] = "rules"
    analyses: List[PlannedAnalysis] = Field(default_factory=list)
    skipped: List[SkippedAnalysis] = Field(default_factory=list)


class ToolExecution(_Model):
    execution_id: str
    tool: str
    version: str
    module: str
    category: str
    params: Dict[str, Any]
    input_fingerprint: str
    sampled_rows: Optional[int] = None
    result_sha256: str
    duration_s: float = 0.0
    origin: Literal["plan", "hypothesis", "model", "validation"] = "plan"


class Score(_Model):
    I: float
    M: float
    S: float
    P: float
    A: float


class Finding(_Model):
    key: str
    finding_id: Optional[str] = None
    kind: str
    family: str
    quality: bool = False
    claim: str
    subject: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any]
    method: str
    module: str
    function: str
    tool: str
    version: str
    params: Dict[str, Any]
    execution_id: str
    test: Optional[str] = None
    p_value: Optional[float] = None
    p_adjusted: Optional[float] = None
    n: int = 0
    magnitude: float = 0.0
    prevalence: float = 0.0
    score: Optional[Score] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None
    status: Optional[Literal["VALIDATED", "WEAK_EVIDENCE", "INCONCLUSIVE", "REJECTED"]] = None
    issues: List[str] = Field(default_factory=list)
    merged_into: Optional[str] = None
    origin: Literal["rules", "model"] = "rules"


class Condition(_Model):
    path: str
    op: Literal[">=", ">", "<=", "<", "==", "!="]
    value: Union[float, int, str, bool]


class DecisionRule(_Model):
    supported: List[Condition]
    rejected: List[Condition]


class Hypothesis(_Model):
    hypothesis_id: str
    round: int
    template: Optional[str] = None
    from_findings: List[str] = Field(default_factory=list)
    parent: Optional[str] = None
    statement: str
    tool: str
    params: Dict[str, Any]
    prediction: str
    decision_rule: DecisionRule
    origin: Literal["template", "model"] = "template"
    execution_id: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["untested", "supported", "rejected", "inconclusive", "invalid"] = "untested"
    explanation: str = ""


class Question(_Model):
    question_id: str
    text: str
    from_findings: List[str] = Field(default_factory=list)
    from_hypotheses: List[str] = Field(default_factory=list)
    tool: Optional[str] = None
    needs_new_tool: bool = False


class ModelInputs(_Model):
    """What language-model roles contributed, recorded so a rerun can replay it with no model (REQ-014).

    ``steps`` keeps the order of the hypothesis stage: ``{"templates": true}`` for the templated loop,
    ``{"proposals": [...]}`` for one batch of investigator proposals exactly as submitted.
    """

    analyses: Optional[List[str]] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    reviews: List[Dict[str, Any]] = Field(default_factory=list)
    narrative: Optional[str] = None


class InvestigationState(_Model):
    spec_version: str = SPEC_VERSION
    run_id: str
    created_at: Optional[str] = None
    config: Config
    dataset: DatasetInfo
    columns: List[ColumnProfile]
    plan: Optional[Plan] = None
    executions: List[ToolExecution] = Field(default_factory=list)
    results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    findings: List[Finding] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    questions: List[Question] = Field(default_factory=list)
    narrative: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    model_inputs: ModelInputs = Field(default_factory=ModelInputs)

    def roles(self) -> Dict[str, str]:
        return {c.name: c.role for c in self.columns}

    def pii(self) -> set:
        return {c.name for c in self.columns if c.pii}

    def execution(self, execution_id: str) -> ToolExecution:
        for e in self.executions:
            if e.execution_id == execution_id:
                return e
        raise KeyError(execution_id)
