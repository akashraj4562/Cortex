# Test Plan — CORTEX Release 2: Camera Capture

**PRD:** PRD-CORTEX-002 v2.1, Release 2  
**Gate:** 3 (written before implementation begins — SOP requirement)  
**Authored:** 2026-06-03

---

## 1. Scope

| Area | Covered |
|---|---|
| `image_processor.py` — decode, orient, resize, save | ✅ |
| `classifier.classify_image()` — Anthropic image content block | ✅ |
| `POST /api/capture/image` endpoint | ✅ |
| DB migration — `image_path`, `input_type` columns | ✅ |
| Auto-reminder creation (date + confidence ≥ 0.70) | ✅ |
| Auto-reminder suppression + action button (date + confidence < 0.70) | ✅ |
| HEIC rejection | ✅ |
| Routing: assign / unknown / new_type via image path | ✅ |
| Regression: all 110 Release 1 tests | ✅ |

---

## 2. Test file layout

```
tests/
  test_image_processor.py    # new — image_processor.py unit tests
  test_classify_image.py     # new — classify_image() unit tests
  test_image_api.py          # new — /api/capture/image integration tests
  (all existing tests unchanged — regression)
```

---

## 3. Unit tests — `image_processor.py` (`TestImageProcessor`)

### 3.1 EXIF transpose applied

**Scenario:** Base64-encode a 100×50 JPEG (wider than tall). Embed an EXIF Orientation tag = 6 (90° CW rotation). Call `process_image(base64_str, "image/jpeg")`. The returned image must have height > width (portrait — correctly transposed).

**Assert:**
- Returned `image_path` exists on filesystem
- File is a valid JPEG
- Image dimensions are portrait (height > width)

### 3.2 No-EXIF image — no orientation call made

**Scenario:** Base64-encode a plain JPEG with no EXIF data. Patch the LLM orientation call. Call `process_image()`. Assert the LLM fallback is NOT called (EXIF transpose alone ran, no EXIF tag = already upright).

**Assert:**
- LLM orientation patch not called
- File saved successfully
- Dimensions unchanged from input

### 3.3 LLM fallback orientation — ROTATE_90_CW

**Scenario:** Base64-encode a 100×50 JPEG with no EXIF. Patch the LLM orientation check to return `"ROTATE_90_CW"`. Call `process_image()`.

**Assert:**
- File saved as portrait (transposed)
- LLM patch called exactly once

### 3.4 LLM fallback orientation — OK (no rotation)

**Scenario:** Same as 3.3 but LLM returns `"OK"`.

**Assert:**
- File dimensions unchanged
- File saved successfully

### 3.5 Resize — longest side clamped to ≤ 1600px

**Scenario:** Create a 3200×2400 pixel synthetic JPEG. Call `process_image()`.

**Assert:**
- Saved image longest side ≤ 1600px
- Aspect ratio preserved (within 1px tolerance)

### 3.6 No resize needed — small image unchanged

**Scenario:** 800×600 JPEG input. Call `process_image()`.

**Assert:**
- Saved image is 800×600 (unchanged)

### 3.7 HEIC rejected

**Scenario:** Call `process_image(base64_str, "image/heic")`.

**Assert:**
- Raises `ValueError` with message containing "JPG or PNG"
- No file written to `data/images/`

### 3.8 PNG input — saved as JPEG

**Scenario:** Base64-encode a small PNG. Call `process_image(base64_str, "image/png")`.

**Assert:**
- `image_path` ends with `.jpg`
- File is a valid JPEG

### 3.9 Image path format — UUID filename in `data/images/`

**Scenario:** Call `process_image()` with a valid JPEG.

**Assert:**
- Returned `image_path` matches `data/images/<UUID>.jpg` (UUID regex)
- File exists at that path

---

## 4. Unit tests — `classifier.classify_image()` (`TestClassifyImage`)

### 4.1 Image content block format — sent correctly to Anthropic

**Scenario:** Patch `anthropic.Anthropic().messages.create`. Call `classify_image(base64="...", media_type="image/jpeg", hint="")`. Inspect the call args.

**Assert:**
- `messages[0]["content"]` is a list
- First element has `"type": "image"` and `"source.media_type": "image/jpeg"`
- Second element has `"type": "text"` (the classification prompt)
- Model is `"claude-opus-4-8"`

### 4.2 Successful extraction — full field parse

**Scenario:** Mock Anthropic to return a valid JSON response with all fields populated:
```json
{
  "type": "reminder",
  "confidence": 0.91,
  "description": "Dentist appointment card",
  "extracted_text": "Dr. Mehta — July 15, 2026 at 3pm",
  "structured_data": {"due_date": "2026-07-15", "due_time": "15:00"},
  "suggested_new_type": null,
  "auto_reminder": {"create": true}
}
```

**Assert:**
- `result["type"] == "reminder"`
- `result["confidence"] == 0.91`
- `result["routing"] == "assign"`
- `result["metadata"]["description"] == "Dentist appointment card"`
- `result["metadata"]["extracted_text"] == "Dr. Mehta — July 15, 2026 at 3pm"`
- `result["metadata"]["structured_data"]["due_date"] == "2026-07-15"`

### 4.3 Routing — assign at high confidence

