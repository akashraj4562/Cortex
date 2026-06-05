import json
import re
import anthropic
from config import ANTHROPIC_API_KEY, MODEL, HAIKU_MODEL, KNOWN_PROJECTS, HIGH_CONFIDENCE, LOW_CONFIDENCE

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
shopping_list: "title": "short description", "items": ["item1", "item2", ...], "store_hint": "zepto|blinkit|null", "notes": ""

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
- shopping_list disambiguation: classify as shopping_list when input is clearly about buying things.
  HIGH CONFIDENCE (0.85+) cases — assign directly, never route to Unsorted:
    • Any plain-text grocery/food/household item with no URL: "milk", "eggs", "bread", "tomatoes", "shampoo"
    • ≥2 commerce-likely items in any form
    • ≥1 quantity-token (e.g. "2kg", "1 dozen", "500ml", "3 bottles", "half kilo")
    • Explicit list format: "- milk\n- eggs\n- onions"
  Lower confidence only when there is genuine ambiguity (single word that could be a note title, etc.).
  A shopping list is about buying things; a reminder is about doing something.
  "milk" → shopping_list 0.90. "Buy milk and eggs" → shopping_list 0.95. "Buy milk for the party" → reminder (single item + occasion). "milk industry trends" → food_for_thought.

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

shopping_list:
{{"title": "short list description", "items": ["item1", "item2", ...], "store_hint": "zepto|blinkit|null", "notes": "any special instructions"}}

For any Corty-created type (not in the list above):
{{"title": "short title", "summary": "1-2 sentences"}}

Today: {today}
Provide 2-4 relevant tags."""


# Excluded from the prompt type list (staging / legacy / system types)
_PROMPT_EXCLUDED = {"unknown", "unclassified", "blog_post", "job_post"}

# Types where a lower confidence threshold is acceptable (unambiguous domain)
_LOW_THRESHOLD_TYPES = {"shopping_list", "reminder"}
_LOW_THRESHOLD_CONFIDENCE = 0.55


def _build_type_list():
    """Build the type list string injected into the Corty system prompt."""
    import db
    types = db.get_all_types()
    lines = []
    for key, t in types.items():
        if key not in _PROMPT_EXCLUDED:
            lines.append(f"- {key} ({t['label']} {t['icon']}): {t.get('description', '')}")
    return "\n".join(lines)


def _tokenize_input(raw: str) -> list:
    """
    Split raw input into semantic tokens for similarity scoring.
    "milk, eggs, bread" → ["milk", "eggs", "bread"]
    "Remind me to call Vikas" → ["Remind me to call Vikas"]
    """
    tokens = re.split(r'[\n,;•\-]\s*', raw)
    tokens = [t.strip() for t in tokens if t.strip()]
    seen, result = set(), []
    for t in tokens:
        if t.lower() not in seen:
            seen.add(t.lower())
            result.append(t)
    return result if result else [raw.strip()]


_SIMILARITY_SYSTEM = """You are Corty, the CORTEX classification engine for a Senior Product Manager named Akash.

You receive INPUT TOKENS extracted from the user's raw input, plus the full list of content types.

## Your task
Score the similarity of the input tokens to EACH content type (0.0–1.0), then pick the best match and extract structured metadata.

## Similarity scoring rules
- 0.85–1.0  Very clear match — tokens unambiguously belong to this type
- 0.70–0.84  Strong match with minor ambiguity
- 0.55–0.69  Plausible — several signals align
- 0.20–0.54  Weak — few signals align
- 0.00–0.19  No meaningful relationship

## Critical scoring guidance
shopping_list:
  - A single grocery/food/household word with no URL → score 0.90+ (milk, eggs, bread, tomatoes, shampoo, onions, dal)
  - ≥2 such items or any quantity-token (2kg, 500ml, 1 dozen) → score 0.95+
  - "Buy X and Y" → score 0.95+
  - "Buy X for the party" → reminder (has occasion), shopping_list score 0.30
