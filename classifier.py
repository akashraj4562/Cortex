import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MODEL, KNOWN_PROJECTS, CONFIDENCE_THRESHOLD

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# When user writes these keywords after a URL, treat as explicit type intent
_EXPLICIT_TYPE_KEYWORDS = {
    "job":       "job_post",
    "jobs":      "job_post",
    "job post":  "job_post",
    "hiring":    "job_post",
    "apply":     "job_post",
    "reminder":  "reminder",
    "remind":    "reminder",
    "todo":      "reminder",
    "to do":     "reminder",
    "idea":      "product_idea",
}

# LinkedIn URL patterns → inferred type (when no explicit user keyword)
_LINKEDIN_URL_TYPES = [
    ("linkedin.com/jobs/",     "job_post"),
    ("/activity-",             "blog_post"),
    ("linkedin.com/posts/",    "blog_post"),
    ("linkedin.com/pulse/",    "blog_post"),
]

_SYSTEM = """You are Corty, the CORTEX classification engine. Classify input into exactly one content type and extract structured metadata.

Content types:
- job_post: A job listing, job opportunity, or job description
- product_idea: A product concept, feature idea, startup idea, or business opportunity
- reminder: A time-sensitive task, deadline, meeting, to-do, or action item
- learning: Educational content to actively study — tutorials, how-to guides, documentation, courses, technical deep-dives, skill-building
- blog_post: Interesting content for reference — LinkedIn posts, news, company updates, product launches, opinions, newsletters, Substack, industry analysis, thought leadership
- general_note: Anything else worth capturing — casual thoughts, WhatsApp-style short messages, observations

Distinction between learning and blog_post:
- learning = you want to actively study and practice this (skill-building, documentation, tutorials, improving a specific skill like Claude/AI/coding)
- blog_post = interesting read for awareness (news, opinions, product features, industry trends, someone's story/experience on LinkedIn)
- All Substack links → blog_post
- LinkedIn posts (linkedin.com/posts/ or /activity-) → almost always blog_post unless clearly educational

URL intelligence:
- linkedin.com/posts/ or /activity- → likely blog_post (someone's LinkedIn post)
- linkedin.com/jobs/ → job_post
- substack.com → blog_post (source: substack)
- docs.* or *.dev/docs → likely learning

Known projects for product_idea: {known_projects}
If a product idea relates to a known project → use that name. Otherwise → "New Idea".

topic_hint priority: If the user provides a topic_hint (keyword after URL), use it as the `topic` field. Capitalize it.
explicit_type: If explicit_type is provided, you MUST classify as that type. Extract metadata for that type. Set confidence ≥ 0.90.

IMPORTANT RULES:
- NEVER return confidence below 0.72 for real text. When uncertain between types → prefer general_note.
- Short casual messages, WhatsApp texts, informal notes → general_note, confidence ≥ 0.80.
- If input is a URL you cannot fully evaluate, use URL domain + topic_hint to classify. Still set confidence ≥ 0.72.
- Only return confidence < 0.70 if input is completely meaningless.

Return ONLY valid JSON:
{{
  "type": "job_post|product_idea|reminder|learning|blog_post|general_note",
  "confidence": 0.0-1.0,
  "rationale": "one concise sentence",
  "metadata": {{...type-specific fields...}},
  "tags": ["tag1", "tag2", "tag3"]
}}

Metadata schemas:

job_post:
{{"company": "infer from URL/content or empty", "role": "infer from URL/content or Job Post", "location": "", "url": "", "deadline": null, "seniority": ""}}

product_idea:
{{"title": "5 words max", "project": "project name or New Idea", "core_insight": "one sentence", "one_liner": "pitch sentence"}}

reminder:
{{"task": "clear action", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low", "recurrence": null}}

learning:
{{"title": "what to learn", "topic": "topic name (e.g. Claude, Payments, React)", "url": "", "summary": "what you'll learn or get from this"}}

blog_post:
{{"title": "post/article title or best guess", "topic": "topic (e.g. Swiggy, Google Maps, AI)", "url": "", "summary": "1-2 sentences on what's interesting", "source": "linkedin|substack|company_blog|news|other"}}

general_note:
{{"title": "short title inferred from content", "summary": "1-2 sentences"}}

Today: {today}
Provide 2-4 relevant tags."""


