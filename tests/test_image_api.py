"""Integration tests for POST /api/capture/image — Phase A."""
import base64
import io
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
import db
from PIL import Image


def _make_jpeg_b64(width=80, height=80) -> str:
    img = Image.new("RGB", (width, height), (120, 140, 160))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def _mock_classify_result(content_type="reminder", confidence=0.91, routing="assign",
                           description="Test image", due_date=None,
                           routing_override=None, suggested_new_type=None):
    structured = {}
    if due_date:
        structured["due_date"] = due_date
    meta = {
        "description": description,
        "extracted_text": "some text",
        "structured_data": structured,
    }
    return {
        "type": "unknown" if (routing_override or routing) == "unknown" else content_type,
        "confidence": confidence,
        "routing": routing_override or routing,
        "rationale": "test classification",
        "metadata": meta,
        "tags": ["test"],
        "suggested_new_type": suggested_new_type,
        "best_guess": content_type if (routing_override or routing) == "unknown" else None,
    }


class TestImageCaptureAPI(unittest.TestCase):

    def setUp(self):
        import app as flask_app
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()

        # Reset DB
        import db
        with db.get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS captures")
            conn.execute("DROP TABLE IF EXISTS content_types")
        db._invalidate_types_cache()
        db.init_db()

    # ── 5.1 Happy path ──────────────────────────────────────────────────────

    @patch("image_processor._llm_orientation_check", return_value="OK")
    @patch("classifier.classify_image")
    def test_happy_path_image_stored(self, mock_classify, mock_orient):
        mock_classify.return_value = _mock_classify_result("reminder", 0.91, "assign")

        res = self.client.post("/api/capture/image", json={
            "image": _make_jpeg_b64(),
            "media_type": "image/jpeg",
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["type"], "reminder")

        with db.get_conn() as conn:
            row = conn.execute("SELECT * FROM captures WHERE id=?", (data["id"],)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["input_type"], "image")
        self.assertIsNotNone(row["image_path"])
        self.assertTrue(os.path.exists(row["image_path"]))

    # ── 5.2 DB migration columns ─────────────────────────────────────────────

    def test_db_migration_columns_present(self):
        with db.get_conn() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(captures)").fetchall()]
        self.assertIn("image_path", cols)
        self.assertIn("input_type", cols)

    # ── 5.3 Existing text captures unaffected ───────────────────────────────

    def test_existing_text_captures_unaffected(self):
        cap_id = db.insert_capture(
            raw_input="text capture",
            content_type="general_note",
            confidence=0.90,
            rationale="test",
            metadata={"title": "Test Note"},
            tags=[],
        )
        with db.get_conn() as conn:
            row = conn.execute("SELECT * FROM captures WHERE id=?", (cap_id,)).fetchone()
        self.assertIn(row["input_type"], ("text", None, ""))
        self.assertIsNone(row["image_path"])

    # ── 5.4 Auto-reminder created when confidence ≥ 0.70 + due_date ─────────

    @patch("image_processor._llm_orientation_check", return_value="OK")
    @patch("classifier.classify_image")
    def test_auto_reminder_created_high_confidence(self, mock_classify, mock_orient):
        mock_classify.return_value = _mock_classify_result(
            "reminder", 0.85, "assign", due_date="2026-07-15"
        )

        res = self.client.post("/api/capture/image", json={
            "image": _make_jpeg_b64(),
            "media_type": "image/jpeg",
        })
        self.assertEqual(res.status_code, 201)
        image_card = res.get_json()

        with db.get_conn() as conn:
            all_caps = conn.execute(
                "SELECT * FROM captures ORDER BY id"
            ).fetchall()

        self.assertEqual(len(all_caps), 2)
        reminder = next(r for r in all_caps if r["content_type"] == "reminder"
                        and r["id"] != image_card["id"])
        reminder_meta = json.loads(reminder["metadata"])
        self.assertEqual(reminder_meta["due_date"], "2026-07-15")
        self.assertEqual(reminder_meta["source_capture_id"], image_card["id"])

        # Image capture should have linked_reminder_id set
        img_meta = json.loads(all_caps[-1]["metadata"]) if all_caps[-1]["id"] == image_card["id"] else \
                   json.loads(all_caps[0]["metadata"])
        self.assertEqual(img_meta.get("linked_reminder_id"), reminder["id"])

    # ── 5.5 Auto-reminder suppressed when confidence < 0.70 ─────────────────

    @patch("image_processor._llm_orientation_check", return_value="OK")
    @patch("classifier.classify_image")
    def test_auto_reminder_suppressed_low_confidence(self, mock_classify, mock_orient):
        mock_classify.return_value = _mock_classify_result(
            "reminder", 0.65, "assign", due_date="2026-07-15"
        )

        res = self.client.post("/api/capture/image", json={
            "image": _make_jpeg_b64(),
            "media_type": "image/jpeg",
        })
        self.assertEqual(res.status_code, 201)

        with db.get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) as n FROM captures").fetchone()["n"]
        self.assertEqual(count, 1)

        # extract_reminder action should be present
        card = res.get_json()
        self.assertIn("extract_reminder", card["display"]["actions"])

    # ── 5.6 No reminder when no due_date ────────────────────────────────────

    @patch("image_processor._llm_orientation_check", return_value="OK")
    @patch("classifier.classify_image")
    def test_no_reminder_when_no_due_date(self, mock_classify, mock_orient):
        mock_classify.return_value = _mock_classify_result("general_note", 0.88, "assign")

        res = self.client.post("/api/capture/image", json={
            "image": _make_jpeg_b64(),
            "media_type": "image/jpeg",
        })
        self.assertEqual(res.status_code, 201)

        with db.get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) as n FROM captures").fetchone()["n"]
        self.assertEqual(count, 1)

        card = res.get_json()
        self.assertNotIn("extract_reminder", card["display"]["actions"])

    # ── 5.7 Unknown routing via image path ──────────────────────────────────

    @patch("image_processor._llm_orientation_check", return_value="OK")
    @patch("classifier.classify_image")
    def test_unknown_routing_image(self, mock_classify, mock_orient):
        mock_classify.return_value = _mock_classify_result(
            "general_note", 0.55, "unknown", routing_override="unknown"
        )

        res = self.client.post("/api/capture/image", json={
            "image": _make_jpeg_b64(),
            "media_type": "image/jpeg",
        })
        self.assertEqual(res.status_code, 201)
        card = res.get_json()
        self.assertEqual(card["type"], "unknown")

        with db.get_conn() as conn:
            row = conn.execute("SELECT was_unknown FROM captures WHERE id=?",
                               (card["id"],)).fetchone()
        self.assertEqual(row["was_unknown"], 0)  # was_unknown set by resolve, not insert

    # ── 5.8 new_type routing via image path ─────────────────────────────────

    @patch("image_processor._llm_orientation_check", return_value="OK")
    @patch("classifier.classify_image")
    def test_new_type_routing_image(self, mock_classify, mock_orient):
        snt = {"key": "receipt", "label": "Receipt", "icon": "🧾"}
        result = _mock_classify_result("receipt", 0.10, "new_type")
        result["suggested_new_type"] = snt
        result["type"] = "receipt"
        mock_classify.return_value = result

        res = self.client.post("/api/capture/image", json={
            "image": _make_jpeg_b64(),
            "media_type": "image/jpeg",
        })
        self.assertEqual(res.status_code, 201)
        card = res.get_json()
        self.assertEqual(card["type"], "receipt")
        self.assertIn("receipt", db.get_all_types())

    # ── 5.9 HEIC rejected ───────────────────────────────────────────────────

    def test_heic_rejected(self):
        res = self.client.post("/api/capture/image", json={
            "image": _make_jpeg_b64(),
            "media_type": "image/heic",
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertIn("JPG or PNG", data.get("error", ""))

        with db.get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) as n FROM captures").fetchone()["n"]
        self.assertEqual(count, 0)

    # ── 5.10 Missing image field ─────────────────────────────────────────────

    def test_missing_image_field(self):
        res = self.client.post("/api/capture/image", json={
            "media_type": "image/jpeg",
        })
        self.assertEqual(res.status_code, 400)

    # ── 5.11 Malformed base64 ────────────────────────────────────────────────

    @patch("image_processor._llm_orientation_check", return_value="OK")
    def test_malformed_base64(self, mock_orient):
        res = self.client.post("/api/capture/image", json={
            "image": "not_valid_base64!!!",
            "media_type": "image/jpeg",
        })
        # binascii.Error is a subclass of ValueError — endpoint returns 400
        self.assertEqual(res.status_code, 400)

        with db.get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) as n FROM captures").fetchone()["n"]
        self.assertEqual(count, 0)

    def tearDown(self):
        import config
        images_dir = os.path.join(os.path.dirname(config.DB_PATH), "images")
        if os.path.isdir(images_dir):
            for f in os.listdir(images_dir):
                if f.endswith(".jpg"):
                    try:
                        os.remove(os.path.join(images_dir, f))
                    except OSError:
                        pass
