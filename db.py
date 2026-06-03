import os
import sqlite3
import json
from datetime import date
from config import DB_PATH

_SEED_TYPES = [
    ("job_application", "Job Applications", "💼", "#4A90E2", "A job listing or hiring post. Action: Apply when ready.", 1),
    ("food_for_thought", "Food for Thought", "🍽️", "#E8600A", "Interesting reads — stories, news, launches, posts worth reading.", 1),
    ("build_better", "Product Craft", "🔨", "#7B61FF", "PM frameworks, teardowns, and analyses to apply in product work.", 1),
    ("learning", "Learnings", "🧠", "#2E9E6B", "Skill-building content to actively study or practice.", 1),
    ("interview_exp", "Interview Exp", "🎯", "#C0392B", "Interview experiences, company culture, and career move content.", 1),
    ("reminder", "Reminder", "⏰", "#E8834A", "Time-sensitive task, deadline, or to-do.", 1),
    ("product_idea", "Idea", "💡", "#8E44AD", "A concrete product or feature idea to build or explore.", 1),
    ("general_note", "Note", "📝", "#5A9E6F", "Anything that doesn't fit another type — reference later.", 1),
    # Special staging type — not a seed, not user-created
    ("unknown", "Unsorted", "?", "#9B9B9B", "Captures awaiting classification.", 0),
    # Legacy types for backward-compat display of old entries
    ("blog_post", "Food for Thought", "🍽️", "#E8600A", "Legacy: blog post", 0),
    ("job_post", "Job Applications", "💼", "#4A90E2", "Legacy: job post", 0),
]

# Module-level cache; invalidated by create_type() and init_db()
_types_cache = None


def _invalidate_types_cache():
    global _types_cache
    _types_cache = None


def get_all_types():
    """Return dict of {key: row_dict} for all content types. Uses module-level cache."""
    global _types_cache
    if _types_cache is None:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM content_types").fetchall()
        _types_cache = {r["key"]: dict(r) for r in rows}
    return _types_cache


def create_type(key, label, icon, color, description):
    """Insert a new dynamic type (idempotent — INSERT OR IGNORE)."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO content_types (key, label, icon, color, description, is_seed) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (key, label, icon, color, description),
        )
    _invalidate_types_cache()


def resolve_unknown(capture_id, new_type_key):
    """Re-assign a capture from unknown to a real type and mark was_unknown=1."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE captures SET content_type = ?, was_unknown = 1 WHERE id = ?",
            (new_type_key, capture_id),
        )


