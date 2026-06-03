# Gate 8 Retrospective — CORTEX Release 1: Dynamic Taxonomy

**Feature:** Dynamic Taxonomy — `content_types` table, Unknown staging, three-routing classifier, Unsorted tab  
**PRD:** PRD-CORTEX-002 v2.1, Release 1  
**Shipped:** 2026-06-03  
**Test result:** 110/110 passing (81 existing + 29 new)  
**Data loss:** Zero. 38 captures migrated cleanly.

---

## What was built

- `content_types` DB table replacing hardcoded `config.CONTENT_TYPES`
- `was_unknown` column on captures for resolution rate tracking
- Three-routing classifier output: `assign | unknown | new_type`
- `_compute_routing()` — pure function, fully testable without mocking Claude
- Module-level types cache with dirty-flag invalidation (`_invalidate_types_cache()`)
- `cluster_unknown()` — async auto-promotion when ≥3 Unknown captures share best_guess
- `GET /api/types`, `POST /api/unknown/resolve` endpoints live
- Unsorted tab (amber) with inline type picker
- Dynamic new-type tabs auto-appear when Corty creates a type

---

## What worked well

### 1. Separating the routing decision from its side effects
The initial implementation placed `db.create_type()` inside `classifier.classify()`. When `classify()` was mocked in tests, the side effect (type creation) never ran — the test for `new_type` routing failed even though the logic was correct. Fixing this by moving `create_type()` to `_process_one()` (the orchestration layer in `app.py`) resolved the failure and clarified the architecture: **classify returns a decision; the orchestration layer executes its consequences.**

This is a strong reusable principle. See back-propagation: elevate to POSITIVE-PATTERNS.md.

### 2. Pure routing function for testability
`_compute_routing(confidence, suggested_new_type, explicit_type)` takes no I/O — no DB calls, no Claude calls. It's a 12-line function that can be unit-tested directly. All threshold logic lives here. Nine tests cover it: boundary conditions, explicit_type override, no-suggestion fallback. This pattern should be applied whenever a classifier or scorer has branching logic — extract the branching into a pure function and test it directly.

### 3. Migration-safe ALTER TABLE
The `was_unknown` column was added to the live 38-capture DB with zero downtime. Pattern:
```python
existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(captures)").fetchall()]
if "was_unknown" not in existing_cols:
    conn.execute("ALTER TABLE captures ADD COLUMN was_unknown INTEGER NOT NULL DEFAULT 0")
```
Same pattern was used for `was_unknown` and will be reused for `image_path` and `input_type` in Release 2. Zero risk of data loss; idempotent on re-run.

### 4. Module-level cache with init invalidation
`_types_cache = None` at module level, invalidated both in `init_db()` (so test setUp clears it) and in `create_type()` (so dynamic types appear immediately). Every card render calls `get_all_types()` — without the cache this would be 37 DB queries per feed load. Cache makes it zero queries after first load. Dirty-flag pattern is O(1) invalidation and fully thread-safe for the single-writer Flask dev server.

### 5. Backward-compatible mock default
`result.get("routing", "assign")` in `_process_one()` means all 81 existing mocked tests continue to pass unchanged — they return no `routing` field, which defaults to `"assign"`. Zero test rewrites needed for the existing suite.

---

## What caused friction

### 1. Side effect inside the classifier (caught before ship)
The `create_type()` call inside `classify()` was the single failing test (109/110 on first run). Root cause: mixing classification logic with DB side effects inside a function that's mocked in tests. Caught and fixed before ship, but the diagnostic took one iteration. Anti-pattern worth logging.

### 2. conftest.py drops only `captures`, not `content_types`
Existing `test_db.py` setUp does `DROP TABLE IF EXISTS captures` but not `content_types`. This meant the content_types table persisted across test methods. New tests in `test_dynamic_taxonomy.py` needed explicit `DROP TABLE IF EXISTS content_types` in setUp to get a clean slate. Minor, but the pattern of "partial teardown" in setUp creates subtle isolation bugs — worth noting for future schema additions.

---

## Metrics baseline (pre-Release 1, for calibration)

| Metric | Value |
|---|---|
| Total captures | 38 |
| Migrated unclassified → unknown | 0 (live corpus was already clean) |
| Content types in DB | 11 (8 seeds + unknown + 2 legacy) |
| Dynamic types created (day 0) | 0 (expected — no captures yet post-ship) |
| Unknown rate (day 0) | 0% (no captures post-ship yet) |
| Test suite | 110/110 |

---

## Learnings to back-propagate to org catalogue

1. **P-new: Classification functions return decisions; orchestration functions execute consequences.** (from §What worked well #1)
2. **P-new: Pure routing functions for all branching classifier logic.** (from §What worked well #2)
3. **P-new: Migration-safe ALTER TABLE with PRAGMA column check.** (from §What worked well #3)
4. **AP-new: DB side effects inside classification functions break mock-based testing.** (from §What caused friction #1)

---

## Release 2 dependencies confirmed

- `data/images/` directory: ✅ created by `init_db()` in Release 1
- `_compute_routing()`: ✅ reusable on image path unchanged
- `get_all_types()` cache: ✅ will serve image path type lookup
- `resolve_unknown()`: ✅ available for image captures that land in Unknown
- DB migration pattern: ✅ same pattern for `image_path` and `input_type` columns
