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
        if _looks_like_shopping_list(chunks):
            return [raw]  # keep entire list as one capture for shopping_list classification
        chunks = _merge_url_keyword_pairs(chunks)
        if len(chunks) > 1:
            return _dedup_urls(chunks)

    # Strategy 3: Multiple bare URLs on consecutive lines
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    url_lines = [l for l in lines if re.match(r'^https?://', l)]
    if len(url_lines) >= 2 and len(url_lines) >= len(lines) * 0.7:
        return _dedup_urls(lines)

    return [raw]


_SENTENCE_WORDS = frozenset({
    # Pronouns
    'i', 'me', 'my', 'mine', 'we', 'our', 'you', 'your', 'he', 'him',
    'his', 'she', 'her', 'they', 'them', 'it', 'its', 'this', 'that',
    'these', 'those',
    # Common verbs / copulas
    'is', 'are', 'was', 'were', 'be', 'been', 'am', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'can', 'could',
    'follow', 'remind', 'check', 'call', 'meet', 'review', 'update', 'sync',
    'thought', 'think', 'seems', 'looks', 'feel', 'seems', 'sounds',
    # Prepositions / conjunctions
    'to', 'at', 'for', 'in', 'on', 'by', 'from', 'with', 'about', 'of',
    'and', 'or', 'but', 'not', 'so', 'yet', 'if', 'then',
    # Common adjectives that don't appear in grocery names
    'good', 'bad', 'new', 'old', 'first', 'second', 'third',
    'long', 'short', 'big', 'small', 'great', 'interesting', 'nice', 'cool',
    # Generic/abstract nouns
    'item', 'thing', 'stuff', 'idea', 'thought', 'job', 'task',
})

_QTY_RE = re.compile(
    r'\b\d+\s*(?:kg|kgs|g|gm|gms|gram|grams|l|lt|ml|litre|liter|liters|litres'
    r'|dozen|piece|pcs|pack|packs|bottle|bottles|box|boxes|bag|bags|lb|lbs|oz)\b',
    re.IGNORECASE,
)


def _looks_like_shopping_list(chunks):
    """
    Return True when double-newline-split chunks look like a grocery list.
    Two paths:
    1. Any chunk has a quantity token (2kg, 500ml, 1 dozen...) → confident match.
    2. No quantities: require ≥3 chunks all ≤3 words with no sentence-indicator words.
    Also bails if any chunk contains common English sentence words (pronouns, verbs,
    prepositions) that would never appear alone in a grocery item.
    """
    if len(chunks) < 2:
        return False
    # URLs are never grocery items
    if any(re.match(r'^https?://', c) for c in chunks):
        return False
    # All chunks must be short
    if not all(len(c.split()) <= 5 for c in chunks):
        return False
    # Any sentence-indicator word disqualifies the whole batch
    for chunk in chunks:
        if set(chunk.lower().split()) & _SENTENCE_WORDS:
            return False
    # Path 1: quantity token present → confident match
    if any(_QTY_RE.search(c) for c in chunks):
        return True
    # Path 2: ≥3 very-short chunks (product-name-only items)
    return len(chunks) >= 3 and all(len(c.split()) <= 3 for c in chunks)


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
