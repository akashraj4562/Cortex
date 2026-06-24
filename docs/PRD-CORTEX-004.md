# PRD-CORTEX-004: Zepto Checkout from Grocery List

**Status:** `Draft`
**Filed:** 2026-06-05
**Product:** CORTEX
**PM:** product-manager
**Last updated:** 2026-06-05 (v1.1 — scope expanded to all payment methods)

**Prior art:**
- PRD-CORTEX-003 (Zepto Cart from Grocery List) — security architecture for Fernet token encryption, confirmation_token pattern, MCP session lifecycle
- `cortex/docs/learnings/feature-02-zepto-cart.md` — Gate 8 retrospective: UPSERT semantics lesson (AP-18), error surfacing failures (AP-19), shared-setup cost (AP-20)
- P-18: Read full API tool descriptions before building — call tools/list first (confirmed in PRD-003 session)

**Anti-patterns checked:**
- AP-18 (assumed API semantics without reading spec): catch mechanism — `create_order` tool description must be read via `tools/list` before any implementation. PRD §8 includes the required pre-build verification step.
- AP-19 (generic error toast with no diagnostic): catch mechanism — every error path in the checkout flow must surface actual Zepto error text (truncated 120 chars) in the UI toast and in `app.logger.error`.
- AP-20 (shared setup function built for most complex caller): catch mechanism — checkout MCP session MUST NOT call `get_past_order_items`. New `_setup_for_checkout()` helper, or reuse `_setup_for_cart(need_past_orders=False)`.
- AP-02 (code before PRD): catch mechanism — this PRD exists. No checkout code until this PRD is approved.

---

## ✅ REQUIRED (gate blocks without these 4)

All four sections are non-empty. PRD is Gate 1 complete.

---

## 1. Problem statement

After a user populates their Zepto cart via CORTEX (PRD-003), they must exit CORTEX, open the Zepto app, and manually complete checkout. This breaks the grocery workflow — the user has already confirmed their cart inside CORTEX and expects to be done. The handoff to a separate app creates friction that is disproportionate to the last step: tapping "Place Order."

`[ASSUMPTION: no data — treat as hypothesis]` — the cart-to-checkout conversion rate inside Zepto is lower because the context switch causes abandonment or order modification that the user did not intend.

The cost of not solving it: every grocery session ends with an unresolved action. The feature that should feel complete (cart confirmed → order placed) instead ends with "go open another app." This trains the user to see CORTEX as a cart-filling tool, not a complete grocery workflow.

---

## 2. True need (interpreted)

**Stated request:** "start the payment and checkout PRD"

**Interpreted need:** The user wants to complete the full grocery workflow — from writing a list to placing an order — without leaving CORTEX. The payment step is the last-mile gap. The user is not asking for a payment gateway or wallet; they want the simplest path to an order being placed.

**Assumption flagged:** COD (Cash on Delivery) is the right v1 payment method. It has zero payment gateway risk, is reversible at delivery, and is the most commonly used default in quick-commerce in India. If Zepto's `get_payment_methods` response confirms COD is available for the user's address, this assumption holds.

---

## 3. User story

```
As a CORTEX user who has confirmed my Zepto cart,
I want to place the order from within CORTEX,
So that my grocery list goes from capture to confirmed order in one place.
```

**Jobs-to-be-done:**
When I finish confirming my Zepto cart in CORTEX, I want to place the order without switching apps, so I can close CORTEX knowing my groceries are on the way.

---

## 4. Success metrics

| # | Metric | Target | Source | Cadence | Type |
|---|---|---|---|---|---|
| M-1 | Checkout completion rate (order placed / cart confirmed) | ≥70% within 4 weeks of ship | `checkout_ops` table: `used_at IS NOT NULL` / `pending_checkout_ops` created | Weekly | Primary |
| M-2 | Checkout errors (Zepto MCP error on `create_order`) | <10% of checkout attempts | `app.logger.error` scan: `create_order` failures | Weekly | Secondary |
| M-3 | Unintended orders (M-5 violation) | 0 — absolute zero | Server log scan for `create_order` calls outside the PRD-gated path | Every session | **Counter — hard zero** |
| M-4 | COD selection rate (of users who see payment method screen) | Track only — no target | UI event in session | Weekly | Observational |

