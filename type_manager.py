"""
Manages dynamic type lifecycle: cluster detection and auto-promotion.
Kept separate from db.py to avoid circular imports (classifier ↔ db).
"""
from datetime import datetime, timedelta

_last_cluster_check = None
_CLUSTER_MIN_SIZE = 3
_CLUSTER_COOLDOWN = timedelta(minutes=10)


def should_cluster():
    """True if enough time has passed and there may be enough unknowns to cluster."""
    global _last_cluster_check
    if _last_cluster_check is None:
        return True
    return datetime.now() - _last_cluster_check > _CLUSTER_COOLDOWN


def cluster_unknown():
    """
    Auto-promote clusters of Unknown captures that share a best_guess.
    Runs in a background daemon thread — never blocks a capture response.

    Logic: group all Unknown captures by metadata._best_guess.
    Any group of ≥3 → resolve them to that type (if the type exists).
    """
    global _last_cluster_check
    _last_cluster_check = datetime.now()

    import db
    unknowns = db.get_unknown_captures()

    if len(unknowns) < _CLUSTER_MIN_SIZE:
        return

    groups: dict[str, list[int]] = {}
    for c in unknowns:
        best = c["metadata"].get("_best_guess")
        if best:
            groups.setdefault(best, []).append(c["id"])

    all_types = db.get_all_types()
    for type_key, capture_ids in groups.items():
        if len(capture_ids) >= _CLUSTER_MIN_SIZE and type_key in all_types:
            for cid in capture_ids:
                db.resolve_unknown(cid, type_key)
