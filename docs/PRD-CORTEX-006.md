# PRD-CORTEX-006 — Hindi / Multilingual Image Understanding

**Version:** 1.0 | **Date:** 2026-06-24 | **Status:** Draft → Gate-2 reviewed | **Owner:** Akash Raj
**PM:** product-manager | **AI Engineer:** ai-engineer | **Phase:** 1 (Personal Tool)

**Grounded in code (read before building):** `classifier.py` → `classify_image()` + `_IMAGE_SYSTEM` (Opus-4-8 vision); `image_processor.py` → `process_image()` (decode/orient/resize, Haiku orientation check); `app.py` image-capture route; `captures.metadata` is a JSON TEXT blob (so new metadata fields need **no schema migration**).

---

## 1. Problem

CORTEX accepts image captures (camera + upload, shipped). `classify_image()` sends the image to Corty (`claude-opus-4-8` vision) with `_IMAGE_SYSTEM`, which asks for `metadata.extracted_text` = "all visible text from the image, verbatim." The model can read Devanagari, but the **prompt and pipeline are English-centric** and were never validated on Hindi:

1. The prompt never tells Corty what to do when the text is **not** English. Downstream fields the system actually uses — `title`, `summary`, `topic`, and especially `shopping_list.items` (which feed Zepto search) — are implicitly English. A Hindi grocery-list photo (`दूध, अंडे, ब्रेड`) may yield items in Devanagari that **Zepto search cannot match**, breaking the capture→cart flow.
2. There is **no `language` signal** and no separation between the **verbatim original** and the **normalized/usable** text.
3. There is **zero regression coverage** for non-Latin scripts — a future prompt edit could silently degrade Hindi handling.

Real friction: Akash photographs Hindi text (a handwritten list, a shop sign, a note) and Corty either under-classifies it or produces metadata he can't act on.

---

## 2. Vision alignment

**Phase 1 — Personal Tool.** Corty's classification accuracy is the **primary Phase-1 quality signal** (per the PM + AI-Engineer mandates). Reading the owner's real-world inputs — many of which are in Hindi or mixed Hindi/English — directly raises accuracy and widens what the corpus can absorb. That corpus depth is the Phase-2 (Thinking Mirror) precondition. **Phase-gate: PASS — pure Phase-1 accuracy feature.** No embeddings, no multi-user, no later-phase dependency.

---

## 3. User story

```
As Akash, when I upload or capture an image containing Hindi (or mixed Hindi/English) text,
I want Corty to read it, understand the intent, and give me usable English-normalized metadata,
so that a Hindi grocery list still becomes Zepto-searchable items and a Hindi note is correctly classified and titled.
```

**JTBD:** When I capture something written in Hindi, I want CORTEX to understand it as well as it understands English — same classification, same actionability.

---

## 4. Success metrics

| # | Metric | Target | Source | Type |
|---|---|---|---|---|
| M-1 | Hindi-image classification accuracy (override rate on a Hindi/mixed test set) | <20% override — parity with English | manual audit of the Hindi test set + live spot-check | Primary |
| M-2 | Verbatim OCR fidelity (`original_text` matches the Devanagari in the image) | 100% on the test set | test-set assertion | Quality |
| M-3 | Hindi `shopping_list` items are English/romanized & Zepto-searchable | ≥80% of items return a Zepto match | search spot-check (needs live token) | Actionability |
| M-4 | **English-image regression** (accuracy unchanged) | 0 regressions; all 207 tests green | `pytest tests/ -v` + English spot-check | **Anti-metric** |

**Primary:** Hindi images classify as accurately as English ones. **Anti-metric (hard):** no regression on existing English image/text classification — the 207-test suite stays green and the `unclassified` rate does not rise.

---

## 5. Scope — In

- [ ] **`_IMAGE_SYSTEM` prompt upgrade (`classifier.py`):** add an explicit multilingual block —
  - Read text in **any language/script**; Hindi/Devanagari is first-class.
  - `metadata.extracted_text` and a new `metadata.original_text` = **verbatim original script** (no translation).
  - New `metadata.language` = ISO-ish tag: `"hi"` | `"en"` | `"mixed"` | other.
  - All **action/display fields stay English**: `title`, `summary`, `topic`, `rationale`, `tags`, and **`shopping_list.items` normalized to English/romanized grocery names** for search (e.g. `दूध` → `"milk"`, `आटा` → `"atta"`). Keep the original in `original_text`.
  - Intent classification is **language-independent** — a Hindi grocery list is still `shopping_list` at the same confidence as its English equivalent.
- [ ] **Apply the same multilingual rule to the text `_SYSTEM` / `_SIMILARITY_SYSTEM`** (typed Hindi text, not just images) — scoped minimally: items/title/summary normalized to English, `original_text`+`language` captured. (Low effort; keeps text and image paths consistent.)
- [ ] **UTF-8 integrity audit:** confirm Devanagari round-trips end-to-end — `json.loads` (UTF-8 native), SQLite TEXT (UTF-8), Flask `jsonify` (`ensure_ascii` behavior), and the template render. Add an assertion. No code change expected unless an `ascii` encode is found.
- [ ] **Metadata fields:** `language`, `original_text` added to the image (and text) metadata JSON. JSON blob → **no schema migration.**
- [ ] **Regression + new tests (`tests/`):** a Hindi/mixed fixture set (mocked Claude responses) asserting routing/normalization for `shopping_list`, `reminder`, `general_note`; a UTF-8 round-trip test; the AI-Engineer spot-check protocol (§7) documented in the test plan.