**Primary success metric:** ≥70% of confirmed carts result in a placed order within the same CORTEX session.

**Counter-metric threshold:** If M-3 ever registers > 0, the feature is immediately disabled (server-side guard re-enabled) pending RCA. This is a hard zero — no exceptions.

**Behavior change:** After this ships, the user will tap "Place Order" inside CORTEX instead of switching to the Zepto app to complete checkout.

**Observable signal:** `checkout_ops.used_at` becomes non-null within the session that populates it, within 4 weeks of ship.

---

## 5. Scope — what's in v1

- [ ] **Payment method detection:** `GET /api/zepto/payment-methods` — calls Zepto MCP `get_payment_methods`, returns available methods for the user's selected address. Displayed in Order Summary modal before checkout.
- [ ] **All available payment methods:** `POST /api/zepto/payment-methods` returns every method Zepto's `get_payment_methods` offers for the user's address (COD, credit/debit card, wallet, UPI). User selects in Order Summary modal.
- [ ] **checkout_token security layer:** Server-issued UUID (single-use, 5-min TTL), tied to `cart_hash` + `address_id`. Stored in new `pending_checkout_ops` SQLite table. Invalidated on use or expiry. Not tied to payment method (selected at confirm time).
- [ ] **cart_hash validation:** SHA-256 of sorted `pvid:qty` pairs from the confirmed cart. Checkout rejected if cart has changed since token was issued.
- [ ] **Payment routing:** Server routes `POST /api/zepto/checkout` to the correct MCP tool based on `payment_method`:
  - COD → `create_order` → returns `order_id` directly
  - Card (online) → `create_online_payment_order` → returns `payment_url`
  - Wallet → `create_wallet_order` → returns `order_id` directly
  - UPI → `create_upi_reserve_pay_order` → returns `payment_url` or UPI deeplink
- [ ] **Order Summary modal (double confirmation UX):**
  - Triggered by "Place Order" button in the View Cart modal footer.
  - Shows: item list with quantities and prices, total, delivery address, payment method selector (radio buttons from available methods).
  - Two buttons: "Confirm & Place Order" (primary) and "Go Back."
  - "Confirm & Place Order" sends `checkout_token` + selected `payment_method` + `cart_items` to server.
- [ ] **Synchronous payment confirmation (COD, wallet):** Order Confirmed screen with Zepto order_id and estimated delivery (if returned).
- [ ] **Async payment handoff (card, UPI):** Server returns `payment_url`. CORTEX opens URL in new browser tab and shows "Complete payment in your browser — check Zepto app for order confirmation." No in-app polling in v1.
- [ ] **Server-side order logging:** Every `create_*` call (all four tools) logged to `checkout_ops` table with timestamp, cart_hash, items snapshot (JSON), total amount, address_id, payment_method, Zepto order_id or payment_url returned.
- [ ] **Error surfacing (AP-19 compliant):** Every Zepto error from any `create_*` tool shown in toast with actual error text (truncated 120 chars) + logged server-side.

---

## 6. Explicitly out of scope (v1)

| Feature | Reason deferred |
|---|---|
| Payment status polling / in-app confirmation for card/UPI | Card and UPI payments are async — order is placed but payment is confirmed by the gateway. V1 opens payment URL in browser; user checks Zepto app for status. In-app `check_payment_status` polling is a v2 candidate requiring webhook or polling infrastructure. |
| Order cancellation | No MCP cancel tool exposed. COD reversible at delivery. Out of scope. |
| Multi-address selection at checkout | Address was already selected during cart add. Changing address at checkout is a v2 flow. |
| Retry on Zepto MCP failure | First call only. On failure, user sees the error and can retry manually. Auto-retry introduces duplicate order risk. |
| Order history inside CORTEX | `list_order_history` MCP tool exists. Out of scope — doesn't serve the Phase 1 capture workflow. |
| Wallet balance pre-check | `get_payment_methods` may return wallet balance. Showing it is deferred — display if available, no gate on wallet balance before showing the wallet option. |
| UPI ID / VPA input | If `create_upi_reserve_pay_order` requires a UPI VPA, this field will be added in v2. V1 assumes collect flow (QR or deeplink). |

