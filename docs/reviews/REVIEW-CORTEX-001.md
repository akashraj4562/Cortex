# CORTEX — Full Implementation Review
**Date:** 2026-06-01  
**Triggered by:** Double-capture bug report  
**Mandate:** Verify that the ICE intent (Intent Classification Engine) is at the core of the implementation, and identify all gaps.  
**Status:** COMPLETE — 4 issues found, 3 fixed, 1 logged to backlog.

---

## Verdict: Intent IS at the core. Three structural gaps found alongside the reported bug.

The architecture correctly implements the ICE philosophy: intent-based taxonomy, server-driven UI, explicit override pipeline, URL inference, confidence threshold. The gaps are in the feedback loop (no reclassify UI), a silent data bug (completed items in feed), and orphaned legacy data rendering.

---

## PM Agent — Intent Alignment Scorecard

| Principle | Implementation | Status |
|---|---|---|
| Classify by intent, not content type | 8 intent-based types; `_SYSTEM` prompt frames "what will Akash DO?" | ✅ |
| Zero friction capture | Single paste box; auto-focus; Enter to submit | ✅ |
| Server-driven UI | Backend returns `display{}` block with icon/color/label/actions; frontend is pure renderer | ✅ |
| Explicit user intent overrides Claude | Keyword map checked before Claude is called; locked if matched | ✅ |
| URL pattern inference | LinkedIn `/jobs/`, `/posts/`, Substack → typed before Claude runs | ✅ |
| Honest uncertainty | Confidence threshold 0.70; below = `unclassified` card | ✅ |
| Intent-specific actions | `complete` only on reminder; `open_url` only when URL present; `archive` universal | ✅ |
| Topic sub-foldering | `food_for_thought`, `build_better`, `learning`, `interview_exp` grouped by topic | ✅ |
| Feedback loop / reclassify | Cards have no override/reclassify action | ❌ **MISSING** |
| Completed items leave the feed | Completed items were NOT filtered from `get_captures()` | ❌ **FIXED** |
| Corpus integrity | Split bug created orphaned keyword captures ("Interesting read" as standalone `general_note`) | ❌ **FIXED** |
| Legacy data renders correctly | `blog_post`/`job_post` (pre-v1.2) rendered as ❓ Unclear | ❌ **FIXED** |

---

## AI Engineer — Classification Engine Review

**Model:** `claude-opus-4-8` ✅ (correct for judgment-heavy classification)

**System prompt quality:**
- Intent framing is explicit: "what will Akash DO with this?" — correct
- Priority ordering (keyword → URL pattern → content) is documented inside the prompt — good
- `food_for_thought` vs `build_better` distinction is explained — needed, edge is real
- `NEVER return confidence below 0.72 for real text input` — this is a floor instruction that conflicts with the honest-uncertainty principle. If Claude is genuinely uncertain, forcing confidence ≥ 0.72 means the item won't hit the `unclassified` fallback when it should. **Recommendation: remove the floor; let confidence be honest.**
- `"claude" → learning` in the keyword map is Akash-specific — correct for a personal tool; would need to be user-configurable in Phase 3+.

**Classification pipeline robustness:**
- Exception handling catches both `json.JSONDecodeError` and generic `Exception` — returns `unclassified` gracefully ✅
- `is_substack` override after Claude runs is correct layering ✅
- `explicit_type` respected after Claude runs ✅

**One concern:** The explicit type is applied post-Claude only if `confidence >= 0.50`. This means a very low-confidence misclassification could bypass the explicit override. The explicit_type from the user's keyword is their stated intent — it should always win regardless of confidence.

---

## Data Analyst — Instrumentation & NSM

**North Star Metric (PRD §4):** `% of captures correctly auto-classified without override`  
**Current state:** Unmeasurable. There is no override log in the DB schema.

**What can be measured now:**
```sql
-- Unclassified rate
SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM captures) 
FROM captures WHERE content_type = 'unclassified';

-- Capture volume by day
SELECT DATE(created_at), COUNT(*) FROM captures GROUP BY DATE(created_at);

-- Type distribution
SELECT content_type, COUNT(*) FROM captures GROUP BY content_type;

-- Confidence distribution
SELECT ROUND(confidence, 1) as band, COUNT(*) FROM captures GROUP BY band;
```

