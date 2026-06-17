# CORTEX — Platform Doctrine

> **One capture-to-recall engine, many surfaces.**
> CORTEX is not eight tabs and a classifier bolted together. It is a single **capture → classify → route → store** engine; the 8-tab feed today, and the Thinking Mirror / Social Graph / Org Memory phases later, are *surfaces* on the same engine and the same growing corpus. The engine is the loop; the corpus is the moat.

*Origin: abstracted from the "one engine, many surfaces" framing (DeciOps assignment), propagated as org pattern **P-20**, first applied to SmartFleet. CORTEX already embodies the loop; this names it.*

**Fit: strong.** CORTEX's "decision" is the **classification decision** — what is this capture, and where does it belong? The six primitives are present; two of them (`route`, `record`) already match org patterns P-15/P-17 and the corpus design.

---

## 1. The shared primitive

Every capture travels one loop:

> **Detect** a capture (paste/URL/image) → **Gather** enriched context (scrape, split, image-process) → **Resolve** into a content type + confidence (Corty) → **Route** by confidence → **Execute** by storing it in the right type/feed → **Record** in the corpus, then **calibrate** via accuracy.

A new content type doesn't change the loop — it's a new entry in the taxonomy. That's the platform payoff: capture stays zero-friction while the engine generalises.

---

## 2. The six primitives, mapped to CORTEX

| # | Primitive | What it answers | Realised in CORTEX |
|---|---|---|---|
| 1 | **Trigger** | What starts a decision? | A capture event in `app.py` (paste, URL, image, share) |
| 2 | **Context** | What does it need? | `scraper.py` (fetch URL content), `image_processor.py`, `splitter.py` (multi-item split) — the enrichment before classification |
| 3 | **Resolve** | What is it? | `classifier.py` — Corty's `_SYSTEM` prompt + keyword map + URL patterns → **content type + confidence**; `type_manager.py` owns the taxonomy |
| 4 | **Route** | Where does it go, at what bar? | `_compute_routing(confidence, suggested_new_type, explicit_type)` — `>0.80` assign · `0.20–0.80` → **unknown** (human re-tag surface) · `<0.20` + suggestion → new_type. Pure, unit-tested (org **P-17**); classification returns a decision, routing executes it (org **P-15**) |
| 5 | **Execute** | The action | Persist to the right type and surface it in the 8-tab feed (`db.py`) |
| 6 | **Record** | What's remembered? | `data/cortex.db` (SQLite WAL) — the **private corpus** *is* the ledger and the moat; classification accuracy is the calibration signal (Data Analyst's 2-week audit + low-confidence review) |

The human boundary is the **confidence gate**: high-confidence captures auto-file; the uncertain `0.20–0.80` band routes to the `unknown` tab for a human to confirm — the lighter-weight analog of SmartFleet's REVIEW tier and Marketpulse's red-team gate.

---

## 3. Surfaces are phases, not separate products

The phase ladder (`CLAUDE.md`) is the surface ladder on one engine + one corpus:

| Phase | Surface | Precondition (gate) |
|---|---|---|
| 1 (now) | Capture + classify + 8-tab feed | — |
| 2 | Thinking Mirror (attention patterns) | 500+ real captures |
| 3 | Private Social Graph | Phase 2 validated + multi-user |
| 4+ | Expertise / Org Memory | Phase 3 validated |

Every later surface reads the *same* corpus the capture loop fills. This is why the phase-gate is load-bearing: the surfaces only light up when the engine has fed the corpus enough.

---

## 4. Platform invariants (never waivable)

1. **Classification accuracy is the primary quality signal** — the engine is only as good as its resolve step; every change is judged against it.
2. **Phase-gate discipline** — never spec or build Phase N+1 before Phase N is validated; Phase 2+ ideas are Vision Notes, not PRDs. (The doctrine's "add a primitive only when it generalises," enforced by corpus depth.)
3. **Classification regression check** whenever `classifier.py` / `config.py` is touched; tests green before and after.
4. **Capture friction is sacred** — no surface may add friction to the trigger; the flywheel dies if capture gets heavier.

---

## 5. The discipline — handling the next request

| Bucket | Action | Example |
|---|---|---|
| **Configure** | fast | A new content type (taxonomy entry + keyword/URL pattern) |
| **Extend** | becomes engine muscle | A new capture modality (audio), a new enrichment in the gather step |
| **Add** a new surface | rare, gated | A new phase — only when the corpus precondition is met |

The test: *does this feed the one corpus through the one loop?* If yes, it's configuration or an enrichment node — never a parallel store.

## 6. The moat is the corpus

The corpus is the only place that holds every capture, its classification, its confidence, and (over time) the owner's attention patterns. It compounds: more captures → better accuracy → more trust → more captures. Phase 2 is literally unbuildable without a deep one. Build everything to fill it with high-quality, well-classified records — that is the capture flywheel in architectural form, and the reason capture friction is an invariant.

---

*See also: org pattern `product-staff/docs/learnings/POSITIVE-PATTERNS.md` P-20 (and P-15/P-17 which this engine already follows) · reference instance `Product Staff - Bytebeam/smartfleet/docs/PLATFORM-DOCTRINE.md`.*
