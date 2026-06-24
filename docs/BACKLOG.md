# CORTEX Backlog

> Prioritized feature and improvement backlog. P0 = blocking / P1 = high value / P2 = nice to have.
> Phase gate: Phase 2 items require 500+ real captures in corpus before building.

---

## P0 — Build next (specs ready)

| ID | Item | Spec | Phase | Status |
|---|---|---|---|---|
| BL-002 | Zepto **credit-card checkout** — pay & place the order from inside CORTEX | `PRD-CORTEX-005` + `TECH-CORTEX-005` | Phase 1 | Spec'd, Gate-2 review complete. **Blocker for live test:** Zepto OAuth token expired (health check 2026-06-24) — re-auth via `/api/zepto/init` before end-to-end test. Build can start against mocked MCP. |
| BL-003 | **Hindi / multilingual image understanding** — Corty reads Devanagari in uploaded images and normalizes to usable English metadata | `PRD-CORTEX-006` + `TECH-CORTEX-006` | Phase 1 | Spec'd, Gate-2 review complete. Touches `classifier.py` (`_IMAGE_SYSTEM`) → classification regression protocol required. |

---

## P1 — High value, build next

| ID | Item | Description | Phase |
|---|---|---|---|
| BL-001 | Neo4j similar-captures graph | Use Neo4j graph DB to power a "Similar Captures" feature — show captures semantically related to the one currently open. Requires embedding each capture on save (via Haiku) and storing in Neo4j with relationship edges. Enables: "you've saved 3 things about MU/semiconductors — see them all." | Phase 2 — **GATED**: corpus at **74/500** captures (2026-06-24). Do not build until ≥500. |

---

## P2 — Nice to have

| ID | Item | Description | Phase |
|---|---|---|---|
| — | — | — | — |

---

## Done / shipped

| ID | Item | Shipped |
|---|---|---|
| — | Zepto Cart (PRD-003) | 2026-06-04 |
| — | Address selector | 2026-06-05 |
| — | View Cart + qty controls | 2026-06-05 |
| — | Similarity-scoring classifier | 2026-06-05 |
| — | Auto-add to cart (shopping_list capture → Haiku picks best past-ordered item → cart) | 2026-06-05 |
| — | Sticky capture UI (static top, scrollable feed) | 2026-06-05 |
| — | Archived section (auto-archive on cart-add, See Archived Only toggle) | 2026-06-05 |

---
*Update at end of each session. Phase 2 items only move to P0/P1 after Phase 1 corpus threshold is met.*
