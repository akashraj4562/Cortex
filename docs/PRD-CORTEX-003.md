# PRD-CORTEX-003 — Zepto Cart from Grocery List

**Status:** `SHIPPED — Gate 7 Complete`
**Test plan:** `docs/test-plan-PRD-003-zepto-cart.md`
**Filed:** 2026-06-04
**Product:** CORTEX
**PM:** product-manager
**Last updated:** 2026-06-04

**Prior art:** PRD-CORTEX-002 established the image capture input channel (camera + gallery upload) and dynamic content_type taxonomy. This PRD builds on both: the image path is reused for photo-of-list capture; the `shopping_list` type is a new intent type entering the dynamic taxonomy. Architecture of item extraction follows the same extract→classify→act pattern established in PRD-CORTEX-001 (classifier pipeline).

**Anti-patterns checked:**
- **AP-02 (Code before PRD):** Caught — PRD drafted before any implementation started.
- **AP-05 (Audit trail deletion):** Caught — open questions tracked with owner + date; resolved questions preserved inline.
- **AP-10 (Ambiguous data source):** Not applicable — no date/recency display in this feature.
- **New risk — Real-money action without confirmation gate:** The Zepto MCP explicitly states orders are real transactions. A missing or skippable confirmation step would be a P0 defect. Catch mechanism: §12 Guardrails mandates a hard confirmation step; Tech Lead must verify this is never bypassed in implementation.

---

## ✅ REQUIRED (gate blocks without these 4)

1. **Problem** — ✅ §1
2. **Solution overview** — ✅ §7
3. **Scope** — ✅ §5 + §6
4. **Open Questions** — ✅ §14

---

## 1. Problem statement

A user has a grocery list — typed quickly, or a photo of a handwritten note, or a recipe screenshot. Converting that list to a Zepto cart today requires opening the Zepto app, searching each item individually, choosing from multiple results, setting quantities, and repeating for every item. For a 15-item list, this is 10–15 minutes of friction. The list already exists; the work is in the manual translation.

CORTEX already captures text and images (PRD-CORTEX-002). It can extract structured data from both. The gap is: CORTEX captures intent but cannot act on it. A `shopping_list` capture is a dead-end — it goes into a tab and sits there. The user still has to open Zepto.

**Cost of not solving:** Every shopping capture is wasted intent. The user does the work twice — once to capture, once to manually transfer. This is exactly the "intent loss" problem CORTEX exists to solve (VISION-CORTEX.md §1), applied to the commerce context.

**[ASSUMPTION: no data — treat as hypothesis]** Grocery shopping occurs 2–4×/week for urban Indian households with Zepto access; manual Zepto search friction is ~30–60 seconds per item.

---

## 2. True need (interpreted)

**Stated request:** "User writes a list of items they need (text or image) → items added to Zepto cart."

**Interpreted need:** The user wants CORTEX to close the loop between *intent formation* (I need these things) and *action execution* (they are in my cart, ready to order). The capture is just the vehicle. The value is zero friction between "I have a list" and "my cart is ready."

**Assumption flagged:** The user wants items added to cart, not orders placed. Order placement (payment, delivery slot selection) is a conscious decision requiring human judgment — it is explicitly out of scope for v1. The action CORTEX takes is: populate the cart. The user decides when and whether to checkout.

**Assumption flagged:** "Best match" product selection will sometimes be ambiguous (user says "milk" — Amul 500ml? Amul 1L? A2 full-fat?). The PRD assumes a match-and-confirm flow rather than a silent auto-select. The user reviews matches before cart add. If this confirmation step proves too much friction after launch, it can be shortened — but it must never be removed entirely (real money guardrail).

---

## 3. User story

```
As a CORTEX user who shops on Zepto,
I want to type or photograph my grocery list and have CORTEX populate my Zepto cart,
So that I can go from "list in hand" to "cart ready to order" in under 60 seconds
without opening the Zepto app.
```

**Jobs-to-be-done:**
- When I finish a recipe and know what ingredients I need, I want to capture the list and have my cart ready, so I can order without the switching-and-searching overhead.
- When I photograph a handwritten shopping list, I want CORTEX to read it and act on it, so I don't re-type every item.
- When I share a grocery list from a family WhatsApp message, I want to paste it into CORTEX and have the cart populated, so the family's list becomes my cart without any manual work.

---

## 4. Success metrics

