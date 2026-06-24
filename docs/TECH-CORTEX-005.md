# TECH-CORTEX-005 — Credit-Card Checkout · Implementation Plan

**Owner:** tech-lead | **For:** PRD-CORTEX-005 | **Date:** 2026-06-24
**Stack:** Python/Flask · SQLite WAL · MCP Streamable-HTTP (`zepto_client.py`) · Vanilla JS
**Estimate:** ~120–160 LOC across 4 files. No new dependencies, no new infra.

> **Pre-build gate (AP-18 catch):** before writing `place_order`, re-auth Zepto (`/api/zepto/init`) and call `list_mcp_tools(token)`; confirm the exact `get_payment_methods` response shape and the card method key string. Log findings in PRD-005 §10 Q1. Until then, code matches the card method by substring `"card"` (case-insensitive).

---

## Files touched

| File | Change |
|---|---|
| `db.py` | + `pending_checkout_ops`, `checkout_ops` table DDL in `init_db()`; + 5 helper fns |
| `zepto_client.py` | + `_setup_for_checkout()`, `preview_order()`, `place_order()`, `_cart_hash()`; **M-5: the only callers of `create_*`** |
| `app.py` | + 3 routes: `/api/zepto/payment-methods`, `/api/zepto/preview`, `/api/zepto/checkout` |
| `templates/index.html` | + "Review & Checkout" button; Order Summary modal; Pay-Now / Order-Confirmed screens; JS |
| `tests/test_zepto.py` (+ `test_db.py`) | + token lifecycle, cart_hash, M-5 guard, route, dispatcher tests (MCP mocked) |

---

## 1. `db.py`

DDL added to `init_db()` (idempotent `CREATE TABLE IF NOT EXISTS`, schemas per PRD-005 §8). Helpers:

```python
def create_pending_checkout(token, cart_hash, address_id, items_json, expires_at): ...
def get_pending_checkout(token): ...           # → row or None
def mark_checkout_previewed(token): ...         # status='previewed'
def mark_checkout_used(token, order_id): ...    # used_at=now, status='used', order_id
def log_checkout_op(token, cart_hash, payment_method, address_id,
                    items_snapshot, total_amount, zepto_order_id, status): ...  # append-only
```

All writes via the existing WAL connection helper. No destructive ops.

## 2. `zepto_client.py` (M-5-critical)

```python
import hashlib, json

def _cart_hash(items):                       # items: [{pvid, qty}, ...]
    canonical = sorted((i["pvid"], int(i["qty"])) for i in items if int(i.get("qty", 0)) > 0)
    return hashlib.sha256(json.dumps(canonical).encode()).hexdigest()

def _setup_for_checkout(token, address_id=None):
    """Checkout session WITHOUT past-order fetch (AP-20: don't reuse the heavy cart setup).
       Reuse _setup_for_cart(token, address_id, need_past_orders=False)."""
    return _setup_for_cart(token, address_id=address_id, need_past_orders=False)

_TOOL_FOR_METHOD = {"CARD": "create_online_payment_order"}  # COD/WALLET/UPI reserved, not wired in v1

def _dispatch_tool(payment_method):
    tool = _TOOL_FOR_METHOD.get(payment_method)
    if not tool:
        raise ValueError(f"unsupported payment method: {payment_method}")
    return tool

def preview_order(token, payment_method, address_id, session_id=None):
    """SAFE — confirmOrder=False. Returns {subtotal, delivery_fee, total, eta_minutes, raw}."""
    sid = session_id or _setup_for_checkout(token, address_id)
    tool = _dispatch_tool(payment_method)
    text = _mcp_tool(token, sid, tool, {"confirmOrder": False, "userAddressId": address_id})
    return _parse_preview(text)            # tolerant parse of Zepto's SSE/JSON

def place_order(token, payment_method, address_id, session_id=None):
    """PLACES THE ORDER — confirmOrder=True. CARD → also check_payment_status(poll=False)."""
    sid = session_id or _setup_for_checkout(token, address_id)
    tool = _dispatch_tool(payment_method)
    text = _mcp_tool(token, sid, tool, {"confirmOrder": True, "userAddressId": address_id})
    order = _parse_order(text)             # → {order_id, total, ...}
    if payment_method == "CARD":
        status = _mcp_tool(token, sid, "check_payment_status",
                           {"orderId": order["order_id"], "poll": False})
        order["payment_url"] = _parse_payment_url(status)
        order["type"] = "redirect"
    else:
        order["type"] = "confirmed"
    return order

def get_payment_methods(token, address_id=None, session_id=None):
    sid = session_id or _setup_for_checkout(token, address_id)
    return _parse_methods(_mcp_tool(token, sid, "get_payment_methods", {}))
```

