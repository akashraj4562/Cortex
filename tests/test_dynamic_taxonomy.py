"""Tests for Release 1 — Dynamic Taxonomy system."""
import sys, os, sqlite3, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from unittest.mock import patch

import config
import db

SEED_KEYS = {
    "job_application", "food_for_thought", "build_better", "learning",
    "interview_exp", "reminder", "product_idea", "general_note",
}


def _mock_classify(routing, type_key, confidence, suggested_new_type=None, best_guess=None):
    return {
        "type": type_key,
        "confidence": confidence,
        "routing": routing,
        "rationale": "mock",
        "metadata": {"title": "Test", "summary": ""},
        "tags": ["test"],
        "best_guess": best_guess,
        "suggested_new_type": suggested_new_type,
    }


class TestContentTypesDB(unittest.TestCase):

    def setUp(self):
        with db.get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS captures")
            conn.execute("DROP TABLE IF EXISTS content_types")
        db._invalidate_types_cache()
        db.init_db()

    def test_content_types_table_exists(self):
        with db.get_conn() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(content_types)").fetchall()]
        self.assertIn("key", cols)
        self.assertIn("label", cols)
        self.assertIn("icon", cols)
        self.assertIn("is_seed", cols)

    def test_seed_types_count(self):
        with db.get_conn() as conn:
            n = conn.execute("SELECT COUNT(*) FROM content_types WHERE is_seed = 1").fetchone()[0]
        self.assertEqual(n, 9)  # 8 original + shopping_list (PRD-003)

    def test_all_seed_keys_present(self):
        types = db.get_all_types()
        for key in SEED_KEYS:
            self.assertIn(key, types, f"Missing seed type: {key}")

    def test_was_unknown_column_exists(self):
        with db.get_conn() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(captures)").fetchall()]
        self.assertIn("was_unknown", cols)

    def test_create_type_new_type(self):
        db.create_type("focus_read", "Focus Read", "🎯", "#FF5733", "Deep reading sessions")
        types = db.get_all_types()
        self.assertIn("focus_read", types)
        self.assertEqual(types["focus_read"]["label"], "Focus Read")
        self.assertEqual(types["focus_read"]["is_seed"], 0)

    def test_create_type_is_idempotent(self):
        db.create_type("focus_read", "Focus Read", "🎯", "#FF5733", "Deep reading sessions")
        db.create_type("focus_read", "Focus Read", "🎯", "#FF5733", "Deep reading sessions")
        with db.get_conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM content_types WHERE key = 'focus_read'"
            ).fetchone()[0]
        self.assertEqual(n, 1)

    def test_get_all_types_cache_invalidated_after_create(self):
        before = set(db.get_all_types().keys())
        db.create_type("temp_type", "Temp", "🔥", "#FF0000", "Temp type")
        after = set(db.get_all_types().keys())
        self.assertIn("temp_type", after)
        self.assertNotIn("temp_type", before)

    def test_resolve_unknown_updates_type(self):
        cid = db.insert_capture("test ambiguous", "unknown", 0.5, "ambiguous",
                                {"title": "T", "summary": ""}, [])
        db.resolve_unknown(cid, "general_note")
        card = db.get_capture(cid)
        self.assertEqual(card["type"], "general_note")

    def test_resolve_unknown_sets_was_unknown_flag(self):
        cid = db.insert_capture("test ambiguous", "unknown", 0.5, "ambiguous",
                                {"title": "T", "summary": ""}, [])
        db.resolve_unknown(cid, "general_note")
        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT was_unknown FROM captures WHERE id = ?", (cid,)
            ).fetchone()
        self.assertEqual(row[0], 1)

    def test_get_unknown_captures_returns_unknown_only(self):
        db.insert_capture("u1", "unknown", 0.5, "", {"title": "A", "summary": ""}, [])
        db.insert_capture("u2", "unknown", 0.4, "", {"title": "B", "summary": ""}, [])
        db.insert_capture("k1", "general_note", 0.9, "", {"title": "C", "summary": ""}, [])
        unknowns = db.get_unknown_captures()
        for c in unknowns:
            self.assertEqual(c["type"], "unknown")
        self.assertEqual(len(unknowns), 2)

    def test_unclassified_migrated_to_unknown(self):
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO captures (raw_input, content_type, confidence, metadata, tags, was_unknown) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("old capture", "unclassified", 0.0, "{}", "[]", 0)
            )
        db._invalidate_types_cache()
        db.init_db()
        with db.get_conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM captures WHERE content_type = 'unclassified'"
            ).fetchone()[0]
        self.assertEqual(n, 0)


