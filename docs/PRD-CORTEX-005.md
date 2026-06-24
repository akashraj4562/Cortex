# PRD-CORTEX-005 — Zepto Credit-Card Checkout

**Version:** 1.0 | **Date:** 2026-06-24 | **Status:** Draft → Gate-2 reviewed | **Owner:** Akash Raj
**PM:** product-manager | **Phase:** 1 (Personal Tool)

**Relationship to PRD-CORTEX-004:** PRD-004 ("Zepto Checkout from Grocery List", Gate-2 PASS) is the **umbrella** spec covering all four payment methods. It was never built. PRD-005 is the **card-first implementable slice** of PRD-004: it builds the shared checkout scaffolding once and lights up exactly the **credit/debit-card** path the owner asked for. COD / wallet / UPI become near-zero-cost fast-follows on the same scaffolding (see §6). All Zepto MCP tool semantics in this PRD were verified via `tools/list` on 2026-06-05 and are carried forward from PRD-004 §7/§14 — they are not re-derived here.

**Prior art / patterns carried forward:**
- PRD-004 — checkout_token, cart_hash, M-5 lift, two-step `confirmOrder` flow, AP-18/19/20 catches.
- `learnings/feature-02-zepto-cart.md` — AP-18 (read tool descriptions first), AP-19 (surface real error text), AP-20 (don't build shared setup for the most complex caller).

---

## 1. Problem

After CORTEX populates and confirms a Zepto cart (PRD-003, shipped), the user hits a wall: there is no way to pay. They must leave CORTEX, open the Zepto app, find the cart, and place the order. The grocery workflow — capture list → classify → fill cart → **place order** — breaks at the last, smallest step. The owner's stated need is specific: *"checkout with credit card payment."*

Cost of not solving it: every grocery session ends unresolved ("now go open another app"), which trains the user to treat CORTEX as a cart-filler, not a complete daily-use grocery tool. Daily-use stickiness is the Phase-1 precondition for a deep corpus, so this friction has second-order cost on the whole roadmap.

---

## 2. Vision alignment

**Phase 1 — Personal Tool.** This closes the grocery workflow loop end-to-end inside CORTEX. It does not require any Phase-2 capability. It increases daily-use frequency (the capture-habit flywheel's input), which is the precondition Phase 2 (Thinking Mirror, 500+ corpus) depends on. **Phase-gate: PASS — pure Phase-1 feature.**

---

## 3. User story

```
As Akash, when my Zepto cart is confirmed inside CORTEX,
I want to pay with my credit/debit card and place the order without leaving the app,
so that my grocery list goes from capture to a confirmed, paid order in one place.
```

**JTBD:** When I finish confirming my Zepto cart in CORTEX, I want to pay by card and be done — so I can close CORTEX knowing groceries are on the way.

---

## 4. Success metrics

| # | Metric | Target | Source | Type |
|---|---|---|---|---|
| M-1 | Card-checkout completion (orders placed / checkouts initiated) | ≥70% within 4 weeks of ship | `checkout_ops.status='success'` ÷ `pending_checkout_ops` rows | Primary |
| M-2 | First successful card order | ≥1 within 48h of ship | `checkout_ops` row, `payment_method='CARD'`, status `success` | Activation |
| M-3 | **Unintended orders** (any `create_*` call outside the gated path) | **0 — hard zero** | server-log scan for `create_*` outside `place_order()` | **Counter** |
| M-4 | Card error rate (Zepto MCP error on `create_online_payment_order`) | <10% of attempts | `app.logger.error` scan | Secondary |

**Primary:** ≥70% of initiated card checkouts result in a placed order. **Counter (hard zero):** if M-3 > 0, the feature is disabled server-side pending RCA — no exceptions.

**Anti-metric (must not sacrifice):** the cart/capture flow stays untouched; no `create_*` tool is ever reachable outside the `checkout_token`-gated route.

---

## 5. Scope — In

The build is **shared scaffolding + the card path only.**

**Shared checkout scaffolding (built once, reused by all methods later):**
- [ ] `pending_checkout_ops` + `checkout_ops` SQLite tables (schema = PRD-004 §8, unchanged).
- [ ] `POST /api/zepto/payment-methods` — calls `get_payment_methods`, computes `cart_hash`, issues a single-use `checkout_token` (UUID, 5-min TTL, bound to `cart_hash`+`address_id`), stores canonical `items_json`. Returns available methods + token. Writes a `status='initiated'` row (resolves PRD-004 R-PM-1, the M-1 denominator).
- [ ] `POST /api/zepto/preview` — validates token; calls `create_online_payment_order(confirmOrder=False, userAddressId=…)` → live preview (subtotal, delivery fee, taxes, total, ETA). **No order placed.**
- [ ] `POST /api/zepto/checkout` — validates token (exists + unused + unexpired + `cart_hash` match); calls `create_online_payment_order(confirmOrder=True, …)`; logs to `checkout_ops`; marks token used.
- [ ] `preview_order()` and `place_order()` dispatchers in `zepto_client.py` — the **only** functions that call any `create_*` tool (M-5 guard, §8).
- [ ] **Order Summary modal** — opened by a "Review & Checkout" button in the View Cart modal footer; shows item list (read-only), live preview totals, delivery address, and the payment-method selector (card preselected); buttons: "Confirm & Pay" (primary) + "Go Back".

**Card path (the lit-up method):**
- [ ] On confirm: server calls `create_online_payment_order(confirmOrder=True)` → returns `orderId` → server **immediately** calls `check_payment_status(orderId, poll=False)` → returns Razorpay `payment_url`/status.
- [ ] Client shows a **"Pay Now →" tappable link/button** (NOT `window.open` — avoids popup blocking, per PRD-004 R-TL-4) + copy: *"Tap Pay Now to complete payment in your browser. Your order confirms in the Zepto app."*
- [ ] Cart **not** cleared on the async card path (payment may not complete).
- [ ] Every error surfaces the actual Zepto error text (truncated 120 chars) in a toast + `app.logger.error` (AP-19).

---

## 6. Scope — Out

| Excluded | Why |
|---|---|
| COD / Wallet / UPI methods | Fast-follow. The scaffolding is method-agnostic; adding COD (synchronous `create_order`) and wallet is ~15 LOC each on top of this. Deferred to keep the build unit tight and card-focused, as requested. Tracked under PRD-004. |
| In-app payment-status polling / confirmation for card | Card is async (Razorpay). v1 returns the pay URL; user confirms in the Zepto app. In-app polling needs `check_payment_status(poll=True)` UX — v2. |
| Order cancellation | No MCP cancel tool exposed. |
| Multi-address change at checkout | Address selected during cart-add (PRD-003). v2. |
| Auto-retry on MCP failure | Duplicate-order risk. User sees the error and retries manually. |
| Saved-card / VPA capture | Razorpay redirect handles card entry in-browser; CORTEX never touches PAN/CVV. |

---

## 7. Classification impact

**None.** There is no Corty / LLM call anywhere in the checkout path. AI-Engineer sign-off is fast-tracked (confirmed in PRD-004 R-AI-1). No change to `classifier.py`, `_SYSTEM`, `_IMAGE_SYSTEM`, keywords, or thresholds.

---

## 8. Data model changes

Two **new** tables (additive, no migration of existing rows — P-16 safe). Schemas are exactly PRD-004 §8:

- `pending_checkout_ops` (token PK, cart_hash, payment_method, address_id, created_at, expires_at, used_at, order_id, **status** — `initiated`|`previewed`|`used`).
- `checkout_ops` (append-only audit: token, cart_hash, payment_method, address_id, items_snapshot JSON, total_amount, zepto_order_id, called_at, status `success`|`error`).

`captures` table untouched.

### M-5 guard (how the order-placing constraint is safely lifted, card-scoped)

- All `create_*` calls live in exactly two `zepto_client.py` functions:
  - `preview_order(session_id, payment_method, address_id)` → `create_*(confirmOrder=False)` — safe, never places an order.
  - `place_order(session_id, payment_method, address_id)` → `create_*(confirmOrder=True)`; for CARD, immediately `check_payment_status(order_id, poll=False)`.
- Dispatch: `"CARD"` → `create_online_payment_order`. Any other value in v1 → `ValueError("unsupported payment method")` (COD/wallet/UPI keys reserved, not wired).
- `preview_order` called **only** from `/api/zepto/preview`; `place_order` called **only** from `/api/zepto/checkout`, which is gated by `checkout_token` validation. No other code path reaches a `create_*` tool.
- Every `place_order` invocation logged at INFO (method, item count, total, address_id).

---

## 9. Security & guardrails

- `checkout_token`: server-issued UUID, single-use, 5-min TTL, in JS memory only (never localStorage).
- `cart_hash`: SHA-256 of sorted `pvid:qty`. Canonical `items_json` stored server-side at issue time; `create_*` called with **stored** items, not the client's checkout-time payload (prevents payload substitution — PRD-004 R-TL-1).
- Double-tap: "Confirm & Pay" disabled after first tap; token invalidated server-side on first use.
- Zepto OAuth token stays Fernet-encrypted at rest; all MCP calls server-side; `.env` never committed.
- Popup blocking: pay URL rendered as a user-tapped link, not `window.open`.

---

## 10. Open questions

| # | Question | Owner | Status |
|---|---|---|---|
| Q1 | Exact `get_payment_methods` response shape + the card method key string ("CARD"? "credit_card"?) | Tech Lead | **Open — needs a live cart + valid token.** Token is currently expired (health check 2026-06-24). Resolve at Gate-4 after re-auth; until then code reads the method list defensively (match on substring "card"). |
| Q2 | Does `create_online_payment_order` need any param beyond `confirmOrder`/`userAddressId`? | Tech Lead | Resolved in PRD-004 §14: same params as `create_order`; returns `orderId`; `check_payment_status` mandatory after. |
| Q3 | checkout_token TTL of 5 min enough for card entry? | PM | Resolved (PRD-004): 5 min. The pay step happens **after** placement in-browser, so the token only needs to cover preview→confirm. |

---

## 11. Dependencies

| Dependency | Status | Blocking? |
|---|---|---|
| PRD-003 Zepto Cart (cart must be confirmable) | Shipped | No |
| Zepto MCP server reachable | **Healthy** (0.2s, 2026-06-24) | No |
| Zepto OAuth token valid | **EXPIRED (401)** as of 2026-06-24 | **Yes — for live test only.** Re-auth via `/api/zepto/init`. Build + mocked tests proceed without it. |
| `create_online_payment_order` + `check_payment_status` semantics | Confirmed (tools/list 2026-06-05) | No |

---

## 12. Proof-of-value gate

```
Behavior change: After ship, Akash pays for Zepto groceries by card from inside CORTEX
instead of switching to the Zepto app.
Observable signal: checkout_ops has ≥1 payment_method='CARD' status='success' row within 48h.
Sustained: ≥70% of initiated card checkouts → placed order within 4 weeks.
Assumption: the only reason checkout doesn't happen in CORTEX today is the missing capability
(the cart-confirm modal already gives a full order review). Reasonable — owner explicitly requested it.
```

---

## 13. Gate-2 team review

**PM:** Scope is the correct card-first slice of PRD-004; phase-gate PASS; M-1 denominator fixed via `status='initiated'` row. Approve pending Q1 at Gate-4.
**Tech Lead:** Architecture = PRD-004, de-risked (tools/list done). Only new risk is Q1 (method key string) — mitigated by defensive substring match until live token. Feasibility GREEN, ~120–160 LOC across `app.py`, `zepto_client.py`, `db.py`, `templates/index.html`. See `TECH-CORTEX-005`.
**AI Engineer:** No LLM in path — fast-track sign-off.
**UX Designer:** "Review & Checkout" label (not "Place Order"); card preselected; pay URL as a tappable "Pay Now" button; show a subtle 5-min token countdown in the modal header (PRD-004 R-UX-3) — accepted for v1.
**Data Analyst:** M-1–M-4 all computable from the two new tables + logs. Instrumentation sufficient.

**Gate-2 verdict: PASS.** Approved for Gate-3 (test plan) and Gate-4 (build). One open item (Q1) tracked, non-blocking for build start against mocks.

---

## 14. Team sign-offs

| Team | Sign-off | Notes |
|---|---|---|
| PM | ✅ | Card-first slice approved |
| AI Engineer | ✅ (fast-track) | No classification impact |
| Tech Lead | ⏳ Gate-4 | Pending Q1 live confirmation |
| UX Designer | ✅ | Order Summary modal spec accepted |
| Data Analyst | ✅ | Instrumentation in §4/§8 |

---
*Personal-tool PRD. Analytical output for the CORTEX Product Staff process.*
