# Gate 2 Review — PRD-CORTEX-003: Zepto Cart from Grocery List

**Reviewers:** product-manager · ai-engineer · tech-lead · data-analyst · uiux-designer
**Review date:** 2026-06-04
**PRD status going in:** In Review
**PRD status coming out:** CONDITIONAL APPROVAL

---

## 1. PM Review

### Problem statement
Holds up well. The framing — "CORTEX captures intent but cannot act on it; a shopping_list capture is a dead-end" — is genuinely consistent with VISION-CORTEX.md §1 (Intent Loss) and is the clearest single demonstration of CORTEX's "capture → act" thesis to date. The cost-of-not-solving is articulated. The `[ASSUMPTION: no data]` marker is correctly applied per AP-06.

**Caveat:** §1 has only one assumption marker but contains two assumptions. The "10–15 minutes of friction for a 15-item list" claim is also unsourced and needs the same marker. This is a minor AP-06 catch.

### Scope correctness for v1
The cart-add-not-checkout boundary is exactly right. `order_placement` deferral via the §6 table is the single most important scope call in this PRD — keep it. The "match-and-confirm flow rather than silent auto-select" decision in §2 is correct: the asymmetry of getting a match wrong (annoyance + money) vs. correct (one less tap) overwhelmingly favors confirmation.

**Missing from scope:**
- **No quantity disambiguation contract.** §5 says items are extracted with `qty: "5kg"` or `qty: "2"`. But Zepto products come in pack sizes ("Amul Taaza 1L", "Amul Taaza 2L pack"). The PRD does not specify the matching rule when the user says "2L milk" and Zepto has only a 1L pack — does CORTEX add 2x1L? 1x2L? Defer to user? **This needs a §7 sub-section, not an open question** — it's load-bearing for the match-review UI.
- **No definition of "best match."** §5 says "find the best matching product" but never defines the heuristic. This is the single most important match-quality lever and is currently a black box.
- **Save-only escape hatch** is mentioned (§7.5) but absent from the §5 scope checklist. Should be lifted into scope.

### Success metrics measurability
M-1, M-3, M-4, M-5 are clearly measurable with the §13 events. **M-2 (item match rate) has a measurement gap:** `items_matched / items_searched` requires defining "matched" — is a returned result always a match? A returned-but-rejected-by-user result? The event schema does not distinguish. This needs explicit definition before instrumentation goes live.

### Phase gate
This is the most contested part of the review. The PRD asserts Phase 1 in §16's footer and §6. The Phase 1 mandate (CORTEX CLAUDE.md) is "capture habit forming, private corpus growing." Cart-add to an external commerce platform is **not** classical Phase 1 work — it's closer to Vector I (Ambient Capture) execution territory.

**However:** the Causal Systems argument lands. The cart-add feature directly drives capture rate (the Phase 1 NSM) because users will return to CORTEX specifically to use the action, forming a daily/weekly ritual around shopping. This is *not* Phase 2 (Thinking Mirror — requires 500+ captures) and is *not* Phase 4 (Communal Boards). It's a single-user habit-deepening feature with an external write.

**Verdict on phase gate:** Acceptable as a Phase 1 *habit deepener* — but only if the AP-15-style trust risk (real money, real consequences) is managed by the confirmation gate the PRD already specifies. If the confirmation gate ever erodes, this becomes a Phase 1 trust-violating feature and the case for Phase 1 inclusion collapses.

### PM verdict: **CONDITIONAL PASS**

Conditions: (1) Add quantity/match heuristic sub-section to §7; (2) Define "match" operationally in M-2; (3) Add second assumption marker on §1's "10–15 minutes" claim.

---

## 2. AI Engineer Review

### Item extraction approach — soundness
Reasonable as framed but underspecified. The PRD treats item extraction as a single capability without distinguishing the three different extraction surfaces, which have different difficulty profiles:

| Surface | Difficulty | Risk |
|---|---|---|
| Pasted bullet/numbered list | Low — high parsability | Format permissiveness, list-vs-prose disambiguation |
| WhatsApp paste with names/timestamps | Medium — paraphrase noise ("ma kehte hain doodh laana") | False positives, embedded non-items |
| Handwritten/photo of list (image path) | Medium-High — OCR + regional script + Hinglish | OCR errors, script switching, abbreviated units |