def get_unknown_captures():
    """Return all active unknown captures (for clustering)."""
    return get_captures(content_type="unknown")


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    data_dir = os.path.join(os.path.dirname(DB_PATH), "images")
    os.makedirs(data_dir, exist_ok=True)

    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS content_types (
                key         TEXT PRIMARY KEY,
                label       TEXT NOT NULL,
                icon        TEXT NOT NULL DEFAULT '?',
                color       TEXT NOT NULL DEFAULT '#9B9B9B',
                description TEXT,
                is_seed     INTEGER NOT NULL DEFAULT 0,
                created_at  TIMESTAMP DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS captures (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_input    TEXT    NOT NULL,
                content_type TEXT    NOT NULL DEFAULT 'unknown',
                confidence   REAL    NOT NULL DEFAULT 0.0,
                rationale    TEXT,
                metadata     TEXT    NOT NULL DEFAULT '{}',
                tags         TEXT    NOT NULL DEFAULT '[]',
                completed    INTEGER NOT NULL DEFAULT 0,
                archived     INTEGER NOT NULL DEFAULT 0,
                was_unknown  INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMP DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_type    ON captures(content_type);
            CREATE INDEX IF NOT EXISTS idx_created ON captures(created_at);
            CREATE INDEX IF NOT EXISTS idx_active  ON captures(archived, completed);
        """)

        # Migration: add new columns to existing tables that lack them
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(captures)").fetchall()]
        if "was_unknown" not in existing_cols:
            conn.execute(
                "ALTER TABLE captures ADD COLUMN was_unknown INTEGER NOT NULL DEFAULT 0"
            )
        if "image_path" not in existing_cols:
            conn.execute("ALTER TABLE captures ADD COLUMN image_path TEXT")
        if "input_type" not in existing_cols:
            conn.execute(
                "ALTER TABLE captures ADD COLUMN input_type TEXT NOT NULL DEFAULT 'text'"
            )

        # Seed all types (idempotent)
        conn.executemany(
            "INSERT OR IGNORE INTO content_types (key, label, icon, color, description, is_seed) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            _SEED_TYPES,
        )

        # Migrate legacy 'unclassified' captures to 'unknown'
        conn.execute(
            "UPDATE captures SET content_type = 'unknown' WHERE content_type = 'unclassified'"
        )

    _invalidate_types_cache()


def insert_capture(raw_input, content_type, confidence, rationale, metadata, tags,
                   image_path=None, input_type="text"):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO captures
               (raw_input, content_type, confidence, rationale, metadata, tags,
                image_path, input_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                raw_input,
                content_type,
                confidence,
                rationale,
                json.dumps(metadata),
                json.dumps(tags),
                image_path,
                input_type,
            ),
        )
        return cur.lastrowid



def get_captures(content_type=None, include_archived=False):
    with get_conn() as conn:
        conditions = []
        params = []

        if not include_archived:
            conditions.append("archived = 0")
            conditions.append("completed = 0")

        if content_type:
            conditions.append("content_type = ?")
            params.append(content_type)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        if content_type == "job_application":
            order = "created_at ASC"  # oldest first — apply urgency
        elif content_type == "reminder":
            order = "json_extract(metadata, '$.due_date') ASC, created_at ASC"
        else:
            order = "created_at DESC"

        rows = conn.execute(
            f"SELECT * FROM captures {where} ORDER BY {order}", params
        ).fetchall()

        return [_row_to_card(r) for r in rows]


def get_captures_grouped_by_topic(content_type, include_archived=False):
    """Return cards grouped by topic for learning and blog_post views."""
    cards = get_captures(content_type=content_type, include_archived=include_archived)

    groups = {}
    ungrouped = []
    for card in cards:
        topic = card["metadata"].get("topic", "").strip()
        if topic:
            groups.setdefault(topic, []).append(card)
        else:
            ungrouped.append(card)

    result = []
    for topic in sorted(groups.keys()):
        result.append({"topic": topic, "cards": groups[topic]})
    if ungrouped:
        result.append({"topic": "Other", "cards": ungrouped})

    return result


def get_capture(capture_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM captures WHERE id = ?", (capture_id,)
        ).fetchone()
        return _row_to_card(row) if row else None


def archive_capture(capture_id):
    with get_conn() as conn:
        conn.execute("UPDATE captures SET archived = 1 WHERE id = ?", (capture_id,))


def complete_capture(capture_id):
    with get_conn() as conn:
        conn.execute("UPDATE captures SET completed = 1 WHERE id = ?", (capture_id,))


def get_due_today_count():
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) as n FROM captures
               WHERE content_type = 'reminder'
               AND completed = 0
               AND archived = 0
               AND json_extract(metadata, '$.due_date') = ?""",
            (today,),
        ).fetchone()
        return row["n"] if row else 0


def get_tab_counts():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT content_type, COUNT(*) as n
               FROM captures
               WHERE archived = 0 AND completed = 0
               GROUP BY content_type"""
        ).fetchall()
        return {r["content_type"]: r["n"] for r in rows}


def _row_to_card(row):
    if row is None:
        return None

    metadata = json.loads(row["metadata"])
    tags = json.loads(row["tags"])
    ct = row["content_type"]
    types = get_all_types()
    cfg = types.get(ct) or {"icon": "?", "color": "#9B9B9B", "label": ct.replace("_", " ").title()}

    title, subtitle = _make_display_text(ct, metadata, row["raw_input"])
    actions = _make_actions(ct, metadata)

    return {
        "id": row["id"],
        "type": ct,
        "confidence": row["confidence"],
        "rationale": row["rationale"],
        "metadata": metadata,
        "tags": tags,
        "completed": bool(row["completed"]),
        "archived": bool(row["archived"]),
        "created_at": row["created_at"],
        "display": {
            "title": title,
            "subtitle": subtitle,
            "icon": cfg["icon"],
            "color": cfg["color"],
            "label": cfg["label"],
            "actions": actions,
        },
    }


def _make_display_text(ct, metadata, raw_input):
    if ct == "job_application":
        company = metadata.get("company") or "Unknown"
        role = metadata.get("role") or "Job Post"
        location = metadata.get("location") or ""
        seniority = metadata.get("seniority") or ""
        title = f"{company} — {role}"
        parts = [p for p in [location, seniority] if p]
        return title, " · ".join(parts)

    if ct in ("food_for_thought", "build_better", "interview_exp"):
        title = metadata.get("title") or raw_input[:60]
        topic = metadata.get("topic") or ""
        return title, topic

    if ct == "learning":
        title = metadata.get("title") or raw_input[:60]
        topic = metadata.get("topic") or ""
        return title, topic

    if ct == "product_idea":
        idea_title = metadata.get("title") or metadata.get("one_liner") or raw_input[:60]
        project = metadata.get("project") or "New Idea"
        return idea_title, project

    if ct == "reminder":
        task = metadata.get("task") or raw_input[:60]
        due = metadata.get("due_date") or ""
        priority = metadata.get("priority") or "medium"
        subtitle = f"{due} · {priority}" if due else priority
        return task, subtitle

    if ct == "general_note":
        title = metadata.get("title") or raw_input[:60]
        summary = (metadata.get("summary") or "")[:80]
        return title, summary

    if ct == "unknown":
        title = metadata.get("title") or raw_input[:60]
        return title, "Awaiting classification"

    return raw_input[:60], ""


def _make_actions(ct, metadata):
    if ct == "unknown":
        return ["assign", "archive"]
    base = ["archive"]
    if ct in ("job_application", "food_for_thought", "build_better", "learning", "interview_exp") and metadata.get("url"):
        base.insert(0, "open_url")
    if ct == "reminder":
        base.insert(0, "complete")
    if metadata.get("_extract_reminder"):
        base.insert(0, "extract_reminder")
    return base