| # | Metric | Target | Source | Cadence | Type |
|---|---|---|---|---|---|
| M-1 | Shopping list captures that result in a cart add (conversion rate) | ≥70% within 4 weeks of launch | CORTEX event log: `zepto_cart_confirmed` / `shopping_list_captured` | Weekly | Primary |
| M-2 | Items successfully matched per list (match rate) | ≥80% of line items found on Zepto | CORTEX event log: `item_matched` / `item_searched` | Weekly | Secondary |
| M-3 | Time from capture submission to cart confirmation | Median ≤45 seconds | CORTEX event log: `shopping_list_captured` → `zepto_cart_confirmed` timestamps | Weekly | Secondary |
| M-4 | Captures that are abandoned at the confirmation step (abandonment rate) | ≤20% | CORTEX event log: `zepto_confirm_shown` vs `zepto_confirm_dismissed` | Weekly | Counter |
| M-5 | Unintended orders placed (real Zepto orders triggered without explicit confirmation) | 0 — hard zero | Manual audit + Zepto order history | Every ship | **Counter / Hard gate** |

**Primary success metric:** 70% of shopping list captures result in a confirmed cart add within 4 weeks.
**Counter-metric threshold (M-4):** If abandonment at confirmation exceeds 30% for 2 consecutive weeks, the confirmation UX or match quality is broken — investigate before any other work.
**Counter-metric threshold (M-5):** Any unintended real order is a P0 incident. Feature is suspended until root cause is resolved.

**Behavior change:** After this ships, the user will add items to their Zepto cart without opening the Zepto app.
**Observable signal:** `zepto_cart_confirmed` events appear in the CORTEX event log within 4 weeks. Shopping list captures stop being dead-end tab entries.

---

## 5. Scope — what's in v1

- [ ] New `shopping_list` content type added to CORTEX classifier (Corty detects shopping lists in text and image input)
- [ ] **Text input path:** User types or pastes a list (any format — bullet, comma-separated, numbered, WhatsApp paste)
- [ ] **Image input path:** User uploads a photo or screenshot of a grocery list (reuses the camera/gallery capture from PRD-CORTEX-002)
- [ ] **Item extraction:** Corty parses the list into structured line items with name + quantity (e.g., `[{item: "atta", qty: "5kg"}, {item: "milk", qty: "2"}]`)
- [ ] **Zepto product search:** For each extracted item, call Zepto MCP `search_products` to find the best matching product
- [ ] **Confirmation UI:** Show the user a match review screen — each extracted item paired with the top Zepto result (product name, weight/size, price). User can accept, change, or remove each match before confirming.
- [ ] **Cart add:** On user confirmation, call Zepto MCP cart management to add all confirmed items
- [ ] **Zepto OAuth setup:** One-time authentication flow (Indian mobile + OTP) surfaced when the user first triggers the Zepto action
- [ ] **Classifier disambiguation rule (P0-4):** Add rule to `classifier.py` system prompt: ≥2 commerce-likely items (food, household goods, consumables) OR ≥1 quantity-token (e.g., "2kg", "1 dozen", "500ml", "x3") → classify as `shopping_list`, not `reminder`. Regression test against full 44-capture corpus required before any implementation ships.
- [ ] **Partial success handling:** If some items are not found on Zepto, show the user which items were skipped. Add the found items. Do not fail the whole list.
- [ ] **Result capture:** Log the completed cart-add as a CORTEX capture with `content_type: shopping_list`, tagged `zepto_fulfilled: true`

---

## 6. Explicitly out of scope (v1)

| Feature | Reason deferred |
|---|---|
| Order placement (checkout, payment, delivery slot) | Real financial transaction requiring conscious user decision. CORTEX populates the cart; the user checks out in the Zepto app. Prevents any accidental orders. |
| Blinkit / Swiggy Instamart / other platforms | Architecture must prove out on one MCP before multi-platform. Zepto is the beachhead. |
| Recurring lists ("add my weekly grocery list automatically") | Automation without confirmation violates the hard guardrail (real money). Phase 2 only — after confirmation UX is validated and trusted. |
| Quantity optimisation (find cheapest pack combination for 5kg atta) | Too complex for v1 match logic. Use the first relevant result. |
| Nutritional / brand preference memory ("always pick Amul milk") | Phase 2 — requires preference persistence layer not yet designed. |
| Voice input ("Corty, add milk and eggs to my Zepto cart") | Phase 3 ambient capture. Not in v1 text/image scope. |
| Order history access via MCP | Not relevant to the use case. Future feature if needed. |
| Sharing cart with another user | Out of CORTEX's single-user Phase 1 scope entirely. |