A single extraction prompt will not handle all three optimally. **Recommendation:** one prompt with conditional sections (text-list vs. image-of-list) — the prompt branches on `input_type` already present in PRD-CORTEX-002's metadata schema.

### Prompt strategy
Structured JSON output, function-calling-style. Recommended structure:
```json
{
  "items": [
    {
      "name_raw": "doodh",
      "name_normalized": "milk",
      "qty_value": 2,
      "qty_unit": "litre",
      "qty_confidence": 0.85,
      "notes": "Amul brand preferred"
    }
  ],
  "extraction_confidence": 0.92,
  "language_detected": ["en", "hi"],
  "non_items_skipped": ["pickup at 6pm"]
}
```
This contract gives the search layer everything it needs (normalized English query for `search_products`) plus an audit trail (`name_raw`) for the confirmation UI.

### Zepto MCP integration architecture
PRD §8 is most wrong here. Offering "Claude Code MCP tool OR equivalent server-side HTTP call" is two completely different architectures:

| Option | Description | Verdict |
|---|---|---|
| **A. Claude Code MCP tool** | CORTEX server calls a Claude Code subprocess | **REJECT** — requires Claude Code on server, OAuth through Claude Code's token store, cart-add endpoint becomes a CLI shell-out. Brittle, slow, wrong. |
| **B. Direct HTTP client from Flask** | CORTEX Flask app implements MCP HTTP client, holds OAuth token in own SQLite | **RECOMMEND** — full control of auth lifecycle, request batching, retries, logging, degradation. |

**Strong recommendation: Option B. Make explicit in §8 before Gate 5.**

### Model choice for extraction
| Model | Pros | Cons | Verdict |
|---|---|---|---|
| Haiku | Fast (~1s), cheap (~$0.001/list) | Worse at Hinglish/regional units | Use for **text-input path** |
| Opus (claude-opus-4-8) | High accuracy, native image support | 3–5x slower, ~10x cost | Use for **image-input path** (already required for OCR) |

### Dynamic taxonomy fit
`shopping_list` fits cleanly. One classifier conflict to flag: a "reminder" capture and a "shopping_list" capture can look identical ("buy milk and eggs"). Today's classifier defaults "buy milk and eggs" to `reminder`. The classifier prompt needs an explicit disambiguation rule:
> A capture is `shopping_list` (not `reminder`) when (a) ≥2 commerce-likely items are present, OR (b) ≥1 item has a quantity/unit token.

### Failure modes in item extraction
1. "ek kilo" / "half dozen" / "do packet" — solve via few-shot examples in prompt (5–8 cases)
2. Compound items — "atta and dal" as one bullet — prompt must instruct split
3. Brand+item — "Amul butter 100g" — extract brand as search-time bias, not separate item
4. OCR errors on photo of list — add "did_you_mean" field in extraction JSON
5. Embedded non-items — "buy at 6pm" — covered by `non_items_skipped` field
6. Empty extraction — list parses to 0 items — need fallback: "I couldn't read this — try typing it?"

### Standalone vs. sub-type recommendation
**`shopping_list` should be a standalone content_type, not a sub-type.** Reasoning: different action surface (cart-add CTA, confirmation screen, fulfilment status); PRD-CORTEX-002 dynamic taxonomy supports first-class new types at zero cost; sub-typing leaks commerce logic into reminder handling; Vector G/H expansion (Phase 4+) likely needs `shopping_list` as a first-class type for routing to a "Family Grocery" communal board.

### AI Engineer verdict: **CONDITIONAL PASS**

Conditions: (1) Specify MCP architecture as Option B in §8; (2) Extraction prompt contract (JSON shape + regional quantity handling) specified before Gate 5; (3) Classifier disambiguation rule added to scope; (4) §14 row 6 resolved as "standalone" in this PRD.

---

## 3. Tech Lead Review

### Flask/SQLite capability
Flask is fully capable. Python `requests`-based MCP client is straightforward. SQLite is fine for auth token storage.

**Critical risk — synchronous request blocking:** 15 parallel `search_products` calls inside a synchronous Flask handler will block for the entire search window.

| Approach | Latency for 15 items | Risk |
|---|---|---|
| Sequential `requests` | 15 × ~1s = ~15s | Blows ≤8s target |
| `ThreadPoolExecutor` (10 workers) | ~1–2s | Acceptable. **Recommended.** |
| `asyncio` + `httpx` | ~1s | Requires async route rewrite — too invasive for v1 |

