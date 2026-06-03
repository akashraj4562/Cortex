import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MODEL, KNOWN_PROJECTS, HIGH_CONFIDENCE, LOW_CONFIDENCE

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# When user writes these keywords after a URL, treat as explicit type intent
_EXPLICIT_TYPE_KEYWORDS = {
    "job":            "job_application",
    "jobs":           "job_application",
    "job post":       "job_application",
    "hiring":         "job_application",
    "apply":          "job_application",
    "interview":      "interview_exp",
    "interviews":     "interview_exp",
    "reminder":       "reminder",
    "remind":         "reminder",
    "todo":           "reminder",
    "to do":          "reminder",
    "idea":           "product_idea",
    "learn":          "learning",
    "learning":       "learning",
    "claude":         "learning",   # user's explicit signal: Claude = skill-building
    "ai":             "learning",
    "build":          "build_better",
    "build better":   "build_better",
    "pm":             "build_better",
}

# LinkedIn URL patterns → inferred type (when no explicit user keyword)
_LINKEDIN_URL_TYPES = [
    ("linkedin.com/jobs/",  "job_application"),
    ("/activity-",          "food_for_thought"),  # generic activity posts
    ("linkedin.com/posts/", "food_for_thought"),
    ("linkedin.com/pulse/", "food_for_thought"),
]

_IMAGE_SYSTEM = """You are Corty, the CORTEX classification engine for a Senior Product Manager named Akash.

Analyze this image and classify it by INTENT — what will Akash DO with this?

Available intent types:
{type_list}

If no type fits well (your honest confidence would be below 0.20), propose a new intent type instead of forcing a bad fit.

Confidence guidance:
- 0.85+: Very clear fit — you're certain
- 0.80-0.84: Clear fit with minor ambiguity
- 0.60-0.79: Plausible but ambiguous — system routes to Unsorted for review
- 0.20-0.59: Weak fit — system routes to Unsorted
- Below 0.20: No good fit — use suggested_new_type instead

Known projects for product_idea: {known_projects}

Return ONLY valid JSON:
{{
  "type": "<best_matching_type_key>",
  "confidence": 0.0-1.0,
  "rationale": "one concise sentence explaining the intent-based classification",
  "metadata": {{
    "description": "what this image shows",
    "extracted_text": "all visible text from the image, verbatim",
    "structured_data": {{
      "due_date": "YYYY-MM-DD or null",
      "due_time": "HH:MM or null",
      "price": "amount with currency symbol or null",
      "names": ["any person or product names"],
      "location": "location or null"
    }},
    ...type-specific fields below...
  }},
  "tags": ["tag1", "tag2", "tag3"],
  "suggested_new_type": null
}}

When confidence is below 0.20, set suggested_new_type to:
{{"key": "snake_case_key", "label": "Human Readable Label", "icon": "single emoji"}}

Type-specific metadata fields (add to metadata based on classified type):

reminder: "task": "clear action item", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low"
job_application: "company": "", "role": "", "location": "", "url": ""
food_for_thought: "title": "", "topic": "", "summary": "1-2 sentences on what's interesting"
build_better: "title": "", "topic": "", "summary": "what Akash will apply from this"
learning: "title": "", "topic": "skill area", "summary": "what Akash will learn"
product_idea: "title": "5 words max", "project": "project name or New Idea", "core_insight": "", "one_liner": ""
general_note: "title": "short title", "summary": "1-2 sentences"
For any Corty-created type: "title": "short title", "summary": "1-2 sentences"

Today: {today}
Provide 2-4 relevant tags."""