class TestClassifierRouting(unittest.TestCase):

    def setUp(self):
        with db.get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS captures")
            conn.execute("DROP TABLE IF EXISTS content_types")
        db._invalidate_types_cache()
        db.init_db()

    def test_high_confidence_routes_assign(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.91, None, None), "assign")

    def test_boundary_high_routes_assign(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.80, None, None), "assign")

    def test_medium_confidence_routes_unknown(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.55, None, None), "unknown")

    def test_boundary_medium_routes_unknown(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.20, None, None), "unknown")

    def test_just_below_medium_routes_unknown_no_suggestion(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.19, None, None), "unknown")

    def test_low_confidence_with_suggestion_routes_new_type(self):
        from classifier import _compute_routing
        suggestion = {"key": "focus_read", "label": "Focus Read", "icon": "🎯"}
        self.assertEqual(_compute_routing(0.10, suggestion, None), "new_type")

    def test_low_confidence_no_suggestion_routes_unknown(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.10, None, None), "unknown")

    def test_explicit_type_forces_assign(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.55, None, "job_application"), "assign")

    def test_explicit_type_forces_assign_even_low_confidence(self):
        from classifier import _compute_routing
        self.assertEqual(_compute_routing(0.10, None, "reminder"), "assign")


import app as flask_app


class TestAPIWithRouting(unittest.TestCase):

    def setUp(self):
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()
        with db.get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS captures")
            conn.execute("DROP TABLE IF EXISTS content_types")
        db._invalidate_types_cache()
        db.init_db()

    def test_get_types_endpoint(self):
        res = self.client.get("/api/types")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 8)
        keys = {t["key"] for t in data}
        for seed in SEED_KEYS:
            self.assertIn(seed, keys)

    @patch("app.classifier.classify")
    @patch("app.scraper.scrape", return_value=None)
    def test_assign_routing_stores_correctly(self, mock_scrape, mock_classify):
        mock_classify.return_value = _mock_classify("assign", "general_note", 0.92)
        res = self.client.post("/api/capture",
            data=json.dumps({"text": "some note to remember"}),
            content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertEqual(data["type"], "general_note")

    @patch("app.classifier.classify")
    @patch("app.scraper.scrape", return_value=None)
    def test_unknown_routing_stores_as_unknown(self, mock_scrape, mock_classify):
        mock_classify.return_value = _mock_classify(
            "unknown", "unknown", 0.55, best_guess="food_for_thought"
        )
        res = self.client.post("/api/capture",
            data=json.dumps({"text": "some ambiguous content that Corty is unsure about"}),
            content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertEqual(data["type"], "unknown")

    @patch("app.classifier.classify")
    @patch("app.scraper.scrape", return_value=None)
    def test_new_type_routing_creates_type_and_stores(self, mock_scrape, mock_classify):
        mock_classify.return_value = _mock_classify(
            "new_type", "meditation_log", 0.10,
            suggested_new_type={"key": "meditation_log", "label": "Meditation Log", "icon": "🧘"}
        )
        res = self.client.post("/api/capture",
            data=json.dumps({"text": "10 minutes breathing exercises today felt great"}),
            content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertEqual(data["type"], "meditation_log")
        types = db.get_all_types()
        self.assertIn("meditation_log", types)
        self.assertEqual(types["meditation_log"]["is_seed"], 0)

    def test_resolve_unknown_endpoint(self):
        cid = db.insert_capture("ambiguous input", "unknown", 0.5, "ambiguous",
                                {"title": "T", "summary": ""}, [])
        res = self.client.post("/api/unknown/resolve",
            data=json.dumps({"id": cid, "type": "general_note"}),
            content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["ok"])
        card = db.get_capture(cid)
        self.assertEqual(card["type"], "general_note")

    def test_resolve_unknown_rejects_missing_fields(self):
        res = self.client.post("/api/unknown/resolve",
            data=json.dumps({"id": 1}),
            content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_unknown_feed_returns_cards(self):
        db.insert_capture("u1", "unknown", 0.5, "", {"title": "A", "summary": ""}, [])
        res = self.client.get("/api/feed?type=unknown")
        data = json.loads(res.data)
        self.assertIn("cards", data)
        self.assertGreaterEqual(len(data["cards"]), 1)
        self.assertFalse(data["grouped"])

    def test_unknown_count_in_tab_counts(self):
        db.insert_capture("u1", "unknown", 0.5, "", {"title": "A", "summary": ""}, [])
        res = self.client.get("/api/counts")
        counts = json.loads(res.data)
        self.assertGreaterEqual(counts.get("unknown", 0), 1)

    @patch("app.classifier.classify")
    @patch("app.scraper.scrape", return_value=None)
    def test_legacy_mock_defaults_to_assign(self, mock_scrape, mock_classify):
        """Mocks without routing field default to assign — backward compat."""
        mock_classify.return_value = {
            "type": "reminder",
            "confidence": 0.92,
            "rationale": "old-format mock",
            "metadata": {"task": "call someone", "due_date": None, "priority": "medium", "recurrence": None},
            "tags": ["reminder"],
        }
        res = self.client.post("/api/capture",
            data=json.dumps({"text": "Remind me to call Vikas"}),
            content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertEqual(data["type"], "reminder")


if __name__ == "__main__":
    unittest.main()
