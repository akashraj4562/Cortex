# PRD-CORTEX-001 — CORTEX v1 (MVP)

**Product:** CORTEX  
**Agent:** Corty  
**Version:** 1.1 — MVP (updated 2026-06-01)  
**Status:** Approved — Implementation  
**Owner:** Akash Raj

**Changelog v1.1:** Added `learning` and `blog_post` content types. Added URL+keyword input pattern for topic-hinted capture. Added topic sub-folder system.

---

## 1. Problem

Valuable thoughts — job opportunities, product ideas, reminders, interesting reads, things to learn — get lost in WhatsApp drafts, browser tabs, and Notes app. There is no single place to dump a thought and trust it will be organized, surfaced, and acted on.

The cost is real: missed applications, half-formed ideas that never get revisited, reminders that fire at the wrong time or not at all, interesting articles bookmarked and never returned to.

---

## 2. Goal

A single paste interface where any thought goes in raw, and CORTEX classifies, organizes, and surfaces it in the right context — automatically.

One box. Every type of capture. Zero manual taxonomy. Smart topic sub-foldering.

---

## 3. Users

Single user: Akash Raj (personal tool). No auth, no multi-tenancy, no sharing.

---

## 4. Content Types (MVP — 6 types)

| Type | Internal key | Trigger | Primary input |
|---|---|---|---|
| **Job Post** | `job_post` | LinkedIn/job board URL, job description | URL or text |
| **Product Idea** | `product_idea` | Feature/product concept, business idea | Text |
| **Reminder** | `reminder` | Time-sensitive task, deadline, meeting | Text |
| **Learning** | `learning` | Tutorial, how-to, documentation, course, skill-building content | URL + keyword or text |
| **Blog & Post** | `blog_post` | Industry news, company feature, opinion piece, Substack, interesting read | URL + keyword or text |
| **General Note** | `general_note` | Anything else worth capturing | Text |

**Learning vs Blog/Post distinction:**
- `learning`: Content you want to **actively study or practice** — documentation, tutorials, deep-dives. The keyword signals an area you're building skill in.
- `blog_post`: Content you find **interesting for reference** — product launches, company updates, opinions, newsletters, industry analysis. Including all Substack links.

---

## 5. Core Flow

```
User pastes input into single box
    ↓
POST /capture
    ↓
[Input Pattern Detection]
  Pattern A: URL only → scrape URL
  Pattern B: URL + keyword → scrape URL, extract keyword as topic_hint
  Pattern C: text only → use as-is
    ↓
Claude (claude-opus-4-8) classifies with topic_hint context:
  {type, confidence, rationale, metadata{...topic...}, tags}
    ↓
confidence ≥ 0.70 → auto-classify → store → render content_card
confidence < 0.70 → store as "unclassified" → render "help me classify" card
    ↓
Feed updates with new card
```

---

## 5b. Input Pattern Detection

```
Input: "https://example.com/article"
→ Pattern A: URL only. scrape + classify.

Input: "https://example.com/article Claude"
→ Pattern B: URL + keyword "Claude". scrape + classify with topic_hint="Claude".

Input: "https://example.com/article payments learn"
→ Pattern B: URL + trailing words. keyword = "payments learn".

Input: "Build a chrome extension that tracks..."
→ Pattern C: Text. classify directly.
```

**Detection rule:** If input starts with `http://` or `https://` or `www.`, split on first whitespace. Everything after the URL = topic_hint. URL is scraped. Topic_hint is passed to Claude as context.

**Special detection — Substack:** Any URL matching `*.substack.com` or containing `/substack.com/` auto-classifies as `blog_post`. Topic_hint or "Newsletter" is used as topic.

---

## 6. Server-Driven UI Contract

Backend returns a `content_card` JSON spec. Frontend is a pure renderer.