---

## 7. Solution design

**Confirmed from tools/list (2026-06-05):** All four `create_*` tools use a two-step pattern. `confirmOrder: false` (default) = preview only (returns live Zepto subtotal, delivery fee, ETA — no order placed). `confirmOrder: true` = places the real order. `check_payment_status` is MANDATORY after `create_online_payment_order` and `create_upi_reserve_pay_order`. UPI Reserve Pay requires a pre-funded Razorpay balance (not a live UPI collect flow).

**User flow:**

View Cart modal (cart confirmed) → "Review & Checkout" button (footer) → POST /api/zepto/payment-methods (get methods + issue checkout_token) → Order Summary modal (payment method selector) → user selects method → "Preview Order" (auto or button) → server calls create_*(confirmOrder: false) → live preview (delivery fee, taxes, final total, ETA) shown → user taps "Confirm & Place Order" → POST /api/zepto/checkout → server calls create_*(confirmOrder: true) →

- COD/Wallet: Order Confirmed screen (order_id + ETA)
- Card/UPI: server calls check_payment_status(poll: false) → returns payment_url → client shows as tappable link

**Key interactions:**

1. User taps "Review & Checkout" in View Cart modal footer.
   - Client POSTs to `/api/zepto/payment-methods` with `{cart_items, address_id}`.
   - Server: calls Zepto `get_payment_methods` (no required params — uses session state for address), computes `cart_hash`, issues `checkout_token` (UUID, 5-min TTL, tied to cart_hash + address_id). Stored in `pending_checkout_ops` with `items_json`.
   - Server returns `{methods: [...], checkout_token}`.
   - Client shows Order Summary modal with payment method radio buttons. COD selected by default if available.

2. User selects payment method. Order Summary auto-calls preview.
   - Client POSTs to `/api/zepto/preview` with `{checkout_token, payment_method}`.
   - Server calls `create_*(confirmOrder: false)` for selected method → Zepto returns live preview (subtotal, delivery_fee, total, eta_minutes).
   - Client shows live pricing in Order Summary: "Subtotal ₹X · Delivery ₹Y · Total ₹Z · ~N min delivery."
   - Preview refreshes if user switches payment method.

3. User taps "Confirm & Place Order."
   - Client POSTs to `/api/zepto/checkout` with `{checkout_token, payment_method}`.
   - Server validates: token exists + not used + not expired + cart_hash matches stored hash.
   - If validation fails → 422 with specific error (expired / already used / cart changed).
   - If validation passes → server calls `create_*(confirmOrder: true, userAddressId=address_id)` → logs to `checkout_ops` → marks token used.
   - COD/wallet: Zepto returns order_id + ETA → server returns `{type: "confirmed", order_id, eta}`.
   - Card/UPI: Zepto returns order_id → server immediately calls `check_payment_status(order_id, poll: false)` → Zepto returns payment URL or status → server returns `{type: "redirect", payment_url, order_id}`.
   - Zepto error → 502 with Zepto error text (truncated 120 chars) → toast.

4a. COD / wallet confirmed:
   - Client shows Order Confirmed screen: order_id, ETA, "Done" button.
   - `_cartItems` cleared in memory.

4b. Card / UPI redirect:
   - Client shows payment_url as a styled "Pay Now →" button (not window.open — avoids popup blocking).
   - Screen text: "Tap 'Pay Now' to complete your payment. Your order will be confirmed in the Zepto app."
   - "Done" button closes modal. Cart NOT cleared.

