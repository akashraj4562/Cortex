import threading
import time
from flask import Flask, request, jsonify, render_template

import db
import scraper
import classifier
import splitter
import type_manager
import image_processor
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

    routing = result.get("routing", "assign")

    # If Corty created a new type, register it in DB before inserting the capture
    if routing == "new_type":
        ntype = result.get("suggested_new_type") or {}
        if ntype.get("key"):
            db.create_type(
                key=ntype["key"],
                label=ntype.get("label", ntype["key"].replace("_", " ").title()),
                icon=ntype.get("icon", "?"),
                color="#6248d8",
                description=f"Corty-created: {ntype.get('label', '')}",
            )

    capture_id = db.insert_capture(
        raw_input=raw_item,
        content_type=result["type"],
        confidence=result["confidence"],
        rationale=result.get("rationale", ""),
        metadata=result.get("metadata", {}),
        tags=result.get("tags", []),
    )

    # Trigger async clustering when a capture lands in Unknown
    if routing == "unknown" and type_manager.should_cluster():
        threading.Thread(target=type_manager.cluster_unknown, daemon=True).start()

    return db.get_capture(capture_id)


@app.route("/api/capture/image", methods=["POST"])
def capture_image():
    body = request.get_json(silent=True) or {}
    b64 = (body.get("image") or "").strip()
    media_type = (body.get("media_type") or "image/jpeg").strip()
    hint = (body.get("hint") or "").strip()

    if not b64:
        return jsonify({"error": "image field is required"}), 400

    # Process: orient, resize, save
    try:
        proc = image_processor.process_image(b64, media_type)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    image_path = proc["image_path"]
    b64_jpeg = proc["base64_jpeg"]

    # Classify via vision
    try:
        result = classifier.classify_image(b64_jpeg, "image/jpeg", hint=hint)
    except Exception as e:
        return jsonify({"error": f"Classification failed: {str(e)[:120]}"}), 500

    routing = result.get("routing", "assign")

    if routing == "new_type":
        ntype = result.get("suggested_new_type") or {}
        if ntype.get("key"):
            db.create_type(
                key=ntype["key"],
                label=ntype.get("label", ntype["key"].replace("_", " ").title()),
                icon=ntype.get("icon", "?"),
                color="#6248d8",
                description=f"Corty-created: {ntype.get('label', '')}",
            )

    # Auto-reminder check
    meta = result.get("metadata", {})
    structured = meta.get("structured_data") or {}
    due_date = structured.get("due_date")
    confidence = result.get("confidence", 0)

    linked_reminder_id = None
    if due_date:
        if confidence >= 0.70:
            reminder_meta = {
                "task": f"{meta.get('description', 'Image capture')} — extracted from image",
                "due_date": due_date,
                "priority": "medium",
                "source_capture_id": None,  # filled after image capture inserted
            }
            linked_reminder_id = db.insert_capture(
                raw_input=f"[auto-reminder] {meta.get('description', '')}",
                content_type="reminder",
                confidence=confidence,
                rationale="Auto-extracted from image capture",
                metadata=reminder_meta,
                tags=[],
                input_type="text",
            )
        else:
            meta["_extract_reminder"] = True

    meta["image_path"] = image_path

    capture_id = db.insert_capture(
        raw_input=hint or "[image capture]",
        content_type=result["type"],
        confidence=confidence,
        rationale=result.get("rationale", ""),
        metadata=meta,
        tags=result.get("tags", []),
        image_path=image_path,
        input_type="image",
    )

    # Back-fill source_capture_id on the reminder and linked_reminder_id on the image capture
    if linked_reminder_id:
        with db.get_conn() as conn:
            import json as _json
            row = conn.execute("SELECT metadata FROM captures WHERE id=?", (linked_reminder_id,)).fetchone()
            if row:
                rm = _json.loads(row["metadata"])
                rm["source_capture_id"] = capture_id
                conn.execute("UPDATE captures SET metadata=? WHERE id=?",
                             (_json.dumps(rm), linked_reminder_id))
            img_row = conn.execute("SELECT metadata FROM captures WHERE id=?", (capture_id,)).fetchone()
            if img_row:
                im = _json.loads(img_row["metadata"])
                im["linked_reminder_id"] = linked_reminder_id
                conn.execute("UPDATE captures SET metadata=? WHERE id=?",
                             (_json.dumps(im), capture_id))

    if routing == "unknown" and type_manager.should_cluster():
        threading.Thread(target=type_manager.cluster_unknown, daemon=True).start()

    return jsonify(db.get_capture(capture_id)), 201


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

@app.route("/api/types")
def get_types():
    types = db.get_all_types()
    # Return as ordered list: seeds first, then dynamic; exclude system/legacy types from UI
    _ui_excluded = {"unknown", "unclassified", "blog_post", "job_post"}
    result = [
        {"key": k, "label": v["label"], "icon": v["icon"], "color": v["color"], "is_seed": v["is_seed"]}
        for k, v in types.items()
        if k not in _ui_excluded
    ]
    result.sort(key=lambda t: (0 if t["is_seed"] else 1, t["key"]))
    return jsonify(result)


@app.route("/api/unknown/resolve", methods=["POST"])
def resolve_unknown():
    body = request.get_json(silent=True) or {}
    capture_id = body.get("id")
    new_type = (body.get("type") or "").strip()
    if not capture_id or not new_type:
        return jsonify({"error": "id and type are required"}), 400
    db.resolve_unknown(capture_id, new_type)
    card = db.get_capture(capture_id)
    return jsonify({"ok": True, "card": card})


@app.route("/api/feed")
def feed():
    ct = request.args.get("type") or None
    grouped_types = {"learning", "food_for_thought", "build_better", "interview_exp"}

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
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "unknown"
    print(f"\n  CORTEX running at:")
    print(f"    Local:   http://localhost:{PORT}")
    print(f"    Network: http://{local_ip}:{PORT}  ← open this on your phone\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