```json
{
  "id": 1,
  "type": "blog_post",
  "confidence": 0.88,
  "rationale": "Swiggy blog about a new feature, interesting industry read",
  "metadata": {
    "title": "Swiggy's new instant delivery feature",
    "topic": "Swiggy",
    "url": "https://...",
    "summary": "Swiggy launches 10-minute grocery delivery in tier-2 cities"
  },
  "tags": ["swiggy", "delivery", "product"],
  "created_at": "2026-06-01T10:30:00",
  "display": {
    "title": "Swiggy's new instant delivery feature",
    "subtitle": "Swiggy · Blog & Post",
    "icon": "📰",
    "color": "#E8600A",
    "actions": ["archive", "open_url"]
  }
}
```

---

## 7. Classification Schema

Claude returns structured JSON for each type. `topic` is the key sub-folder field — present on `learning` and `blog_post`.

**job_post:**
```json
{"company": "", "role": "", "location": "", "url": "", "deadline": null, "seniority": ""}
```

**product_idea:**
```json
{"title": "", "project": "CORTEX | Marketpulse | New Idea | ...", "core_insight": "", "one_liner": ""}
```

**reminder:**
```json
{"task": "", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low", "recurrence": null}
```

**learning:**
```json
{
  "title": "short title of what to learn",
  "topic": "Claude | Payments | React | ... (from topic_hint or inferred)",
  "url": "",
  "summary": "what you'll learn from this"
}
```

**blog_post:**
```json
{
  "title": "article/post title",
  "topic": "Swiggy | OpenAI | Stripe | ... (from topic_hint or inferred)",
  "url": "",
  "summary": "1-2 sentence summary of what's interesting",
  "source": "substack | company_blog | news | linkedin | other"
}
```

**general_note:**
```json
{"title": "", "summary": ""}
```

---

## 8. Topic Sub-Folder System

Topics are dynamic — created automatically when new topic values appear. No predefined list.

- `topic` field on `learning` and `blog_post` acts as the sub-folder key
- UI groups cards by topic within the Learnings and Blogs tabs
- New topics auto-appear as a new group when first used
- Topic names are Title-Cased (e.g., "claude" → "Claude", "payments" → "Payments")
- Topics are derived from: (1) topic_hint from input, (2) Claude inference from content

---

## 9. Views (MVP)

| Tab | Content | Sort |
|---|---|---|
| All | Everything | Newest first |
| Jobs | `job_post` | **Oldest first** (urgency) |
| Ideas | `product_idea` | Newest first |
| Reminders | `reminder` | Due date ascending, then newest first |
| Learnings | `learning` | Grouped by topic, newest first within group |
| Blogs | `blog_post` | Grouped by topic, newest first within group |
| Notes | `general_note` | Newest first |

---

## 10. Reminder System

- Background thread polls every 60 seconds
- If reminder `due_date` = today: badge appears on Reminders tab
- No push notifications in MVP (OQ-3: badge is sufficient)
- Reminders marked complete via card action

---

## 11. Project Association (OQ-2)

Product ideas include a `project` field. Claude selects from a config-defined list:

```python
KNOWN_PROJECTS = ["CORTEX", "Marketpulse", "TrueRating", "ClearCart", "MicroManga"]
```

If no strong match → "New Idea". Config is editable in `config.py`.

---

## 12. Out of Scope (MVP)

| Feature | Status |
|---|---|
| ML fine-tuning on override history | P2 Backlog |
| WhatsApp bot input | P2 Backlog |
| Push notifications (browser/mobile) | P1 Backlog |
| Search / natural language query | P1 Backlog |
| Export / integrations | P3 Backlog |
| Multi-device sync | P3 Backlog |
| Manual re-classification UI | P1 Backlog |

---

## 13. Technical Spec

| Attribute | Value |
|---|---|
| Port | 5050 |
| Backend | Python 3, Flask |
| Database | SQLite (WAL mode) |
| AI | claude-opus-4-8 |
| Frontend | Vanilla JS, no framework |
| Scraping | requests + BeautifulSoup4 |
| Env | `.env` with `ANTHROPIC_API_KEY` |

---

## 14. Success Metrics (4-week check)

- Override rate < 20% (classification accuracy)
- 0 missed reminders (reminder fire rate)
- ≥ 5 captures/day (adoption signal)
- Topic sub-folders feel right ≥ 80% of time (qualitative)

---

*Not investment advice. Analytical output for training purposes only.*