_SYSTEM = """You are Corty, the CORTEX classification engine for a Senior Product Manager named Akash.

Your job: classify each input by INTENT — what will Akash DO with this?

Available intent types:
{type_list}

If no type fits well (your honest confidence would be below 0.20), propose a new intent type instead of forcing a bad fit.

Classification signals (in priority order):
1. Explicit user keyword (highest priority — Akash always means what he writes):
   - "Job" / "hiring" → job_application
   - "Interview" → interview_exp
   - "Learn" / "learning" → learning
   - "Claude" → learning (Akash uses Claude as a builder tool)
   - "Build" / "PM" → build_better
   - Topic hints like "Swiggy", "Google Maps", "OpenAI" alone → food_for_thought (unless content says otherwise)

2. URL pattern:
   - linkedin.com/jobs/ → job_application
   - linkedin.com/posts/ or /activity- → likely food_for_thought unless content says otherwise
   - substack.com → food_for_thought
   - docs.* or technical tutorials → learning

3. Content analysis (when URL is scraped):
   - Job listing → job_application
   - Interview experience → interview_exp
   - PM framework / product analysis / "how I improved X" → build_better
   - Interesting story or industry read → food_for_thought
   - Skill-building for Claude, AI, or technical building → learning

Confidence guidance:
- 0.85+: Very clear fit — you're certain
- 0.80-0.84: Clear fit with minor ambiguity
- 0.60-0.79: Plausible but ambiguous — system routes to Unsorted for review
- 0.20-0.59: Weak fit — system routes to Unsorted
- Below 0.20: No good fit — use suggested_new_type instead

Notes:
- food_for_thought = passive consumption (read, reflect, stay informed)
- build_better = active application (a framework or analysis you'll USE)
- learning = skill-building (study and practice); build_better = PM strategy
- For LinkedIn posts with no extra context → food_for_thought is the safe default
- When uncertain between types → prefer food_for_thought over general_note

If explicit_type is provided in the prompt, you MUST use it. Set confidence ≥ 0.90.
topic_hint: when provided, use as the `topic` field. Capitalize it.

Known projects for product_idea: {known_projects}

Return ONLY valid JSON:
{{
  "type": "<best_matching_type_key>",
  "confidence": 0.0-1.0,
  "rationale": "one concise sentence explaining the intent-based classification",
  "metadata": {{...type-specific fields...}},
  "tags": ["tag1", "tag2", "tag3"],
  "suggested_new_type": null
}}

When confidence is below 0.20, set suggested_new_type to:
{{"key": "snake_case_key", "label": "Human Readable Label", "icon": "single emoji"}}

Metadata schemas:

job_application:
{{"company": "infer from URL slug or content", "role": "infer from URL slug or content", "location": "", "url": "", "deadline": null, "seniority": ""}}

food_for_thought:
{{"title": "post/article title", "topic": "topic area (e.g. Swiggy, Google Maps, AI)", "url": "", "summary": "1-2 sentences on what's interesting", "source": "linkedin|substack|company_blog|news|other"}}

build_better:
{{"title": "what the framework/idea is", "topic": "topic area (e.g. Google Maps, Product Strategy)", "url": "", "summary": "what Akash will apply from this", "source": "linkedin|substack|other"}}

learning:
{{"title": "what to learn", "topic": "skill area (e.g. Claude, AI Agents, Prompting, React)", "url": "", "summary": "what Akash will learn or improve"}}

interview_exp:
{{"title": "company or topic", "topic": "company or domain (e.g. Google, Swiggy, PM Interviews)", "url": "", "summary": "what's relevant for interviews or career"}}

reminder:
{{"task": "clear action", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low", "recurrence": null}}

product_idea:
{{"title": "5 words max", "project": "project name or New Idea", "core_insight": "one sentence", "one_liner": "pitch sentence"}}

general_note:
{{"title": "short title inferred from content", "summary": "1-2 sentences"}}

For any Corty-created type (not in the list above):
{{"title": "short title", "summary": "1-2 sentences"}}

Today: {today}
Provide 2-4 relevant tags."""


# Excluded from the prompt type list (staging / legacy / system types)
_PROMPT_EXCLUDED = {"unknown", "unclassified", "blog_post", "job_post"}


def _build_type_list():
    """Build the type list string injected into the Corty system prompt."""
    import db
    types = db.get_all_types()
    lines = []
    for key, t in types.items():
        if key not in _PROMPT_EXCLUDED:
            lines.append(f"- {key} ({t['label']} {t['icon']}): {t.get('description', '')}")
    return "\n".join(lines)


def _compute_routing(confidence, suggested_new_type, explicit_type):
    """
    Pure routing logic — no I/O, fully testable.
    Returns 'assign' | 'unknown' | 'new_type'.
    """
    if explicit_type:
        return "assign"
    if confidence >= HIGH_CONFIDENCE:
        return "assign"
    if confidence >= LOW_CONFIDENCE:
        return "unknown"
    # Below LOW_CONFIDENCE
    if suggested_new_type and isinstance(suggested_new_type, dict) and suggested_new_type.get("key"):
        return "new_type"
    return "unknown"