def parse_input(raw):
    """
    Parse raw input into (url, topic_hint, explicit_type).

    Handles:
    - Pattern A: URL only
    - Pattern B: URL + keyword on same line: "https://url.com Claude"
    - Pattern C: URL + keyword on next line: "https://url.com\\n\\nClaude" (WhatsApp style)
    - Pattern D: plain text (no URL)

    Returns:
      url:           the URL string, or None
      topic_hint:    keyword(s) the user appended (same line or next lines), or None
      explicit_type: if topic_hint matches a known classification keyword, the forced type; or None
    """
    raw = raw.strip()

    # Match URL at the start (handle trailing spaces before newlines)
    url_match = re.match(r'^(https?://[^\s]+|www\.[^\s]+)', raw)
    if not url_match:
        return None, None, None

    url = url_match.group(1).rstrip('.,;')  # strip accidental trailing punctuation
    remainder = raw[len(url_match.group(1)):].strip()

    # Remainder may be multi-line (WhatsApp style: blank line then keyword)
    # Collapse to first non-empty content
    lines = [l.strip() for l in remainder.splitlines() if l.strip()]
    topic_hint = " ".join(lines) if lines else None

    # Explicit type from user keyword
    explicit_type = None
    if topic_hint:
        kw = topic_hint.lower().strip()
        explicit_type = _EXPLICIT_TYPE_KEYWORDS.get(kw)

    # LinkedIn URL pattern inference (only when no explicit user keyword)
    if not explicit_type:
        for pattern, ltype in _LINKEDIN_URL_TYPES:
            if pattern in url.lower():
                explicit_type = ltype
                break

    return url, topic_hint, explicit_type


def is_substack(url):
    return bool(url) and "substack.com" in url.lower()


def classify(raw_input, scraped_text=None, source_url=None, topic_hint=None, explicit_type=None):
    """
    Classify input. Returns dict: type, confidence, rationale, metadata, tags.

    explicit_type: pre-determined type (from keyword or URL pattern) — Claude must use it.
    """
    import datetime

    parts = []
    if explicit_type:
        parts.append(f"[Classification directive: type = {explicit_type}]")
    if topic_hint:
        parts.append(f"[Topic hint from user: {topic_hint}]")
    if source_url:
        parts.append(f"Source URL: {source_url}")
    if scraped_text:
        parts.append(scraped_text)
    elif source_url:
        parts.append(f"URL (could not be scraped — use URL pattern and topic hint): {source_url}")
    else:
        parts.append(raw_input)

    content = "\n\n".join(parts)

    system = _SYSTEM.format(
        known_projects=json.dumps(KNOWN_PROJECTS),
        today=datetime.date.today().isoformat(),
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=700,
            system=system,
            messages=[{"role": "user", "content": content}],
        )

        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            parts_split = raw.split("```")
            raw = parts_split[1] if len(parts_split) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)

    except (json.JSONDecodeError, IndexError, KeyError):
        result = {
            "type": "unclassified",
            "confidence": 0.0,
            "rationale": "Classification failed — could not parse response",
            "metadata": {},
            "tags": [],
        }
    except Exception as e:
        result = {
            "type": "unclassified",
            "confidence": 0.0,
            "rationale": f"Classification error: {str(e)[:100]}",
            "metadata": {},
            "tags": [],
        }

    meta = result.setdefault("metadata", {})

    # Preserve URL
    if source_url and not meta.get("url"):
        meta["url"] = source_url

    # Substack override
    if is_substack(source_url) and result.get("confidence", 0) >= 0.50:
        result["type"] = "blog_post"
        meta.setdefault("source", "substack")

    # Explicit type must be honoured (user's stated intent overrides Claude)
    if explicit_type and result.get("confidence", 0) >= 0.50:
        result["type"] = explicit_type
        if explicit_type in ("learning", "blog_post") and "topic" not in meta:
            meta["topic"] = ""

    # Normalize topic to Title Case
    if meta.get("topic"):
        meta["topic"] = meta["topic"].strip().title()

    # If topic_hint given but topic empty, apply it (only for types that use topic)
    if topic_hint and result.get("type") in ("learning", "blog_post"):
        if not meta.get("topic"):
            # Don't use explicit classification keywords as topic (e.g. "Job" shouldn't be topic)
            kw = topic_hint.lower().strip()
            if kw not in _EXPLICIT_TYPE_KEYWORDS:
                meta["topic"] = topic_hint.strip().title()

    # Low confidence → unclassified
    if result.get("confidence", 0) < CONFIDENCE_THRESHOLD:
        result["type"] = "unclassified"

    return result