5. "Go Back" from Order Summary → returns to View Cart modal. checkout_token abandoned (expires in 5 min).

**Design spec:** No wireframe tool available. Layouts described in §8 Technical Requirements.

---

## 8. Technical requirements

### New SQLite table: `pending_checkout_ops`

```sql
CREATE TABLE IF NOT EXISTS pending_checkout_ops (
    token TEXT PRIMARY KEY,
    cart_hash TEXT NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'COD',
    address_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    used_at TEXT,
    order_id TEXT
);
```

**Migration:** PRAGMA-safe column addition (P-16 compliant). Table is new — no existing rows to migrate.

### New SQLite table: `checkout_ops` (audit log — append-only)

```sql
CREATE TABLE IF NOT EXISTS checkout_ops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    cart_hash TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    address_id TEXT,
    items_snapshot TEXT NOT NULL,  -- JSON
    total_amount REAL,
    zepto_order_id TEXT,
    called_at TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL  -- 'success' | 'error'
);
```

### New Flask routes

| Route | Method | Purpose |
|---|---|---|
| `/api/zepto/payment-methods` | POST | Call `get_payment_methods` MCP; compute cart_hash; issue `checkout_token`; return available methods + token |
| `/api/zepto/preview` | POST | Validate checkout_token; call `create_*(confirmOrder: false)` for selected method; return live pricing preview |
| `/api/zepto/checkout` | POST | Validate checkout_token + cart_hash; call `create_*(confirmOrder: true)`; for card/UPI call `check_payment_status`; log to checkout_ops |

### cart_hash computation (server-side)

```python
import hashlib, json

def _cart_hash(items):
    # items: list of {pvid, qty} dicts from the confirmed cart
    canonical = sorted([(i["pvid"], int(i["qty"])) for i in items if i.get("qty", 0) > 0])
    return hashlib.sha256(json.dumps(canonical).encode()).hexdigest()
```

The client sends the cart items to `/api/zepto/payment-methods`. Server computes hash from submitted items and stores the hash + the canonical `items_json` in `pending_checkout_ops`. At checkout time, server recomputes hash from items in the checkout payload and compares against the stored hash. If hashes match, server uses the stored `items_json` (not the client-resent payload) to call `create_*`. This prevents payload substitution between the two calls.

### M-5 guard — how the constraint is safely lifted for this PRD only

All four order tools are now gated identically. The lift is formal and scoped:

- All four `create_*` tools are called **only** from two new functions in `zepto_client.py`:
  - `preview_order(session_id, payment_method, address_id)` → calls `create_*(confirmOrder: False, userAddressId=address_id)`. Returns preview dict. Safe — does NOT place an order.
  - `place_order(session_id, payment_method, address_id)` → calls `create_*(confirmOrder: True, userAddressId=address_id)`. For card/UPI, immediately calls `check_payment_status(order_id, poll=False)`.
- Both functions dispatch based on `payment_method`:
  - `"COD"` → `create_order`
  - `"CARD"` → `create_online_payment_order`
  - `"WALLET"` → `create_wallet_order`
  - `"UPI"` → `create_upi_reserve_pay_order`
  - Any other value → `ValueError("unsupported payment method")`
- `preview_order` is called **only** from `/api/zepto/preview`.
- `place_order` is called **only** from `/api/zepto/checkout`.
- `/api/zepto/checkout` is gated by `checkout_token` validation (expiry + cart_hash + single-use).
- Server logs every invocation of `place_order` at INFO level with: payment_method, item count, cart total, address_id.
- No other code in the codebase calls any `create_*` tool.

**Pre-build verification required (AP-18 catch):** Before Gate 3, Tech Lead must call `tools/list` and read the full description of all four `create_*` tools and `get_payment_methods`. Required parameters, response format, and async vs synchronous behavior must be confirmed and logged in §14.

### Client-side

