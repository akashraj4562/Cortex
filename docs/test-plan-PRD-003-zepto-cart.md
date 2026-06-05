# Test Plan: Zepto Cart from Grocery List

**Feature ID:** PRD-CORTEX-003
**PRD link:** `docs/PRD-CORTEX-003.md`
**Filed:** 2026-06-04
**Owner:** PM + Tech Lead
**Status:** `Draft`

---

## 1. Scope of this test plan

**In scope:**
- `shopping_list` classifier routing — new content_type detection, disambiguation from `reminder`
- Classifier regression — all 44 existing captures still classified correctly after adding the new rule
- Item extraction — text and image paths, multilingual, all list formats
- Confirmation token — server-side generation, storage, single-use enforcement, expiry, bypass rejection
- Zepto MCP integration — product search (mocked), cart add (mocked), OAuth callback handler
- OAuth credential storage — Fernet encryption at rest, no token in client responses or logs
- Partial success handling — found items added, not-found items surfaced to user
- Event logging — `shopping_list_captured`, `zepto_cart_confirmed`, all §13 events instrumented
- Capture result — `zepto_fulfilled: true` written to capture metadata on success
- Performance — extraction ≤3s, parallel search ≤8s, cart add ≤5s
- M-5 hard zero — `order_placement` MCP tool never called

**Out of scope (not tested here):**
- Live Zepto MCP calls with real auth — tested in a separate manual auth smoke test (P0-2 port validation)
- Confirmation screen visual design — UX sign-off separate
- Token refresh flow — to be covered in Tech Lead's integration spike at Gate 5
- Multi-user scenarios — Phase 1 single-user only

---

## 2. Acceptance criteria → test case mapping