---

## 6. Scope — Out

| Excluded | Why |
|---|---|
| Localizing the CORTEX UI into Hindi | This is about Corty **understanding** Hindi input, not a Hindi interface. UI stays English. |
| Languages beyond Hindi + English (Tamil, Bengali, …) | Opus may handle them, but v1 only **claims & tests** Hindi/English. Others may work but are unvalidated. |
| Handwriting / audio beyond what Opus vision already does | No pipeline change; rely on the model's native capability. |
| Translating the existing corpus | Backfill is out of scope; applies to new captures only. |
| Model change | Stays `claude-opus-4-8` — its vision + multilingual reasoning is exactly why we don't downgrade (AI-Engineer rule). |

---

## 7. Classification impact (AI Engineer — required)

**Touches `_IMAGE_SYSTEM` and the text `_SYSTEM`/`_SIMILARITY_SYSTEM` → full regression protocol applies.**

Per the AI-Engineer mandate, before/after any change to these prompts:
1. `python -m pytest tests/test_classifier_parse.py tests/test_classify_image.py -v` — all green before and after.
2. Manual spot-check on 10 real inputs across all types — **5 English (regression) + 5 Hindi/mixed (new)**.
3. Verify the `unclassified` rate does not rise (`db.get_captures(content_type='unknown')` count stable).
4. Confidence calibration: Hindi inputs must clear the same `HIGH_CONFIDENCE = 0.80` bar as English for unambiguous types (`shopping_list`, `reminder`). If Hindi confidence is systematically lower, the prompt's multilingual block is under-instructing — fix the prompt, do not lower the threshold.
5. Post-ship: monitor override rate 48h (target <20%).

**Model selection:** unchanged. Opus reads Devanagari and reasons about intent in one call — no separate OCR stage, no Haiku downgrade.

---

## 8. Data model changes

`captures.metadata` is already a JSON TEXT blob holding `structured_data`, `extracted_text`, etc. Adding `language` and `original_text` is **additive inside the JSON** — **no `ALTER TABLE`, no migration.** P-16 trivially satisfied. The orientation/resize pipeline in `image_processor.py` is language-agnostic and unchanged.

---

## 9. Open questions

| # | Question | Owner | Status |
|---|---|---|---|
| Q1 | Which Hindi inputs matter most to the owner — grocery lists, notes, signs? | PM → owner | Assume grocery lists + notes drive v1 (they hit the Zepto flow + capture habit). Confirm with owner. |
| Q2 | For `shopping_list` items: translate (`दूध`→`milk`) or transliterate (`आटा`→`atta`)? | AI Engineer | v1: **search-normalized English** — translate where a common English grocery term exists, else romanize. Both stored; `original_text` keeps Devanagari. |
| Q3 | Does Flask `jsonify` emit `ensure_ascii=True` (escaping Devanagari to `\uXXXX`)? | Tech Lead | Functionally fine (still valid UTF-8 on parse) but confirm template renders the glyphs; set `app.config['JSON_AS_ASCII']=False` if display needs it. Resolve at Gate-4. |

---

## 10. Proof-of-value gate

```
Behavior change: After ship, Akash captures Hindi-text images and Corty classifies + normalizes them
as well as English — a Hindi grocery photo becomes Zepto-searchable items.
Observable signal: a Hindi-image capture produces correct type + English-normalized shopping_list items,
with original_text holding the Devanagari, within the first session of use.
Assumption: the model can already read Devanagari (true for Opus-4-8); the gap is prompt instruction +
downstream normalization + test coverage — all addressed here.
```

---

## 11. Gate-2 team review

**PM:** Phase-1 accuracy feature, clean phase-gate PASS. Anti-metric (no English regression) is the right guardrail. Approve.
**AI Engineer:** The fix is prompt-level, not model-level — correct call. Insist on the §7 regression protocol and a Hindi fixture set in `tests/` *before* merge. Watch confidence calibration on mixed-script (don't paper over with a lower threshold). Approve with protocol.
**Tech Lead:** Zero schema migration (JSON blob) — low risk. Only real engineering is the UTF-8 audit + tests. Feasibility GREEN, ~prompt edits + ~3 test files. See `TECH-CORTEX-006`.
**UX Designer:** Show `original_text` (Devanagari) on the card alongside the English title/summary so the user trusts the OCR. Minor card-template addition.
**Data Analyst:** M-1/M-4 measurable via the override audit + pytest; M-3 needs a live Zepto token (shares the PRD-005 re-auth dependency).

**Gate-2 verdict: PASS** with the AI-Engineer regression protocol as a merge gate.

---

## 12. Team sign-offs

| Team | Sign-off | Notes |
|---|---|---|
| PM | ✅ | Phase-1, anti-regression guardrail set |
| AI Engineer | ✅ (with protocol) | §7 regression + Hindi fixtures are a merge gate |
| Tech Lead | ✅ | No migration; UTF-8 audit + tests |
| UX Designer | ✅ | Card shows original_text + English |
| Data Analyst | ✅ | Override audit instrumentation |

---
*Personal-tool PRD. Analytical output for the CORTEX Product Staff process.*