**Invariant (M-5):** `grep -n "create_online_payment_order\|create_order\|create_wallet_order\|create_upi" zepto_client.py app.py` must show calls **only** inside `preview_order`/`place_order`. Add a test asserting this.

## 3. `app.py` routes

```
POST /api/zepto/payment-methods   {cart_items, address_id}
  → token check (get_zepto_token/decrypt); methods = get_payment_methods(...)
  → cart_hash = _cart_hash(cart_items); token = uuid4(); expires = now+5min
  → db.create_pending_checkout(token, cart_hash, address_id, json(cart_items), expires)  # status='initiated'
  → 200 {methods, checkout_token, expires_at}

POST /api/zepto/preview           {checkout_token, payment_method}
  → row = get_pending_checkout(token); validate exists/not used/not expired
  → preview = preview_order(token=zepto, payment_method, row.address_id)   # confirmOrder=False
  → mark_checkout_previewed(token); 200 {preview}

POST /api/zepto/checkout          {checkout_token, payment_method}
  → row validate: exists + used_at IS NULL + not expired + recompute _cart_hash(row.items_json)==row.cart_hash
  → on fail → 422 {error: 'expired'|'already_used'|'cart_changed'}
  → result = place_order(zepto, payment_method, row.address_id)            # confirmOrder=True
  → mark_checkout_used(token, result.order_id); log_checkout_op(..., status='success')
  → 200 {type:'redirect', payment_url, order_id}     # CARD
  → on Zepto error → log status='error'; 502 {error: zepto_text[:120]}    # AP-19
```

Reuse the existing token-decrypt preamble (`db.get_zepto_token()` → `decrypt_token`) already repeated across the Zepto routes.

## 4. `templates/index.html`

- View Cart modal footer: add **"Review & Checkout"** button → `POST /payment-methods` → open Order Summary modal.
- `#order-summary-modal`: read-only item list, live preview totals (from `/preview`), address, payment-method radios (card preselected; match `"card"`), header **5-min countdown timer** (R-UX-3), buttons **"Confirm & Pay"** (primary, disables on tap) + **"Go Back"**.
- On confirm → `POST /checkout` → render **Pay-Now screen**: a styled `<a href=payment_url target="_blank">Pay Now →</a>` (NOT `window.open`) + "Complete payment in your browser; order confirms in the Zepto app." + Done. **Cart not cleared.**
- `checkout_token` in a JS variable only; cleared after use.

---

## 5. Test plan hooks (`tests/`, MCP mocked — never a live order)

1. `_cart_hash` deterministic + order-independent; mismatch on qty change.
2. Token lifecycle: issue → preview → use; reject reuse, expiry, cart-change (422 each).
3. `_dispatch_tool`: `"CARD"`→`create_online_payment_order`; unknown→`ValueError`.
4. `place_order(CARD)` calls `check_payment_status(poll=False)` and returns `payment_url` (mock asserts call args incl. `confirmOrder=True`).
5. **M-5 guard test:** static assert no `create_*` reference outside `preview_order`/`place_order`.
6. Route tests: 200/422/502 paths; `checkout_ops` row written with correct status; AP-19 error text truncation.
7. Full suite green: `python -m pytest tests/ -v` (207 → 207+new).

## 6. Build order (Gate-4)

```
1. db.py tables + helpers            → test_db green
2. zepto_client dispatchers+hash     → test_zepto unit green (mocked)
3. app.py 3 routes                   → route tests green
4. index.html modal + JS            → manual click-through (mock or live)
5. Re-auth Zepto, resolve Q1 (method key), live preview (confirmOrder=False) sanity
6. ONE live card order (owner-supervised) → confirm checkout_ops row → M-2 hit
```

**Definition of done:** all tests green; M-5 guard test passing; one live card order placed + logged; PRD-005 §10 Q1 resolved in the doc.