**Recommendation: `ThreadPoolExecutor` with `max_workers=10`.**

### OAuth flow for server-side Flask
The correct flow:
1. CORTEX exposes `GET /auth/zepto/start` → builds Zepto OAuth authorize URL with `redirect_uri=http://localhost:5050/auth/zepto/callback`
2. Browser redirects user to Zepto OAuth page → OTP verification on Zepto's domain
3. Zepto redirects back to CORTEX `/auth/zepto/callback?code=...&state=...`
4. CORTEX exchanges `code` for access + refresh tokens (server-to-server POST)
5. Tokens stored encrypted in SQLite

**The unknown (P0-2):** does Zepto's MCP OAuth client registration accept arbitrary localhost redirect URIs? If they whitelist only `claude.ai` and `claude-code` URIs, the entire architecture changes. Must resolve before Gate 3.

### Auth token storage schema
```sql
CREATE TABLE external_credentials (
  service       TEXT PRIMARY KEY,
  access_token  BLOB NOT NULL,       -- Fernet-encrypted
  refresh_token BLOB,                -- Fernet-encrypted
  expires_at    DATETIME,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME
);
```
Encryption key from `.env` (`CORTEX_ENCRYPTION_KEY`). For a single-user personal tool this is acceptable. Do not extend to Phase 3+ multi-user without HSM / OS keyring layer.

### Performance risk of parallel calls
- **Zepto-side rate limiting:** undocumented. Pilot with `max_workers=5`, raise to 10 only after 7+ days of no throttling.
- **Timeout cascade:** add per-call timeout (5s) and aggregate timeout (8s for the batch). Timed-out items show as "search failed — retry" in confirmation UI.

### New files/tables/migrations
| Artifact | Type | Purpose |
|---|---|---|
| `zepto_client.py` | New file | MCP HTTP client wrapper |
| `oauth_flask.py` | New file | OAuth start/callback handlers |
| `encryption.py` | New file | Fernet wrapper for token storage |
| `external_credentials` | New table | Encrypted token storage |
| `events` | New table | Instrumentation events (§13) |
| `classifier.py` | Modified | `shopping_list` disambiguation rule |
| `app.py` | Modified | `/api/zepto/*` routes |
| `templates/index.html` | Modified | Zepto CTA, confirmation modal, OAuth UI |
| `content_types` | Data | Insert `shopping_list` seed row |

**Existing files at risk:**
- `classifier.py` — disambiguation rule risks shifting existing `reminder` captures. **Mandatory:** regression test against the existing 38-capture corpus.
- `app.py` — `shopping_list` routing must verify it correctly hits the >0.80 confidence path, not the Unknown-staging path.

### P0 Security — confirmation enforcement
PRD §8 specifies a client-controlled `session_confirmed: true` flag. **This is trivially bypassable.** Any direct API call with this flag set will trigger cart-add without user review.

**Correct pattern:** Server issues a single-use `confirmation_token` (UUID) tied to `(capture_id, items_to_add)` with a 5-minute TTL, stored server-side. Confirmation UI submits with the token. Server validates token → tied to exact items → not expired → not previously used → executes cart-add → marks token consumed. Direct API call without a valid server-issued token → 403.

This makes the confirmation step **structurally** unbypassable, not just convention-bypassable.

### Technical feasibility verdict: **YELLOW**

Reasons: Zepto OAuth redirect URI compatibility unknown (could be RED); MCP API stability external; parallel call pattern untested against this MCP; confirmation enforcement as written is bypassable (P0 fix above). With the three P0 fixes, this becomes GREEN.

---

## 4. Data Analyst Review

### Metric definition quality
| Metric | Well-defined? | Issues |
|---|---|---|
| M-1 (conversion ≥70%) | Yes | Calibration concern — see below |
| M-2 (match rate ≥80%) | **No** | "Matched" undefined — returned? accepted? added? Three different numbers. |
| M-3 (time ≤45s median) | Yes | Clarify: from `shopping_list_captured` or `zepto_cta_accepted`? Auth time inflates the former. |
| M-4 (abandonment ≤20%) | Yes | |
| M-5 (unintended orders = 0) | Yes — excellent hard counter | |

