import re

# Handles two WhatsApp timestamp formats:
#   Global/Indian: [DD/MM/YYYY, HH:MM AM/PM] Name: message
#   iOS/American:  [H:MM AM/PM, M/DD/YYYY] Name: message
_WA_TIMESTAMP = re.compile(
    r'\[(?:'
    # Global: date first  e.g. [01/06/2026, 10:30 AM]
    r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}[,\s]+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?'
    r'|'
    # iOS: time first  e.g. [1:11 PM, 5/31/2026]
    r'\d{1,2}:\d{2}\s*(?:AM|PM)[,\s]+\d{1,2}/\d{1,2}/\d{2,4}'
    r')\]\s+[^:\[\]]+:\s*',
    re.IGNORECASE,
)

_URL_LINE = re.compile(r'^https?://\S+', re.MULTILINE)


def split_items(raw):
    """
    Split a multi-item paste into individual capture units.
    Returns a list of non-empty strings.
    """
    raw = raw.strip()
    if not raw:
        return []

    # Strategy 1: WhatsApp timestamp format (both iOS and global)
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

    return [raw]


def _dedup_urls(items):
    seen = set()
    result = []
    for item in items:
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