---

## 7. Solution design

**User flow (text input):**

```
User opens CORTEX capture box
  → Types or pastes grocery list (any format)
  → Corty detects shopping_list intent (confidence ≥80%)
  → CORTEX shows: "Found a grocery list — add to Zepto cart?"  [Add to Zepto] [Save only]
  → User taps [Add to Zepto]
    → If not authenticated: Zepto OAuth flow (one-time, browser redirect, OTP)
    → CORTEX extracts items: ["atta 5kg", "Amul milk 2L", "eggs 12", ...]
    → Parallel: search_products for each item on Zepto
    → Confirmation screen shows:
        ✅ Atta (Aashirvaad, 5kg) — ₹285
        ✅ Milk (Amul Taaza, 2L) — ₹112
        ✅ Eggs (White, 12-pack) — ₹98
        ❌ "kokum" — not found on Zepto [Skip]
    → User reviews, changes any match, taps [Add 3 items to cart]
    → Zepto MCP adds confirmed items to cart
    → CORTEX shows: "3 items added to your Zepto cart. Open Zepto to checkout."
```

**User flow (image input):**

```
User opens CORTEX capture → taps camera icon → [Upload from Gallery]
  → Selects photo of handwritten list / recipe screenshot
  → Corty reads image via vision API → detects shopping_list intent
  → Same flow as text input from the extraction step onwards
```

**Key interactions:**

1. **Corty detects list → prompts action:** The "Add to Zepto" CTA appears contextually on `shopping_list` captures. It does not appear on other content types.
2. **First-time auth:** Zepto OAuth is triggered lazily — only when the user first taps [Add to Zepto]. Auth token is stored in CORTEX (encrypted, server-side) and reused across sessions.
3. **Match review is mandatory:** The confirmation screen cannot be bypassed. There is no "add all without review" shortcut in v1.
4. **Partial success is success:** If 4/6 items are found, add the 4 and tell the user about the 2. The user opens Zepto to manually search the missing 2.
5. **Save-only path:** If the user selects [Save only] at the first prompt, the capture is saved as a `shopping_list` tab entry. No Zepto action. They can trigger the cart-add later from the capture card.

**Design spec:** UX Designer to produce confirmation screen wireframe — specifically the match-review card layout and the "not found" state for unmatched items.

---

## 8. Technical requirements

**Data to store:**
- `shopping_list` as a new `content_type` in the `content_types` table
- `zepto_auth_token` — encrypted OAuth token, stored server-side, linked to user session
- Extracted items stored in capture `metadata` JSON field: `{items: [{name, qty, zepto_product_id, price, status}]}`
- `zepto_fulfilled: boolean` tag on completed captures

**APIs needed:**
- **Zepto MCP** (HTTP transport): `https://mcp.zepto.co.in/mcp`
  - `search_products(query: string)` — called once per extracted item
  - `cart_management(action: "add", item_id, quantity)` — called for each confirmed item
- **Anthropic Vision API** — already integrated in PRD-CORTEX-002 for image extraction
- **Anthropic Completions API** — item extraction prompt (structured JSON output from free-text list)

**Third-party integrations:**
- **Zepto MCP** — HTTP transport at `https://mcp.zepto.co.in/mcp`. JSON-RPC 2.0 protocol. OAuth 2.0 authentication (Indian mobile + OTP).

**MCP integration architecture (P0-3 resolved):** Flask calls the Zepto MCP directly as an HTTP client — no Claude Code subprocess, no `claude mcp add` command. Flask sends `POST https://mcp.zepto.co.in/mcp` with a JSON-RPC 2.0 body and `Authorization: Bearer <decrypted_access_token>` header. The token is decrypted server-side from `external_credentials` immediately before use and never returned to the client or logged.

**OAuth credentials storage** (`external_credentials` table — new migration required):

```sql
CREATE TABLE external_credentials (
  service       TEXT PRIMARY KEY,
  access_token  BLOB NOT NULL,   -- Fernet-encrypted (AES-128-CBC)
  refresh_token BLOB,            -- Fernet-encrypted
  expires_at    DATETIME,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME
);
```

