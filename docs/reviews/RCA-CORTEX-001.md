# RCA — CORTEX Double-Capture Bug
**Date:** 2026-06-01  
**Severity:** High (corrupted corpus; every mobile LinkedIn paste created a ghost capture)  
**Status:** Fixed + test coverage added

---

## What happened

Every time the user pasted a LinkedIn URL from mobile (without WhatsApp timestamps), CORTEX created two separate DB entries:
1. The URL — correctly classified as `food_for_thought`, `job_application`, etc.
2. The user's topic keyword ("Interesting read", "Swiggy", "Claude") — incorrectly classified as a standalone `general_note` or `food_for_thought`

The keyword was meant to be a topic hint for the URL (making the URL classify into the right sub-folder). Instead it became an orphaned ghost capture with no content value.

---

## Root cause

`splitter.py` Strategy 2 (double-newline split) fired on `URL\n\nkeyword` because it correctly identified two paragraphs separated by a blank line. It had no way to know that the second paragraph was a topic hint belonging to the first URL, not an independent capture.

The WhatsApp timestamp strategy (Strategy 1) handles this correctly — timestamps bind the URL and keyword into one item. But mobile sharing without timestamps falls through to Strategy 2, which has no URL+keyword awareness.

**Specific gap:** No test existed for the pattern `bare URL\n\n short keyword`. All URL+keyword tests used the inline format (`https://url.com keyword`) or the WhatsApp timestamp format. The double-newline format was only tested with two full standalone paragraphs.

---

## Why the test suite didn't catch it

The test `test_double_newline_splits` tested `https://url1.com\n\nhttps://url2.com` — two URLs. Correct result: 2 items.

The test `test_mixed_content` tested a URL with inline keyword, then a reminder, then another URL with inline keyword. All items were already complete — no bare URL + dangling keyword.

The gap: no test for `bare URL\n\nshort keyword` (the exact mobile sharing pattern).

---

## Fix

Added `_merge_url_keyword_pairs()` to `splitter.py`. After double-newline splitting, it re-merges consecutive `(bare URL, short-non-URL-text ≤ 60 chars)` pairs.

**Key discriminator:** Only bare URLs (nothing after the URL on the same line) trigger the merge. A URL that already has an inline keyword is already complete — don't merge it with the next chunk. This correctly handles the mixed case where some items have inline keywords and some need the next-line keyword attached.

---

## Structural fix — test coverage rule

**The gap that must not recur:** When a new splitting strategy is added, tests must cover ALL adjacent input patterns, not just the happy path and the multi-item path.

Specifically for any capture input parser: test the boundary between "this is one item" and "this is two items" — because that boundary is exactly where splitting bugs live.

New tests added to `test_splitter.py`:
- `test_url_newline_keyword_stays_one_item` — bare URL + short keyword → 1 item
- `test_url_newline_single_word_keyword_stays_one_item` — single word keyword
- `test_two_url_keyword_pairs_split_correctly` — two pairs → 2 items, each with keyword
- `test_url_newline_long_text_splits` — long text > 60 chars → 2 items (not a topic hint)
- `test_two_urls_no_keywords_split` — two bare URLs → 2 items (no merge)
- `test_url_keyword_then_standalone_text` — pair + standalone → 2 items

---

## Secondary bugs found during review

The bug investigation surfaced two additional issues fixed in the same session:

**Completed items not filtered from feed:** `get_captures()` filtered `archived = 0` but not `completed = 0`. PRD §10 specifies completed items leave the feed. Fixed in `db.py`. Test added: `test_completed_removed_from_feed`.

**Legacy taxonomy renders as Unclear:** Pre-v1.2 captures (`blog_post`, `job_post`) are in the DB but not in `CONTENT_TYPES`. They rendered as ❓ Unclear. Fixed in `config.py` with backward-compat display entries.

---

## Process change

**New rule (applies to CORTEX and all projects with input parsers):**

> When any splitting, parsing, or tokenisation function is written or modified, the test suite must include cases for the boundary between "treat as one item" and "treat as multiple items." Boundary cases are where parser bugs live. Happy path + multi-item tests are necessary but not sufficient.

This rule is being propagated to Product Staff ANTI-PATTERNS.md as AP-XX (see Learning Manager propagation).