def classify_image(base64_jpeg: str, media_type: str = "image/jpeg",
                   hint: str = "", explicit_type=None):
    """
    Classify an image using claude-opus-4-8 vision.
    Returns same dict shape as classify(): type, confidence, routing, rationale, metadata, tags.
    """
    import datetime

    system = _IMAGE_SYSTEM.format(
        type_list=_build_type_list(),
        known_projects=json.dumps(KNOWN_PROJECTS),
        today=datetime.date.today().isoformat(),
    )

    text_parts = []
    if explicit_type:
        text_parts.append(f"[Classification directive: type = {explicit_type}]")
    if hint:
        text_parts.append(f"[Context hint from user: {hint}]")
    text_parts.append("Classify this image.")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_jpeg,
                        },
                    },
                    {
                        "type": "text",
                        "text": "\n".join(text_parts),
                    },
                ],
            }],
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
            "type": "unknown",
            "confidence": 0.0,
            "rationale": "Classification failed — could not parse response",
            "metadata": {},
            "tags": [],
            "suggested_new_type": None,
        }
    except Exception as e:
        result = {
            "type": "unknown",
            "confidence": 0.0,
            "rationale": f"Classification error: {str(e)[:100]}",
            "metadata": {},
            "tags": [],
            "suggested_new_type": None,
        }

    meta = result.setdefault("metadata", {})
    confidence = result.get("confidence", 0)
    suggested_new_type = result.get("suggested_new_type")

    # Honour explicit_type override
    if explicit_type:
        result["type"] = explicit_type
        result["confidence"] = max(confidence, HIGH_CONFIDENCE)

    final_confidence = result.get("confidence", 0)
    routing = _compute_routing(final_confidence, suggested_new_type, explicit_type)
    result["routing"] = routing
    result["best_guess"] = result["type"] if routing == "unknown" else None

    if routing == "assign":
        pass
    elif routing == "unknown":
        meta["_best_guess"] = result["type"]
        result["type"] = "unknown"
    elif routing == "new_type":
        result["type"] = suggested_new_type["key"]

    return result


def parse_input(raw):
    """
    Parse raw input into (url, topic_hint, explicit_type).

    Handles:
    - URL only
    - URL + keyword on same line: "https://url.com Claude"
    - URL + keyword on next line (WhatsApp style): "https://url.com\\n\\nClaude"
    - Plain text (no URL)

    Returns:
      url:           the URL string, or None
      topic_hint:    keyword(s) the user appended, or None
      explicit_type: forced type from keyword or URL pattern, or None
    """
    raw = raw.strip()

    url_match = re.match(r'^(https?://[^\s]+|www\.[^\s]+)', raw)
    if not url_match:
        return None, None, None

    url = url_match.group(1).rstrip('.,;')
    remainder = raw[len(url_match.group(1)):].strip()

    # Collect all non-empty lines after the URL (handles WhatsApp next-line keywords)
    lines = [l.strip() for l in remainder.splitlines() if l.strip()]
    topic_hint = " ".join(lines) if lines else None

    # Explicit type from user keyword (highest priority)
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
    Classify input. Returns dict with: type, confidence, routing, rationale, metadata, tags.
    routing is one of: 'assign' | 'unknown' | 'new_type'
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
        parts.append(f"URL (could not be scraped — use URL pattern and topic hint to classify): {source_url}")
    else:
        parts.append(raw_input)

    content = "\n\n".join(parts)

    system = _SYSTEM.format(
        type_list=_build_type_list(),
        known_projects=json.dumps(KNOWN_PROJECTS),
        today=datetime.date.today().isoformat(),
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=800,
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
            "type": "unknown",
            "confidence": 0.0,
            "rationale": "Classification failed — could not parse response",
            "metadata": {},
            "tags": [],
            "suggested_new_type": None,
        }
    except Exception as e:
        result = {
            "type": "unknown",
            "confidence": 0.0,
            "rationale": f"Classification error: {str(e)[:100]}",
            "metadata": {},
            "tags": [],
            "suggested_new_type": None,
        }

    meta = result.setdefault("metadata", {})
    confidence = result.get("confidence", 0)
    suggested_new_type = result.get("suggested_new_type")

    # Preserve URL
    if source_url and not meta.get("url"):
        meta["url"] = source_url

    # Substack override
    if is_substack(source_url) and confidence >= 0.50:
        result["type"] = "food_for_thought"
        result["confidence"] = max(confidence, HIGH_CONFIDENCE)
        meta.setdefault("source", "substack")

    # Honour explicit_type (user's stated intent is always correct)
    if explicit_type and confidence >= 0.50:
        result["type"] = explicit_type
        result["confidence"] = max(confidence, HIGH_CONFIDENCE)

    # Normalize topic to Title Case
    if meta.get("topic"):
        meta["topic"] = meta["topic"].strip().title()

    # Apply topic_hint if topic is empty (but don't use explicit classification keywords as topic)
    if topic_hint and not meta.get("topic"):
        kw = topic_hint.lower().strip()
        if kw not in _EXPLICIT_TYPE_KEYWORDS:
            if result.get("type") in ("food_for_thought", "build_better", "learning", "interview_exp"):
                meta["topic"] = topic_hint.strip().title()

    # Compute routing based on final confidence and explicit_type
    final_confidence = result.get("confidence", 0)
    routing = _compute_routing(final_confidence, suggested_new_type, explicit_type)
    result["routing"] = routing
    result["best_guess"] = result["type"] if routing == "unknown" else None

    # Apply routing to the stored type
    if routing == "assign":
        pass  # type stays as Corty returned it
    elif routing == "unknown":
        meta["_best_guess"] = result["type"]
        result["type"] = "unknown"
    elif routing == "new_type":
        result["type"] = suggested_new_type["key"]

    return result
