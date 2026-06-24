# Test Plan: Zepto Checkout from Grocery List

**Feature ID:** PRD-CORTEX-004
**PRD link:** `cortex/docs/PRD-CORTEX-004.md`
**Filed:** 2026-06-05
**Owner:** PM + Tech Lead
**Status:** `Draft`

---

## 1. Scope of this test plan

**In scope:**
- `/api/zepto/payment-methods` — get available methods, issue checkout_token
- `/api/zepto/preview` — live order preview via `create_*(confirmOrder: false)`
- `/api/zepto/checkout` — place real order via `create_*(confirmOrder: true)`; check_payment_status for card/UPI
- checkout_token security: single-use, 5-min TTL, cart_hash validation, payload substitution prevention
- `place_order()` and `preview_order()` dispatchers in `zepto_client.py`
- Order Summary modal: payment method selector, live preview display
- Order Confirmed screen (COD/wallet) + Payment Initiated screen (card/UPI)
- M-5 guard: no create_* call outside PRD-gated path
- Error surfacing: all error paths show actual Zepto error text in toast + server log

**Out of scope (not tested here):**
- In-app payment status polling (`check_payment_status` with `poll: true`) — v2 feature
- Order history, order tracking — out of PRD-004 scope
- Multi-address selection at checkout — out of scope
- Wallet balance pre-check — out of scope
- UPI VPA input — out of scope

---

## 2. Acceptance criteria → test case mapping

| AC | Acceptance criterion | TC | Test case | Type |
|---|---|---|---|---|
| AC-01 | `POST /api/zepto/payment-methods` returns available methods and a valid checkout_token | TC-01 | Call endpoint with valid cart_items + address_id; assert response contains `methods` list and `checkout_token` UUID | Integration |
| AC-01 | checkout_token is stored in `pending_checkout_ops` with correct cart_hash + address_id + items_json | TC-02 | After TC-01, query DB; assert row exists with correct values | Integration |
| AC-02 | checkout_token expires after 5 minutes | TC-03 | Manually insert expired token (expires_at in past); call `/api/zepto/checkout` with it; assert 422 + "expired" error | Unit |
| AC-02 | checkout_token is single-use: second call with same token is rejected | TC-04 | Place one order (TC-07); call `/api/zepto/checkout` again with same token; assert 422 + "already used" | Integration |
| AC-03 | cart_hash mismatch rejected: checkout rejected if cart changed since token issued | TC-05 | Issue token for cart [A, B]; submit checkout with cart [A, B, C]; assert 422 + "cart changed" | Unit |
| AC-03 | cart_hash match accepted: identical cart passes validation | TC-06 | Issue token for cart [A, B]; submit checkout with identical items; assert 200 | Integration |
| AC-03 | `create_*` is called with stored `items_json` not client-resent items (payload substitution prevented) | TC-07 | Mock `place_order`; verify it receives items from DB, not from checkout request body | Unit |
| AC-04 | `preview_order()` calls `create_*(confirmOrder=False)` and returns subtotal/delivery_fee/total/eta | TC-08 | Call `/api/zepto/preview` with valid checkout_token + payment_method=COD; assert response has pricing fields | Integration |
| AC-04 | Preview does NOT place an order | TC-09 | Call `/api/zepto/preview` multiple times; assert `checkout_ops` table has no new rows and token is not marked used | Integration |
| AC-04 | Preview refreshes correctly when payment method changes | TC-10 | Call preview with COD, then with CARD (if available); assert both return valid pricing | Integration |
| AC-05 | COD: `place_order()` calls `create_order(confirmOrder=True)` and returns order_id | TC-11 | POST `/api/zepto/checkout` with valid token + method=COD; assert 200, `{type: "confirmed", order_id: <non-empty>}` | Integration |
| AC-05 | Wallet: `place_order()` calls `create_wallet_order(confirmOrder=True)` | TC-12 | POST `/api/zepto/checkout` with method=WALLET; assert correct MCP tool called | Unit (mock) |
| AC-05 | Card: `place_order()` calls `create_online_payment_order` then `check_payment_status` | TC-13 | POST `/api/zepto/checkout` with method=CARD; assert `check_payment_status` called with returned order_id; assert response `{type: "redirect", payment_url: <non-empty>}` | Unit (mock) |
| AC-05 | UPI: `place_order()` calls `create_upi_reserve_pay_order` then `check_payment_status` | TC-14 | POST `/api/zepto/checkout` with method=UPI; assert same pattern as TC-13 | Unit (mock) |
| AC-05 | Unsupported payment method rejected before any MCP call | TC-15 | Call `place_order(payment_method="BITCOIN")`; assert ValueError raised, no MCP call made | Unit |
| AC-06 | Every order call logged to `checkout_ops` with all fields populated | TC-16 | After TC-11; query `checkout_ops`; assert row with correct token, cart_hash, payment_method, items_snapshot, zepto_order_id, status=success | Integration |
| AC-06 | Failed order call still logged with status=error | TC-17 | Mock Zepto to return error; call `/api/zepto/checkout`; assert `checkout_ops` row with status=error | Unit (mock) |
| AC-07 | M-5 guard: no `create_*` callable outside the PRD-gated path | TC-18 | Grep codebase for `create_order\|create_online_payment_order\|create_wallet_order\|create_upi_reserve_pay_order` calls; assert only `preview_order()` and `place_order()` in `zepto_client.py` call them | Static |
| AC-07 | M-5 guard: `place_order` not callable from any route except `/api/zepto/checkout` | TC-19 | Grep app.py for `place_order` calls; assert exactly one call site | Static |
| AC-08 | Error surfacing: Zepto error text appears in toast (truncated 120 chars) and in server log | TC-20 | Mock Zepto to return "Item out of stock — please try again later." error; call `/api/zepto/checkout`; assert 502 response body contains that text; assert `app.logger.error` called | Unit (mock) |
| AC-09 | Client shows Order Summary modal with payment method radio buttons after calling payment-methods | TC-21 | Manual — open CORTEX, populate cart, tap "Review & Checkout"; verify modal appears with payment methods listed | Manual |
| AC-09 | Client shows live pricing after preview call | TC-22 | Manual — in Order Summary modal, verify subtotal/delivery fee/total appear (not blank, not "0") | Manual |
| AC-09 | Client shows Order Confirmed screen on COD success | TC-23 | Manual — place COD order; verify Order Confirmed screen with order_id | Manual |
| AC-09 | Client shows Payment Initiated screen with tappable "Pay Now" link for card/UPI | TC-24 | Manual — place card order; verify "Pay Now →" link appears (not auto-opening tab) | Manual |
| AC-09 | "Review & Checkout" button visible in View Cart modal footer | TC-25 | Manual — open View Cart; verify button label is "Review & Checkout" not "Place Order" | Manual |

