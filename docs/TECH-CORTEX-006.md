# TECH-CORTEX-006 — Hindi / Multilingual Understanding · Implementation Plan

**Owner:** tech-lead + ai-engineer | **For:** PRD-CORTEX-006 | **Date:** 2026-06-24
**Estimate:** prompt edits + ~3 test files. **No schema migration, no model change, no new deps.**

> Gate (AI-Engineer): the §5 regression protocol below is a **merge gate** — Hindi fixtures + green suite before this ships.

---

## Files touched

| File | Change |
|---|---|
| `classifier.py` | multilingual block in `_IMAGE_SYSTEM`; same rule in `_SYSTEM`/`_SIMILARITY_SYSTEM`; add `language` + `original_text` to the JSON schemas |
| `app.py` | (only if Q3 needs it) `app.config['JSON_AS_ASCII'] = False` for Devanagari display |
| `templates/index.html` | card shows `original_text` (Devanagari) under the English title/summary |
| `tests/test_classify_image.py`, `tests/test_classifier_parse.py`, + new `tests/test_multilingual.py` | Hindi/mixed fixtures, UTF-8 round-trip, normalization asserts (Claude mocked) |

---

## 1. `classifier.py` — prompt changes

### 1a. Add to `_IMAGE_SYSTEM` (and mirror in `_SYSTEM`/`_SIMILARITY_SYSTEM`), before the JSON schema:

```
## Multilingual input (Hindi & mixed Hindi/English are first-class)
- Read text in ANY language or script. Devanagari/Hindi is fully supported.
- Classify by INTENT independent of language: a Hindi grocery list is `shopping_list`
  at the SAME confidence as its English equivalent. Never lower confidence just because
  the text is not English.
- `metadata.original_text`: the visible text VERBATIM in its original script (no translation).
- `metadata.language`: "hi" | "en" | "mixed" | <iso> — the dominant script/language.
- ALL action & display fields MUST be English: `rationale`, `tags`, `title`, `summary`,
  `topic`, and `shopping_list.items`. Normalize each shopping item to the English/romanized
  grocery name used for search (दूध→"milk", आटा→"atta", अंडे→"eggs", प्याज़→"onions");
  keep the original phrasing in `original_text`.
```

### 1b. Schema additions

Add `"language"` and `"original_text"` to the returned `metadata` object in every schema block (`_IMAGE_SYSTEM`, `_SYSTEM`, `_SIMILARITY_SYSTEM`). Both optional/back-compatible — absent on old captures, present going forward.

### 1c. No parsing-code change required

`_parse_llm_json` / `json.loads` are UTF-8 native and already `setdefault("metadata", {})`. `language`/`original_text` flow through untouched. `extract_shopping_items` (Haiku) — add one line to its system prompt: *"Item names must be English/romanized for grocery search even if the input is in Hindi."*

## 2. UTF-8 integrity audit (no change expected; verify + assert)

| Layer | Check |
|---|---|
| `json.loads` (classifier) | UTF-8 native ✓ |
| SQLite store (`db.insert_capture`) | column is TEXT (UTF-8) ✓ — assert round-trip of `दूध, अंडे` in `test_db` |
| Flask `jsonify` | default `JSON_AS_ASCII=True` escapes to `\uXXXX` — still valid; if the card must render glyphs from the API, set `app.config['JSON_AS_ASCII']=False` (Q3, decide at build) |
| Template render | ensure UTF-8 meta + no `.encode('ascii')` anywhere — `grep -rn "encode('ascii')\|encode(\"ascii\")" .` must be empty |

## 3. `templates/index.html`

On the capture card, when `metadata.original_text` exists and `language != "en"`, render it in a muted line under the English title: `<div class="orig-text" lang="hi">{original_text}</div>` — builds trust that the OCR read the Hindi correctly.

---

## 4. Tests (`tests/`, Claude mocked)

`tests/test_multilingual.py` (new):
1. **Routing parity:** mocked Corty returns a Hindi `shopping_list` (`original_text:"दूध, अंडे, ब्रेड"`, items `["milk","eggs","bread"]`, language `"hi"`, conf 0.9) → `_compute_routing` → `assign` (not `unknown`). Same for a Hindi `reminder`.
2. **Normalization contract:** assert items are ASCII/English while `original_text` holds Devanagari; `language` set.
3. **UTF-8 round-trip:** insert a capture with Devanagari metadata → read back byte-identical (`test_db`).
4. **No-regression:** existing `test_classify_image.py` / `test_classifier_parse.py` unchanged and green.

## 5. Regression protocol (AI-Engineer merge gate)

```
BEFORE merge:
  python -m pytest tests/test_classifier_parse.py tests/test_classify_image.py tests/test_multilingual.py -v   # all green
  10-input spot-check: 5 English (regression) + 5 Hindi/mixed (new), across shopping_list/reminder/general_note
  db.get_captures(content_type='unknown') count must NOT rise vs baseline
  Hindi unambiguous types clear HIGH_CONFIDENCE=0.80 — if not, strengthen the prompt block, DO NOT lower the threshold
AFTER ship:
  monitor override rate 48h (<20%); confirm a real Hindi grocery photo → English items that return Zepto matches (needs token re-auth)
```

## 6. Build order (Gate-4)

```
1. Edit _IMAGE_SYSTEM + _SYSTEM + _SIMILARITY_SYSTEM (1a–1b) + extract_shopping_items line
2. Add tests/test_multilingual.py + UTF-8 round-trip in test_db
3. Run full suite (207 + new) green
4. UTF-8 audit grep; decide JSON_AS_ASCII (Q3)
5. Card template: show original_text
6. Live spot-check: 5 Hindi images across types; confirm normalization + no English regression
```

**Definition of done:** suite green incl. Hindi fixtures; English `unknown` rate unchanged; a Hindi grocery image yields English-normalized `shopping_list.items` + Devanagari `original_text`; card shows both.