- "Place Order" button added to View Cart modal footer (currently only has "Close"). Label: "Review & Checkout" (sets correct expectation — does not immediately place order).
- Order Summary modal: new `<div id="order-summary-modal">` — item list (read-only), total, address, payment method radio selector (from server-returned methods list), two buttons: "Confirm & Place Order" (primary) + "Go Back."
- Order Confirmed screen (COD/wallet): order_id, ETA if available, "Done" button.
- Payment Initiated screen (card/UPI): "Complete payment in your browser. Check the Zepto app for confirmation." + "Done" button. Cart not cleared.
- `checkout_token` stored in JS memory only (never in localStorage/sessionStorage). Used once and discarded.
- Cart state (`_cartItems`) cleared after synchronous order success (COD/wallet) only. Not cleared for async payment (card/UPI) since payment may not complete.

### Security constraints

- `checkout_token` issued server-side, single-use, 5-min TTL.
- `cart_hash` computed server-side at token-issue time; canonical `items_json` stored in `pending_checkout_ops`. `create_*` called with stored items, not client-resent items — prevents payload substitution.
- Zepto OAuth token remains encrypted at rest (Fernet), never in browser.
- All MCP calls server-side only.
- `.env` never committed.
- `ANTHROPIC_API_KEY` in `.env`.

### Performance

- `get_payment_methods` MCP call expected ≤3s. Show spinner on "Place Order" tap.
- `create_order` MCP call expected ≤5s. "Confirm & Place Order" button disabled after tap; show "Placing order…" state.

**Technical feasibility:** Green — same MCP session pattern as PRD-003, no new infrastructure.

**Tech Lead notes:** To be completed at Gate 4.

---

## 9. RICE score

| Factor | Score | Rationale |
|---|---|---|
| **Reach** | 5 | Every grocery session that reaches "cart confirmed" now has a checkout path. 100% of the shopping_list flow. |
| **Impact** | 5 | Completes the grocery workflow. Changes CORTEX from a cart-filling tool to a full grocery assistant. |
| **Confidence** | 0.8 | Zepto `create_order` tool exists and is confirmed in tools/list. COD is the default Zepto payment method. AP-18 risk (semantics) mitigated by pre-build tools/list verification. |
| **Effort** | T3 | New modal, 2 new routes, 2 new DB tables, security layer, MCP integration. ~150–200 new lines across app.py, zepto_client.py, db.py, index.html. |
| **Foundation bonus** | ×1.5 | Enables: online payment (v2), order tracking (v2), repeat-order from history (v3). |
| **NSM bonus** | ×1.25 | Directly closes the grocery workflow loop — the feature that makes CORTEX a complete daily-use tool for grocery. |
| **Score** | **(5×5×0.8)/3 × 1.5 × 1.25 = ~12.5** | High priority. |

**Priority tier:** P0

---

## 10. Proof of value gate

```
Behavior change: After this ships, the user will place Zepto orders from within CORTEX
instead of switching to the Zepto app after every cart confirmation.

Observable signal: checkout_ops table has ≥1 successful row within 48 hours of ship.
Sustained signal: ≥70% of cart-confirmed sessions result in a placed order within 4 weeks.

Assumption: The reason the user doesn't complete checkout in CORTEX today is that the
capability doesn't exist — not that they prefer to review/modify the order in the Zepto app.
This is reasonable because: the user explicitly requested this feature and the cart
confirmation modal already provides a full order review.
```

---

## 11. Dependencies

| Dependency | Owner | Status | Blocking? |
|---|---|---|---|
| PRD-003 (Zepto Cart) — cart must be populated before checkout | Shipped | Done | No — already shipped |
| `checkout_token` pattern — adaptation of `confirmation_token` from PRD-003 | Tech Lead | Not started | Yes — needed for Gate 4 |
| Zepto `create_order` API semantics confirmed via `tools/list` | Tech Lead | Not started | Yes — required before Gate 3 (test plan) |
| `get_payment_methods` response format confirmed | Tech Lead | Not started | Yes — required before Gate 3 |
| Fernet encryption key in `.env` | Already exists (from PRD-003) | Done | No |

