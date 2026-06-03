# PRD-CORTEX-002 — Camera Capture & Dynamic Collection Intelligence

**Product:** CORTEX  
**Version:** 2.1  
**Status:** Release 1 SHIPPED (2026-06-03) · Release 2 APPROVED for implementation  
**Owner:** Akash Raj

**Changelog:**
- v1.0 (2026-06-03): Initial draft — camera capture + collections as separate semantic layer
- v2.0 (2026-06-03): Collections redesigned — intent-based groups, unified with content_type taxonomy, dynamic growth. Camera is a new input channel feeding the same unified system.
- v2.1 (2026-06-03): Release 1 shipped (110/110 tests green, live on port 5050). Camera UX updated: single icon → two-option popup (Open Camera / Upload from Gallery). RANSAC architecture decision logged. Base64 JSON payload replaces multipart for `/api/capture/image`. Open questions §17 resolved.

---

## 1. Problem

Two related gaps:

**Gap 1 — Visual capture is impossible.** Product labels with expiry dates, event flyers, whiteboards, screenshots — all require manual transcription to enter CORTEX today. That friction kills the habit.

**Gap 2 — The taxonomy is closed.** Corty classifies into 8 fixed intent types. When a capture genuinely doesn't fit — a shopping list, a recipe, a travel idea — it lands in "unclassified," a dead end. The system has no way to learn that a new intent pattern is emerging.

Both gaps have the same root: the system doesn't grow with the user.

---

## 2. Goal

1. **Open the input channel** — add camera/image capture alongside the text path
2. **Open the taxonomy** — turn the 8 fixed types into a dynamic, growing set of intent-based groups (collections). New intent patterns get detected and named automatically. Ambiguous captures are staged, not lost.

A "collection" and an "intent type" are the same thing. The naming is interchangeable. What matters is the logic:
- **> 80% confidence** → assign to an existing type
- **20–80% confidence** → stage in Unknown (temporary holding)
- **< 20% confidence** → Corty understands the new intent and creates a new type directly

---

## 3. Users

Single user: Akash Raj. No auth, no multi-tenancy.

---

## 4. Feature scope — what's in vs. out

| Feature | In v1 | Out v1 | Notes |
|---|---|---|---|
| Camera capture (getUserMedia API) | ✅ | | In-browser camera |
| File upload fallback | ✅ | | For screenshots/saved images |
| EXIF-based image re-orientation | ✅ | | Fixes portrait/landscape from phone |
| LLM-based re-orientation (fallback) | ✅ | | For non-EXIF images |
| Image text extraction (OCR via Claude vision) | ✅ | | claude-opus-4-8 native — no Cloud Vision API |
| Intent classification of image content | ✅ | | Same unified taxonomy as text path |
| Structured data extraction (dates, names, prices) | ✅ | | Returned in metadata |
| Auto-reminder creation when date found | ✅ | | Creates a linked reminder capture |
| Dynamic taxonomy — new types auto-created at < 20% | ✅ | | Applies to text AND image captures |
| Unknown staging area (20–80%) | ✅ | | Applies to text AND image captures |
| Unknown auto-promotion when cluster forms | ✅ | | Corty scans Unknown on each new Unknown capture |
| Image storage | ✅ | | Filesystem `data/images/` |
| Multi-image capture (batch) | ❌ | P2 | One image at a time in v1 |
| Embedding-based similarity | ❌ | P2 | LLM comparison is sufficient at this scale |
| Image search | ❌ | P2 | |
| Video capture | ❌ | P3 | |

---

## 5. The unified classification model

The 8 existing types are the **seed set**. They are not the ceiling. The full classification logic for every capture — text or image — is:

```
Corty classifies the capture against all known types
    ↓
max_confidence = highest confidence score across all types

if max_confidence > 0.80:
    → Assign to that type (existing behavior, threshold raised from 0.70)

elif 0.20 ≤ max_confidence ≤ 0.80:
    → Assign content_type = 'unknown' (Unknown staging)
    → Run Unknown cluster check (see §7)

elif max_confidence < 0.20:
    → Corty infers the new intent from the content
    → Auto-names a new type (e.g., "shopping_list", "recipe", "travel_idea")
    → Registers it in content_types table
    → Assigns this capture to the new type
```

