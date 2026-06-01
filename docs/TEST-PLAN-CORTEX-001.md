# Test Plan — CORTEX MVP (Gate 3)

**PRD:** PRD-CORTEX-001  
**Date:** 2026-06-01

---

## T1 — Capture & Classification

| # | Test | Input | Expected |
|---|---|---|---|
| T1-01 | Job URL → auto-classify | LinkedIn job URL | type=job_post, confidence≥0.70, company+role populated |
| T1-02 | Job text → auto-classify | Pasted JD paragraph | type=job_post, confidence≥0.70 |
| T1-03 | Product idea → auto-classify | "Build a chrome extension that..." | type=product_idea, project field populated |
| T1-04 | Reminder → auto-classify | "Call Vikas Thursday 4pm" | type=reminder, due_date populated |
| T1-05 | General note → auto-classify | Random thought paragraph | type=general_note |
| T1-06 | Ambiguous input → low confidence | Single ambiguous word | confidence<0.70, renders "help me classify" card |
| T1-07 | Empty input → reject | Empty paste | 400 error, no DB write |
| T1-08 | URL scrape failure → fallback | Invalid URL | Treats raw URL as text, classifies as general_note |

---

## T2 — Feed & Views

| # | Test | Action | Expected |
|---|---|---|---|
| T2-01 | Feed loads | GET / | All captures rendered as cards |
| T2-02 | Jobs view sorts oldest first | GET /jobs | Oldest job post appears first |
| T2-03 | Reminders view sorts by due date | GET /reminders | Earliest due date appears first |
| T2-04 | New capture appears without reload | POST /capture | Card inserts at top of feed (or bottom of jobs) |
| T2-05 | Archive removes from feed | Click archive | Card disappears; GET feed excludes archived |
| T2-06 | Type tabs filter correctly | Click each tab | Only matching type shown |

---

## T3 — Reminder System

| # | Test | Setup | Expected |
|---|---|---|---|
| T3-01 | Due today badge fires | Add reminder due_date=today | Reminders tab shows badge |
| T3-02 | Future reminder no badge | Add reminder due_date=tomorrow | No badge |
| T3-03 | Complete clears badge | Mark reminder complete | Badge clears |
| T3-04 | Background thread runs | Server restart | Thread starts, polls every 60s |

---

## T4 — Database

| # | Test | Action | Expected |
|---|---|---|---|
| T4-01 | SQLite WAL mode active | Read PRAGMA journal_mode | Returns "wal" |
| T4-02 | Capture persists on restart | Add capture, restart server | Capture present on GET / |
| T4-03 | Schema correct | Inspect captures table | All columns present |

---

## T5 — Error Handling

| # | Test | Trigger | Expected |
|---|---|---|---|
| T5-01 | Claude API down | Kill API key temporarily | 503 with user-facing message, no crash |
| T5-02 | Scraper times out | Unreachable URL | Fallback to raw text classification |
| T5-03 | Malformed JSON from Claude | (mock) | Re-classify attempt or unclassified card |

---

## Pass Criteria

All T1 and T2 tests must pass. T3-01 through T3-03 must pass. T4-01 and T4-02 must pass. T5-01 must not crash the server.