| AC | Acceptance criterion (from PRD §5) | TC | Test case | Type |
|---|---|---|---|---|
| AC-01 | `shopping_list` content_type added to classifier | TC-01 | Submit "milk 2L, eggs 12, atta 5kg" — assert `content_type == shopping_list` | Unit |
| AC-01 | `shopping_list` classifier fires on quantity-token alone | TC-02 | Submit "get 2kg sugar" — assert `shopping_list` (1 quantity-token sufficient) | Unit |
| AC-01 | `shopping_list` does NOT override `reminder` intent | TC-03 | Submit "pick up dry cleaning tomorrow at 6pm" — assert `reminder`, not `shopping_list` | Unit |
| AC-01 | Single ambiguous item does not trigger `shopping_list` | TC-04 | Submit "milk" (1 word, no qty) — assert NOT `shopping_list` (falls to `general_note` or `reminder`) | Unit |
| AC-01 | Regression: 44-capture corpus unchanged | TC-05 | Run classifier against all 44 existing captures in `cortex.db`; assert zero content_type changes | Integration |
| AC-02 | Text input — bullet list | TC-06 | Submit "- atta\n- milk\n- eggs" — assert 3 items extracted with correct names | Unit |
| AC-02 | Text input — numbered list | TC-07 | Submit "1. sugar 1kg\n2. oil 1L\n3. butter" — assert 3 items, qty parsed on items 1+2 | Unit |
| AC-02 | Text input — comma-separated | TC-08 | Submit "onions, potatoes, tomatoes 1kg" — assert 3 items | Unit |
| AC-02 | Text input — WhatsApp paste (mixed language) | TC-09 | Submit "doodh 2L, anda 12, aloo 500g" — assert Hindi items normalised (milk, eggs, potatoes), qty extracted | Unit |
| AC-02 | Non-item lines excluded from extraction | TC-10 | Submit "milk, eggs\npickup at 6pm" — assert 2 items extracted, "pickup at 6pm" in `non_items_skipped` | Unit |
| AC-03 | Image input path produces same extraction output | TC-11 | POST a base64-encoded JPEG of a handwritten 5-item list to `/api/capture/image` — assert `content_type == shopping_list` and ≥3 items extracted | Manual |
| AC-04 | Item extraction schema — all fields populated | TC-12 | Submit "Amul milk 2 litre" — assert `{name_raw, name_normalized, qty_value, qty_unit, qty_confidence, notes}` all present in extracted item | Unit |
| AC-04 | Extraction confidence field present | TC-13 | Any extraction call — assert `extraction_confidence` (0–1) and `language_detected` in response | Unit |
| AC-05 | `search_products` called once per extracted item | TC-14 | Submit 5-item list, mock Zepto MCP — assert exactly 5 `search_products` calls fired | Integration |
| AC-05 | Parallel search calls complete within 8s for 15-item list | TC-15 | Submit 15-item list with mocked MCP (each call delayed 400ms) — assert total wall time ≤8s | Integration |
| AC-05 | Per-call timeout respected | TC-16 | Mock Zepto MCP to hang on one item — assert that call times out at 5s, others complete, item marked not-found | Integration |
| AC-06 | Confirmation screen data returned correctly | TC-17 | POST 3-item list, mock search returns 3 results — assert confirmation response contains matched item array with `{name_raw, zepto_product_name, weight, price}` per item | Integration |
| AC-06 | `confirmation_token` present in confirmation response | TC-18 | Same as TC-17 — assert `confirmation_token` UUID present in response, stored in `pending_cart_ops` | Unit |
| AC-06 | `confirmation_token` has 5-minute TTL | TC-19 | Read `pending_cart_ops` row after TC-18 — assert `expires_at` is within ±5s of `now + 300s` | Unit |
| AC-07 | Cart add succeeds with valid token | TC-20 | POST `/api/zepto/cart-add` with valid `confirmation_token` + items — assert `cart_management` called once per item, `zepto_fulfilled: true` on capture | Integration |
| AC-07 | Cart add rejected with missing token | TC-21 | POST `/api/zepto/cart-add` with no `confirmation_token` — assert HTTP 403 | Security |
| AC-07 | Cart add rejected with invalid token | TC-22 | POST `/api/zepto/cart-add` with fabricated UUID — assert HTTP 403 | Security |
| AC-07 | Cart add rejected with expired token | TC-23 | Manually expire a `pending_cart_ops` row by setting `expires_at = now - 1s`, then POST cart-add — assert HTTP 403 | Security |
| AC-07 | Token is single-use — replay rejected | TC-24 | POST cart-add with valid token (succeeds) → POST same cart-add again with same token — assert second call returns 403 | Security |
| AC-08 | OAuth callback route receives auth code | TC-25 | GET `/api/zepto/callback?code=test_code&state=test_state` with mock token exchange — assert tokens written to `external_credentials`, Fernet-encrypted | Integration |
| AC-08 | OAuth token never appears in any HTTP response | TC-26 | After TC-25, GET any CORTEX API endpoint — assert no `access_token` or `refresh_token` in response body | Security |
| AC-08 | OAuth token stored encrypted in DB | TC-27 | After TC-25, query `external_credentials` table directly — assert `access_token` column is bytes (not plaintext string) | Security |
| AC-09 | Classifier disambiguation rule in `classifier.py` prompt | TC-28 | Read `classifier.py` `_SYSTEM` prompt — assert disambiguation rule text present (`≥2 commerce-likely items OR ≥1 quantity-token → shopping_list`) | Code inspection |
| AC-09 | Disambiguation: reminder with one food item stays `reminder` | TC-29 | Submit "remind me to buy milk tomorrow" — assert `reminder`, not `shopping_list` | Unit |
| AC-10 | Partial success: found items added, not-found shown | TC-30 | 4-item list, mock MCP returns results for 3, not-found for 1 — assert 3 items added to cart, UI response includes 1 not-found item name | Integration |
| AC-10 | Full not-found: zero items matched | TC-31 | All items return no results from mock MCP — assert no `cart_management` call, user shown "no items found" message | Integration |
| AC-11 | Result capture logged with `zepto_fulfilled: true` | TC-32 | After successful cart-add — query `captures` table for the capture, assert `metadata.zepto_fulfilled == true` | Integration |
| AC-11 | `zepto_cart_confirmed` event logged | TC-33 | After successful cart-add — query `events` table, assert `zepto_cart_confirmed` event present with `capture_id` and `items_count` | Integration |
| M-5 | `order_placement` tool never called anywhere | TC-34 | `grep -rn "order_placement"` in `cortex/` codebase — assert zero results in Python source files | Code inspection |
| PERF | Item extraction ≤3s for 20-item list | TC-35 | Submit 20-item list, measure extraction step wall time — assert ≤3000ms | Integration |
| PERF | Cart add ≤5s for 20 items | TC-36 | 20 confirmed items, mock MCP with 200ms delay each — assert total cart-add ≤5000ms | Integration |

---

## 3. Test data conditions