**Why raise the confident threshold from 0.70 to 0.80?**
The current 0.70 threshold was set when the taxonomy was fixed and "unclassified" was a dead end. Now that Unknown is an intelligent staging area, there's no cost to staging a 0.73-confidence capture — Corty will resolve it. Raising to 0.80 keeps the direct-assign path high-confidence only.

---

## 6. Core flow — image capture path

### 6a. Camera entry point — UI design

A single 📷 icon sits below the capture textarea. Clicking it reveals a two-option popup:

```
┌──────────────────────────────┐
│  📷  Open Camera             │
│  🖼️  Upload from Gallery     │
└──────────────────────────────┘
```

**Open Camera:** calls `getUserMedia({video: {facingMode: "environment"}})`. Opens a live camera stream with a Capture button. On phone: uses back camera. On laptop: webcam. User sees live preview → taps Capture → image frozen → confirm/retake → submit.

**Upload from Gallery:** triggers `<input type="file" accept="image/*">`. Standard OS file picker — Chrome-sandboxed access, no broad folder permissions. User selects one file → preview shown → submit.

Both paths converge at: image → canvas → base64 JPEG → `POST /api/capture/image`.

### 6b. Full pipeline

```
User triggers camera icon → selects Open Camera or Upload from Gallery
    ↓
Browser: capture/read image → Canvas.toDataURL('image/jpeg', 0.85) → base64 string
    ↓
POST /api/capture/image  {image: "<base64>", media_type: "image/jpeg", hint: "<optional>"}
    ↓
image_processor.py:
  → Decode base64 → Pillow Image
  → ImageOps.exif_transpose(img)  ← handles ~90% of phone captures
  → If no EXIF orientation tag: send thumbnail to Claude — "Is this upright? Reply: OK | ROTATE_90_CW | ROTATE_90_CCW | ROTATE_180"
  → Resize longest side to ≤ 1600px (bilinear)
  → Save as data/images/<UUID>.jpg
  → Return: image_path, base64_for_classification
    ↓
classifier.py — classify_image(base64, media_type, hint):
  → Send as Anthropic image content block to claude-opus-4-8
  → Single call extracts ALL of: description, OCR text, intent type, structured data, suggested_new_type
  → Run unified routing (§5): assign | unknown | new_type
    ↓
app.py — auto-reminder check:
  if structured_data.due_date is not null AND confidence ≥ 0.70:
    → db.insert_capture() with content_type='reminder', metadata.source_capture_id set
  elif structured_data.due_date not null AND confidence < 0.70:
    → Add 'extract_reminder' to card actions (user-triggered)
    ↓
Store image capture → return card to frontend
```

### 6c. Rejected formats

HEIC/HEIF: rejected at upload with user message "Please convert to JPG or PNG before uploading." No `pillow-heif` dependency added — HEIC is Apple-proprietary and adds ~15MB of build weight for a rare edge case.

---

## 7. The Unknown staging area

Unknown is not a bucket. It is a temporary state with two resolution paths.

### Resolution path A — Manual assignment
The user sees Unknown captures in a dedicated "Unknown" tab (or indicator). They can assign any Unknown capture to an existing type, or name a new type for it. Once assigned, the capture moves out of Unknown.

### Resolution path B — Auto-promotion
After every new Unknown capture is added, Corty scans all current Unknown captures for clusters:

```
Fetch all captures where content_type = 'unknown'
Send to Claude:
  "Here are N unclassified captures. Group any that share the same intent
  (what the user would DO with them). For each group of 3+, suggest a
  new intent type: a key (snake_case) and a label (Title Case).
  Return groups that do NOT suggest a new type as 'keep in Unknown'."

If Claude returns any groups with 3+ captures:
  → Create the new type in content_types table
  → Assign all grouped captures to the new type
  → Remaining: stay in Unknown
```

**Cluster threshold: 3 captures.** Below 3, not enough signal to name a type reliably.

**When does this run?** After every new Unknown capture is added. At 38 total captures, this is cheap. Revisit with a daily batch job at 500+ captures.

---

## 8. Dynamic type registry

New types created by Corty (either from < 20% direct creation or from Unknown cluster promotion) are stored in a `content_types` table:

