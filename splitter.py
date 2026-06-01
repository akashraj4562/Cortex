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
        chunks = _merge_url_keyword_pairs(chunks)
        if len(chunks) > 1:
            return _dedup_urls(chunks)

    # Strategy 3: Multiple bare URLs on consecutive lines
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    url_lines = [l for l in lines if re.match(r'^https?://', l)]
    if len(url_lines) >= 2 and len(url_lines) >= len(lines) * 0.7:
        return _dedup_urls(lines)

    return [raw]


def _merge_url_keyword_pairs(chunks):
    """
    Re-merge consecutive (bare-URL, short-non-URL-text) pairs that represent
    a single URL + topic_hint capture, not two separate items.

    Mobile sharing (LinkedIn, Substack) produces:
        https://linkedin.com/posts/...
        [blank line]
        Interesting read

    The double-newline strategy splits this into two chunks. This function
    detects the pattern and merges them back so parse_input() can correctly
    treat the keyword as a topic_hint.

    Rules:
    - chunk must be a BARE URL (nothing else on the same line) — a URL that
      already has an inline keyword (e.g. "https://url.com Payments") does not
      need merging; its keyword is already attached.
    - next chunk must be ≤ 60 chars and not itself a URL.
    """
    result = []
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        next_chunk = chunks[i + 1] if i + 1 < len(chunks) else None
        url_match = re.match(r'^(https?://\S+)$', chunk)  # $ = nothing after URL
        is_bare_url = bool(url_match)
        if (next_chunk is not None
                and is_bare_url
                and not re.match(r'^https?://', next_chunk)
                and len(next_chunk) <= 60):
            result.append(chunk + '\n\n' + next_chunk)
            i += 2
        else:
            result.append(chunk)
            i += 1
    return result


def _dedup_urls(items):
    seen = set()
    result = []
    for item in items:
        key = item.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