reminder:
  - Has time component OR action verb + occasion → 0.85+
  - "Call Vikas tomorrow", "submit by Friday" → 0.90+
food_for_thought:
  - Requires a URL or clear reference to an article/post/news
  - Plain text with no URL → score 0.05 max
learning / build_better / interview_exp:
  - Requires a URL or explicit domain signal (framework name, course, tutorial)
  - Plain grocery word → 0.02
product_idea:
  - Requires "idea", "build", or a product concept statement
general_note:
  - Catch-all; never score above 0.60 when another type fits better

Suggested new type: if no type scores above 0.20, propose a new type.

## Available types
{type_list}

Known projects for product_idea: {known_projects}

## Metadata schemas (for the best_type)
job_application: {{"company": "", "role": "", "location": "", "url": "", "seniority": ""}}
food_for_thought: {{"title": "", "topic": "", "url": "", "summary": "", "source": ""}}
build_better: {{"title": "", "topic": "", "url": "", "summary": ""}}
learning: {{"title": "", "topic": "", "url": "", "summary": ""}}
interview_exp: {{"title": "", "topic": "", "url": "", "summary": ""}}
reminder: {{"task": "", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low", "recurrence": null}}
product_idea: {{"title": "", "project": "project name or New Idea", "core_insight": "", "one_liner": ""}}
general_note: {{"title": "", "summary": ""}}
shopping_list: {{"title": "", "items": ["item1", ...], "store_hint": "zepto|blinkit|null", "notes": ""}}
For any Corty-created type: {{"title": "", "summary": ""}}

Today: {today}

## Output
Return ONLY valid JSON:
{{
  "scores": {{"type_key": 0.0, ...}},
  "best_type": "type_key",
  "confidence": 0.0,
  "rationale": "one sentence",
  "metadata": {{...}},
  "tags": ["tag1", "tag2"],
  "suggested_new_type": null
}}

When no type scores above 0.20, set suggested_new_type to:
{{"key": "snake_case_key", "label": "Human Readable Label", "icon": "single emoji"}}

Provide 2-4 relevant tags."""


def _compute_routing(confidence, suggested_new_type, explicit_type, content_type=None):
    """
    Pure routing logic — no I/O, fully testable.
    Returns 'assign' | 'unknown' | 'new_type'.
    Type-specific lower threshold for unambiguous domains (shopping_list, reminder).
    """
    if explicit_type:
        return "assign"
    threshold = _LOW_THRESHOLD_CONFIDENCE if content_type in _LOW_THRESHOLD_TYPES else HIGH_CONFIDENCE
    if confidence >= threshold:
        return "assign"
    if confidence >= LOW_CONFIDENCE:
        return "unknown"
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


_EXTRACT_ITEMS_SYSTEM = """Extract a structured shopping list from this text.
Return ONLY valid JSON with no markdown fencing:
{
  "items": [
    {"name": "item name normalized for search", "quantity": "amount with unit or null", "notes": "any special notes or null"}
  ]
}
Normalize item names for grocery search (e.g. "2 kgs of tomatoes" -> name: "tomatoes", quantity: "2 kg").
Return an empty list if no grocery or household items are found."""


def extract_shopping_items(raw_input: str):
    """
    Use Haiku to extract structured items from a shopping list text.
    Returns list of {"name": str, "quantity": str|None, "notes": str|None}.
    """
    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=500,
            system=_EXTRACT_ITEMS_SYSTEM,
            messages=[{"role": "user", "content": raw_input}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            parts_split = raw.split("```")
            raw = parts_split[1] if len(parts_split) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        extracted = json.loads(raw)
        return extracted.get("items", [])
    except Exception:
        return []


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


def _parse_llm_json(raw_text: str) -> dict:
    """Strip markdown fencing and parse JSON from LLM response."""
    raw = raw_text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def classify(raw_input, scraped_text=None, source_url=None, topic_hint=None, explicit_type=None):
    """
    Classify input using a two-step pipeline:
      1. Tokenize the raw input into semantic tokens
      2. Send tokens + all type descriptions to LLM for similarity scoring
      3. LLM returns per-type similarity scores + best match + metadata
      4. Apply type-specific confidence thresholds to route

    Returns dict: type, confidence, routing, rationale, metadata, tags, scores.
    routing: 'assign' | 'unknown' | 'new_type'
    """
    import datetime

    # ── Step 1: Tokenize ──────────────────────────────────────────────────────
    tokens = _tokenize_input(scraped_text or raw_input)

    # ── Step 2: Build prompt ──────────────────────────────────────────────────
    prompt_parts = []
    if explicit_type:
        prompt_parts.append(f"[Classification directive: type = {explicit_type}. Set confidence ≥ 0.90.]")
    if topic_hint:
        prompt_parts.append(f"[User topic hint: {topic_hint}]")
    if source_url:
        prompt_parts.append(f"[Source URL: {source_url}]")

    prompt_parts.append(f"INPUT TOKENS: {json.dumps(tokens)}")

    if scraped_text:
        prompt_parts.append(f"FULL CONTENT (for metadata extraction):\n{scraped_text[:3000]}")
    elif source_url and not scraped_text:
        prompt_parts.append(f"(URL could not be scraped — classify from URL pattern and tokens only)")

    content = "\n\n".join(prompt_parts)

    system = _SIMILARITY_SYSTEM.format(
        type_list=_build_type_list(),
        known_projects=json.dumps(KNOWN_PROJECTS),
        today=datetime.date.today().isoformat(),
    )

    # ── Step 3: LLM similarity scoring call ──────────────────────────────────
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        result = _parse_llm_json(response.content[0].text)

    except (json.JSONDecodeError, IndexError, KeyError):
        result = {
            "scores": {},
            "best_type": "unknown",
            "confidence": 0.0,
            "rationale": "Classification failed — could not parse response",
            "metadata": {},
            "tags": [],
            "suggested_new_type": None,
        }
    except Exception as e:
        result = {
            "scores": {},
            "best_type": "unknown",
            "confidence": 0.0,
            "rationale": f"Classification error: {str(e)[:100]}",
            "metadata": {},
            "tags": [],
            "suggested_new_type": None,
        }

    # Normalise field names (LLM may return "type" instead of "best_type")
    if "type" in result and "best_type" not in result:
        result["best_type"] = result.pop("type")
    result.setdefault("scores", {})
    result["type"] = result.get("best_type", "unknown")

    meta = result.setdefault("metadata", {})
    confidence = float(result.get("confidence", 0))
    suggested_new_type = result.get("suggested_new_type")

    # ── Step 4: Post-processing overrides ────────────────────────────────────

    # Preserve URL in metadata
    if source_url and not meta.get("url"):
        meta["url"] = source_url

    # Substack always → food_for_thought
    if is_substack(source_url) and confidence >= 0.50:
        result["type"] = "food_for_thought"
        confidence = max(confidence, HIGH_CONFIDENCE)
        result["confidence"] = confidence
        meta.setdefault("source", "substack")

    # Explicit type: user intent is always correct
    if explicit_type:
        result["type"] = explicit_type
        confidence = max(confidence, HIGH_CONFIDENCE)
        result["confidence"] = confidence

    # Normalize topic to Title Case
    if meta.get("topic"):
        meta["topic"] = meta["topic"].strip().title()

    # Apply topic_hint if topic is empty
    if topic_hint and not meta.get("topic"):
        kw = topic_hint.lower().strip()
        if kw not in _EXPLICIT_TYPE_KEYWORDS:
            if result.get("type") in ("food_for_thought", "build_better", "learning", "interview_exp"):
                meta["topic"] = topic_hint.strip().title()

    # ── Step 5: Route using type-specific thresholds ──────────────────────────
    final_confidence = float(result.get("confidence", confidence))
    routing = _compute_routing(final_confidence, suggested_new_type, explicit_type, result["type"])
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
