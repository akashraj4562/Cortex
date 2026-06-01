import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MODEL, KNOWN_PROJECTS, CONFIDENCE_THRESHOLD

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """You are Corty, the CORTEX classification engine. Classify input into exactly one content type and extract structured metadata.

Content types:
- job_post: A job listing, job opportunity, or job description
- product_idea: A product concept, feature idea, startup idea, or business opportunity
- reminder: A time-sensitive task, deadline, meeting, to-do, or action item
- learning: Educational content to actively study — tutorials, how-to guides, documentation, courses, technical deep-dives
- blog_post: Interesting content for reference — news, company updates, product launches, opinions, newsletters, Substack articles, industry analysis
- general_note: Anything else worth capturing

Distinction between learning and blog_post:
- learning = you want to actively study and practice this (skill-building, documentation, tutorials)
- blog_post = you find it interesting to read and reference (news, opinions, company features, Substack)
- All Substack links → blog_post

Known projects for product_idea association: {known_projects}
If a product idea clearly relates to one project → use that name. Otherwise → "New Idea".

If a topic_hint is provided in the input, use it as the `topic` field for learning/blog_post types. Topic_hint takes priority over Claude-inferred topic. Capitalize the topic (e.g. "claude" → "Claude").

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
{{"company": "", "role": "", "location": "", "url": "", "deadline": null, "seniority": ""}}

product_idea:
{{"title": "5 words max", "project": "project name or New Idea", "core_insight": "one sentence", "one_liner": "pitch sentence"}}

reminder:
{{"task": "clear action", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low", "recurrence": null}}

learning:
{{"title": "what to learn", "topic": "topic name (e.g. Claude, Payments, React)", "url": "", "summary": "what you'll learn"}}

blog_post:
{{"title": "article title", "topic": "topic name (e.g. Swiggy, OpenAI, Stripe)", "url": "", "summary": "1-2 sentences on what's interesting", "source": "substack|company_blog|news|linkedin|other"}}

general_note:
{{"title": "short title", "summary": "1-2 sentences"}}

Today: {today}
Set confidence < 0.70 only when genuinely uncertain. Provide 2-4 relevant tags."""


def parse_input(raw):
    """
    Parse raw input into (url, topic_hint, content_text).
    Pattern B: URL followed by words → url + topic_hint
    Pattern A: URL only → url, no hint
    Pattern C: text only → no url
    """
    raw = raw.strip()

    # Check if starts with URL
    url_match = re.match(r'^(https?://\S+|www\.\S+)', raw)
    if not url_match:
        return None, None, raw

    url = url_match.group(1)
    remainder = raw[len(url):].strip()

    topic_hint = remainder if remainder else None
    return url, topic_hint, raw


def is_substack(url):
    if not url:
        return False
    return "substack.com" in url.lower()


def classify(raw_input, scraped_text=None, source_url=None, topic_hint=None):
    """
    Classify input. Returns dict: type, confidence, rationale, metadata, tags.

    raw_input: original paste from user
    scraped_text: text extracted from URL (if URL was scraped)
    source_url: the URL, if input was a URL
    topic_hint: trailing keyword(s) from URL+keyword pattern
    """
    import datetime

    # Build the content to classify
    parts = []
    if topic_hint:
        parts.append(f"[Topic hint from user: {topic_hint}]")
    if source_url:
        parts.append(f"Source URL: {source_url}")
    if scraped_text:
        parts.append(scraped_text)
    elif source_url:
        parts.append(f"URL (could not be scraped): {source_url}")
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

        # Strip markdown code fences
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

    # Preserve URL in metadata
    if source_url and not meta.get("url"):
        meta["url"] = source_url

    # Substack override → always blog_post
    if is_substack(source_url) and result.get("confidence", 0) >= 0.50:
        result["type"] = "blog_post"
        meta.setdefault("source", "substack")

    # Normalize topic to Title Case
    if "topic" in meta and meta["topic"]:
        meta["topic"] = meta["topic"].strip().title()

    # If topic_hint given but topic not set by Claude, apply it
    if topic_hint and "topic" in meta and not meta["topic"]:
        meta["topic"] = topic_hint.strip().title()

    # Low confidence → unclassified
    if result.get("confidence", 0) < CONFIDENCE_THRESHOLD:
        result["type"] = "unclassified"

    return result
