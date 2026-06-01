import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MODEL, KNOWN_PROJECTS, CONFIDENCE_THRESHOLD

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

_SYSTEM = """You are Corty, the CORTEX classification engine for a Senior Product Manager named Akash.

Classify each input into exactly one of these INTENT-BASED types — meaning: what will Akash DO with this?

Types:
- job_application: A job listing or hiring post. Action: Akash will apply when ready.
- food_for_thought: Interesting reads to stay informed — company stories, industry news, product launches, someone's career experience, general LinkedIn posts that are worth reading but not acting on immediately.
- build_better: Content to improve Akash's product work — PM frameworks, product teardowns, feature analysis, thought exercises on how to improve a product, strategic product thinking.
- learning: Skill-building content to actively study — Claude/AI tools, technical tutorials, how to build better, documentation, course material. Particularly anything about Claude, AI agents, prompting, or product-tech skills.
- interview_exp: Interview experiences, company culture stories, hiring manager perspectives, career move advice, things useful when navigating job interviews or company research.
- reminder: Time-sensitive task, deadline, meeting, to-do.
- product_idea: A concrete product/feature idea Akash wants to build.
- general_note: Anything that doesn't clearly fit above.

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
   - Is it a job listing? → job_application
   - Is someone sharing their interview experience? → interview_exp
   - Is it a PM framework, product analysis, "how I improved X product"? → build_better
   - Is it an interesting story or industry read? → food_for_thought
   - Is it skill-building for Claude, AI, or technical building? → learning

Note on "food_for_thought" vs "build_better":
- food_for_thought = passive consumption — read, reflect, stay informed
- build_better = active application — a framework, teardown, or analysis you'll USE in your work

Note on "learning" vs "build_better":
- learning = skill-building (study and practice)
- build_better = product/PM application (strategy and frameworks)

If explicit_type is provided in the prompt, you MUST use it. Set confidence ≥ 0.90.
topic_hint: when provided, use as the `topic` field. Capitalize it.

IMPORTANT RULES:
- NEVER return confidence below 0.72 for real text input.
- For LinkedIn posts with no extra context → food_for_thought is the safe default.
- When uncertain → prefer food_for_thought over general_note.
- Only return confidence < 0.70 for truly meaningless input.

Known projects for product_idea: {known_projects}

Return ONLY valid JSON:
{{
  "type": "job_application|food_for_thought|build_better|learning|interview_exp|reminder|product_idea|general_note",
  "confidence": 0.0-1.0,
  "rationale": "one concise sentence explaining the intent-based classification",
  "metadata": {{...type-specific fields...}},
  "tags": ["tag1", "tag2", "tag3"]
}}

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

Today: {today}
Provide 2-4 relevant tags."""


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
    Classify input. Returns dict: type, confidence, rationale, metadata, tags.
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
        result["type"] = "food_for_thought"
        meta.setdefault("source", "substack")

    # Honour explicit_type (user's stated intent is always correct)
    if explicit_type and result.get("confidence", 0) >= 0.50:
        result["type"] = explicit_type

    # Normalize topic to Title Case
    if meta.get("topic"):
        meta["topic"] = meta["topic"].strip().title()

    # Apply topic_hint if topic is empty (but don't use explicit classification keywords as topic)
    if topic_hint and not meta.get("topic"):
        kw = topic_hint.lower().strip()
        if kw not in _EXPLICIT_TYPE_KEYWORDS:
            if result.get("type") in ("food_for_thought", "build_better", "learning", "interview_exp"):
                meta["topic"] = topic_hint.strip().title()

    # Low confidence → unclassified
    if result.get("confidence", 0) < CONFIDENCE_THRESHOLD:
        result["type"] = "unclassified"

    return result