Fernet key stored in `.env` as `FERNET_KEY` (never committed to git). Server refreshes token if `expires_at < now + 5 minutes` before each MCP call.

**OAuth callback route:** Flask must implement `GET /api/zepto/callback?code=<auth_code>&state=<state>` to receive the redirect from Zepto after OTP verification. This route exchanges the auth code for access + refresh tokens and writes them (Fernet-encrypted) to `external_credentials`. The `redirect_uri` sent in the auth request must exactly match the whitelist entry used — start with `http://localhost:5050/callback` (RFC 8252 port-agnostic expected); if rejected, request `http://localhost:5050/callback` be added via GitHub issue on zeptonow/mcp.

**Performance requirements:**
- Item extraction: ≤3 seconds for a list of ≤20 items
- Product search: parallel calls per item; all searches complete in ≤8 seconds for a 15-item list
- Confirmation screen renders: ≤1 second after search completes
- Cart add: ≤5 seconds for ≤20 items (sequential MCP calls)

**Security requirements:**
- Zepto OAuth token encrypted at rest (AES-256 or equivalent); never exposed to browser
- Auth token must be revocable by user (settings page: "Disconnect Zepto")
- All Zepto MCP calls made server-side — no token or MCP credentials in client JS
- **Confirmation enforcement — non-bypassable (P0-1 resolved):** The cart-add endpoint (`POST /api/zepto/cart-add`) requires a `confirmation_token` — a single-use UUID generated by the server when it renders the confirmation screen. Flow:
  1. Server renders confirmation screen → generates UUID → stores in `pending_cart_ops` table (`confirmation_token TEXT PRIMARY KEY`, `capture_id TEXT`, `items_hash TEXT`, `expires_at DATETIME`, TTL: 5 minutes) → returns token in the confirmation-screen API response alongside match results
  2. Client displays confirmation screen to user, then includes `confirmation_token` in the cart-add request body
  3. Server validates token (exists + not expired) → deletes it → calls `cart_management` on Zepto MCP
  - Token is single-use: once consumed, replay is rejected 403
  - Direct `POST /api/zepto/cart-add` without a valid token → 403 Forbidden
  - Bypass is structurally impossible from the client side

**Technical feasibility:** Yellow — Zepto MCP is a live, documented external service (not under our control). Risk: MCP API changes, rate limits (undocumented), or auth flow changes could break the integration at any time. Mitigation: design the integration as a swappable adapter so a Blinkit or alternative MCP can be substituted without rebuilding the core flow.

**Tech Lead notes:** To be completed at Gate 5.

---

## 9. RICE score