| TC | Required data state | How to seed |
|---|---|---|
| TC-05 (44-capture regression) | All 44 real captures in `cortex.db` | No seeding needed — run against live DB. **Run before any migrations** on a copy: `cp data/cortex.db data/cortex_pre_003_backup.db` |
| TC-14, TC-15, TC-16, TC-17, TC-20, TC-30, TC-31 | Mock Zepto MCP server | pytest fixture: `MockZeptoMCP` — HTTP server on a test port returning canned JSON-RPC responses. Configurable: normal, delayed, hanging, not-found. |
| TC-18, TC-19 | Empty `pending_cart_ops` table | Schema migration must run first; table starts empty per test |
| TC-23 | Expired `pending_cart_ops` row | Fixture: insert row with `expires_at = datetime.utcnow() - timedelta(seconds=1)` |
| TC-25, TC-26, TC-27 | Empty `external_credentials` table | Schema migration must run first; `FERNET_KEY` set in test env |
| TC-32, TC-33 | Completed cart-add flow, `events` table must exist | Full integration flow with mock MCP; events migration must run first |
| TC-35, TC-36 | 20-item seed list | Fixture: hardcoded 20-item grocery string |
| TC-11 (manual) | A real JPEG of a handwritten grocery list | Owner-supplied photo; no automation |

**Critical precondition for all tests:** Run `cp data/cortex.db data/cortex_pre_003_backup.db` before any schema migration so the 44-capture regression test (TC-05) can be run against the pre-migration state.

---

## 4. Regression checklist

| Existing feature | Why it might break | How we verify it didn't |
|---|---|---|
| **Classifier — all 8 seed types** | Disambiguation rule for `shopping_list` could push borderline `reminder` or `general_note` captures to wrong type | TC-05: run classifier against all 44 existing captures, assert zero type changes |
| **`reminder` classification** | The ≥2-commerce-items rule could grab "remind me to buy milk and eggs tomorrow" as `shopping_list` | TC-03, TC-29: two distinct reminder inputs asserted to NOT classify as shopping_list |
| **Image capture pipeline (PRD-002)** | New shopping_list image path reuses same `classify_image()` — shared code path could regress non-grocery image handling | TC-37: POST a non-grocery image (screenshot of article) → assert not classified as `shopping_list` |
| **Dynamic taxonomy** | Adding `shopping_list` as a new type via `content_types` table must not break the existing `get_all_types()` cache or the Unknown staging flow | TC-38: after migration, GET `/api/types` → assert all 8 seed types + `shopping_list` present; assert Unknown tab still renders |
| **Feed tab routing** | `shopping_list` captures must appear in the correct tab and not bleed into other tabs | TC-39: POST a shopping_list capture → verify it appears in shopping_list tab only, not in `general_note` or `reminder` tab |
| **144 existing tests** | Any shared module touched (classifier.py, db.py, app.py) could break existing test suite | Run `python -m pytest tests/ -v` — assert all 144 tests pass before and after implementation |

---

## 5. Manual smoke test script

```
Setup:
1. CORTEX server running on port 5050: `python3 app.py`
2. `external_credentials` table has a valid (test) Zepto token inserted
3. Mock Zepto MCP running on test port (or: real Zepto account authenticated)
4. Open browser to http://localhost:5050

--- FLOW A: Text input, happy path ---

Steps:
1. In the capture box, type: "atta 5kg, Amul milk 2L, eggs 12, kokum"
   → Expected: capture submitted, CORTEX shows "Found a grocery list — add to Zepto cart?" prompt
2. Tap [Add to Zepto]
   → Expected: loading state while search runs (≤8s)
3. Confirmation screen renders
   → Expected: 3 matched items shown (atta, milk, eggs) each with product name/weight/price
   → Expected: "kokum" shown as not found with [Skip] state
   → Expected: [Add 3 items to cart] button visible
4. Tap [Add 3 items to cart]
   → Expected: success state — "3 items added to your Zepto cart. Open Zepto to checkout."
   → Expected: capture card appears in shopping_list tab with zepto_fulfilled badge

--- FLOW B: Save-only path ---

5. In the capture box, type: "onions, potatoes, tomatoes"
   → Expected: "Found a grocery list" prompt appears
6. Tap [Save only]
   → Expected: capture saved in shopping_list tab with no Zepto action taken
   → Expected: capture card shows [Add to Zepto] action for later use

--- FLOW C: Confirmation bypass attempt ---

7. Using curl or browser devtools: POST /api/zepto/cart-add directly with no confirmation_token
   → Expected: HTTP 403, no cart_management call fired

--- FLOW D: Classifier disambiguation ---

8. In capture box, type: "remind me to pick up milk tomorrow"
   → Expected: classified as `reminder`, NOT `shopping_list`. Zepto CTA does NOT appear.

--- FLOW E: Image input ---

9. Tap camera icon → Upload from Gallery → select a photo of a handwritten grocery list
   → Expected: image processed, items extracted, same confirmation flow as Flow A

Teardown:
1. If using real Zepto account: verify Zepto cart contains only the items explicitly confirmed
2. If using mock: no teardown needed
```

