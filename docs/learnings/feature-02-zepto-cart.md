# Gate 8 Retrospective — CORTEX PRD-003: Zepto Cart from Grocery List (Releases 1–3)

**Feature:** Zepto Cart integration — shopping_list type, auto-add, Swap ↻, cart qty controls, deletion  
**PRD:** PRD-CORTEX-003 v1.0  
**Shipped:** 2026-06-05 (Release 1: auto-add; Release 2: View Cart + qty controls; Release 3: Swap ↻ + fixes)  
**Test result:** 207/207 passing (9 new for deterministic product selection)  
**Security:** Fernet OAuth, confirmation_token, M-5 hard zero enforced throughout. Zero unintended orders.

---

## What shipped

- `shopping_list` content type with Zepto MCP HTTP client (`zepto_client.py`)
- Auto-add pipeline: extract items → search Zepto → deterministic product selection (word-overlap × order_count) → Haiku fallback → merge into cart → archive capture
- View Cart modal: per-item `[🗑/−] qty [+] [Swap ↻]` controls
- Swap ↻ bottom-sheet: search Zepto for replacement, "Previously bought" badge, real MCP swap
- Archived card rows: per-item "✓ token → product" with Swap ↻

---

## Bugs found and fixed post-ship (all in Release 3)

### 1. Product selection: wrong brand selected
- **Root cause:** `previously_bought` used exact-string match → always False → Haiku had no past-order signal → picked first result
- **Fix:** `_word_overlap_score()` + `_deterministic_best_match()` — scores every (product, past_order) pair as `overlap × order_count`; bypasses Haiku when overlap ≥ 0.5
- **Elevated to org:** Not elevated (CORTEX-specific product selection logic)

### 2. Cart sync failed with no diagnostic info
- **Root cause:** `get_past_order_items` called on every cart write (not needed); error text never surfaced in toast, console, or server log
- **Fix:** `need_past_orders=False` param on `_setup_for_cart`; `console.error` + `app.logger.error` + actual error text in toast
- **Elevated to org:** AP-19 (generic error toast), AP-20 (shared setup function over-built for complex caller)

### 3. Cart deletion silently doing nothing
- **Root cause:** Assumed `update_cart` = full replace; built delete-by-omission. Actual semantics: UPSERT — omitted items unchanged, `quantity: 0` = delete signal. Never read `tools/list` before building.
- **Fix:** `tools/list` called via `/api/zepto/debug/tools`; confirmed qty=0 = delete signal; send qty=0 for removed items
- **Elevated to org:** AP-18 (assumed API semantics without reading spec), P-18 (read tools/list first)

### 4. Rapid deletion only registered first click
- **Root cause:** `_renderCartItems()` called `body.innerHTML = ''` + full rebuild on every state change. Second rapid tap landed on detached (destroyed) node.
- **Fix:** In-place DOM updates — `row.style.display = 'none'` for deletions, direct span updates for qty changes. Full rebuild only on initial open and post-sync.
- **Elevated to org:** AP-17 (full DOM rebuild on every state change), P-19 (in-place DOM mutation for interactive lists)

### 5. Stale cart accumulation
- **Root cause:** (a) `closeCartModal` cancelled debounce instead of flushing it; (b) auto-add added duplicate brands on each run
- **Fix:** (a) `closeCartModal` flushes pending sync before closing; (b) 60% word-overlap duplicate guard in `auto_add_shopping_items`
- **Elevated to org:** Not elevated (Zepto-specific session state pattern)

---

## Patterns confirmed (already in catalogue)
- **AP-12** (stale server after code change) — hit during swap feature; server restart was required to see new JS

---

## What should have been done differently

1. **Call `tools/list` on day 1 of MCP integration** — read every tool description before writing a single line of CRUD code. Would have saved 2+ debug sessions on deletion.
2. **Test delete semantics explicitly in the test plan** — the test plan had no test for "item removed from cart stays removed on re-open." AC-to-test mapping would have caught this.
3. **In-place DOM update pattern should be in the initial implementation** — it's the correct pattern for any interactive list; full-rebuild-on-change is never correct for user-initiated state changes.
4. **Error surfacing should be a first-class implementation requirement** — console.error + server log + actual error text in toast should be in the Prompt Engineer's standard template for any external API call.

---

## Tests added this feature
- `TestWordOverlapScore` (5 tests)
- `TestDeterministicBestMatch` (4 tests)
- Total: 207/207 (up from 198)