---

## 3. Test data conditions

| TC | Required data state | How to seed |
|---|---|---|
| TC-01 to TC-07 | Valid Zepto access token encrypted in DB; active Zepto session (address selected) | Existing from PRD-003 — token already stored |
| TC-02 | `pending_checkout_ops` table exists | Created by migration in Gate 6 |
| TC-03 | Expired checkout_token in DB | `INSERT INTO pending_checkout_ops (token, cart_hash, address_id, items_json, created_at, expires_at) VALUES ('test-expired', 'abc', 'addr1', '[]', datetime('now','-10 minutes'), datetime('now','-5 minutes'))` |
| TC-04 | Successfully placed order from TC-11 | Run TC-11 first; reuse same token |
| TC-05 | checkout_token in DB for cart [pvid-A qty-1, pvid-B qty-2] | Call `/api/zepto/payment-methods` with that cart; extract token |
| TC-08 to TC-10 | Valid checkout_token (not yet used or expired); Zepto session active | Call payment-methods first |
| TC-11 | Valid cart in Zepto (items previously added via PRD-003); checkout_token issued | Real Zepto cart — use existing test cart |
| TC-12 to TC-14 | Mock `zepto_client._mcp_tool` for MCP calls | `unittest.mock.patch` |
| TC-16, TC-17 | `checkout_ops` table exists | Created by migration in Gate 6 |
| TC-21 to TC-25 | Server running on :5050; Zepto access token valid; shopping_list capture with archived cart present | Start server with `python3 app.py`; use existing grocery capture |

---

## 4. Regression checklist

| Existing feature | Why it might break | How we verify it didn't |
|---|---|---|
| Zepto auto-add (`POST /api/zepto/auto-add`) | Shares `_setup_for_cart()` helper; new `preview_order`/`place_order` functions in zepto_client must not alter this path | Run auto-add on a test grocery capture; assert items added to cart correctly |
| Zepto cart-update (`POST /api/zepto/cart-update`) | Shares `update_cart_items()`; new DB tables must not break existing schema | Open View Cart modal; change qty; verify debounced sync still works |
| Zepto swap (`POST /api/zepto/swap`) | Shares `swap_cart_item()`; no shared code with checkout path | Open swap sheet on a cart item; perform swap; verify in-memory update |
| Shopping list card rendering (archived cards with row items) | `_pvidTokenMap` populated from archived cards; checkout modal is a separate surface | Verify archived card row still shows Swap ↻ button and token text |
| Full test suite (207 existing tests) | New DB tables + new functions could introduce import errors or schema conflicts | `python -m pytest tests/ -v` — all 207 must pass before and after |

---

## 5. Manual smoke test script

