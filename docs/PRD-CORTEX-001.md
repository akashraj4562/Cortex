# PRD-CORTEX-001 — CORTEX v1 (MVP)

**Product:** CORTEX  
**Agent:** Corty  
**Version:** 1.2 — MVP (updated 2026-06-01)  
**Status:** Approved — Live  
**Owner:** Akash Raj

**Changelog:**
- **v1.0:** Original MVP — 6 content types, single-item capture, basic feed.
- **v1.1:** Added `learning` and `blog_post` types. Added URL+keyword input pattern. Added topic sub-folder system.
- **v1.2 (this version):** Taxonomy overhauled to 8 intent-based types (replaced `job_post` → `job_application`, replaced `blog_post` → `food_for_thought` + `build_better`, added `interview_exp`). Multi-item splitting shipped. Explicit keyword overrides and LinkedIn URL pattern inference added. Mobile-first UI with network access. Tab live-count badges.

---

## 1. Problem

Valuable thoughts — job opportunities, product ideas, reminders, interesting reads, things to learn — get lost in WhatsApp drafts, browser tabs, and Notes app. There is no single place to dump a thought and trust it will be organized, surfaced, and acted on.

The deeper problem: most capture tools require you to know what something IS before you can save it. CORTEX inverts this — zero-friction capture first, classification second.

---

## 2. Goal

A single paste interface where any thought goes in raw, and CORTEX classifies, organizes, and surfaces it in the right context — automatically.

One box. Every type of capture. Zero manual taxonomy. Smart topic sub-foldering.

---

## 3. Users

Single user: Akash Raj (personal tool). No auth, no multi-tenancy, no sharing.

---

## 4. Content Types (v1.2 — 8 types)

The taxonomy is **intent-based**, not content-based. Classification answers: "what will Akash DO with this?" not "what type of content is this?"

| Type | Internal key | Icon | Intent | Trigger examples |
|---|---|---|---|---|
| **Job Application** | `job_application` | 💼 | Apply when ready | LinkedIn job post, hiring announcement, JD |
| **Food for Thought** | `food_for_thought` | 🍽️ | Read, reflect, stay informed | Industry news, company stories, LinkedIn posts, Substack, product launches |
| **Product Craft** | `build_better` | 🔨 | Apply to product work | PM frameworks, product teardowns, feature analysis, strategic thinking |
| **Learning** | `learning` | 🧠 | Actively study or practice | Documentation, tutorials, deep-dives, courses, skill-building |
| **Interview Exp** | `interview_exp` | 🎯 | Use in interview prep / company research | Interview experiences, company culture stories, hiring manager perspectives |
| **Reminder** | `reminder` | ⏰ | Act by a specific time | Tasks, deadlines, meetings, follow-ups |
| **Product Idea** | `product_idea` | 💡 | Build or explore later | Feature concepts, business ideas, CORTEX/Marketpulse improvements |
| **General Note** | `general_note` | 📝 | Reference later | Anything that doesn't fit a more specific intent |

**Key distinctions:**
- `food_for_thought` = passive consumption (read, reflect). `build_better` = active application (USE in product work).
- `learning` = skill-building (Claude API, React, prompting). `build_better` = PM application (strategy, frameworks).
- `interview_exp` = career navigation (interview prep, company research). `job_application` = a specific opening to apply to.
- Default when uncertain about a LinkedIn post: `food_for_thought`.

---

## 5. Core Flow

```
User pastes input into single box
    ↓
Splitter: detect multi-item input (WhatsApp timestamps, double-newline)
  Single item  → _process_one()
  Multiple items → _process_one() × N, return {cards: [...]}
    ↓
Input Pattern Detection (per item):
  Pattern A: URL only          → scrape URL
  Pattern B: URL + keyword(s)  → scrape URL, extract keyword as topic_hint
  Pattern C: text only         → use as-is
    ↓
Explicit type keyword check:
  If input contains a keyword mapping (e.g. "job", "interview", "build") → override type
    ↓
Claude (claude-opus-4-8) classifies with full context:
  {type, confidence, rationale, metadata{...topic...}, tags}
    ↓
confidence ≥ 0.70 → auto-classify → store → render card
confidence < 0.70 → store as "unclassified" → render "help me classify" card
    ↓
Feed updates live; tab counts refresh
```

---

## 5b. Input Pattern Detection