### Instrumentation gaps (§13)
Missing events that must be added:
1. `zepto_match_overridden { capture_id, item_id, original_product_id, replacement_product_id }` — critical M-2 signal
2. `zepto_auth_failed { error_code, error_stage }` — auth funnel is incomplete without this
3. `shopping_list_extraction_empty { capture_id, input_type }` — undetected 0-item extractions are invisible
4. Per-item search latency (inside `zepto_search_completed` `items` array) — needed for parallel-calls diagnosis
5. Partial cart-add rollup — when 4/6 add and 2 fail, the success/fail count must be explicitly captured

### M-1 target calibration
70% is too aggressive for v1 with external dependency. Realistic funnel:

| Step | Realistic drop-off | Cumulative survival |
|---|---|---|
| capture → CTA shown | 95% | 95% |
| CTA accepted (vs save-only) | 80% | 76% |
| OAuth survives (first-time) | 70% | 53% |
| Search completes | 90% | 48% |
| Confirmation completes | 80% | **38%** |

**Recommendation:** keep 70% as 8-week target; add a 4-week interim milestone of 40%. Mark all targets `[ASSUMPTION: no baseline — calibrate after week 4]` per AP-06.

### Data Analyst verdict: **CONDITIONAL PASS**

Conditions: (1) Define "match" for M-2; (2) Add 5 missing events; (3) Re-anchor M-1 with 4-week interim target + assumption label; (4) Add calibration audit cadence (week 4, week 8, week 12) to §13.

---

## 5. UX Designer Review

### Confirmation screen sufficiency
§7 is directionally right but incomplete. Since this is cart-add (not checkout), one-tap confirm is defensible — the user still must go to Zepto to pay. Hard guardrail: M-5 = 0 unintended orders. Show aggregate total price prominently before the tap (currently missing from §7 mockup).

### "Not found" item state
Skipping silently is unacceptable. Required design:
- Skipped item appears in confirmation screen with ❌ icon and raw extraction shown
- CTA copy must read: "Add N items to cart (M skipped)" — not just "Add N items"
- Each skipped item offers "Search again" (relaxed query without quantity)
- Success screen re-states skipped items: "3 added. 2 not found — try searching in the Zepto app: kokum, dhania powder"

### [Add to Zepto] CTA placement
PRD is underspecified. Concrete placement:
1. **Inline on capture card** — primary path, consistent with `job_application` cards
2. **Post-capture toast/modal** — "Add to Zepto?" + "Save only" — highest-conversion path
3. **Shopping_list tab card view** — CTA persists until `zepto_fulfilled: true`

Missing: what does a `zepto_fulfilled: true` card look like? Should show "Cart added 2 days ago" + "Reopen in Zepto" link.

### OAuth failure UX (undesigned — gap)
Three failure paths not specified in §7:
1. OAuth abandoned (user closes tab) → return to capture card with "Connect Zepto when you're ready" + retry CTA
2. Token exchange failure → "Zepto connection failed. Try again." + retry CTA
3. Scope/permission denial → "Zepto did not grant cart access. [Help]"

### Match-review card — required content
For a confident accept/reject decision, per item:

| Information | In PRD? | Action |
|---|---|---|
| Raw user input ("doodh") | ❌ | Must add |
| Matched product full name | ✓ | |
| Pack size + quantity | ✓ | |
| Price | ✓ | |
| Product image (thumbnail) | ❌ | **Strongly recommended** — fastest visual disambiguation signal |
| "Why this match?" tap-to-expand | ❌ | Add for low-confidence matches |
| "Change match" action | ✓ implicit | |
| "Remove" action | ✓ implicit | |

Product thumbnail is the single highest-impact addition. Image beats text for grocery item verification every time.

### UX Designer verdict: **CONDITIONAL PASS**

Conditions: (1) Design OAuth failure/abandonment states (3 paths); (2) Match-review card must include raw user input, product thumbnail, skipped-item visibility in CTA copy; (3) Define `zepto_fulfilled: true` card state; (4) Aggregate total price visible before cart-add tap.

---

## Consolidated Review Verdict

| Reviewer | Verdict | Top 2 concerns |
|---|---|---|
| **PM** | CONDITIONAL PASS | (1) Add quantity/match heuristic to §7; (2) Define "match" operationally for M-2 |
| **AI Engineer** | CONDITIONAL PASS | (1) Specify MCP architecture as direct HTTP client (Option B); (2) Classifier disambiguation rule must be in scope |
| **Tech Lead** | YELLOW (conditional) | (1) Confirmation enforcement is bypassable — server-issued single-use token required; (2) Zepto OAuth localhost-redirect compatibility unknown |
| **Data Analyst** | CONDITIONAL PASS | (1) Define "matched" for M-2 + add 5 missing events; (2) Re-anchor M-1 with 4-week interim 40% target |
| **UX Designer** | CONDITIONAL PASS | (1) OAuth failure UX undesigned; (2) Match-review card needs thumbnail + raw input + skipped-item visibility |