**Scenario:** Mock returns confidence = 0.85 with known type.

**Assert:** `result["routing"] == "assign"`

### 4.4 Routing — unknown at mid confidence

**Scenario:** Mock returns confidence = 0.55.

**Assert:**
- `result["routing"] == "unknown"`
- `result["type"] == "unknown"`

### 4.5 Routing — new_type at low confidence with suggestion

**Scenario:** Mock returns confidence = 0.12 with `suggested_new_type = {"key": "receipt", "label": "Receipt", "description": "..."}`.

**Assert:**
- `result["routing"] == "new_type"`
- `result["suggested_new_type"]["key"] == "receipt"`

### 4.6 max_tokens — at least 1200

**Scenario:** Patch Anthropic. Call `classify_image()`. Inspect call args.

**Assert:** `max_tokens >= 1200` (image responses are more verbose than text — per AP-14 flag in propagation log)

### 4.7 Hint injected into prompt text

**Scenario:** Call `classify_image(base64="...", media_type="image/jpeg", hint="shopping list")`.

**Assert:** The text content block in the Anthropic call contains "shopping list".

### 4.8 No-hint path — prompt still valid

**Scenario:** Call with empty hint.

**Assert:** Anthropic call is made without error. Text prompt does not contain an empty "hint:" field (should be omitted or marked "none").

---

## 5. Integration tests — `POST /api/capture/image` (`TestImageCaptureAPI`)

All integration tests use a real (test) DB and patch `classifier.classify_image` to avoid actual Anthropic calls.

### 5.1 Happy path — image capture stored

**Scenario:** POST valid base64 JPEG with mocked classify returning assign/reminder/0.91.

**Assert:**
- HTTP 200
- Response JSON has `card.type == "reminder"`
- DB has one capture with `input_type = "image"`
- `image_path` column is non-null and file exists on disk

### 5.2 DB migration — `image_path` and `input_type` columns present

**Scenario:** After `db.init_db()` in test setUp, inspect `PRAGMA table_info(captures)`.

**Assert:**
- Column `image_path TEXT` exists (nullable)
- Column `input_type TEXT` exists with `DEFAULT 'text'`

### 5.3 Existing text captures unaffected by migration

**Scenario:** After DB migration, fetch text captures inserted before migration.

**Assert:**
- `input_type == "text"` (or null, coerced to text)
- `image_path` is null
- All existing card fields intact

### 5.4 Auto-reminder created — date extracted + confidence ≥ 0.70

**Scenario:** POST image. Mock classify returns:
```json
{"type": "reminder", "confidence": 0.85, "routing": "assign",
 "metadata": {"structured_data": {"due_date": "2026-07-15"}}}
```

**Assert:**
- DB has 2 new captures (image capture + linked reminder)
- Reminder capture has `content_type == "reminder"`
- Reminder capture metadata has `source_capture_id` pointing to image capture
- Image capture metadata has `linked_reminder_id` set

### 5.5 Auto-reminder suppressed — date extracted + confidence < 0.70

**Scenario:** POST image. Mock classify returns confidence = 0.65, due_date present.

**Assert:**
- DB has 1 new capture (image capture only)
- Image capture card actions include `"extract_reminder"`
- No second capture in DB

### 5.6 No reminder — no date in structured_data

**Scenario:** POST image. Mock classify returns no `due_date` in structured_data.

**Assert:**
- DB has 1 capture
- Card actions do NOT include `"extract_reminder"`

### 5.7 Unknown routing via image path

**Scenario:** Mock classify returns `routing="unknown"`, confidence=0.55.

**Assert:**
- Capture stored with `content_type == "unknown"`
- `was_unknown == 1`

### 5.8 new_type routing via image path

**Scenario:** Mock classify returns `routing="new_type"`, `suggested_new_type={"key": "receipt", "label": "Receipt", "description": "..."}`.

**Assert:**
- `"receipt"` appears in `db.get_all_types()`
- Capture stored with `content_type == "receipt"`

### 5.9 HEIC rejected at API boundary

**Scenario:** POST `{"image": "<base64>", "media_type": "image/heic"}`.

**Assert:**
- HTTP 400
- Response JSON has `error` containing "JPG or PNG"
- No file written to `data/images/`
- No capture in DB

### 5.10 Missing `image` field

**Scenario:** POST `{"media_type": "image/jpeg"}` (no image field).

**Assert:** HTTP 400 with error message.

### 5.11 Malformed base64

**Scenario:** POST `{"image": "not_valid_base64!!!", "media_type": "image/jpeg"}`.

**Assert:** HTTP 400. No file written.

---

## 6. Regression check

Run `python -m pytest tests/ -v` after all Phase A implementation. All 110 existing tests must remain green before proceeding to Phase B.

---

## 7. Phase B additions (written before Phase B, not now)

- `classify_image()` wired to real POST endpoint
- LLM orientation fallback integration test
- Phase A stub replaced with real classification

---

## 8. Acceptance criteria — Release 2 ships when

- All new tests pass (target: 110 + ~30 new = ~140 total)
- Zero existing tests broken
- Manual browser check: camera popup appears, gallery upload → card appears in feed with image
- Manual check: phone camera → EXIF orientation correct on desk photo
- `data/images/` confirmed absent from git (`git status`)
