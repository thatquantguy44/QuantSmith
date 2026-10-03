"""Asian-language NLP foundation (spec 0094): identification, segmentation, extraction,
evaluation, and baseline-vs-model comparison. Standard library only; no network, no model."""

from .compare import agreement_by_language, compare, decision_ready, validate_model_item
from .evaluate import (DEFAULT_MIN_N, MIN_CASES_PER_CELL, PooledScoreRefused, below_threshold,
                       evaluate_cases, pooled_score, render_markdown)
from .extract import KNOWN_FAILURE_MODES, extract, load_conventions, parse_number, verify_spans
from .identify import chinese_variant, identify, script_shares
from .normalize import normalize_text, normalize_with_offsets, original_span
from .segment import TOKENIZER_ID, TOKENIZER_VERSION, segment

__all__ = [
    "DEFAULT_MIN_N", "KNOWN_FAILURE_MODES", "MIN_CASES_PER_CELL", "PooledScoreRefused", "TOKENIZER_ID",
    "TOKENIZER_VERSION", "agreement_by_language", "below_threshold", "chinese_variant", "compare",
    "decision_ready", "evaluate_cases", "extract", "identify", "load_conventions", "normalize_text",
    "normalize_with_offsets", "original_span", "parse_number", "pooled_score", "render_markdown",
    "script_shares", "segment", "validate_model_item", "verify_spans",
]