---

## P0 Findings (must resolve before ANY implementation)

**P0-1 — Confirmation enforcement is bypassable.**
PRD §8 specifies a client-controlled `session_confirmed: true` flag — trivially bypassable. **Fix:** server-issued single-use `confirmation_token` (UUID) tied to `(capture_id, items_to_add)` with 5-minute TTL, validated and consumed server-side at cart-add time. Update §8 accordingly.

**P0-2 — Zepto OAuth localhost-redirect compatibility unknown.**
Must be resolved before Gate 3. If Zepto's OAuth does not accept localhost redirect URIs, the entire architecture changes. Owner must confirm with Zepto MCP documentation or testing. If unfavorable, PRD must be re-scoped.

**P0-3 — MCP integration architecture not specified.**
PRD §8 ambiguously offers two architectures. **Fix:** §8 must state explicitly "Direct HTTP client from Flask (MCP JSON-RPC over HTTPS, OAuth tokens stored in CORTEX SQLite, Fernet-encrypted)." Delete the Claude Code subprocess option.

**P0-4 — Classifier `shopping_list` vs. `reminder` disambiguation absent.**
Without an explicit rule, short commerce phrases like "buy milk and eggs" default to `reminder` and never trigger the Zepto path. **Fix:** add disambiguation rule to `classifier.py` prompt ("≥2 commerce-likely items OR ≥1 quantity-token → shopping_list") within this PRD's scope, with a regression test against the existing 38-capture corpus.

---

## P1 Findings (resolve before build, do not block Gate 3)

| # | Finding |
|---|---|
| P1-1 | Add quantity/match heuristic sub-section to §7 (recommendation: request user's stated qty; fall back to closest-pack-up; surface choice in confirmation when ambiguous) |
| P1-2 | Define "match" for M-2: "top result returned by `search_products` AND accepted by user without override" |
| P1-3 | Add 5 missing instrumentation events: `zepto_match_overridden`, `zepto_auth_failed`, `shopping_list_extraction_empty`, per-item search latency, partial cart-add rollup |
| P1-4 | Add 4-week interim M-1 target (~40%) before 8-week target (70%); mark all targets `[ASSUMPTION: no baseline]` |
| P1-5 | UX Designer to spec OAuth failure UX (3 paths: abandoned, token exchange failure, scope denial) |
| P1-6 | Match-review card: add raw user input, product thumbnail, aggregate total price, "Add N items (M skipped)" CTA copy |
| P1-7 | Specify `zepto_fulfilled: true` card state |
| P1-8 | Resolve §14 row 6 (standalone vs. sub-type) as "standalone content_type" in this PRD |
| P1-9 | Add empty-extraction fallback: "I couldn't read this — try typing it?" |
| P1-10 | Specify parallel search pilot: start `max_workers=5`, per-call 5s timeout, aggregate 8s timeout |
| P1-11 | Add second `[ASSUMPTION: no data]` marker on §1's "10–15 minutes" claim |
| P1-12 | Specify dual-model extraction: Haiku for text-input path, Opus for image-input path |

---

## Recommended PRD Status

**CONDITIONAL APPROVAL.**

**Named conditions for advancing to Gate 3 (test plan):**
1. **P0-1 fixed in §8** — server-issued single-use token replaces bypassable `session_confirmed` flag
2. **P0-2 resolved by Owner** — Zepto OAuth redirect URI compatibility confirmed
3. **P0-3 fixed in §8** — MCP integration specified as direct HTTP client from Flask
4. **P0-4 added to scope** — classifier disambiguation rule + regression test against existing corpus

P1 findings must be addressed before Gate 5 (tech proposal review). They do not block Gate 3 from starting once P0s are resolved.

**Rationale:** The PRD frames the problem correctly, is in-scope for Phase 1 as a habit-deepener, and respects the hard guardrail (cart-add, not checkout). The four P0 conditions protect against the two highest-cost failure modes: accidental real-money orders and architecture rework mid-build. With those fixes, this is the clearest CORTEX feature to date for demonstrating the "capture → act" thesis.