```sql
CREATE TABLE content_types (
  key         TEXT PRIMARY KEY,          -- e.g., 'shopping_list'
  label       TEXT NOT NULL,             -- e.g., 'Shopping List'
  icon        TEXT NOT NULL DEFAULT '📌', -- default icon; user can change
  description TEXT,                       -- used in Corty's classification prompt
  is_seed     INTEGER NOT NULL DEFAULT 0, -- 1 = original 8 types, 0 = dynamic
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

The 8 seed types are pre-populated with `is_seed = 1`. Dynamic types have `is_seed = 0`.

**Corty's classification prompt** includes the full list of all known types (seed + dynamic) with their descriptions. As the taxonomy grows, the prompt grows. At large type counts (50+), this will need pruning — defer to Phase 2.

**UI:** Dynamic types get their own tab in the feed automatically when they have ≥ 1 active capture. Tabs with no active captures are hidden (not deleted).

---

## 9. Auto-reminder extraction

When `structured_data.due_date` is not null in the image extraction:

1. If extraction confidence ≥ 0.7: auto-create a linked reminder capture
   - `content_type = reminder`
   - `metadata.task = "[image description] — extracted from image"`
   - `metadata.due_date = extracted date`
   - `metadata.source_capture_id = <original image capture id>`
2. If extraction confidence < 0.7: show "Extract reminder?" action button on the image card

The original image capture stores `metadata.linked_reminder_id` pointing to the created reminder.

---

## 10. Image storage

**Location:** `data/images/<UUID>.jpg`  
**Why filesystem:** SQLite BLOBs degrade query performance at scale. Standard: reference path in DB.  
**Size limit:** 10MB max upload. Resized to ≤1600px on ingest.  
**Format:** JPEG for storage regardless of input format.  
**Retention:** Images persist as long as the capture is not deleted (archive ≠ delete).  
**Gitignore:** `data/images/` must be added to `.gitignore`.

---

## 11. Classification metadata schema — image path

When a capture arrives via the image path, `metadata` carries:

```json
{
  "description": "what this image shows",
  "extracted_text": "all visible text from the image",
  "image_path": "data/images/<UUID>.jpg",
  "structured_data": {
    "due_date": "2026-07-15",
    "due_time": null,
    "price": "₹245",
    "names": ["Amul Butter"],
    "location": null
  },
  "linked_reminder_id": 47,
  "input_type": "image"
}
```

Text captures continue to use their existing metadata schemas (unchanged).

---

## 12. Technical spec changes

### 12a. Release 1 — SHIPPED (2026-06-03)

| Change | Status |
|---|---|
| `GET /api/types` — list all types (seed + dynamic) | ✅ Live |
| `POST /api/unknown/resolve` — manually assign Unknown capture | ✅ Live |
| `classifier.py` — `_compute_routing()`, confidence thresholds 0.80/0.20 | ✅ Live |
| `app.py` — routing in `_process_one()`, cluster trigger, new endpoints | ✅ Live |
| `db.py` — `content_types` table, `was_unknown` column, `get_all_types()` cache | ✅ Live |
| `config.py` — `CONTENT_TYPES` removed, `HIGH_CONFIDENCE`/`LOW_CONFIDENCE` | ✅ Live |
| `templates/index.html` — Unsorted tab (amber), type picker on Unknown cards, dynamic tabs | ✅ Live |
| `type_manager.py` — `cluster_unknown()`, `should_cluster()` | ✅ Live |

### 12b. Release 2 — TO BUILD

| Change | Detail |
|---|---|
| New endpoint | `POST /api/capture/image` — JSON body `{image, media_type, hint}` (base64, not multipart) |
| New endpoint | `PATCH /api/types/<key>` — user renames a dynamic type's label/icon |
| New file | `image_processor.py` — base64 decode, EXIF rotation, LLM fallback rotation, resize ≤1600px, JPEG save |
| Modified | `classifier.py` — add `classify_image(base64, media_type, hint, explicit_type)` |
| Modified | `app.py` — `POST /api/capture/image` route with auto-reminder logic |
| Modified | `db.py` — add `image_path TEXT` and `input_type TEXT DEFAULT 'text'` columns |
| Modified | `templates/index.html` — camera icon + two-option popup, stream UI, preview, file picker |

**New columns on `captures` (Release 2 migration):**

```sql
ALTER TABLE captures ADD COLUMN image_path TEXT;                -- null for text captures
ALTER TABLE captures ADD COLUMN input_type TEXT DEFAULT 'text'; -- 'text' | 'image'
```

**Payload format — image endpoint:**
```json
POST /api/capture/image
{
  "image": "<base64-encoded JPEG>",
  "media_type": "image/jpeg",
  "hint": "optional topic hint"
}
```
Rationale for base64 JSON over multipart: both camera (Canvas.toDataURL) and file picker (FileReader.readAsDataURL) naturally produce base64. Avoids Flask multipart parsing; consistent on both paths.

### 12c. Architecture Decision Record — Image Re-orientation

**Decision: EXIF transpose → LLM fallback. RANSAC not used.**

RANSAC (Random Sample Consensus) was evaluated and rejected for this use case:

1. **Wrong problem class.** RANSAC is a robust fitting algorithm for problems with feature correspondences between two or more views (panorama stitching, camera pose estimation, homography from matching keypoints). Single-image orientation has no reference image to match against — RANSAC has nothing to fit.

2. **What RANSAC-adjacent methods would actually require.** Feature-based orientation (detect dominant line/edge directions, vote for rotation) requires OpenCV (~50MB dependency), SIFT/ORB keypoint detection, and heuristic line-voting logic. It fails on textureless images, crumpled receipts, angled documents — exactly the captures CORTEX handles.

3. **EXIF already solves the common case.** Phone cameras embed orientation in EXIF tag 274. `PIL.ImageOps.exif_transpose()` reads this and corrects automatically. Coverage: ~90% of real captures.

4. **LLM beats feature-based for the remainder.** For the ~10% without EXIF (screenshots, old files, certain cameras): a vision model understands scene geometry semantically — "text should be readable," "horizon should be horizontal," "faces should be upright." A feature-based heuristic would need hand-tuned rules for the same understanding.

5. **Dependency budget.** Pillow is already in requirements.txt. No new dependencies needed. OpenCV would be a significant addition for marginal gain.

---

## 13. Phase gate assessment

**Verdict: APPROVED for Phase 1**

Both capabilities serve Phase 1 directly:
- Camera capture removes a class of friction that suppresses capture rate (the Phase 1 north star metric)
- Dynamic taxonomy eliminates the "unclassified" dead end — every capture now has a resolution path, which reduces the cognitive cost of capturing ambiguous things

Neither requires the Thinking Mirror infrastructure (Phase 2). Neither requires 500+ captures to be useful.

**Risk flag — threshold change:** Raising the confident-assign threshold from 0.70 to 0.80 will increase Unknown captures in the short term (captures that previously auto-classified at 0.72 will now stage). This is by design — 0.72-confidence classifications were frequently wrong. The Unknown tab needs to be visible and easy to action from day one.

---

## 14. Implementation plan — Tech Lead

**Shipping decision (2026-06-03):** Ship in two independent releases. Validate the classification model on the live text corpus before adding the image pipeline.

---

### Release 1 — Dynamic Taxonomy ✅ SHIPPED (2026-06-03)

**Result:** 110/110 tests green. Live at port 5050. DB migrated. 38 captures intact.

All Release 1 tests passed:
- Confidence routing: >0.80 assign, 0.20–0.80 unknown, <0.20 new type ✅
- `create_type()` idempotent ✅
- `resolve_unknown()` sets was_unknown=1 ✅
- GET /api/types, POST /api/unknown/resolve live ✅
- Unsorted tab (amber) with assign action ✅
- All 81 existing tests still passing ✅

---

### Release 2 — Camera Capture & Image Intelligence

**Complexity: T3** (image pipeline only — taxonomy system already live from Release 1)  
**Prerequisite:** Release 1 shipped and stable ✅

**Phase A — Image ingestion + UI (no AI classification yet)**
1. Add `data/images/` to `.gitignore`
2. Create `image_processor.py`:
   - `process_image(base64_str, media_type)` → decode → EXIF transpose → resize ≤1600px → save JPEG → return (image_path, base64_for_classification)
   - Rejects HEIC with user-friendly error
3. DB migration in `db.py`: add `image_path TEXT` and `input_type TEXT DEFAULT 'text'` to captures (migration-safe ALTER TABLE)
4. Add `POST /api/capture/image` route (base64 JSON body): image_processor → store capture (content_type='unknown', image_path set) → return card
5. UI: camera icon below textarea → two-option popup → Open Camera (getUserMedia stream) / Upload from Gallery (file input) → preview → submit

**Phase B — Vision classification**
6. Add `classify_image(base64, media_type, hint, explicit_type)` to `classifier.py`:
   - Build Anthropic image content block: `{"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}`
   - Prompt extracts: description, all OCR text, intent type, structured_data (dates, amounts, names), suggested_new_type
   - Same `_compute_routing()` function as text path — no new logic
7. Wire into `POST /api/capture/image`: full vision classification replaces the 'unknown' stub from Phase A
8. LLM orientation fallback: if `exif_transpose` made no change AND image has no readable EXIF, send downscaled version with prompt "Reply: OK | ROTATE_90_CW | ROTATE_90_CCW | ROTATE_180"

**Phase C — Auto-reminders from images**
9. In `app.py` image handler: check `result.get("auto_reminder")`
10. If `auto_reminder.create == true` AND `auto_reminder.confidence ≥ 0.70`: call `db.insert_capture()` for linked reminder with `metadata.source_capture_id`
11. If date detected but confidence < 0.70: add `"extract_reminder"` to card actions (surfaces button on card, user-triggered)

**Release 2 test plan:**
- Unit: `image_processor.py` — EXIF rotation detected and applied, resize respects ≤1600px longest side, JPEG output confirmed, HEIC rejected with correct error message
- Unit: `_compute_routing()` — unchanged, same thresholds work for image path (already tested in Release 1)
- Unit: `classify_image()` — mock Anthropic client, verify image content block structure is correct, verify `suggested_new_type` handling
- Integration: base64 JPEG → `POST /api/capture/image` → image stored in `data/images/`, capture in DB with `input_type='image'`
- Integration: image with extracted date + confidence ≥ 0.70 → linked reminder created in same request
- Integration: image with extracted date + confidence < 0.70 → `extract_reminder` action on card, no auto-reminder
- Regression: all 110 Release 1 tests still green

---

## 15. Success metrics (4-week check)

| Metric | Target | How to measure |
|---|---|---|
| Image captures / week | ≥ 5 | `SELECT COUNT(*) FROM captures WHERE input_type = 'image'` |
| Unknown resolution rate | ≥ 70% resolved within 7 days | Manual or `SELECT COUNT(*) WHERE content_type='unknown' AND created_at < NOW()-7d` |
| Dynamic types created | ≥ 1 (signal the system is learning) | `SELECT COUNT(*) FROM content_types WHERE is_seed=0` |
| Auto-reminder accuracy | ≥ 80% correct date when date visible | Manual spot-check |
| Image classification accuracy | ≥ 70% correct intent | Manual spot-check of 10 image captures |
| Regression: text classification | Unclassified rate ≤ current baseline | `SELECT COUNT(*) WHERE content_type='unknown' AND input_type='text'` |

---

## 16. Out of scope (v1)

| Feature | Backlog |
|---|---|
| Embedding-based type matching | P2 — LLM comparison sufficient at current scale |
| Type merging (user combines two similar types) | P2 |
| Type deletion (with re-assign) | P2 |
| Multi-image batch capture | P2 |
| Image search by extracted content | P2 |
| User-initiated type creation (before Corty auto-creates) | P2 |
| Type count limits / taxonomy pruning | P3 — needed at 50+ types |
| Video capture | P3 |

---

## 17. Open questions — resolved

1. **Unknown tab placement:** ✅ RESOLVED (Release 1) — Dedicated "? Unsorted" tab with amber badge. Actionable from day one.

2. **New type icon assignment:** ✅ RESOLVED — Corty suggests icon in `suggested_new_type.icon` field. Default fallback `?` if not supplied. User can rename via `PATCH /api/types/<key>` (to be built in Release 2).

3. **Threshold tuning:** Open — calibrate empirically after 2 weeks of production use. If Unknown rate > 30%, lower to HIGH=0.75. If Unknown rate < 5%, raise to HIGH=0.85.

4. **Text path first:** ✅ RESOLVED — Release 1 shipped text path standalone. Release 2 now proceeding.

5. **Multipart vs. base64:** ✅ RESOLVED — base64 JSON for `POST /api/capture/image`. Both camera (Canvas.toDataURL) and file picker (FileReader.readAsDataURL) natively produce base64. Simpler Flask handler, no multipart parsing.