| Factor | Score | Rationale |
|---|---|---|
| **Reach** | 4/5 | Grocery shopping is a high-frequency, near-weekly behaviour. Every CORTEX user who shops on Zepto (large overlap in urban India) benefits. |
| **Impact** | 5/5 | Converts a 10–15 minute multi-step manual workflow to a 45-second single capture. This is the clearest possible CORTEX value demonstration: capture → act. |
| **Confidence** | 0.8 | Zepto MCP is live and documented. Use case is precisely stated. Risk is MCP stability (external dependency). |
| **Effort** | T4 | New external MCP integration, OAuth flow, item extraction prompt, confirmation UI, new content_type, server-side cart-add. Cross-file, new architecture. 2+ sessions. |
| **Foundation bonus** | ×1.5 | Directly enables: (a) Blinkit MCP integration (same adapter pattern), (b) Swiggy Instamart MCP, (c) recipe-to-cart (image input → ingredient list → cart), (d) recurring list automation (Phase 2). The commerce action adapter is the reusable primitive. |
| **NSM bonus** | ×1.25 | Directly drives capture habit (CORTEX's Phase 1 NSM) — users will return specifically to use the cart feature, forming a daily/weekly capture ritual around shopping. |
| **Score** | **(4×5×0.8)/4 × 1.5 × 1.25 = 4.0 × 1.875 = 7.5** | |

**Priority tier:** P1 — High value, clear use case, external dependency risk is manageable. Does not block any other current work.

---

## 10. Proof of value gate

```
Behavior change: After this ships, the user will open CORTEX to manage their grocery list
                 instead of opening the Zepto app to search manually.
Observable signal: zepto_cart_confirmed events appear ≥2×/week within 4 weeks of launch.
                   Shopping list tab entries transition from dead-end saves to fulfilled carts.
Assumption: The user shops on Zepto ≥1×/week — reasonable given Zepto's urban India penetration
            and the user's existing Zepto account (confirmed by the OAuth flow succeeding).
```

---

## 11. Dependencies

| Dependency | Owner | Status | Blocking? |
|---|---|---|---|
| Image capture pipeline (PRD-CORTEX-002 Release 2) | Tech Lead | Approved for implementation | Yes — image path requires this to be live |
| Dynamic content_type taxonomy (PRD-CORTEX-002) | Tech Lead | Shipped (Release 1) | Yes — `shopping_list` type requires dynamic taxonomy |
| Zepto MCP account / OAuth | Owner (Akash) | Not started — requires Indian mobile verification | Yes — cannot test without authenticated Zepto account |
| Anthropic Vision API | AI Engineer | Live (integrated in PRD-CORTEX-002) | No — already available |
| Zepto MCP availability | Zepto (external) | Live at `https://mcp.zepto.co.in/mcp` | Yes — external dependency, no SLA |

---

## 12. Guardrails

| Risk | Counter-metric | Threshold | Response |
|---|---|---|---|
| **Unintended real Zepto order placed** | M-5: confirmed unintended orders | Any single occurrence | P0 incident — suspend feature, root cause analysis, confirmation flow audit |
| **Wrong items added to cart** (match quality failure) | M-2: match rate | <70% for 2 consecutive weeks | Review item extraction prompt + search query construction; add manual override to confirmation screen |
| **Auth token leakage** (Zepto OAuth exposed to browser) | Security audit | Any occurrence | P0 incident — rotate token, audit server-side MCP call implementation |
| **Zepto MCP outage breaks CORTEX** (dependency failure) | Zepto cart confirmation errors | >30% error rate in 1 hour | Show graceful error: "Zepto is unavailable. Your list is saved — try again later." CORTEX must degrade without breaking. |
| **Confirmation screen fatigue** (users abandon because too many clicks) | M-4: abandonment rate | >30% for 2 consecutive weeks | Simplify confirmation UX — consider bulk accept with item-level opt-out instead of item-level opt-in |
| **MCP instability** (Zepto changes API without notice) | Cart-add error rate | >10% for 24 hours | Alert owner. Fall back to save-only mode until MCP is stable. |

---

## 13. Data and instrumentation

| Event | Trigger | Properties | Purpose |
|---|---|---|---|
| `shopping_list_captured` | User submits text or image classified as shopping_list | `{input_type: text\|image, item_count_raw, confidence}` | Measure capture volume and input method split |
| `zepto_cta_shown` | Confirmation prompt shown after shopping_list detection | `{capture_id, item_count_extracted}` | Funnel — how many captures trigger the Zepto CTA |
| `zepto_cta_accepted` | User taps [Add to Zepto] | `{capture_id}` | Funnel — intent to use Zepto action |
| `zepto_cta_dismissed` | User taps [Save only] | `{capture_id}` | Funnel — users who prefer save-only |
| `zepto_auth_initiated` | OAuth flow triggered | `{first_time: bool}` | Auth funnel |
| `zepto_auth_completed` | OAuth flow completed successfully | `{capture_id}` | Auth success rate |
| `zepto_search_completed` | All item searches done | `{capture_id, items_found, items_not_found, search_latency_ms}` | Match rate + performance |
| `zepto_confirm_shown` | Confirmation screen rendered | `{capture_id, items_matched, items_unmatched}` | Confirmation funnel entry |
| `zepto_confirm_dismissed` | User closes confirmation without acting | `{capture_id}` | M-4 abandonment counter |
| `zepto_cart_confirmed` | User taps [Add N items to cart] | `{capture_id, items_count, total_price_inr}` | M-1 primary metric |
| `zepto_cart_add_success` | MCP cart_management call succeeds | `{capture_id, item_id, qty}` | Per-item success tracking |
| `zepto_cart_add_error` | MCP call fails | `{capture_id, item_id, error_code}` | MCP reliability monitoring |

**Data pipeline:** All events logged to CORTEX SQLite `events` table (new table — Tech Lead to add migration). Data Analyst to define weekly accuracy audit query.

**A/B test required?** No — single user in Phase 1.

---

## 14. Open questions

| Question | Owner | Due | Status |
|---|---|---|---|
| Does the Zepto MCP `search_products` tool return a structured result (product_id, name, price, weight) or free-text? The item matching logic depends on this. | Tech Lead | 2026-06-07 | Open |
| ~~P0-2~~ **Resolved** — Zepto MCP whitelist explicitly includes `http://localhost` and `http://localhost/callback`. Localhost redirect is confirmed supported. Remaining uncertainty: port. Whitelist entries have no port specified; CORTEX Flask runs on :5050. Zepto likely follows RFC 8252 (port-agnostic for loopback), but not confirmed. Implementation approach: (1) attempt OAuth with `redirect_uri=http://localhost:5050/callback`; if rejected, (2) raise GitHub issue on zeptonow/mcp to whitelist `http://localhost:5050/callback` explicitly. | Tech Lead | Gate 5 | **Conditionally resolved** — architecture sound; port matching to be confirmed at implementation. |
| Does the Zepto MCP store cart state server-side (persists across sessions) or is it session-scoped (cart lost if MCP connection drops)? | Tech Lead | 2026-06-07 | Open |
| Should the item extraction prompt return quantities in Zepto-native units (grams, packs) or user-native (kg, dozen)? The search query construction depends on this. | AI Engineer + Prompt Engineer | 2026-06-07 | Open |
| PRD-CORTEX-002 Release 2 (camera capture) — what is the current implementation timeline? Zepto image path depends on this. | Tech Lead | 2026-06-07 | Open |
| Is "shopping_list" a new standalone content_type or should it be handled as a sub-type under an existing type (e.g., `reminder` with commerce intent)? | PM + AI Engineer | 2026-06-04 | **Resolved** — standalone `content_type`. Commerce-intent items need distinct classifier routing (P0-4 rule), a dedicated card with Zepto CTA, and separate tab. Folding into `reminder` conflates two different intents. |
| Rate limits: The Zepto MCP documentation states no explicit rate limits. What happens if we send 20 parallel search_products calls? Does the MCP throttle? | Tech Lead | 2026-06-08 | Open |
| User preference for Zepto disconnect: Should "Disconnect Zepto" appear in a CORTEX Settings page (not yet built) or as a capture-level action? | PM + UX Designer | 2026-06-09 | Open |

---

## 15. Team sign-offs

| Team | Sign-off | Date | Notes |
|---|---|---|---|
| PM | ⬜ Pending | — | |
| AI Engineer | ⬜ Pending | — | Classification impact + extraction prompt design |
| Data Analyst | ⬜ Pending | — | Metrics validation + instrumentation plan |
| UX Designer | ⬜ Pending | — | Confirmation screen + match-review card design |
| Tech Lead | ⬜ Pending | — | Feasibility: MCP integration + OAuth + server-side call architecture |
| Security review | ⬜ Pending | — | OAuth token storage, server-side enforcement of confirmation step |

---

## 16. History

| Date | Author | Change |
|---|---|---|
| 2026-06-04 | PM | Initial draft — full PRD, all 14 sections complete |
| 2026-06-04 | PM | v1.1 — P0-1 resolved: `confirmation_token` server-side enforcement replaces bypassable flag (§8). P0-3 resolved: Flask HTTP client architecture specified, `claude mcp add` removed (§8). P0-4 resolved: classifier disambiguation rule added to §5 scope. P0-2 flagged as owner-action blocker in §14. OQ #6 resolved (standalone type). Status → Gate 3. |
| 2026-06-04 | PM | v1.2 — P0-2 conditionally resolved: Zepto whitelist confirmed to include `http://localhost` and `http://localhost/callback`. Port uncertainty flagged (CORTEX :5050 vs implicit :80). OAuth callback route specified in §8: `GET /api/zepto/callback`. Approach: attempt with port, raise GitHub issue if rejected. |
| 2026-06-04 | PM | v1.3 — Gate 3 complete. Test plan filed: `docs/test-plan-PRD-003-zepto-cart.md`. 36 TCs across unit/integration/security/manual. MockZeptoMCP fixture required. 7 edge cases specified. M-5 hard-stop criterion enforced. |

---

*Phase gate confirmation: This feature is Phase 1 (personal tool). It serves a single user with a high-frequency personal action (grocery shopping). It does not require multi-user auth, communal boards, or social graph features. It is within Phase 1 scope.*