```
Input: "https://example.com/article"
→ Pattern A: URL only. scrape + classify.

Input: "https://example.com/article Claude"
→ Pattern B: URL + keyword "Claude". scrape + classify with topic_hint="Claude".

Input: "Build a chrome extension that tracks..."
→ Pattern C: Text. classify directly.

Input: "Job\nhttps://linkedin.com/jobs/123"
→ Explicit keyword "Job" → override type = job_application, regardless of Claude output.
```

**Detection rule:** If input starts with `http://`, `https://`, or `www.`, split on first whitespace. Everything after the URL = topic_hint. URL is scraped.

---

## 5c. Explicit Type Keywords (override layer)

These keywords, if present in the input, override Claude's classification regardless of confidence:

| Keyword(s) | Overrides to |
|---|---|
| job, jobs, job post, hiring, apply | `job_application` |
| interview, interviews | `interview_exp` |
| remind, reminder, remindme | `reminder` |
| idea, product idea | `product_idea` |
| note, save | `general_note` |
| learn, learning | `learning` |
| build, build better, pm | `build_better` |
| food, thought, read, fft | `food_for_thought` |

**Rule:** Explicit keywords are checked before Claude is called. If matched, Claude still runs but the type field is locked.

---

## 5d. LinkedIn URL Pattern Inference

When a LinkedIn URL is present and no explicit keyword overrides, URL pattern determines a default type that Claude can confirm or override:

| URL pattern | Default type |
|---|---|
| `linkedin.com/jobs/` | `job_application` |
| `linkedin.com/posts/` | `food_for_thought` |
| `linkedin.com/pulse/` | `food_for_thought` |
| `linkedin.com/activity-` | `food_for_thought` |

Substack URLs (`*.substack.com`) → default `food_for_thought`.

---

## 5e. Multi-Item Splitting (shipped v1.2)

The splitter detects multi-item input and processes each independently:

- **WhatsApp iOS timestamps:** `HH:MM AM/PM` pattern between items
- **WhatsApp global timestamps:** `DD/MM/YYYY, HH:MM` pattern
- **Double-newline break:** Two or more consecutive blank lines between items

Each detected item is classified and stored separately. The API returns `{cards: [...], count: N}` for multi-item captures. The UI prepends all cards simultaneously.

---

## 6. Server-Driven UI Contract

Backend returns a card JSON spec. Frontend is a pure renderer — no display logic in JS.

```json
{
  "id": 1,
  "type": "food_for_thought",
  "confidence": 0.88,
  "rationale": "Industry post about Swiggy's new feature, interesting read",
  "metadata": {
    "title": "Swiggy's new instant delivery feature",
    "topic": "Swiggy",
    "url": "https://...",
    "summary": "Swiggy launches 10-minute grocery delivery in tier-2 cities",
    "source": "company_blog"
  },
  "tags": ["swiggy", "delivery", "product"],
  "created_at": "2026-06-01 10:30:00",
  "display": {
    "title": "Swiggy's new instant delivery feature",
    "subtitle": "Swiggy · Food for Thought",
    "icon": "🍽️",
    "color": "#E8600A",
    "label": "Food for Thought",
    "actions": ["archive", "open_url"]
  }
}
```

---

## 7. Classification Metadata Schemas

Claude returns structured JSON for each type. `topic` is the key sub-folder field — present on `food_for_thought`, `build_better`, `learning`, and `interview_exp`.

**job_application:**
```json
{"company": "", "role": "", "location": "", "url": "", "deadline": null, "seniority": ""}
```

**food_for_thought:**
```json
{
  "title": "post/article title",
  "topic": "topic area (e.g. Swiggy, Google Maps, AI — from topic_hint or inferred)",
  "url": "",
  "summary": "1-2 sentences on what's interesting",
  "source": "linkedin|substack|company_blog|news|other"
}
```

**build_better:**
```json
{
  "title": "what the framework/idea is",
  "topic": "topic area (e.g. Google Maps, Product Strategy)",
  "url": "",
  "summary": "what Akash will apply from this",
  "source": "linkedin|substack|other"
}
```

**learning:**
```json
{
  "title": "what to learn",
  "topic": "skill area (e.g. Claude, AI Agents, Prompting, React)",
  "url": "",
  "summary": "what Akash will learn or improve"
}
```

**interview_exp:**
```json
{
  "title": "company or topic",
  "topic": "company or domain (e.g. Google, Swiggy, PM Interviews)",
  "url": "",
  "summary": "what's relevant for interviews or career navigation"
}
```

**reminder:**
```json
{"task": "", "due_date": "YYYY-MM-DD or null", "priority": "high|medium|low", "recurrence": null}
```

