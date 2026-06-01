"""Tests for Flask API endpoints. Uses test DB + mocked classifier/scraper."""
import sys, os, json, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from unittest.mock import patch

import config
import db

_MOCK_REMINDER = {
    "type": "reminder",
    "confidence": 0.92,
    "rationale": "Mock: time-sensitive task",
    "metadata": {"task": "Follow up", "due_date": "2026-06-04", "priority": "medium", "recurrence": None},
    "tags": ["follow-up"],
}

_MOCK_JOB = {
    "type": "job_application",
    "confidence": 0.91,
    "rationale": "Mock: job listing",
    "metadata": {"company": "TestCo", "role": "PM", "location": "Remote",
                 "url": "", "deadline": None, "seniority": "senior"},
    "tags": ["pm"],
}

import app as flask_app


class TestCaptureAPI(unittest.TestCase):

    def setUp(self):
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()
        with db.get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS captures")
        db.init_db()

    @patch("app.classifier.classify", return_value=_MOCK_REMINDER)
    @patch("app.scraper.scrape", return_value=None)
    def test_single_text_capture(self, mock_scrape, mock_classify):
        res = self.client.post("/api/capture",
            data=json.dumps({"text": "Remind me to follow up"}),
            content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertIn("type", data)
        self.assertEqual(data["type"], "reminder")

    def test_empty_capture_rejected(self):
        res = self.client.post("/api/capture",
            data=json.dumps({"text": ""}),
            content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_missing_body_rejected(self):
        res = self.client.post("/api/capture",
            data=json.dumps({}),
            content_type="application/json")
        self.assertEqual(res.status_code, 400)

    @patch("app.classifier.classify", side_effect=[_MOCK_REMINDER, _MOCK_JOB])
    @patch("app.scraper.scrape", return_value=None)
    def test_multi_item_capture_returns_array(self, mock_scrape, mock_classify):
        blob = "Remind me to follow up\n\nJob at TestCo is interesting"
        res = self.client.post("/api/capture",
            data=json.dumps({"text": blob}),
            content_type="application/json")
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertIn("cards", data)
        self.assertEqual(data["count"], 2)

    @patch("app.classifier.classify", return_value=_MOCK_REMINDER)
    @patch("app.scraper.scrape", return_value=None)
    def test_multi_item_all_cards_stored(self, mock_scrape, mock_classify):
        blob = "Item one\n\nItem two"
        mock_classify.side_effect = [_MOCK_REMINDER, _MOCK_JOB]
        self.client.post("/api/capture",
            data=json.dumps({"text": blob}),
            content_type="application/json")
        cards = db.get_captures()
        self.assertEqual(len(cards), 2)

    @patch("app.classifier.classify", return_value=_MOCK_REMINDER)
    @patch("app.scraper.scrape", return_value=None)
    def test_feed_returns_cards(self, *_):
        self.client.post("/api/capture",
            data=json.dumps({"text": "Remind me to follow up"}),
            content_type="application/json")
        res = self.client.get("/api/feed")
        data = json.loads(res.data)
        self.assertIn("cards", data)
        self.assertFalse(data["grouped"])
        self.assertGreaterEqual(len(data["cards"]), 1)

    @patch("app.classifier.classify", return_value=_MOCK_REMINDER)
    @patch("app.scraper.scrape", return_value=None)
    def test_archive_removes_from_feed(self, *_):
        res = self.client.post("/api/capture",
            data=json.dumps({"text": "Something to archive"}),
            content_type="application/json")
        card_id = json.loads(res.data)["id"]

        self.client.post(f"/api/capture/{card_id}/archive")
        feed = json.loads(self.client.get("/api/feed").data)
        ids = [c["id"] for c in feed["cards"]]
        self.assertNotIn(card_id, ids)

    @patch("app.classifier.classify", return_value=_MOCK_REMINDER)
    @patch("app.scraper.scrape", return_value=None)
    def test_complete_returns_ok_and_badge(self, *_):
        res = self.client.post("/api/capture",
            data=json.dumps({"text": "task to complete"}),
            content_type="application/json")
        card_id = json.loads(res.data)["id"]

        res2 = self.client.post(f"/api/capture/{card_id}/complete")
        data = json.loads(res2.data)
        self.assertTrue(data["ok"])
        self.assertIn("reminder_badge", data)

    def test_badge_endpoint(self):
        res = self.client.get("/api/badge")
        data = json.loads(res.data)
        self.assertIn("reminder_badge", data)
        self.assertIsInstance(data["reminder_badge"], int)

    def test_counts_endpoint(self):
        res = self.client.get("/api/counts")
        self.assertEqual(res.status_code, 200)

    def test_index_renders(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"CORTEX", res.data)

    def test_index_has_capture_box(self):
        res = self.client.get("/")
        self.assertIn(b"capture-box", res.data)


class TestFeedGrouped(unittest.TestCase):

    def setUp(self):
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()
        with db.get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS captures")
        db.init_db()

    def test_food_for_thought_feed_is_grouped(self):
        db.insert_capture("b1", "food_for_thought", 0.85, "",
            {"title": "T", "topic": "Swiggy", "url": "", "summary": "", "source": "linkedin"}, [])
        res = self.client.get("/api/feed?type=food_for_thought")
        data = json.loads(res.data)
        self.assertTrue(data["grouped"])
        self.assertIn("groups", data)

    def test_learning_feed_is_grouped(self):
        db.insert_capture("l1", "learning", 0.85, "",
            {"title": "T", "topic": "Claude", "url": "", "summary": ""}, [])
        res = self.client.get("/api/feed?type=learning")
        data = json.loads(res.data)
        self.assertTrue(data["grouped"])

    def test_jobs_feed_not_grouped(self):
        res = self.client.get("/api/feed?type=job_application")
        data = json.loads(res.data)
        self.assertFalse(data["grouped"])
        self.assertIn("cards", data)

    def test_all_feed_not_grouped(self):
        res = self.client.get("/api/feed")
        data = json.loads(res.data)
        self.assertFalse(data["grouped"])


if __name__ == "__main__":
    unittest.main()