**What's missing for the NSM:** An `overrides` table (logged when user reclassifies). Without it, we can only measure unclassified rate — a proxy, not the true accuracy metric.

**Current unclassified rate (live data):** 0 out of 38 active captures = 0% unclassified. 
Classification accuracy appears high, but cannot be confirmed without override data.

---

## UX Designer — Capture & Feed Review

**Capture box:** ✅ Full-width, auto-focus, placeholder text explains the pattern, 44px touch targets for mobile.

**Feed cards:** ✅ Icon + color coding per type, title + subtitle, action buttons below body.

**Mobile (iOS):** ✅ `safe-area-inset-bottom`, viewport-fit=cover, `-webkit-tap-highlight-color` disabled.

**Gap — Override/Reclassify:**  
Every card shows what CORTEX classified but there is no way to say "wrong, this is actually a job application." The Vision document and PRD §7 both state this is core. Without it:
- Misclassified items sit in the wrong tab permanently
- The user's only recourse is to archive and re-paste, which corrupts the corpus
- The ICE has no feedback mechanism — it cannot learn

**Proposed override UX (for next PRD):**  
Small "✏️ reclassify" link below rationale text. Tapping opens an inline type-selector (8 types as chips). Selecting a type fires `POST /api/capture/<id>/reclassify` with the new type. Card updates in place. Override is logged.

---

## Tech Lead — Code Quality Review

**Strengths:**
- Single-table schema with JSON metadata blob — correct choice for a personal tool; flexible, queryable, upgradeable
- WAL mode enabled on every connection — correct for concurrent reads
- `_row_to_card` is the single rendering path — no display logic leaking into routes
- Splitter strategies are correctly ordered and independent

**Issues found and fixed:**
1. `get_captures()` did not filter `completed = 0` — completed reminders appeared in All feed (fixed: added condition)
2. Legacy `blog_post`/`job_post` types not in `CONTENT_TYPES` — rendered as ❓ Unclear (fixed: added backward-compat entries)
3. Splitter `_merge_url_keyword_pairs` missing — caused double-capture on `URL\n\nkeyword` pattern (fixed: new function added)

**Remaining technical debt:**
- The `_WA_TIMESTAMP` regex in `splitter.py` is a comment-heavy pattern; add a named-group version for readability when time permits
- `db.get_captures_grouped_by_topic` docstring still says "learning and blog_post views" — should say "learning and food_for_thought views"

**Backlog items identified (not in scope for this review):**
- `POST /api/capture/<id>/reclassify` — needed for override UX (P1)
- `overrides` table in DB schema — needed for NSM measurement (P1)

---

## Prompt Engineer — Prompt Risks

One structural risk in the current `_SYSTEM` prompt:

```
IMPORTANT RULES:
- NEVER return confidence below 0.72 for real text input.
```

This instruction conflicts with the confidence threshold design. If Claude cannot classify something (genuinely ambiguous input), forcing confidence ≥ 0.72 means it will return a wrong type at 0.72 rather than `unclassified` at 0.65. The `unclassified` path exists exactly for these cases — the prompt shouldn't suppress it.

**Recommended change:** Remove the floor. Replace with: *"For inputs with clear text or URL signals, confidence should typically be 0.75+. Only return low confidence for genuinely ambiguous input — do not inflate."*

This preserves Claude's ability to be honest while still guiding toward confident classification on clear inputs.

---

## P1 Backlog — Logged

| Item | Priority | What it unlocks |
|---|---|---|
| Override/reclassify UI (`✏️` on each card) | **P1** | ICE feedback loop; user can correct misclassifications |
| `POST /api/capture/<id>/reclassify` endpoint | **P1** | Required for override UI |
| `overrides` table in DB | **P1** | NSM measurement; classification accuracy tracking |
| Remove confidence floor from `_SYSTEM` prompt | **P1** | Honest uncertainty; correct `unclassified` fallback |

---

## Fixes Shipped in This Review

| Fix | File(s) | Tests added |
|---|---|---|
| Splitter double-capture: `URL\n\nkeyword` split into two items | `splitter.py` | 6 new splitter tests |
| Completed items not filtered from feed | `db.py` | `test_completed_removed_from_feed` |
| Legacy `blog_post`/`job_post` rendering as ❓ Unclear | `config.py` | — (display-only; existing tests cover config loading) |

**Tests:** 81/81 passing.