```
Setup:
1. Ensure server is running: python3 app.py (port 5050)
2. Ensure Zepto access token is stored (from PRD-003 auth flow)
3. Ensure at least one shopping_list capture exists with archived auto-add results
   (i.e., a capture where auto-add was run and cart items are shown in the card)
4. Verify Zepto cart has items (view cart modal shows items before starting)

Steps (COD path):
1. Open http://localhost:5050 → navigate to shopping_list tab
2. Find an archived capture with cart items shown
3. Tap "View Cart" button → cart modal opens, items listed
4. Tap "Review & Checkout" button in footer
   → Expected: Order Summary modal opens. Payment method radio buttons visible.
             Spinner shown briefly, then live pricing appears (subtotal, delivery fee, total).
5. Verify payment method options shown (at least COD if available)
6. Select COD if not already selected
7. Verify live preview shows: subtotal, delivery fee, final total, ETA in minutes
8. Tap "Confirm & Place Order"
   → Expected: Button disabled immediately ("Placing order…" text).
             After 3–8s: Order Confirmed screen shows order_id (non-empty string).
9. Tap "Done"
   → Expected: Modal closes. View Cart button still visible (cart NOT cleared yet for safety — 
             only cleared if we confirm full COD success).
             
Steps (error path):
10. Open Order Summary modal again (new "Review & Checkout" tap)
11. Wait 6 minutes without tapping anything
    → Expected: On "Confirm & Place Order" tap: toast "Session expired — start checkout again"
    (If UX implements countdown timer: timer visible in modal header)

Steps (card/UPI path, if available):
12. Open Order Summary modal
13. Select "Credit/Debit Card" or "Zepto UPI Reserve Pay" if shown
14. Verify preview refreshes (new delivery fee and total loaded)
15. Tap "Confirm & Place Order"
    → Expected: "Payment Initiated" screen appears with "Pay Now →" tappable link.
              "Complete payment in your browser." message visible.
16. Verify "Pay Now →" link is a real anchor tag (not disabled button)

Teardown:
1. If COD order was placed: cancel via Zepto app before delivery is dispatched.
2. Verify checkout_ops table has the row: 
   sqlite3 data/cortex.db "SELECT token, payment_method, status, zepto_order_id FROM checkout_ops ORDER BY id DESC LIMIT 1;"
```

---

## 6. Edge cases to verify

| # | Edge case | Expected behaviour |
|---|---|---|
| EC-01 | User taps "Confirm & Place Order" twice in rapid succession (double-tap) | Second request arrives after token is marked used → 422 "already used" → toast shown. No duplicate order. Button disabled after first tap prevents this in most cases. |
| EC-02 | Cart changes in Zepto between "Review & Checkout" and "Confirm & Place Order" (e.g. item went out of stock) | `create_*(confirmOrder: true)` returns Zepto error → 502 → toast with actual Zepto error text. Token remains unused if Zepto rejects. Retry is possible with same token (token only marked used on server success). |
| EC-03 | `get_payment_methods` returns no available methods (empty list) | Server returns 200 with empty methods list; client shows "No payment methods available — use Zepto app to checkout" message. "Confirm & Place Order" button hidden. |
| EC-04 | `create_wallet_order` rejected because wallet balance is insufficient | Zepto returns error → 502 → toast "Insufficient Zepto Cash balance" (or actual Zepto error text). User can switch to another payment method and retry (new checkout_token needed after error). |
| EC-05 | UPI Reserve Pay selected but user has no reserve balance | Same as EC-04 — Zepto returns error → 502 → toast with actual error. |
| EC-06 | `check_payment_status` call fails after `create_online_payment_order` succeeds | Order was placed (order_id exists) but payment URL not retrieved. Server logs the order_id at ERROR level. Returns 502 to client with "Order placed but payment link unavailable — check Zepto app." |
| EC-07 | checkout_token issued for address A but user's active address changed to B between payment-methods and checkout calls | cart_hash validates correctly (hash is of items, not address). But `userAddressId` in the create_* call uses the stored address_id from pending_checkout_ops — not the (potentially stale) client-sent value. Address lock-in at token issue time. |

---

## 7. Success criteria

- [ ] All unit and integration TCs (TC-01 to TC-20) pass in `tests/test_checkout.py`
- [ ] All 207 existing tests continue to pass after implementation (`python -m pytest tests/ -v`)
- [ ] Manual smoke script (§5) completes without deviation — COD path fully exercised
- [ ] EC-01 through EC-07 behave as specified
- [ ] No `create_*` MCP tool callable outside `preview_order()` / `place_order()` (TC-18, TC-19 pass)
- [ ] checkout_ops table populated with all required fields after every order attempt
- [ ] No new console errors or warnings in browser DevTools during smoke test
- [ ] Counter-metric M-3 confirmed: zero — no `create_*` call outside PRD-gated path exists in codebase

---

## 8. Sign-offs

| Role | Sign-off | Date | Notes |
|---|---|---|---|
| PM | [ ] | | |
| Tech Lead | [ ] | | |
| Data Analyst | [ ] | Instrumentation in §13 of PRD is straightforward — checkout_ops is the source of truth | |

---

## 9. Post-execution retrospective hook

After ship: Gate 8 retrospective at `cortex/docs/learnings/feature-03-zepto-checkout.md`. Key questions to answer:
- Did the two-step `confirmOrder` flow (preview + place) cause any confusion or extra latency?
- Did `check_payment_status` for card/UPI return a usable payment URL in the first call?
- Which edge cases (EC-01 through EC-07) were hit in real usage?
- Was the `get_payment_methods` session dependency a real issue, and did `_setup_for_cart()` solve it?

---

*Not investment advice. Analytical output for training purposes only.*