**product_idea:**
```json
{"title": "", "project": "CORTEX|Marketpulse|TrueRating|ClearCart|MicroManga|New Idea", "core_insight": "", "one_liner": ""}
```

**general_note:**
```json
{"title": "", "summary": ""}
```

---

## 8. Topic Sub-Folder System

Topics are dynamic — created automatically when new topic values appear. No predefined list.

- `topic` field on `food_for_thought`, `build_better`, `learning`, and `interview_exp` acts as the sub-folder key
- UI groups cards by topic within those tabs
- New topics auto-appear as a new group on first use
- Topic names are Title-Cased (e.g., "claude" → "Claude", "payments" → "Payments")
- Source of topic: (1) topic_hint from user input, (2) Claude inference from content

---

## 9. Views (v1.2)

| Tab | Content type | Sort | Grouped? |
|---|---|---|---|
| All | Everything | Newest first | No |
| 💼 Jobs | `job_application` | Oldest first (urgency) | No |
| 🍽️ Food for Thought | `food_for_thought` | Newest first within group | By topic |
| 🔨 Product Craft | `build_better` | Newest first within group | By topic |
| 🧠 Learnings | `learning` | Newest first within group | By topic |
| 🎯 Interviews | `interview_exp` | Newest first within group | By topic |
| ⏰ Reminders | `reminder` | Due date ascending, then newest | No |
| 💡 Ideas | `product_idea` | Newest first | No |
| 📝 Notes | `general_note` | Newest first | No |

**Tab counts:** All tabs show a live count of active (non-archived, non-completed) captures. Counts refresh after every capture, archive, and complete action, and on a 60-second poll. Reminders tab shows a red badge for items due today.

---

## 10. Reminder System

- Background thread polls every 60 seconds
- If reminder `due_date` = today: red badge appears on Reminders tab
- No push notifications in v1 (badge is sufficient for single-user personal tool)
- Reminders marked complete via card action → removed from feed, badge decrements

---

## 11. Project Association

Product ideas include a `project` field. Claude selects from a config-defined list:

```python
KNOWN_PROJECTS = ["CORTEX", "Marketpulse", "TrueRating", "ClearCart", "MicroManga"]
```

If no strong match → "New Idea". Config is editable in `config.py`.

---

## 12. Technical Spec

| Attribute | Value |
|---|---|
| Port | 5050 |
| Backend | Python 3, Flask |
| Database | SQLite (WAL mode) — `data/cortex.db` |
| AI model | `claude-opus-4-8` |
| Frontend | Vanilla JS, no framework |
| Scraping | requests + BeautifulSoup4 |
| Env | `.env` with `ANTHROPIC_API_KEY` |
| Network access | `host=0.0.0.0` — accessible on local network (phone + Mac same URL) |
| Confidence threshold | 0.70 (below → `unclassified`) |
| Content types | 8 active + `unclassified` fallback |

**DB schema (captures table):**
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
raw_input    TEXT    NOT NULL
content_type TEXT    NOT NULL DEFAULT 'unclassified'
confidence   REAL    NOT NULL DEFAULT 0.0
rationale    TEXT
metadata     TEXT    NOT NULL DEFAULT '{}'   -- JSON blob, type-specific
tags         TEXT    NOT NULL DEFAULT '[]'   -- JSON array
completed    INTEGER NOT NULL DEFAULT 0
archived     INTEGER NOT NULL DEFAULT 0
created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
```

---

## 13. Out of Scope (v1)

| Feature | Backlog status |
|---|---|
| ML fine-tuning on override history | P3 |
| WhatsApp bot input | P2 |
| Push notifications (browser/mobile) | P1 |
| Search / natural language query | P1 |
| Export / integrations | P3 |
| Multi-device sync | P3 |
| Manual re-classification UI | P1 |
| Thinking Mirror (attention pattern surfacing) | Phase 2 (500+ captures required) |
| Private Social Graph (team overlap) | Phase 3 |

---

## 14. Success Metrics (4-week check)

| Metric | Target | How to measure |
|---|---|---|
| Classification override rate | < 20% | Manual review of last 20 low-confidence captures |
| Missed reminders | 0 | Reminder badge fires on due date |
| Capture rate | ≥ 5/day | `SELECT COUNT(*), DATE(created_at) FROM captures GROUP BY DATE(created_at)` |
| Topic sub-folders feel right | ≥ 80% qualitative | Owner review of grouped tabs |
| Unclassified rate | < 10% | `SELECT COUNT(*) FROM captures WHERE content_type = 'unclassified'` |

---

*Not investment advice. Analytical output for training purposes only.*
