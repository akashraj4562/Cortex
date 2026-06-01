"""Tests for db.py — SQLite operations, WAL mode, schema correctness."""
import sys, os, sqlite3, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
import config
import db


class TestDB(unittest.TestCase):

    def setUp(self):
        # Drop and recreate table for isolation
        with db.get_conn() as conn:
            conn.execute("DROP TABLE IF EXISTS captures")
        db.init_db()

    def test_wal_mode(self):
        # Use db.get_conn() which sets WAL mode
        with db.get_conn() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "wal")

    def test_schema_columns(self):
        with db.get_conn() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(captures)").fetchall()]
        for col in ["id", "raw_input", "content_type", "confidence", "rationale",
                    "metadata", "tags", "completed", "archived", "created_at"]:
            self.assertIn(col, cols)

    def test_insert_and_retrieve(self):
        cid = db.insert_capture(
            raw_input="test input",
            content_type="general_note",
            confidence=0.85,
            rationale="test",
            metadata={"title": "Test", "summary": "A test"},
            tags=["test"],
        )
        card = db.get_capture(cid)
        self.assertIsNotNone(card)
        self.assertEqual(card["type"], "general_note")
        self.assertAlmostEqual(card["confidence"], 0.85)
        self.assertEqual(card["metadata"]["title"], "Test")

    def test_get_nonexistent(self):
        card = db.get_capture(99999)
        self.assertIsNone(card)

    def test_archive(self):
        cid = db.insert_capture("x", "general_note", 0.8, "", {}, [])
        db.archive_capture(cid)
        cards = db.get_captures()
        ids = [c["id"] for c in cards]
        self.assertNotIn(cid, ids)

    def test_complete(self):
        cid = db.insert_capture(
            "remind me x", "reminder", 0.9, "",
            {"task": "x", "due_date": None, "priority": "low", "recurrence": None}, []
        )
        db.complete_capture(cid)
        card = db.get_capture(cid)
        self.assertTrue(card["completed"])

    def test_get_captures_by_type(self):
        db.insert_capture("job1", "job_application", 0.9, "",
            {"company": "A", "role": "PM", "location": "", "url": "", "deadline": None, "seniority": ""}, [])
        db.insert_capture("note1", "general_note", 0.8, "",
            {"title": "N", "summary": ""}, [])
        jobs = db.get_captures(content_type="job_application")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["type"], "job_application")

    def test_jobs_sorted_oldest_first(self):
        import time
        db.insert_capture("job_a", "job_application", 0.9, "",
            {"company": "A", "role": "PM", "location": "", "url": "", "deadline": None, "seniority": ""}, [])
        time.sleep(0.02)
        db.insert_capture("job_b", "job_application", 0.9, "",
            {"company": "B", "role": "PM", "location": "", "url": "", "deadline": None, "seniority": ""}, [])
        jobs = db.get_captures(content_type="job_application")
        self.assertEqual(jobs[0]["metadata"]["company"], "A")  # oldest first

    def test_reminder_badge_today(self):
        from datetime import date
        today = date.today().isoformat()
        db.insert_capture("r", "reminder", 0.9, "",
            {"task": "x", "due_date": today, "priority": "high", "recurrence": None}, [])
        n = db.get_due_today_count()
        self.assertGreaterEqual(n, 1)

    def test_reminder_badge_future_not_counted(self):
        n_before = db.get_due_today_count()
        db.insert_capture("r", "reminder", 0.9, "",
            {"task": "x", "due_date": "2099-01-01", "priority": "low", "recurrence": None}, [])
        n_after = db.get_due_today_count()
        self.assertEqual(n_before, n_after)  # future reminder doesn't change badge

    def test_grouped_by_topic(self):
        db.insert_capture("b1", "food_for_thought", 0.85, "",
            {"title": "T1", "topic": "Swiggy", "url": "", "summary": "", "source": "linkedin"}, [])
        db.insert_capture("b2", "learning", 0.85, "",
            {"title": "T2", "topic": "Claude", "url": "", "summary": ""}, [])
        groups_fft = db.get_captures_grouped_by_topic("food_for_thought")
        groups_learn = db.get_captures_grouped_by_topic("learning")
        self.assertIn("Swiggy", [g["topic"] for g in groups_fft])
        self.assertIn("Claude", [g["topic"] for g in groups_learn])

    def test_tab_counts(self):
        db.insert_capture("j", "job_application", 0.9, "",
            {"company": "X", "role": "PM", "location": "", "url": "", "deadline": None, "seniority": ""}, [])
        db.insert_capture("n", "general_note", 0.8, "",
            {"title": "N", "summary": ""}, [])
        counts = db.get_tab_counts()
        self.assertGreaterEqual(counts.get("job_application", 0), 1)
        self.assertGreaterEqual(counts.get("general_note", 0), 1)


if __name__ == "__main__":
    unittest.main()