---

## 12. Guardrails

| Risk | Counter-metric | Threshold | Response |
|---|---|---|---|
| Unintended order placement (M-5 violation) | M-3: `create_*` calls outside PRD-gated path | 0 — any violation | Immediate: re-block all create_* tools, RCA before re-ship |
| Duplicate order (double-tap on "Confirm & Place Order") | checkout_token single-use enforcement | Any duplicate order | Button disabled after first tap; token invalidated server-side after first use |
| Stale cart checkout (cart changed between modal open and confirm) | cart_hash mismatch rate | >5% of checkout attempts | Show "Your cart has changed. Please review and try again." — close Order Summary, reopen View Cart |
| Zepto MCP create_* unavailable or returning errors | M-2: Zepto error rate on checkout | >10% of attempts for 2+ consecutive sessions | Show error with actual Zepto text; "Use Zepto app to complete checkout" |
| checkout_token expiry (user is slow to select payment method) | Token TTL (5 min) | N/A — expected behavior | Show "Session expired. Please start checkout again." — close Order Summary |
| Card/UPI payment URL not opened (popup blocked by browser) | User reports / browser console | Any block | Show URL as a tappable link as fallback: "Tap here to complete payment" |
| Card/UPI payment abandoned (user opened tab, didn't pay) | checkout_ops rows with type=redirect and no subsequent order_id | >50% of card/UPI attempts | Informational — no automated response in v1. Track for v2 in-app polling decision. |

---

## 13. Data and instrumentation

| Event | Trigger | Properties | Purpose |
|---|---|---|---|
| `checkout_initiated` | User taps "Place Order" in View Cart | `{address_id, item_count, cart_total}` | Measure checkout funnel entry rate |
| `checkout_confirmed` | User taps "Confirm & Place Order" | `{payment_method, item_count, cart_total}` | Measure confirmation rate |
| `checkout_success` | `create_order` returns 200 | `{order_id, payment_method, item_count, cart_total}` | Primary success metric |
| `checkout_error` | Any error in checkout flow | `{error_type, error_message}` | Diagnose failure modes |
| `checkout_abandoned` | "Go Back" tapped on Order Summary | `{time_on_summary_seconds}` | Measure abandonment at confirmation step |

**Data pipeline:** All events logged server-side to `checkout_ops`. Client-side events stored in JS session memory only (no analytics SDK in scope for Phase 1).

**A/B test required?** No — single user, Phase 1.

---

## 14. Open questions

| Question | Owner | Due | Status |
|---|---|---|---|
| What parameters does `create_order` (COD) require? | Tech Lead | 2026-06-05 | _Resolved 2026-06-05 by Tech Lead (tools/list): No required params. Optional: `confirmOrder` (bool, default false = preview), `userAddressId` (string), `riderTip` (number), `useZeptoCash` (bool). Two-step: false=preview, true=place._ |
| What parameters does `create_online_payment_order` require? Does it return a redirect URL? | Tech Lead | 2026-06-05 | _Resolved 2026-06-05 by Tech Lead (tools/list): Same params as create_order. Returns orderId. MUST call check_payment_status(orderId, poll:false) after — check_payment_status returns payment URL/status._ |
| What parameters does `create_wallet_order` require? | Tech Lead | 2026-06-05 | _Resolved 2026-06-05 by Tech Lead (tools/list): Same params minus useZeptoCash (it IS the wallet). No check_payment_status required. Wallet must fully cover order total._ |
| What parameters does `create_upi_reserve_pay_order` require? Is it a live UPI flow? | Tech Lead | 2026-06-05 | _Resolved 2026-06-05 by Tech Lead (tools/list): NOT a live UPI collect flow. UPI Reserve Pay = Razorpay pre-funded balance that must fully cover total. MUST call check_payment_status after. Same params as create_order._ |
| What does `get_payment_methods` return exactly? What are the method identifiers? | Tech Lead | 2026-06-06 | Open — need to call the endpoint with a live cart to see response shape and method key strings |
| Does `get_payment_methods` require prior `select_saved_address` in the same MCP session? | Tech Lead | 2026-06-06 | Open — no required params in schema; must test with live cart to confirm session dependency |
| Is payment method availability address-dependent? | Tech Lead | 2026-06-06 | Open — will be answered when get_payment_methods is called with a live cart |
| checkout_token TTL set to 5 min — is this enough for a slow user? | PM | 2026-06-06 | _Resolved 2026-06-05 by PM: 5 min (was 2 min). User may read Order Summary + preview carefully._ |

---

## 15. Team sign-offs

| Team | Sign-off | Date | Notes |
|---|---|---|---|
| PM | — | — | Draft — pending open questions resolution |
| AI Engineer | — | — | No LLM call in checkout path — sign-off fast-track |
| Tech Lead | — | — | Pending Gate 4 |
| UX Designer | — | — | Pending modal wireframe review |
| Data Analyst | — | — | Instrumentation plan in §13 |
| DevOps | — | — | No new infra — same server, same DB |

---

## 16. History

| Date | Author | Change |
|---|---|---|
| 2026-06-05 | PM | Initial draft — v1.0 (COD only) |
| 2026-06-05 | PM | v1.1 — scope expanded to all payment methods (COD + card + wallet + UPI). M-5 formally lifted for all four create_* tools via unified `place_order()` dispatcher gated by checkout_token. checkout_token TTL raised from 2 min to 5 min. "Place Order" button renamed "Review & Checkout." |
| 2026-06-05 | Tech Lead | v1.2 — tools/list verified. Added two-step confirmOrder flow (preview + place). Added /api/zepto/preview endpoint. Added check_payment_status call after card/UPI placement. Card/UPI payment_url returned as tappable link (not window.open). Gate 2 blockers R-TL-2 resolved, R-TL-3 de-blocked. Gate 2 PASSED. |

---

## Gate 2 — PRD Review (2026-06-05)

**Status:** IN REVIEW

---

### PM self-review

**R-PM-1 (OPEN):** M-1 denominator gap. "Checkout completion rate (order placed / cart confirmed)" requires a denominator — "cart confirmed" sessions. The `checkout_initiated` event in §13 is stored in JS session memory only, which is not queryable after the session closes. To make M-1 computable, `checkout_initiated` must be persisted server-side. **Recommendation:** Add a `status='initiated'` row to `pending_checkout_ops` when the payment-methods endpoint is called. Completion rate = `checkout_ops.status='success'` / `pending_checkout_ops` total. Owner: Tech Lead to add to Gate 4. **— OPEN**

---

### Tech Lead review

**R-TL-1 (RESOLVED):** Payload substitution risk. Original PRD said "server recomputes hash from items in checkout payload." This meant the client could send different items at checkout time with a matching hash (if they computed it client-side). Fixed in v1.1: server stores canonical `items_json` in `pending_checkout_ops` at token-issue time. `create_*` called with stored items, not re-trusted client payload. **— RESOLVED**

**R-TL-2 (RESOLVED):** All four `create_*` tool parameters confirmed via tools/list (2026-06-05). Key findings: (1) Two-step flow — `confirmOrder: false` = safe preview (delivery fee + ETA from Zepto, no order placed); `confirmOrder: true` = real order. (2) Card and UPI Reserve Pay MUST call `check_payment_status(orderId, poll: false)` after placement — server-side. (3) UPI Reserve Pay is a Razorpay pre-funded balance, not a live UPI collect. (4) All params optional; `userAddressId` and `confirmOrder` are the key ones. Architecture updated in §7 + §8. **— RESOLVED**

**R-TL-3 (PARTIALLY RESOLVED):** `get_payment_methods` has no required parameters (confirmed via tools/list). Whether it requires `select_saved_address` in session first is still unknown — must test with a live cart. However, this is no longer a Gate 3 blocker: the test plan can include a test case for this session dependency. If it requires address context, `_setup_for_cart()` is the fix (already in codebase from PRD-003). **— PARTIAL — no longer a Gate 3 blocker.**

**R-TL-4 (OPEN):** Card/UPI popup blocking. `window.open(payment_url)` is blocked by modern browsers unless called from a direct user-action handler (synchronous). Since the payment URL is returned from a server call (async fetch), `window.open` will be blocked. Solution: open the URL in a full `<a href target="_blank">` link the user taps explicitly, OR store the URL and show it as a styled button after the server returns. **Recommendation:** Show "Open Payment Page" as a styled button after server returns payment_url; user taps it directly. Owner: UX Designer to incorporate into design. **— OPEN**

---

### UX Designer review

**R-UX-1 (RESOLVED):** "Place Order" button label implies immediate action. Fixed in v1.1: renamed to "Review & Checkout." **— RESOLVED**

**R-UX-2 (OPEN → accepted as design spec):** Payment method radio selector UX. The Order Summary modal needs a clear visual hierarchy: items summary (top) → payment method selector (middle, radio buttons with labels like "Cash on Delivery", "Credit/Debit Card", "Zepto Wallet", "UPI") → action buttons (bottom). Default selection: COD if available; otherwise first in list. Payment method icons (COD: 💵, Card: 💳, Wallet: 👛, UPI: 📱) improve scanability. **— ACCEPTED as design spec; no blocker.**

**R-UX-3 (OPEN):** Silent checkout_token expiry on Order Summary is poor UX. If 5-min token expires while user is still on Order Summary, they only discover it when they tap "Confirm & Place Order" and get a 422. **Recommendation:** Show a subtle countdown timer in the Order Summary modal header ("Session expires in 4:32"). On expiry, auto-show toast: "Session expired — tap Place Order again." and close Order Summary back to View Cart. **Owner: Tech Lead to evaluate. Owner's call on whether to implement in v1 or v2.** **— OPEN**

---

### AI Engineer review

**R-AI-1 (RESOLVED):** No LLM call in the checkout path — confirmed. Fast-track sign-off on AI impact. **— RESOLVED**

**R-AI-2 (NOTE — no action required in v1):** `checkout_ops.items_snapshot` (JSON of pvid/qty/amount for every confirmed order) is high-quality training data for a future "smart reorder" or "predicted grocery list" feature. The schema already supports this — no changes needed now. Filing as a Vision Note: when Phase 2 corpus is large enough, `checkout_ops` + `auto_add_results` metadata together could power a personalised weekly grocery suggestion. **— NOTE, no action.**

---

### Gate 2 resolution summary

| Comment | Status | Gate 3 blocker? |
|---|---|---|
| R-PM-1: M-1 denominator — add status='initiated' to pending_checkout_ops | OPEN | No — Tech Lead adds at Gate 4 |
| R-TL-1: Payload substitution — fixed in v1.1 | RESOLVED | — |
| R-TL-2: All create_* parameters unknown — tools/list required | OPEN | **YES** |
| R-TL-3: get_payment_methods session dependency unknown | OPEN | **YES** |
| R-TL-4: window.open popup blocking for card/UPI | OPEN | No — design fix incorporated at Gate 4 |
| R-UX-1: "Place Order" label — fixed in v1.1 | RESOLVED | — |
| R-UX-2: Payment method radio selector design | ACCEPTED | — |
| R-UX-3: Countdown timer on checkout_token expiry | OPEN | No — owner's call for v1/v2 |
| R-AI-1: No LLM in checkout path | RESOLVED | — |
| R-AI-2: checkout_ops as future training data | NOTE | — |

**Gate 2 verdict: PASS.** R-TL-2 resolved (tools/list confirmed). R-TL-3 no longer blocks Gate 3. Remaining open items (R-PM-1, R-TL-4, R-UX-3) are tracked for Gate 4. PRD approved for Gate 3 — test plan can be written now.

---

*Not investment advice. Analytical output for training purposes only.*
