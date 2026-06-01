import re

# WhatsApp exported chat formats:
# [01/06/2026, 10:30 AM] Name: message
# [1/6/26, 10:30 am] Name: message
_WA_TIMESTAMP = re.compile(
    r'^\[\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\]\s+[^:]+:\s*',
    re.MULTILINE | re.IGNORECASE,
)

# Multiple URLs on separate lines within a chunk
_URL_LINE = re.compile(r'^https?://\S+', re.MULTILINE)


def split_items(raw):
    """
    Split a multi-item paste (WhatsApp blob, multi-line notes) into individual
    capture units. Returns a list of non-empty strings.
    """
    raw = raw.strip()
    if not raw:
        return []

    # Strategy 1: WhatsApp timestamp format
    if _WA_TIMESTAMP.search(raw):
        parts = _WA_TIMESTAMP.split(raw)
        items = [p.strip() for p in parts if p.strip()]
        if len(items) > 1:
            return _dedup_urls(items)

    # Strategy 2: Double newline paragraph breaks
    chunks = re.split(r'\n\s*\n', raw)
    chunks = [c.strip() for c in chunks if c.strip()]

    if len(chunks) > 1:
        return _dedup_urls(chunks)

    # Strategy 3: Multiple bare URLs on consecutive lines
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    url_lines = [l for l in lines if re.match(r'^https?://', l)]
    if len(url_lines) >= 2 and len(url_lines) >= len(lines) * 0.7:
        return _dedup_urls(lines)

    # Single item
    return [raw]


def _dedup_urls(items):
    """Remove exact duplicates while preserving order."""
    seen = set()
    result = []
    for item in items:
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
