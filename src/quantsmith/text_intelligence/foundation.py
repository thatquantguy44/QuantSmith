"""Governed NLP/LLM and quant text-intelligence contracts for spec 0071.

The module is deliberately standard-library only.  It validates immutable
corpus snapshots, transformation lineage, provider-neutral model capabilities,
embedding/index evidence, structured task results, text-derived signals, and
text-specific evaluation suites.  A text run is not a second orchestration
system: every manifest points to one spec-0070 run envelope and reuses its audit
ledger and replay command.

No provider, vector database, MCP server, or training runtime is called here.
Those dependencies are represented by versioned metadata and optional fixtures.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quantsmith.orchestration import (
    ACCESS_LEVELS,
    Finding,
    ReplayReport,
    ValidationReport,
    load_json,
    load_jsonl,
    replay_envelope_file,
    sha256_file,
    validate_audit_events,
    validate_run_envelope_file,
)

SCHEMA_VERSION_MANIFEST = "quantsmith.text_intelligence.manifest.v1"
SCHEMA_VERSION_CORPUS = "quantsmith.text_intelligence.corpus.v1"
SCHEMA_VERSION_TRANSFORMS = "quantsmith.text_intelligence.transforms.v1"
SCHEMA_VERSION_CAPABILITIES = "quantsmith.text_intelligence.capabilities.v1"
SCHEMA_VERSION_EMBEDDINGS = "quantsmith.text_intelligence.embeddings.v1"
SCHEMA_VERSION_INDEX = "quantsmith.text_intelligence.index.v1"
SCHEMA_VERSION_TRAINING = "quantsmith.text_intelligence.training.v1"
SCHEMA_VERSION_RESULTS = "quantsmith.text_intelligence.results.v1"
SCHEMA_VERSION_SIGNALS = "quantsmith.text_intelligence.signals.v1"
SCHEMA_VERSION_EVALUATION = "quantsmith.text_intelligence.evaluation.v1"

ALLOWED_SPLITS = ("train", "validation", "test", "retrieval", "backtest", "none")
ALLOWED_ACCESS_LEVELS = ACCESS_LEVELS
_ACCESS_RANK = {name: rank for rank, name in enumerate(ALLOWED_ACCESS_LEVELS)}
ALLOWED_SECURITY_STATUSES = ("accepted", "quarantined", "excluded")
ALLOWED_SUPERSESSION_STATES = ("current", "superseded", "withdrawn")
ALLOWED_REPLAY_CLASSES = (
    "deterministic",
    "pinned_local",
    "fixture_backed",
    "non_reproducible_external",
)
ALLOWED_OPERATIONS = (
    "generation",
    "embedding",
    "rerank",
    "tokenize",
    "train_adapt",
    "lexical",
)
ALLOWED_TASK_TYPES = (
    "classification",
    "entity_extraction",
    "event_extraction",
    "value_extraction",
    "sentiment_stance",
    "theme_detection",
    "semantic_retrieval",
    "reranking",
    "summarization",
    "evidence_synthesis",
)
ALLOWED_RESULT_STATUSES = ("supported", "abstained", "unsupported", "rejected")
ALLOWED_TRANSFORMS = (
    "extraction",
    "ocr_metadata",
    "normalization",
    "redaction",
    "language_detection",
    "chunking",
    "deduplication",
    "labeling",
    "filtering",
)
REQUIRED_EVALUATION_LAYERS = (
    "corpus_integrity",
    "temporal_correctness",
    "duplicate_overlap",
    "benchmark_contamination",
    "task_quality",
    "retrieval_quality",
    "reranking_quality",
    "calibration",
    "citation_coverage",
    "faithfulness",
    "robustness",
    "prompt_injection",
    "unsafe_tool_use",
    "privacy_access",
    "latency_cost",
    "signal_stability",
)
REQUIRED_TEXT_AUDIT_EVENTS = (
    "corpus_selection",
    "text_transformation",
    "model_invocation",
    "task_execution",
    "evaluation",
    "human_review",
    "signal_publication",
)
RETRIEVAL_TEXT_AUDIT_EVENTS = (
    "embedding_creation",
    "index_creation",
    "retrieval",
    "citation",
)

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bghp_[0-9A-Za-z]{30,}\b")),
)
_INJECTION_PATTERNS = (
    ("ignore-instructions", re.compile(r"\bignore (all |any |the )?(previous|prior) instructions?\b", re.IGNORECASE)),
    ("system-prompt-request", re.compile(r"\b(system prompt|developer message)\b", re.IGNORECASE)),
    ("undeclared-tool-request", re.compile(r"\b(call|invoke|execute|use) (the )?(tool|shell|terminal|plugin)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class TextReplayReport:
    """A spec-0071 replay report backed by the authoritative 0070 replay."""

    manifest_id: str
    status: str
    orchestration: ReplayReport
    artifact_hashes: Mapping[str, str]
    findings: tuple[Mapping[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "status": self.status,
            "orchestration": self.orchestration.to_dict(),
            "artifact_hashes": dict(self.artifact_hashes),
            "findings": list(self.findings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass(frozen=True)
class AgentTextIntelligenceView:
    """Provider-neutral, access-filtered evidence delivered to agent consumers."""

    manifest_id: str
    run_id: str
    consumer: str
    decision_time: str
    task_schema_version: str
    task_results: tuple[Mapping[str, Any], ...]
    signals: tuple[Mapping[str, Any], ...]
    source_spans: tuple[Mapping[str, Any], ...]
    orchestration: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "run_id": self.run_id,
            "consumer": self.consumer,
            "decision_time": self.decision_time,
            "task_schema_version": self.task_schema_version,
            "task_results": list(self.task_results),
            "signals": list(self.signals),
            "source_spans": list(self.source_spans),
            "orchestration": dict(self.orchestration),
        }


def canonical_hash(value: Any, *, omit_keys: Sequence[str] = ()) -> str:
    """Hash a JSON-compatible value using a canonical serialization."""

    if isinstance(value, Mapping):
        value = {key: item for key, item in value.items() if key not in omit_keys}
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def discover_manifests(root: str | Path) -> tuple[Path, ...]:
    """Discover text-intelligence manifests beneath a file or directory."""

    root = Path(root)
    if root.is_file():
        return (root,)
    if not root.exists():
        return ()
    return tuple(sorted(root.rglob("text_intelligence_manifest.json")))


def validate_discovered_manifests(root: str | Path) -> ValidationReport:
    """Deep-validate every discovered text-intelligence evidence bundle."""

    reports = [validate_text_intelligence_manifest_file(path) for path in discover_manifests(root)]
    findings = tuple(finding for report in reports for finding in report.findings)
    counts: dict[str, int] = {"manifests": len(reports)}
    for report in reports:
        for key, count in report.counts.items():
            if key == "manifests":
                continue
            counts[key] = counts.get(key, 0) + count
    return ValidationReport(findings=findings, counts=counts)


def validate_text_intelligence_manifest_file(path: str | Path) -> ValidationReport:
    """Deep-validate a manifest, all domain artifacts, and its 0070 envelope."""

    path = Path(path)
    try:
        manifest = load_json(path)
    except (OSError, ValueError) as exc:
        return ValidationReport(
            findings=(Finding(str(path), "manifest", "load", str(exc)),),
            counts={"manifests": 1},
        )
    if not isinstance(manifest, Mapping):
        return ValidationReport(
            findings=(Finding(str(path), "manifest", "type", "manifest must be an object"),),
            counts={"manifests": 1},
        )

    base = path.parent
    repo_root = _find_repo_root(path)
    report = validate_text_intelligence_manifest(manifest, source=str(path))
    findings = list(report.findings)
    loaded: dict[str, Any] = {}

    singular_refs = (
        "corpus_snapshot",
        "transform_chain",
        "model_capabilities",
        "task_results",
        "evaluation_suite",
    )
    optional_refs = ("embedding_artifact", "index_snapshot", "training_run")
    for name in singular_refs + optional_refs:
        ref = manifest.get(name)
        if name in optional_refs and ref is None:
            continue
        ref_path = _validate_ref(ref, base, str(path), name, findings)
        if ref_path is not None and ref_path.exists():
            try:
                loaded[name] = load_json(ref_path)
            except (OSError, ValueError) as exc:
                _add(findings, str(path), name, "load", str(exc))

    signal_refs = manifest.get("signal_artifacts", [])
    loaded_signals: list[Mapping[str, Any]] = []
    if _is_list(signal_refs):
        for index, ref in enumerate(signal_refs):
            ref_path = _validate_ref(
                ref,
                base,
                str(path),
                f"signal_artifacts[{index}]",
                findings,
            )
            if ref_path is not None and ref_path.exists():
                try:
                    value = load_json(ref_path)
                    if isinstance(value, Mapping):
                        loaded_signals.append(value)
                    else:
                        _add(findings, str(path), f"signal_artifacts[{index}]", "type", "signal artifact must be an object")
                except (OSError, ValueError) as exc:
                    _add(findings, str(path), f"signal_artifacts[{index}]", "load", str(exc))
    else:
        _add(findings, str(path), "signal_artifacts", "type", "signal_artifacts must be a list")

    corpus = loaded.get("corpus_snapshot", {})
    transforms = loaded.get("transform_chain", {})
    capabilities = loaded.get("model_capabilities", {})
    task_results = loaded.get("task_results", {})
    evaluation = loaded.get("evaluation_suite", {})
    embeddings = loaded.get("embedding_artifact")
    index_snapshot = loaded.get("index_snapshot")
    training = loaded.get("training_run")

    reports: list[ValidationReport] = []
    if isinstance(corpus, Mapping):
        reports.append(
            validate_corpus_snapshot(
                corpus,
                base_dir=base,
                repo_root=repo_root,
                source=f"{path}:corpus_snapshot",
            )
        )
    if isinstance(transforms, Mapping):
        reports.append(validate_transform_chain(transforms, base_dir=base, source=f"{path}:transform_chain"))
    if isinstance(capabilities, Mapping):
        reports.append(validate_model_capabilities(capabilities, base_dir=base, source=f"{path}:model_capabilities"))
    if isinstance(embeddings, Mapping):
        reports.append(
            validate_embedding_and_index(
                embeddings,
                index_snapshot if isinstance(index_snapshot, Mapping) else None,
                corpus=corpus if isinstance(corpus, Mapping) else {},
                capabilities=capabilities if isinstance(capabilities, Mapping) else {},
                source=f"{path}:embeddings",
            )
        )
    elif index_snapshot is not None:
        _add(findings, str(path), "index_snapshot", "missing-dependency", "index snapshot requires an embedding artifact")
    if isinstance(training, Mapping):
        reports.append(validate_training_run(training, base_dir=base, source=f"{path}:training_run"))
    if isinstance(task_results, Mapping):
        reports.append(
            validate_task_results(
                task_results,
                corpus=corpus if isinstance(corpus, Mapping) else {},
                capabilities=capabilities if isinstance(capabilities, Mapping) else {},
                index_snapshot=index_snapshot if isinstance(index_snapshot, Mapping) else None,
                source=f"{path}:task_results",
            )
        )
    for index, signals in enumerate(loaded_signals):
        reports.append(
            validate_signal_artifact(
                signals,
                corpus=corpus if isinstance(corpus, Mapping) else {},
                task_results=task_results if isinstance(task_results, Mapping) else {},
                source=f"{path}:signal_artifacts[{index}]",
            )
        )
    if isinstance(evaluation, Mapping):
        reports.append(validate_evaluation_suite(evaluation, source=f"{path}:evaluation_suite"))
    for nested_report in reports:
        findings.extend(nested_report.findings)

    envelope_path = _validate_orchestration_ref(
        manifest.get("orchestration"),
        base,
        str(path),
        findings,
    )
    if envelope_path is not None and envelope_path.exists():
        orchestration_report = validate_run_envelope_file(envelope_path)
        findings.extend(orchestration_report.findings)
        _validate_0070_integration(
            manifest=manifest,
            manifest_path=path,
            envelope_path=envelope_path,
            findings=findings,
        )

    counts = {
        "manifests": 1,
        "documents": len(corpus.get("documents", [])) if isinstance(corpus, Mapping) and _is_list(corpus.get("documents")) else 0,
        "spans": len(corpus.get("spans", [])) if isinstance(corpus, Mapping) and _is_list(corpus.get("spans")) else 0,
        "task_results": len(task_results.get("results", [])) if isinstance(task_results, Mapping) and _is_list(task_results.get("results")) else 0,
        "signals": sum(len(item.get("signals", [])) for item in loaded_signals if _is_list(item.get("signals"))),
    }
    return ValidationReport(tuple(findings), counts)


def validate_text_intelligence_manifest(
    manifest: Mapping[str, Any],
    *,
    source: str = "<text_intelligence_manifest>",
) -> ValidationReport:
    """Validate the shallow, provider-neutral spec-0071 manifest contract."""

    findings: list[Finding] = []
    required = (
        "schema_version",
        "manifest_id",
        "run_id",
        "purpose",
        "decision_time",
        "orchestration",
        "corpus_snapshot",
        "transform_chain",
        "model_capabilities",
        "task_schema_version",
        "task_results",
        "evaluation_suite",
        "signal_artifacts",
        "audit_correlation_id",
        "downstream_consumers",
        "review",
        "replay_class",
    )
    _require_fields(manifest, required, source, findings)
    _expect_schema(manifest, SCHEMA_VERSION_MANIFEST, source, findings)
    for key in ("manifest_id", "run_id", "purpose", "task_schema_version", "audit_correlation_id"):
        _require_string(manifest, key, source, findings)
    _expect_timestamp(manifest.get("decision_time"), source, "decision_time", findings)
    _expect_member(manifest.get("replay_class"), ALLOWED_REPLAY_CLASSES, source, "replay_class", findings)
    _expect_non_empty_list(manifest.get("downstream_consumers"), source, "downstream_consumers", findings)
    _validate_review(manifest.get("review"), source, "review", findings, material=True)
    return ValidationReport(tuple(findings), {"manifests": 1})


def validate_corpus_snapshot(
    corpus: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    repo_root: str | Path | None = None,
    source: str = "<corpus_snapshot>",
) -> ValidationReport:
    """Validate immutable documents/spans, source policy, PIT, and split safety."""

    findings: list[Finding] = []
    base = Path(base_dir)
    root = Path(repo_root) if repo_root else _find_repo_root(base)
    required = (
        "schema_version",
        "snapshot_id",
        "created_at",
        "decision_cutoff",
        "immutable",
        "source_policy",
        "documents",
        "spans",
        "deduplication_policy",
        "split_policy",
        "exclusions",
        "snapshot_hash",
    )
    _require_fields(corpus, required, source, findings)
    _expect_schema(corpus, SCHEMA_VERSION_CORPUS, source, findings)
    _require_string(corpus, "snapshot_id", source, findings)
    _expect_timestamp(corpus.get("created_at"), source, "created_at", findings)
    cutoff = _expect_timestamp(corpus.get("decision_cutoff"), source, "decision_cutoff", findings)
    if corpus.get("immutable") is not True:
        _add(findings, source, "immutable", "immutable-required", "corpus snapshot must be immutable")
    expected_snapshot_hash = canonical_hash(corpus, omit_keys=("snapshot_hash",))
    if corpus.get("snapshot_hash") != expected_snapshot_hash:
        _add(findings, source, "snapshot_hash", "hash-mismatch", "snapshot_hash does not match canonical corpus payload")

    source_policy = corpus.get("source_policy")
    registered_sources: set[str] = set()
    allowed_licenses: set[str] = set()
    if isinstance(source_policy, Mapping):
        registered = source_policy.get("registered_source_ids")
        if _expect_non_empty_list(registered, source, "source_policy.registered_source_ids", findings):
            registered_sources = {str(item) for item in registered}
            for source_id in registered_sources:
                if not _source_exists(root, source_id):
                    _add(findings, source, "source_policy.registered_source_ids", "unregistered-source", f"source {source_id!r} is not registered under sources/")
        licenses = source_policy.get("allowed_license_classes")
        if _expect_non_empty_list(licenses, source, "source_policy.allowed_license_classes", findings):
            allowed_licenses = {str(item) for item in licenses}
        if source_policy.get("credentials_by_reference") is not True:
            _add(findings, source, "source_policy.credentials_by_reference", "credential-policy", "credentials_by_reference must be true")
        if source_policy.get("raw_credentials_prohibited") is not True:
            _add(findings, source, "source_policy.raw_credentials_prohibited", "credential-policy", "raw_credentials_prohibited must be true")
    else:
        _add(findings, source, "source_policy", "type", "source_policy must be an object")

    documents = corpus.get("documents")
    spans = corpus.get("spans")
    document_map: dict[str, Mapping[str, Any]] = {}
    if _expect_non_empty_list(documents, source, "documents", findings):
        for index, document in enumerate(documents):
            field_name = f"documents[{index}]"
            if not isinstance(document, Mapping):
                _add(findings, source, field_name, "type", "document must be an object")
                continue
            required_doc = (
                "document_id",
                "source_id",
                "content_ref",
                "source_locator",
                "publication_time",
                "event_time",
                "effective_time",
                "ingestion_time",
                "observation_time",
                "available_at",
                "revision_group_id",
                "revision_number",
                "supersession_state",
                "language",
                "content_type",
                "access_level",
                "entitlement",
                "license_class",
                "split",
                "canonical_group_id",
                "near_duplicate_group_id",
                "security_status",
            )
            _require_fields(document, required_doc, source, findings, prefix=field_name)
            document_id = _string(document.get("document_id"))
            if not document_id:
                _add(findings, source, f"{field_name}.document_id", "required", "document_id is required")
            elif document_id in document_map:
                _add(findings, source, f"{field_name}.document_id", "duplicate", f"duplicate document_id {document_id!r}")
            else:
                document_map[document_id] = document
            source_id = _string(document.get("source_id"))
            if source_id not in registered_sources:
                _add(findings, source, f"{field_name}.source_id", "unregistered-source", f"source {source_id!r} is not allowed by the snapshot")
            _expect_member(document.get("access_level"), ALLOWED_ACCESS_LEVELS, source, f"{field_name}.access_level", findings)
            if not _string(document.get("entitlement")):
                _add(findings, source, f"{field_name}.entitlement", "required", "document entitlement is required")
            if _contains_secret(document):
                _add(findings, source, field_name, "raw-credential", "document metadata contains a token-shaped secret")
            if allowed_licenses and document.get("license_class") not in allowed_licenses:
                _add(findings, source, f"{field_name}.license_class", "unlicensed", "document license is not eligible for this corpus")
            _expect_member(document.get("split"), ALLOWED_SPLITS, source, f"{field_name}.split", findings)
            _expect_member(document.get("supersession_state"), ALLOWED_SUPERSESSION_STATES, source, f"{field_name}.supersession_state", findings)
            _expect_member(document.get("security_status"), ALLOWED_SECURITY_STATUSES, source, f"{field_name}.security_status", findings)
            if document.get("security_status") != "accepted":
                _add(findings, source, f"{field_name}.security_status", "quarantined-in-corpus", "only accepted documents may enter a corpus snapshot")
            if not isinstance(document.get("revision_number"), int) or document.get("revision_number", 0) < 1:
                _add(findings, source, f"{field_name}.revision_number", "revision", "revision_number must be a positive integer")
            timestamps = []
            for name in ("publication_time", "event_time", "effective_time", "ingestion_time", "observation_time", "available_at"):
                parsed = _expect_timestamp(document.get(name), source, f"{field_name}.{name}", findings)
                if name in ("publication_time", "ingestion_time", "observation_time") and parsed:
                    timestamps.append(parsed)
            available_at = _parse_timestamp(document.get("available_at"))
            if timestamps and available_at and available_at < max(timestamps):
                _add(findings, source, f"{field_name}.available_at", "availability", "available_at precedes a required source/ingestion timestamp")
            if cutoff and available_at and available_at > cutoff:
                _add(findings, source, f"{field_name}.available_at", "future-document", "document was unavailable at the corpus decision cutoff")
            content_path = _validate_ref(document.get("content_ref"), base, source, f"{field_name}.content_ref", findings)
            if content_path is not None and content_path.exists():
                try:
                    text = content_path.read_text(encoding="utf-8")
                    flags = inspect_untrusted_text(text)
                    if flags:
                        _add(findings, source, f"{field_name}.security_status", "unsafe-text", f"accepted document contains quarantinable text: {', '.join(flags)}")
                except UnicodeDecodeError:
                    _add(findings, source, f"{field_name}.content_ref", "encoding", "reference text fixtures must be UTF-8")

    span_map: dict[str, Mapping[str, Any]] = {}
    if _expect_non_empty_list(spans, source, "spans", findings):
        for index, span in enumerate(spans):
            field_name = f"spans[{index}]"
            if not isinstance(span, Mapping):
                _add(findings, source, field_name, "type", "span must be an object")
                continue
            _require_fields(
                span,
                ("span_id", "document_id", "start", "end", "content_ref", "transform_version", "access_level", "split"),
                source,
                findings,
                prefix=field_name,
            )
            span_id = _string(span.get("span_id"))
            if not span_id:
                _add(findings, source, f"{field_name}.span_id", "required", "span_id is required")
            elif span_id in span_map:
                _add(findings, source, f"{field_name}.span_id", "duplicate", f"duplicate span_id {span_id!r}")
            else:
                span_map[span_id] = span
            document = document_map.get(str(span.get("document_id")))
            if document is None:
                _add(findings, source, f"{field_name}.document_id", "broken-reference", "span document_id does not resolve")
            else:
                if span.get("access_level") != document.get("access_level"):
                    _add(findings, source, f"{field_name}.access_level", "permission-widening", "span access must equal its source document access")
                if span.get("split") != document.get("split"):
                    _add(findings, source, f"{field_name}.split", "split-mismatch", "span split must equal its source document split")
            if not isinstance(span.get("start"), int) or not isinstance(span.get("end"), int) or span.get("start", -1) < 0 or span.get("end", -1) <= span.get("start", 0):
                _add(findings, source, f"{field_name}.start", "offsets", "span offsets must satisfy 0 <= start < end")
            _validate_ref(span.get("content_ref"), base, source, f"{field_name}.content_ref", findings)

    _validate_split_groups(documents if _is_list(documents) else (), source, findings)
    _expect_list(corpus.get("exclusions"), source, "exclusions", findings)
    return ValidationReport(tuple(findings), {"documents": len(document_map), "spans": len(span_map)})


def validate_transform_chain(
    chain: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    source: str = "<transform_chain>",
) -> ValidationReport:
    """Validate ordered, hash-backed text transformation lineage."""

    findings: list[Finding] = []
    base = Path(base_dir)
    _require_fields(chain, ("schema_version", "chain_id", "corpus_snapshot_id", "transforms"), source, findings)
    _expect_schema(chain, SCHEMA_VERSION_TRANSFORMS, source, findings)
    _require_string(chain, "chain_id", source, findings)
    _require_string(chain, "corpus_snapshot_id", source, findings)
    transforms = chain.get("transforms")
    seen_ids: set[str] = set()
    previous_order = 0
    if _expect_non_empty_list(transforms, source, "transforms", findings):
        for index, transform in enumerate(transforms):
            field_name = f"transforms[{index}]"
            if not isinstance(transform, Mapping):
                _add(findings, source, field_name, "type", "transform must be an object")
                continue
            _require_fields(
                transform,
                (
                    "transform_id",
                    "operation",
                    "implementation",
                    "config_version",
                    "parameters",
                    "input_refs",
                    "output_refs",
                    "timestamp",
                    "deterministic",
                    "lineage_order",
                    "security_scan",
                ),
                source,
                findings,
                prefix=field_name,
            )
            transform_id = _string(transform.get("transform_id"))
            if not transform_id:
                _add(findings, source, f"{field_name}.transform_id", "required", "transform_id is required")
            elif transform_id in seen_ids:
                _add(findings, source, f"{field_name}.transform_id", "duplicate", f"duplicate transform_id {transform_id!r}")
            else:
                seen_ids.add(transform_id)
            _expect_member(transform.get("operation"), ALLOWED_TRANSFORMS, source, f"{field_name}.operation", findings)
            order = transform.get("lineage_order")
            if not isinstance(order, int) or order <= previous_order:
                _add(findings, source, f"{field_name}.lineage_order", "lineage-order", "lineage_order must be strictly increasing")
            elif order:
                previous_order = order
            _expect_timestamp(transform.get("timestamp"), source, f"{field_name}.timestamp", findings)
            for ref_name in ("input_refs", "output_refs"):
                refs = transform.get(ref_name)
                if _expect_non_empty_list(refs, source, f"{field_name}.{ref_name}", findings):
                    for ref_index, ref in enumerate(refs):
                        _validate_ref(ref, base, source, f"{field_name}.{ref_name}[{ref_index}]", findings)
            scan = transform.get("security_scan")
            if not isinstance(scan, Mapping):
                _add(findings, source, f"{field_name}.security_scan", "type", "security_scan must be an object")
            else:
                _require_fields(scan, ("status", "flags", "quarantine_action"), source, findings, prefix=f"{field_name}.security_scan")
                if scan.get("status") not in ("pass", "quarantined"):
                    _add(findings, source, f"{field_name}.security_scan.status", "security", "security scan must pass or quarantine the input")
    return ValidationReport(tuple(findings), {"transforms": len(transforms) if _is_list(transforms) else 0})


def validate_model_capabilities(
    payload: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    source: str = "<model_capabilities>",
) -> ValidationReport:
    """Validate provider-neutral model, tokenizer, and plugin capability evidence."""

    findings: list[Finding] = []
    base = Path(base_dir)
    _require_fields(payload, ("schema_version", "capability_set_id", "profiles"), source, findings)
    _expect_schema(payload, SCHEMA_VERSION_CAPABILITIES, source, findings)
    _require_string(payload, "capability_set_id", source, findings)
    profiles = payload.get("profiles")
    seen: set[str] = set()
    if _expect_non_empty_list(profiles, source, "profiles", findings):
        for index, profile in enumerate(profiles):
            field_name = f"profiles[{index}]"
            if not isinstance(profile, Mapping):
                _add(findings, source, field_name, "type", "capability profile must be an object")
                continue
            required = (
                "capability_id",
                "operations",
                "provider",
                "runtime",
                "model",
                "revision",
                "license",
                "execution_location",
                "privacy_classes",
                "deterministic_settings",
                "limits",
                "fallback",
                "replay_class",
            )
            _require_fields(profile, required, source, findings, prefix=field_name)
            capability_id = _string(profile.get("capability_id"))
            if not capability_id:
                _add(findings, source, f"{field_name}.capability_id", "required", "capability_id is required")
            elif capability_id in seen:
                _add(findings, source, f"{field_name}.capability_id", "duplicate", f"duplicate capability_id {capability_id!r}")
            else:
                seen.add(capability_id)
            operations = profile.get("operations")
            if _expect_non_empty_list(operations, source, f"{field_name}.operations", findings):
                for operation in operations:
                    _expect_member(operation, ALLOWED_OPERATIONS, source, f"{field_name}.operations", findings)
            for key in ("provider", "runtime", "model", "revision", "license", "execution_location"):
                _require_string(profile, key, source, findings, prefix=field_name)
            _expect_non_empty_list(profile.get("privacy_classes"), source, f"{field_name}.privacy_classes", findings)
            for privacy_class in profile.get("privacy_classes", []) if _is_list(profile.get("privacy_classes")) else []:
                _expect_member(privacy_class, ALLOWED_ACCESS_LEVELS, source, f"{field_name}.privacy_classes", findings)
            _expect_member(profile.get("replay_class"), ALLOWED_REPLAY_CLASSES, source, f"{field_name}.replay_class", findings)
            if not isinstance(profile.get("deterministic_settings"), Mapping):
                _add(findings, source, f"{field_name}.deterministic_settings", "type", "deterministic_settings must be an object")
            if not isinstance(profile.get("limits"), Mapping):
                _add(findings, source, f"{field_name}.limits", "type", "limits must be an object")
            fallback = profile.get("fallback")
            if not isinstance(fallback, Mapping) or not _string(fallback.get("behavior")):
                _add(findings, source, f"{field_name}.fallback", "fallback", "fallback behavior is required")
            localish = profile.get("provider") in ("local", "fixture") or any(
                operation in ("embedding", "rerank", "tokenize", "train_adapt")
                for operation in operations if isinstance(operation, str)
            )
            checksum = profile.get("artifact_checksum")
            if localish and not checksum:
                _add(findings, source, f"{field_name}.artifact_checksum", "required", "local, fixture, embedding, rerank, tokenizer, and training profiles require an artifact checksum")
            elif checksum:
                _expect_hash(checksum, source, f"{field_name}.artifact_checksum", findings)
            fixture_ref = profile.get("fixture_ref")
            if fixture_ref is not None:
                _validate_ref(fixture_ref, base, source, f"{field_name}.fixture_ref", findings)
            if _contains_secret(profile):
                _add(findings, source, field_name, "raw-credential", "capability profile contains a token-shaped secret")
    return ValidationReport(tuple(findings), {"capabilities": len(seen)})


def validate_embedding_and_index(
    embeddings: Mapping[str, Any],
    index_snapshot: Mapping[str, Any] | None,
    *,
    corpus: Mapping[str, Any],
    capabilities: Mapping[str, Any],
    source: str = "<embedding_index>",
) -> ValidationReport:
    """Validate vector/span lineage and immutable pre-search access isolation."""

    findings: list[Finding] = []
    _require_fields(
        embeddings,
        (
            "schema_version",
            "embedding_id",
            "corpus_snapshot_id",
            "model_capability_id",
            "tokenizer",
            "pooling",
            "normalization",
            "dimension",
            "quantization",
            "preprocessing_hash",
            "created_at",
            "vectors",
        ),
        source,
        findings,
    )
    _expect_schema(embeddings, SCHEMA_VERSION_EMBEDDINGS, source, findings)
    dimension = embeddings.get("dimension")
    if not isinstance(dimension, int) or dimension <= 0:
        _add(findings, source, "dimension", "dimension", "dimension must be a positive integer")
        dimension = 0
    _expect_hash(embeddings.get("preprocessing_hash"), source, "preprocessing_hash", findings)
    _expect_timestamp(embeddings.get("created_at"), source, "created_at", findings)
    corpus_id = corpus.get("snapshot_id")
    if embeddings.get("corpus_snapshot_id") != corpus_id:
        _add(findings, source, "corpus_snapshot_id", "corpus-mismatch", "embedding corpus snapshot does not match")
    profile_map = _profile_map(capabilities)
    profile = profile_map.get(str(embeddings.get("model_capability_id")))
    if profile is None or "embedding" not in profile.get("operations", []):
        _add(findings, source, "model_capability_id", "capability-mismatch", "embedding model capability does not resolve to an embedding profile")
    span_map = _span_map(corpus)
    vector_map: dict[str, Mapping[str, Any]] = {}
    vectors = embeddings.get("vectors")
    if _expect_non_empty_list(vectors, source, "vectors", findings):
        for index, vector in enumerate(vectors):
            field_name = f"vectors[{index}]"
            if not isinstance(vector, Mapping):
                _add(findings, source, field_name, "type", "vector must be an object")
                continue
            _require_fields(vector, ("vector_id", "span_id", "values", "access_level"), source, findings, prefix=field_name)
            vector_id = _string(vector.get("vector_id"))
            if not vector_id:
                _add(findings, source, f"{field_name}.vector_id", "required", "vector_id is required")
            elif vector_id in vector_map:
                _add(findings, source, f"{field_name}.vector_id", "duplicate", f"duplicate vector_id {vector_id!r}")
            else:
                vector_map[vector_id] = vector
            values = vector.get("values")
            if not _is_list(values) or len(values) != dimension or not all(isinstance(value, (int, float)) for value in values):
                _add(findings, source, f"{field_name}.values", "dimension-mismatch", "vector values must match declared dimension")
            span = span_map.get(str(vector.get("span_id")))
            if span is None:
                _add(findings, source, f"{field_name}.span_id", "broken-reference", "vector span_id does not resolve")
            elif vector.get("access_level") != span.get("access_level"):
                _add(findings, source, f"{field_name}.access_level", "permission-widening", "vector access must equal source span access")

    if index_snapshot is None:
        _add(findings, source, "index_snapshot", "required", "embedding artifact requires an index snapshot in this foundation")
        return ValidationReport(tuple(findings), {"vectors": len(vector_map), "indexes": 0})

    _require_fields(
        index_snapshot,
        (
            "schema_version",
            "index_snapshot_id",
            "embedding_id",
            "access_tier",
            "entitlements",
            "algorithm",
            "config",
            "distance_metric",
            "vector_ids",
            "vector_set_hash",
            "build_version",
            "corpus_cutoff",
            "source_license_eligibility",
            "immutable",
        ),
        source,
        findings,
    )
    _expect_schema(index_snapshot, SCHEMA_VERSION_INDEX, source, findings)
    if index_snapshot.get("embedding_id") != embeddings.get("embedding_id"):
        _add(findings, source, "index_snapshot.embedding_id", "embedding-mismatch", "index snapshot does not reference this embedding artifact")
    tier = index_snapshot.get("access_tier")
    _expect_member(tier, ALLOWED_ACCESS_LEVELS, source, "index_snapshot.access_tier", findings)
    if index_snapshot.get("immutable") is not True:
        _add(findings, source, "index_snapshot.immutable", "immutable-required", "index snapshot must be immutable")
    _expect_timestamp(index_snapshot.get("corpus_cutoff"), source, "index_snapshot.corpus_cutoff", findings)
    _expect_list(index_snapshot.get("entitlements"), source, "index_snapshot.entitlements", findings)
    _expect_non_empty_list(index_snapshot.get("source_license_eligibility"), source, "index_snapshot.source_license_eligibility", findings)
    if not isinstance(index_snapshot.get("config"), Mapping):
        _add(findings, source, "index_snapshot.config", "type", "index config must be an object")
    vector_ids = index_snapshot.get("vector_ids")
    if _expect_non_empty_list(vector_ids, source, "index_snapshot.vector_ids", findings):
        for vector_id in vector_ids:
            vector = vector_map.get(str(vector_id))
            if vector is None:
                _add(findings, source, "index_snapshot.vector_ids", "broken-reference", f"index vector {vector_id!r} does not resolve")
                continue
            if not _access_allows(str(vector.get("access_level")), str(tier)):
                _add(findings, source, "index_snapshot.vector_ids", "cross-tier", f"{tier} index contains {vector.get('access_level')} vector {vector_id}")
        expected = canonical_hash(sorted(str(item) for item in vector_ids))
        if index_snapshot.get("vector_set_hash") != expected:
            _add(findings, source, "index_snapshot.vector_set_hash", "hash-mismatch", "vector_set_hash does not match ordered vector IDs")
    return ValidationReport(tuple(findings), {"vectors": len(vector_map), "indexes": 1})


def validate_training_run(
    training: Mapping[str, Any],
    *,
    base_dir: str | Path = ".",
    source: str = "<training_run>",
) -> ValidationReport:
    """Validate fixture-only local training/adaptation evidence."""

    findings: list[Finding] = []
    _require_fields(
        training,
        (
            "schema_version",
            "training_run_id",
            "base_model_capability_id",
            "corpus_snapshot_id",
            "labels",
            "split_policy",
            "label_provenance",
            "objective",
            "seeds",
            "environment",
            "hardware",
            "checkpoint_refs",
            "metrics",
            "contamination_checks",
            "model_card_ref",
            "fixture_only",
        ),
        source,
        findings,
    )
    _expect_schema(training, SCHEMA_VERSION_TRAINING, source, findings)
    if training.get("fixture_only") is not True:
        _add(findings, source, "fixture_only", "scope", "0071 foundation training evidence must remain fixture-only")
    _expect_non_empty_list(training.get("seeds"), source, "seeds", findings)
    for index, ref in enumerate(training.get("checkpoint_refs", []) if _is_list(training.get("checkpoint_refs")) else []):
        _validate_ref(ref, Path(base_dir), source, f"checkpoint_refs[{index}]", findings)
    _validate_ref(training.get("model_card_ref"), Path(base_dir), source, "model_card_ref", findings)
    return ValidationReport(tuple(findings), {"training_runs": 1})


def validate_task_results(
    payload: Mapping[str, Any],
    *,
    corpus: Mapping[str, Any],
    capabilities: Mapping[str, Any],
    index_snapshot: Mapping[str, Any] | None = None,
    source: str = "<task_results>",
) -> ValidationReport:
    """Validate evidence-bearing structured NLP/LLM task outputs."""

    findings: list[Finding] = []
    _require_fields(payload, ("schema_version", "result_set_id", "task_schema_version", "results", "promotion_policy"), source, findings)
    _expect_schema(payload, SCHEMA_VERSION_RESULTS, source, findings)
    spans = _span_map(corpus)
    profiles = _profile_map(capabilities)
    results = payload.get("results")
    seen: set[str] = set()
    if _expect_non_empty_list(results, source, "results", findings):
        for index, result in enumerate(results):
            field_name = f"results[{index}]"
            if not isinstance(result, Mapping):
                _add(findings, source, field_name, "type", "task result must be an object")
                continue
            _require_fields(
                result,
                (
                    "result_id",
                    "task_type",
                    "status",
                    "model_capability_id",
                    "corpus_snapshot_id",
                    "evidence_span_ids",
                    "confidence",
                    "calibration",
                    "output",
                    "uncertainty",
                    "review",
                    "error_code",
                ),
                source,
                findings,
                prefix=field_name,
            )
            result_id = _string(result.get("result_id"))
            if not result_id:
                _add(findings, source, f"{field_name}.result_id", "required", "result_id is required")
            elif result_id in seen:
                _add(findings, source, f"{field_name}.result_id", "duplicate", f"duplicate result_id {result_id!r}")
            else:
                seen.add(result_id)
            _expect_member(result.get("task_type"), ALLOWED_TASK_TYPES, source, f"{field_name}.task_type", findings)
            _expect_member(result.get("status"), ALLOWED_RESULT_STATUSES, source, f"{field_name}.status", findings)
            if result.get("model_capability_id") not in profiles:
                _add(findings, source, f"{field_name}.model_capability_id", "broken-reference", "model capability does not resolve")
            if result.get("corpus_snapshot_id") != corpus.get("snapshot_id"):
                _add(findings, source, f"{field_name}.corpus_snapshot_id", "corpus-mismatch", "task result corpus does not match")
            evidence = result.get("evidence_span_ids")
            if result.get("status") == "supported":
                if _expect_non_empty_list(evidence, source, f"{field_name}.evidence_span_ids", findings):
                    for span_id in evidence:
                        if str(span_id) not in spans:
                            _add(findings, source, f"{field_name}.evidence_span_ids", "broken-reference", f"evidence span {span_id!r} does not resolve")
                confidence = result.get("confidence")
                if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                    _add(findings, source, f"{field_name}.confidence", "confidence", "supported result confidence must be between 0 and 1")
            elif not _string(result.get("error_code")):
                _add(findings, source, f"{field_name}.error_code", "required", "abstained, unsupported, or rejected result requires an error_code")
            _validate_review(result.get("review"), source, f"{field_name}.review", findings, material=True)
            output = result.get("output")
            if not isinstance(output, Mapping):
                _add(findings, source, f"{field_name}.output", "type", "output must be an object")
            elif result.get("task_type") == "evidence_synthesis" and result.get("status") == "supported":
                claims = output.get("claims")
                if _expect_non_empty_list(claims, source, f"{field_name}.output.claims", findings):
                    for claim_index, claim in enumerate(claims):
                        claim_field = f"{field_name}.output.claims[{claim_index}]"
                        if not isinstance(claim, Mapping) or not _is_list(claim.get("citation_span_ids")) or not claim.get("citation_span_ids"):
                            _add(findings, source, claim_field, "uncited-claim", "supported synthesis claim requires citation_span_ids")
            if result.get("task_type") in ("semantic_retrieval", "reranking") and (
                index_snapshot is None
                or result.get("index_snapshot_id")
                != index_snapshot.get("index_snapshot_id")
            ):
                _add(
                    findings,
                    source,
                    f"{field_name}.index_snapshot_id",
                    "index-mismatch",
                    "retrieval/reranking result must reference the validated index snapshot",
                )
    return ValidationReport(tuple(findings), {"task_results": len(seen)})


def validate_signal_artifact(
    payload: Mapping[str, Any],
    *,
    corpus: Mapping[str, Any],
    task_results: Mapping[str, Any],
    source: str = "<signals>",
) -> ValidationReport:
    """Validate fail-closed, point-in-time text-derived quant signals."""

    findings: list[Finding] = []
    _require_fields(payload, ("schema_version", "signal_set_id", "signals"), source, findings)
    _expect_schema(payload, SCHEMA_VERSION_SIGNALS, source, findings)
    spans = _span_map(corpus)
    documents = _document_map(corpus)
    result_ids = {
        str(result.get("result_id"))
        for result in task_results.get("results", [])
        if isinstance(result, Mapping)
    } if _is_list(task_results.get("results")) else set()
    signals = payload.get("signals")
    if _expect_non_empty_list(signals, source, "signals", findings):
        for index, signal in enumerate(signals):
            field_name = f"signals[{index}]"
            if not isinstance(signal, Mapping):
                _add(findings, source, field_name, "type", "signal must be an object")
                continue
            required = (
                "signal_id",
                "observation_time",
                "decision_time",
                "availability_lag_seconds",
                "universe",
                "entity_instrument_mapping",
                "horizon",
                "aggregation_rule",
                "missingness_policy",
                "task_result_ids",
                "model_capability_ids",
                "contributing_span_ids",
                "confidence",
                "calibration",
                "revision_policy",
                "downstream_dataset_refs",
                "downstream_backtest_refs",
                "review",
                "publication_state",
            )
            _require_fields(signal, required, source, findings, prefix=field_name)
            decision = _expect_timestamp(signal.get("decision_time"), source, f"{field_name}.decision_time", findings)
            _expect_timestamp(signal.get("observation_time"), source, f"{field_name}.observation_time", findings)
            if not isinstance(signal.get("availability_lag_seconds"), int) or signal.get("availability_lag_seconds", -1) < 0:
                _add(findings, source, f"{field_name}.availability_lag_seconds", "lag", "availability lag must be a non-negative integer")
            for result_id in signal.get("task_result_ids", []) if _is_list(signal.get("task_result_ids")) else []:
                if str(result_id) not in result_ids:
                    _add(findings, source, f"{field_name}.task_result_ids", "broken-reference", f"task result {result_id!r} does not resolve")
            evidence = signal.get("contributing_span_ids")
            if _expect_non_empty_list(evidence, source, f"{field_name}.contributing_span_ids", findings):
                for span_id in evidence:
                    span = spans.get(str(span_id))
                    if span is None:
                        _add(findings, source, f"{field_name}.contributing_span_ids", "broken-reference", f"span {span_id!r} does not resolve")
                        continue
                    document = documents.get(str(span.get("document_id")))
                    available = _parse_timestamp(document.get("available_at")) if document else None
                    if decision and available and available > decision:
                        _add(findings, source, f"{field_name}.decision_time", "future-signal-input", f"span {span_id!r} was unavailable at signal decision time")
            _expect_non_empty_list(signal.get("universe"), source, f"{field_name}.universe", findings)
            _expect_non_empty_list(signal.get("entity_instrument_mapping"), source, f"{field_name}.entity_instrument_mapping", findings)
            _expect_non_empty_list(signal.get("model_capability_ids"), source, f"{field_name}.model_capability_ids", findings)
            for key in ("horizon", "aggregation_rule", "missingness_policy", "revision_policy"):
                _require_string(signal, key, source, findings, prefix=field_name)
            confidence = signal.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                _add(findings, source, f"{field_name}.confidence", "confidence", "signal confidence must be between 0 and 1")
            for ref_name in ("downstream_dataset_refs", "downstream_backtest_refs"):
                _expect_non_empty_list(signal.get(ref_name), source, f"{field_name}.{ref_name}", findings)
            _validate_review(signal.get("review"), source, f"{field_name}.review", findings, material=True)
            if signal.get("publication_state") not in ("fixture_only", "research", "approved", "production"):
                _add(findings, source, f"{field_name}.publication_state", "state", "invalid publication_state")
    return ValidationReport(tuple(findings), {"signals": len(signals) if _is_list(signals) else 0})


def validate_evaluation_suite(
    suite: Mapping[str, Any],
    *,
    source: str = "<evaluation_suite>",
) -> ValidationReport:
    """Require meaningful coverage or a justified exception for each text layer."""

    findings: list[Finding] = []
    _require_fields(suite, ("schema_version", "suite_id", "manifest_id", "required_layers", "checks", "promotion_status"), source, findings)
    _expect_schema(suite, SCHEMA_VERSION_EVALUATION, source, findings)
    declared = suite.get("required_layers")
    if not _is_list(declared):
        _add(findings, source, "required_layers", "type", "required_layers must be a list")
        declared = []
    for layer in REQUIRED_EVALUATION_LAYERS:
        if layer not in declared:
            _add(findings, source, "required_layers", "missing-layer", f"required text evaluation layer {layer!r} is missing")
    checks = suite.get("checks")
    covered: set[str] = set()
    if _expect_non_empty_list(checks, source, "checks", findings):
        for index, check in enumerate(checks):
            field_name = f"checks[{index}]"
            if not isinstance(check, Mapping):
                _add(findings, source, field_name, "type", "evaluation check must be an object")
                continue
            _require_fields(check, ("check_id", "layer", "status", "deterministic", "metrics", "findings", "exception"), source, findings, prefix=field_name)
            layer = _string(check.get("layer"))
            if layer:
                covered.add(layer)
            if check.get("status") not in ("pass", "fail", "warn", "skipped"):
                _add(findings, source, f"{field_name}.status", "status", "evaluation status is invalid")
            if check.get("status") == "skipped" and not _string(check.get("exception")):
                _add(findings, source, f"{field_name}.exception", "required", "skipped evaluation layer requires a justified exception")
            if check.get("status") != "skipped" and not isinstance(check.get("metrics"), Mapping):
                _add(findings, source, f"{field_name}.metrics", "metrics", "active evaluation check requires metrics")
    for layer in REQUIRED_EVALUATION_LAYERS:
        if layer not in covered:
            _add(findings, source, f"checks.{layer}", "missing-layer-coverage", f"evaluation layer {layer!r} lacks a check or exception")
    if suite.get("promotion_status") not in ("pass", "fail", "review_required"):
        _add(findings, source, "promotion_status", "status", "invalid promotion_status")
    return ValidationReport(tuple(findings), {"evaluation_checks": len(checks) if _is_list(checks) else 0})


def validate_text_audit_events(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    correlation_id: str,
    base_dir: str | Path = ".",
    required_domain_events: Sequence[str] = REQUIRED_TEXT_AUDIT_EVENTS,
    source: str = "<text_audit_events>",
) -> ValidationReport:
    """Validate text domain events inside the authoritative 0070 audit ledger."""

    findings: list[Finding] = []
    base_report = validate_audit_events(
        events,
        run_id=run_id,
        base_dir=base_dir,
        source=source,
    )
    findings.extend(base_report.findings)
    domain_events: set[str] = set()
    event_ids: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            continue
        event_ids.add(str(event.get("event_id")))
        payload = event.get("payload_ref")
        if isinstance(payload, Mapping):
            domain_event = _string(payload.get("domain_event"))
            if domain_event:
                domain_events.add(domain_event)
        if "raw_text" in event or (isinstance(payload, Mapping) and "raw_text" in payload):
            _add(findings, source, f"events[{index}]", "raw-text", "audit ledger must not store raw source/model text")
    for domain_event in required_domain_events:
        if domain_event not in domain_events:
            _add(findings, source, "events", "missing-domain-event", f"required text audit event {domain_event!r} is missing")
    if correlation_id not in event_ids:
        _add(findings, source, "correlation_id", "broken-reference", "manifest audit_correlation_id does not resolve")
    return ValidationReport(tuple(findings), {"audit_events": len(events), "text_domain_events": len(domain_events)})


def evaluate_text_leakage(
    corpus: Mapping[str, Any],
    *,
    benchmark_document_ids: Sequence[str] = (),
    source: str = "<text_leakage>",
) -> ValidationReport:
    """Evaluate temporal, duplicate/split, revision, and benchmark leakage."""

    findings: list[Finding] = []
    cutoff = _parse_timestamp(corpus.get("decision_cutoff"))
    documents = corpus.get("documents", [])
    revision_groups: dict[str, list[Mapping[str, Any]]] = {}
    if _is_list(documents):
        for index, document in enumerate(documents):
            if not isinstance(document, Mapping):
                continue
            available = _parse_timestamp(document.get("available_at"))
            if cutoff and available and available > cutoff:
                _add(findings, source, f"documents[{index}].available_at", "future-document", "document is future-known at cutoff")
            if document.get("document_id") in benchmark_document_ids and document.get("split") in ("train", "validation"):
                _add(findings, source, f"documents[{index}].split", "benchmark-contamination", "benchmark document appears in model-development split")
            revision_group = _string(document.get("revision_group_id"))
            if revision_group:
                revision_groups.setdefault(revision_group, []).append(document)
    for revision_group, revisions in revision_groups.items():
        current = [item for item in revisions if item.get("supersession_state") == "current"]
        revision_numbers = [item.get("revision_number") for item in revisions]
        if len(current) > 1 or len(set(revision_numbers)) != len(revision_numbers):
            _add(findings, source, "documents.revision_group_id", "revision-overlap", f"revision group {revision_group!r} has ambiguous active or duplicate revisions")
    _validate_split_groups(documents if _is_list(documents) else (), source, findings)
    return ValidationReport(tuple(findings), {"leakage_checks": 1})


def inspect_untrusted_text(text: str, *, declared_tools: Sequence[str] = ()) -> tuple[str, ...]:
    """Return high-signal prompt-injection or prohibited-data indicators.

    The text is always treated as data.  The detector is intentionally small and
    conservative; callers quarantine on a hit and record the review decision.
    """

    flags: list[str] = []
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            if name == "undeclared-tool-request" and declared_tools:
                lowered = text.casefold()
                if any(tool.casefold() in lowered for tool in declared_tools):
                    continue
            flags.append(name)
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            flags.append(name)
    return tuple(sorted(set(flags)))


def select_eligible_index(
    indexes: Sequence[Mapping[str, Any]],
    *,
    caller_clearance: str,
    entitlements: Sequence[str] = (),
) -> Mapping[str, Any]:
    """Select the highest eligible immutable index before retrieval.

    The function never searches a higher-tier index and filters afterward.  That
    prevents result scores from revealing restricted-resource existence.
    """

    if caller_clearance not in _ACCESS_RANK:
        raise ValueError(f"unknown caller clearance: {caller_clearance}")
    caller_entitlements = set(entitlements)
    eligible: list[Mapping[str, Any]] = []
    for index in indexes:
        tier = index.get("access_tier")
        required = set(index.get("entitlements", []) if _is_list(index.get("entitlements")) else [])
        if tier in _ACCESS_RANK and _access_allows(str(tier), caller_clearance) and required <= caller_entitlements and index.get("immutable") is True:
            eligible.append(index)
    if not eligible:
        raise PermissionError("no caller-eligible immutable index snapshot")
    return max(eligible, key=lambda item: _ACCESS_RANK[str(item["access_tier"])])


def build_agent_consumption_view(
    path: str | Path,
    *,
    consumer: str,
    caller_clearance: str = "public",
) -> AgentTextIntelligenceView:
    """Load one validated shared result view without provider or storage details."""

    if caller_clearance not in _ACCESS_RANK:
        raise ValueError(f"unknown caller clearance: {caller_clearance}")
    path = Path(path)
    validation = validate_text_intelligence_manifest_file(path)
    validation.raise_if_errors()
    manifest = load_json(path)
    if consumer not in manifest.get("downstream_consumers", []):
        raise PermissionError(f"consumer is not declared by the manifest: {consumer}")
    corpus = load_json(_ref_path(manifest["corpus_snapshot"], path.parent))
    task_results = load_json(_ref_path(manifest["task_results"], path.parent))
    signal_payloads = [
        load_json(_ref_path(ref, path.parent))
        for ref in manifest.get("signal_artifacts", [])
    ]
    eligible_spans: dict[str, Mapping[str, Any]] = {}
    documents = _document_map(corpus)
    for span_id, span in _span_map(corpus).items():
        if _access_allows(str(span.get("access_level")), caller_clearance):
            document = documents.get(str(span.get("document_id")), {})
            content_ref = document.get("content_ref", {})
            eligible_spans[span_id] = {
                "span_id": span_id,
                "document_id": span.get("document_id"),
                "source_id": document.get("source_id"),
                "content_hash": content_ref.get("hash") if isinstance(content_ref, Mapping) else None,
                "access_level": span.get("access_level"),
                "citation": f"text://{span_id}",
            }
    eligible_tasks = tuple(
        result
        for result in task_results.get("results", [])
        if isinstance(result, Mapping)
        and all(str(span_id) in eligible_spans for span_id in result.get("evidence_span_ids", []))
    )
    eligible_result_ids = {str(result.get("result_id")) for result in eligible_tasks}
    signals = tuple(
        signal
        for payload in signal_payloads
        for signal in payload.get("signals", [])
        if isinstance(signal, Mapping)
        and set(map(str, signal.get("task_result_ids", []))) <= eligible_result_ids
        and all(str(span_id) in eligible_spans for span_id in signal.get("contributing_span_ids", []))
    )
    return AgentTextIntelligenceView(
        manifest_id=str(manifest["manifest_id"]),
        run_id=str(manifest["run_id"]),
        consumer=consumer,
        decision_time=str(manifest["decision_time"]),
        task_schema_version=str(manifest["task_schema_version"]),
        task_results=eligible_tasks,
        signals=signals,
        source_spans=tuple(eligible_spans.values()),
        orchestration={
            "run_id": manifest["orchestration"]["run_id"],
            "schema_version": manifest["orchestration"]["schema_version"],
            "path": manifest["orchestration"]["path"],
        },
    )


def replay_text_intelligence_manifest_file(
    path: str | Path,
    *,
    fixture_mode: bool = False,
    allow_non_reproducible: bool = False,
) -> TextReplayReport:
    """Replay a text run through the spec-0070 replay implementation."""

    path = Path(path)
    manifest = load_json(path)
    if not isinstance(manifest, Mapping):
        raise TypeError("text-intelligence manifest must be an object")
    validation = validate_text_intelligence_manifest_file(path)
    orchestration = manifest.get("orchestration")
    envelope_path = _orchestration_path(orchestration, path.parent)
    if envelope_path is None:
        raise ValueError("manifest orchestration.path is required")
    replay = replay_envelope_file(
        envelope_path,
        fixture_mode=fixture_mode,
        allow_non_reproducible=allow_non_reproducible,
    )
    artifact_hashes: dict[str, str] = {"text_intelligence_manifest.json": sha256_file(path)}
    for name in (
        "corpus_snapshot",
        "transform_chain",
        "model_capabilities",
        "embedding_artifact",
        "index_snapshot",
        "training_run",
        "task_results",
        "evaluation_suite",
    ):
        ref = manifest.get(name)
        ref_path = _ref_path(ref, path.parent)
        if ref_path is not None and ref_path.exists():
            artifact_hashes[str(ref.get("path"))] = sha256_file(ref_path)
    for ref in manifest.get("signal_artifacts", []) if _is_list(manifest.get("signal_artifacts")) else []:
        ref_path = _ref_path(ref, path.parent)
        if ref_path is not None and ref_path.exists():
            artifact_hashes[str(ref.get("path"))] = sha256_file(ref_path)
    if validation.errors:
        status = "invalid"
    else:
        status = replay.status
    return TextReplayReport(
        manifest_id=str(manifest.get("manifest_id", "<unknown>")),
        status=status,
        orchestration=replay,
        artifact_hashes=artifact_hashes,
        findings=tuple(finding.to_dict() for finding in validation.findings),
    )


def _validate_0070_integration(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    envelope_path: Path,
    findings: list[Finding],
) -> None:
    try:
        envelope = load_json(envelope_path)
    except (OSError, ValueError) as exc:
        _add(findings, str(manifest_path), "orchestration", "load", str(exc))
        return
    if not isinstance(envelope, Mapping):
        _add(findings, str(manifest_path), "orchestration", "type", "0070 envelope must be an object")
        return
    if manifest.get("run_id") != envelope.get("run_id"):
        _add(findings, str(manifest_path), "run_id", "run-mismatch", "text manifest run_id does not match 0070 envelope")
    orchestration_ref = manifest.get("orchestration")
    if isinstance(orchestration_ref, Mapping):
        if orchestration_ref.get("run_id") != envelope.get("run_id"):
            _add(findings, str(manifest_path), "orchestration.run_id", "run-mismatch", "orchestration reference run_id does not match envelope")
        if orchestration_ref.get("schema_version") != envelope.get("schema_version"):
            _add(findings, str(manifest_path), "orchestration.schema_version", "schema-version", "orchestration reference schema does not match envelope")

    manifest_hash = sha256_file(manifest_path)
    manifest_artifacts = []
    for artifact in envelope.get("artifacts", []) if _is_list(envelope.get("artifacts")) else []:
        if not isinstance(artifact, Mapping):
            continue
        artifact_path = _ref_path(artifact, envelope_path.parent)
        if artifact_path is not None and artifact_path.resolve() == manifest_path.resolve():
            manifest_artifacts.append(artifact)
    if not manifest_artifacts:
        _add(findings, str(manifest_path), "orchestration.artifacts", "missing-text-manifest", "0070 envelope must list the 0071 manifest as an artifact")
    elif manifest_artifacts[0].get("hash") != manifest_hash:
        _add(findings, str(manifest_path), "orchestration.artifacts", "hash-mismatch", "0070 envelope text-manifest hash does not match")

    audit_ref = envelope.get("audit_events")
    audit_path = _ref_path(audit_ref, envelope_path.parent)
    if audit_path is None or not audit_path.exists():
        _add(findings, str(manifest_path), "orchestration.audit_events", "missing", "0070 audit ledger is required")
        return
    events = load_jsonl(audit_path)
    audit_report = validate_text_audit_events(
        events,
        run_id=str(manifest.get("run_id", "")),
        correlation_id=str(manifest.get("audit_correlation_id", "")),
        base_dir=audit_path.parent,
        required_domain_events=(
            REQUIRED_TEXT_AUDIT_EVENTS + RETRIEVAL_TEXT_AUDIT_EVENTS
            if manifest.get("embedding_artifact") is not None
            else REQUIRED_TEXT_AUDIT_EVENTS
        ),
        source=str(audit_path),
    )
    findings.extend(audit_report.findings)


def _validate_orchestration_ref(
    ref: Any,
    base: Path,
    source: str,
    findings: list[Finding],
) -> Path | None:
    if not isinstance(ref, Mapping):
        _add(findings, source, "orchestration", "type", "orchestration must be an object")
        return None
    _require_fields(ref, ("path", "run_id", "schema_version"), source, findings, prefix="orchestration")
    path = _orchestration_path(ref, base)
    if path is not None and not path.exists():
        _add(findings, source, "orchestration.path", "missing", f"orchestration envelope does not exist: {ref.get('path')}")
    return path


def _orchestration_path(ref: Any, base: Path) -> Path | None:
    if not isinstance(ref, Mapping):
        return None
    value = _string(ref.get("path"))
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else base / path


def _validate_ref(
    ref: Any,
    base: Path,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> Path | None:
    if not isinstance(ref, Mapping):
        _add(findings, source, field_name, "type", f"{field_name} must be an artifact reference")
        return None
    path_value = _string(ref.get("path"))
    expected_hash = _string(ref.get("hash"))
    if not path_value:
        _add(findings, source, f"{field_name}.path", "required", "artifact path is required")
        return None
    if not expected_hash:
        _add(findings, source, f"{field_name}.hash", "required", "artifact hash is required")
    else:
        _expect_hash(expected_hash, source, f"{field_name}.hash", findings)
    path = Path(path_value)
    path = path if path.is_absolute() else base / path
    if not path.exists():
        _add(findings, source, f"{field_name}.path", "missing", f"artifact path does not exist: {path_value}")
    elif expected_hash and _HASH_RE.match(expected_hash):
        actual = sha256_file(path)
        if actual != expected_hash:
            _add(findings, source, f"{field_name}.hash", "hash-mismatch", f"expected {expected_hash}, got {actual}")
    return path


def _ref_path(ref: Any, base: Path) -> Path | None:
    if not isinstance(ref, Mapping):
        return None
    value = _string(ref.get("path"))
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else base / path


def _validate_split_groups(
    documents: Sequence[Any],
    source: str,
    findings: list[Finding],
) -> None:
    for group_field in ("canonical_group_id", "near_duplicate_group_id"):
        groups: dict[str, set[str]] = {}
        for document in documents:
            if not isinstance(document, Mapping):
                continue
            group_id = _string(document.get(group_field))
            split = _string(document.get("split"))
            if group_id and split and split != "none":
                groups.setdefault(group_id, set()).add(split)
        for group_id, splits in groups.items():
            if len(splits) > 1:
                _add(findings, source, group_field, "cross-split-duplicate", f"group {group_id!r} crosses splits: {', '.join(sorted(splits))}")
    content_groups: dict[str, set[str]] = {}
    for document in documents:
        if not isinstance(document, Mapping):
            continue
        content_ref = document.get("content_ref")
        content_hash = _string(content_ref.get("hash")) if isinstance(content_ref, Mapping) else None
        split = _string(document.get("split"))
        if content_hash and split and split != "none":
            content_groups.setdefault(content_hash, set()).add(split)
    for content_hash, splits in content_groups.items():
        if len(splits) > 1:
            _add(findings, source, "content_ref.hash", "cross-split-exact-duplicate", f"content hash {content_hash!r} crosses splits: {', '.join(sorted(splits))}")


def _validate_review(
    review: Any,
    source: str,
    field_name: str,
    findings: list[Finding],
    *,
    material: bool,
) -> None:
    if not isinstance(review, Mapping):
        _add(findings, source, field_name, "type", "review must be an object")
        return
    required = ("status", "owner", "reviewer", "reviewed_at", "uncertainty", "overrides", "rejected_alternatives", "escalation_conditions")
    _require_fields(review, required, source, findings, prefix=field_name)
    if material and review.get("status") not in ("fixture_approved", "reviewed", "approved"):
        _add(findings, source, f"{field_name}.status", "review-required", "material output requires fixture_approved, reviewed, or approved status")
    for key in ("owner", "reviewer", "uncertainty"):
        _require_string(review, key, source, findings, prefix=field_name)
    _expect_timestamp(review.get("reviewed_at"), source, f"{field_name}.reviewed_at", findings)
    _expect_list(review.get("overrides"), source, f"{field_name}.overrides", findings)
    _expect_list(review.get("rejected_alternatives"), source, f"{field_name}.rejected_alternatives", findings)
    _expect_non_empty_list(review.get("escalation_conditions"), source, f"{field_name}.escalation_conditions", findings)


def _profile_map(capabilities: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    profiles = capabilities.get("profiles", [])
    if not _is_list(profiles):
        return {}
    return {
        str(profile.get("capability_id")): profile
        for profile in profiles
        if isinstance(profile, Mapping) and profile.get("capability_id")
    }


def _document_map(corpus: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    documents = corpus.get("documents", [])
    if not _is_list(documents):
        return {}
    return {
        str(document.get("document_id")): document
        for document in documents
        if isinstance(document, Mapping) and document.get("document_id")
    }


def _span_map(corpus: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    spans = corpus.get("spans", [])
    if not _is_list(spans):
        return {}
    return {
        str(span.get("span_id")): span
        for span in spans
        if isinstance(span, Mapping) and span.get("span_id")
    }


def _source_exists(repo_root: Path, source_id: str) -> bool:
    return (repo_root / "sources" / f"{source_id}.yml").exists() or (repo_root / "sources" / f"{source_id}.yaml").exists()


def _find_repo_root(path: str | Path) -> Path:
    candidate = Path(path).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for current in (candidate, *candidate.parents):
        if (current / "sources").is_dir() and (current / "pyproject.toml").exists():
            return current
    return candidate


def _contains_secret(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, default=str)
    return any(pattern.search(text) for _, pattern in _SECRET_PATTERNS)


def _access_allows(item_level: str, caller_clearance: str) -> bool:
    return _ACCESS_RANK.get(item_level, 99) <= _ACCESS_RANK.get(caller_clearance, -1)


def _parse_timestamp(value: Any) -> _dt.datetime | None:
    if not isinstance(value, str) or not _TIMESTAMP_RE.match(value):
        return None
    try:
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _expect_timestamp(
    value: Any,
    source: str,
    field_name: str,
    findings: list[Finding],
) -> _dt.datetime | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        _add(findings, source, field_name, "timestamp", "timestamp must be valid UTC YYYY-MM-DDTHH:MM:SSZ")
    return parsed


def _expect_hash(value: Any, source: str, field_name: str, findings: list[Finding]) -> None:
    if not isinstance(value, str) or not _HASH_RE.match(value):
        _add(findings, source, field_name, "hash-format", "hash must be sha256:<64 lowercase hex characters>")


def _expect_schema(
    payload: Mapping[str, Any],
    expected: str,
    source: str,
    findings: list[Finding],
) -> None:
    if payload.get("schema_version") != expected:
        _add(findings, source, "schema_version", "schema-version", f"schema_version must be {expected!r}")


def _expect_member(
    value: Any,
    allowed: Sequence[str],
    source: str,
    field_name: str,
    findings: list[Finding],
) -> None:
    if value not in allowed:
        _add(findings, source, field_name, "allowed-value", f"{field_name} must be one of {', '.join(allowed)}")


def _require_fields(
    payload: Mapping[str, Any],
    fields: Sequence[str],
    source: str,
    findings: list[Finding],
    *,
    prefix: str = "",
) -> None:
    for key in fields:
        if key not in payload:
            field_name = f"{prefix}.{key}" if prefix else key
            _add(findings, source, field_name, "required", f"{key} is required")


def _require_string(
    payload: Mapping[str, Any],
    key: str,
    source: str,
    findings: list[Finding],
    *,
    prefix: str = "",
) -> None:
    if not _string(payload.get(key)):
        field_name = f"{prefix}.{key}" if prefix else key
        _add(findings, source, field_name, "required", f"{key} must be a non-empty string")


def _expect_list(value: Any, source: str, field_name: str, findings: list[Finding]) -> bool:
    if not _is_list(value):
        _add(findings, source, field_name, "type", f"{field_name} must be a list")
        return False
    return True


def _expect_non_empty_list(value: Any, source: str, field_name: str, findings: list[Finding]) -> bool:
    if not _expect_list(value, source, field_name, findings):
        return False
    if not value:
        _add(findings, source, field_name, "required", f"{field_name} cannot be empty")
        return False
    return True


def _is_list(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _add(
    findings: list[Finding],
    source: str,
    field_name: str,
    code: str,
    message: str,
    *,
    severity: str = "error",
) -> None:
    findings.append(Finding(source, field_name, code, message, severity))
