# Asian-Language NLP Foundation (Spec 0094)

A dependency-free, deterministic baseline for text in Mandarin (Simplified and
Traditional), Japanese, Korean, Thai, Vietnamese, Indonesian/Malay, Filipino, Russian,
Kazakh, Uzbek, and English. It makes the `multilingual_document_nlp` agent's promises
testable and gives any model-based extraction something to be compared against.

| Module | What it does |
| --- | --- |
| `normalize.py` | NFKC and Thai-digit normalization per grapheme cluster, with offsets back to the original text |
| `identify.py` | Script and candidate-language identification; `undetermined` with reasons for short, mixed, or unsupported text |
| `segment.py` | Whitespace tokens for spaced scripts, character n-grams for Han/kana/Thai, and a declared `segmenter` slot |
| `extract.py` | Amounts, currencies, dates, era years, and fiscal periods with verbatim spans and offsets; ambiguity flagged, never guessed |
| `evaluate.py` | Per-language, per-type precision/recall/exact-match; refuses a pooled score that would hide a thin cell |
| `compare.py` | Baseline-versus-model comparison; never overwrites a baseline value; model items need provenance and a named reviewer |
| `lexicon.py` | Month names and identification word lists (conventions live in `knowledge/venture_intelligence/conventions.json`) |
| `fixtures/` | Synthetic labelled cases (199 extraction, 41 identification) |

```python
from quantsmith.asian_nlp import extract, identify, segment

extract("估值1,200万美元,2024年3月31日", "zh-Hans")
identify("บริษัทได้รับเงินลงทุนจากนักลงทุนหลายรายในปีที่ผ่านมา")["language"]   # 'th'
```

## What it is not

- Not a translator, OCR, or entity recognizer; not trained on real documents.
- Character n-grams are a search baseline, not word segmentation; a dictionary segmenter
  or model plugs in through `segment(..., segmenter=...)` and must declare
  `tokenizer_id` and `tokenizer_version`.
- Scores apply only to the labelled synthetic fixtures; they are not general accuracy.
- Kazakh, Uzbek, and Filipino month names are unverified (`gap.kk_uz_fil_month_lexicons`).
- Known failure modes per language: `KNOWN_FAILURE_MODES` in `extract.py`.

Conventions are read from the repository checkout, so run from a checkout (or pass
`conventions=` to `extract`). Tests: `tests/test_asian_nlp.py`. Spec:
`specs/0094-asian-language-nlp-foundation/`.
