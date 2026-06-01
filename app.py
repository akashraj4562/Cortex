import threading
import time
from flask import Flask, request, jsonify, render_template

import db
import scraper
import classifier
import splitter
from config import PORT, REMINDER_POLL_INTERVAL

app = Flask(__name__)
db.init_db()

# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def _process_one(raw_item):
    """Classify and store a single item. Returns the saved card dict."""
    url, topic_hint, explicit_type = classifier.parse_input(raw_item)
    scraped_text = scraper.scrape(url) if url else None

    result = classifier.classify(
        raw_input=raw_item,
        scraped_text=scraped_text,
        source_url=url,
        topic_hint=topic_hint,
        explicit_type=explicit_type,
    )

    capture_id = db.insert_capture(
        raw_input=raw_item,
        content_type=result["type"],
        confidence=result["confidence"],
        rationale=result.get("rationale", ""),
        metadata=result.get("metadata", {}),
        tags=result.get("tags", []),
    )
    return db.get_capture(capture_id)


@app.route("/api/capture", methods=["POST"])
def capture():
    body = request.get_json(silent=True) or {}
    raw = (body.get("text") or "").strip()

    if not raw:
        return jsonify({"error": "Empty input"}), 400

    items = splitter.split_items(raw)

    if len(items) == 1:
        card = _process_one(items[0])
        return jsonify(card), 201

    # Multi-item: process each and return array
    cards = [_process_one(item) for item in items]
    return jsonify({"cards": cards, "count": len(cards)}), 201


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

@app.route("/api/feed")
def feed():
    ct = request.args.get("type") or None
    grouped_types = {"learning", "blog_post"}

    if ct in grouped_types:
        groups = db.get_captures_grouped_by_topic(content_type=ct)
        badge = db.get_due_today_count()
        return jsonify({"groups": groups, "reminder_badge": badge, "grouped": True})

    cards = db.get_captures(content_type=ct)
    badge = db.get_due_today_count()
    return jsonify({"cards": cards, "reminder_badge": badge, "grouped": False})


@app.route("/api/counts")
def counts():
    return jsonify(db.get_tab_counts())


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@app.route("/api/capture/<int:capture_id>/archive", methods=["POST"])
def archive(capture_id):
    db.archive_capture(capture_id)
    return jsonify({"ok": True})


@app.route("/api/capture/<int:capture_id>/complete", methods=["POST"])
def complete(capture_id):
    db.complete_capture(capture_id)
    badge = db.get_due_today_count()
    return jsonify({"ok": True, "reminder_badge": badge})


@app.route("/api/badge")
def badge():
    return jsonify({"reminder_badge": db.get_due_today_count()})


# ---------------------------------------------------------------------------
# Reminder background thread
# ---------------------------------------------------------------------------

def _reminder_poll():
    while True:
        time.sleep(REMINDER_POLL_INTERVAL)
        # Badge count computed on-demand via /api/badge.
        # Thread exists for future push/alert logic.


threading.Thread(target=_reminder_poll, daemon=True).start()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(port=PORT, debug=False)