---

## 6. Edge cases to verify

| # | Edge case | Expected behaviour |
|---|---|---|
| EC-01 | User submits a list, reaches confirmation screen, waits 6 minutes (token expires), then taps [Add to cart] | Cart-add rejected with a user-visible message: "Session expired — please re-confirm your list." Confirmation screen re-rendered with a new token. No items added from the expired session. |
| EC-02 | Zepto MCP returns a search result but the product is out of stock | Out-of-stock product shown in confirmation screen with ⚠️ label. User can skip it. Out-of-stock item excluded from cart-add call. Does not count as a "not found" — it is found but unavailable. |
| EC-03 | User submits a 0-item list (e.g., just "tomorrow at 6pm, doctor appointment") | Extraction returns empty `items` array. CORTEX does not show Zepto CTA. Capture classified as `reminder`. No Zepto flow triggered. |
| EC-04 | Zepto MCP `search_products` call returns malformed JSON-RPC response for one item | That item marked not-found. Other items proceed normally. Error logged to server log. No crash, no silent failure — user sees the item as "not found." |
| EC-05 | User taps [Add to Zepto] but is not authenticated (no token in `external_credentials`) | OAuth flow triggered immediately (browser redirect to Zepto OTP page). After successful auth, user returned to confirmation screen for the same capture — not forced to re-submit the list. |
| EC-06 | Same list submitted twice within 5 minutes (double-tap) | Two separate captures created (each with its own `confirmation_token`). Confirming one does not affect the other. Both show in the shopping_list tab. No duplicate cart-add if only one is confirmed. |
| EC-07 | Zepto MCP is unreachable (connection refused) at cart-add time | Graceful error shown: "Zepto is unavailable — your list is saved. Try again later." Capture saved with `zepto_fulfilled: false`. No crash. Existing CORTEX features unaffected. |

---

## 7. Success criteria

PASS means all of the following are true at Gate 7:

- [ ] All 36 TCs in §2 pass (security TCs TC-21 through TC-24 and TC-26/TC-27 are non-negotiable)
- [ ] All 6 regression checks in §4 pass — including full 144-test suite green
- [ ] TC-05: zero content_type changes across the 44-capture corpus
- [ ] Manual smoke script §5 completes all 5 flows without deviation
- [ ] All 7 edge cases in §6 behave as specified
- [ ] No new console errors or unhandled exceptions introduced
- [ ] All §13 events (`shopping_list_captured`, `zepto_cart_confirmed`, etc.) present in `events` table after smoke test
- [ ] `grep -rn "order_placement" cortex/*.py` returns zero results (TC-34 — M-5 hard zero)
- [ ] `external_credentials.access_token` column is bytes in DB, never plaintext (TC-27)

FAIL means: any checkbox above is unchecked at Gate 7. Partial passes are FAILs.

**Hard stop — M-5:** If any test run produces a real Zepto order without explicit user confirmation, the feature is suspended immediately pending root cause analysis. This overrides all other criteria.

---

## 8. Sign-offs

| Role | Sign-off | Date | Notes |
|---|---|---|---|
| PM | [ ] | | |
| Tech Lead | [ ] | | Confirm MockZeptoMCP fixture design is sufficient for integration tests |
| AI Engineer | [ ] | | Confirm extraction prompt produces correct schema for all TC-06–TC-13 inputs |

---

## 9. Post-execution retrospective hook

After Gate 7 passes and the feature ships, PM writes the retrospective at `cortex/docs/learnings/feature-003-zepto-cart.md`. Direct inputs from this plan:

- Which TCs caught real bugs during implementation?
- Did any security TCs (TC-21 through TC-24) surface implementation issues?
- Did TC-05 (44-capture regression) catch any classifier drift?
- Did any edge case (EC-01 through EC-07) behave differently than specified?
- Was the MockZeptoMCP fixture adequate, or did it miss real MCP behaviour?

Gate 8 is non-negotiable. File the retrospective before closing the feature.
