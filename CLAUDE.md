# CLAUDE.md — CORTEX Product Staff

> CORTEX's dedicated product team. Focused exclusively on building the system described in `docs/VISION-CORTEX.md`.
> North star: **CORTEX is the operating system for what humans actually pay attention to.**

---

## Current phase: Phase 1 — Personal Tool

Single user (Akash). Capture habit forming. Private corpus growing. Every feature decision must serve Phase 1 stickiness — because Phase 2 (Thinking Mirror) only works when the corpus is real and deep.

**Stack:** Python/Flask · SQLite WAL (`data/cortex.db`) · claude-opus-4-8 (Corty) · Vanilla JS · Port 5050

**Start server:** `python3 app.py`

**Run tests:** `python -m pytest tests/ -v`

---

## The CORTEX team

| Role | Agent | Mandate | When to invoke |
|---|---|---|---|
| **Head of Product** | `product-manager` | Shapes ideas into PRDs grounded in VISION-CORTEX.md. Owns phase-gate roadmap and classification accuracy as the primary quality signal. | First — every idea comes here. |
| **AI Engineer** | `ai-engineer` | Owns Corty's classification engine — the system prompt, confidence scoring, keyword map, URL patterns, and future embedding/RAG architecture. | When classification accuracy degrades, when a new content type is added, when the model needs to change, when Phase 2 AI architecture is designed. |
| **Prompt Engineer** | `prompt-engineer` | Owns Corty's `_SYSTEM` prompt in `classifier.py`. Converts Tech Lead plans into atomic implementation prompts. Gets features working in ≤3 iterations. | When a classification is wrong and the fix is in the prompt. After Tech Lead produces an implementation plan. |
| **Tech Lead** | `tech-lead` | Knows the Flask/SQLite/Vanilla JS stack. Produces implementation plans, reviews PRDs for technical feasibility, architects CORTEX's scaling path through Phase 3+. | After PM has a PRD. When a schema change is proposed. When Phase 2+ architecture needs to be designed. |
| **UX Designer** | `uiux-designer` | Owns the capture interface, card design, tab navigation. Designs for zero friction at input and maximum clarity at recall. | When a new capture pattern is introduced, when a new card type is designed, when the feed needs a new view. |
| **Data Analyst** | `data-analyst` | Measures classification accuracy, capture rate, confidence distribution. Defines the Phase 2 analytics (Thinking Mirror data). | After PRD — validates impact assumptions. On a 2-week cadence — classification accuracy audit. |
| **Causal Systems Analyst** | `causal-systems-analyst` | Builds and maintains the CORTEX Causal Systems Model (CSM). Maps the core capture flywheel (capture habit → corpus → accuracy → Corty trust → habit), the friction kill condition (feature complexity → capture friction → capture rate), and the Phase 2 Thinking Mirror loop (not yet active). Ranks feature candidates by leverage. Enforces phase-gate mechanically: flags Phase 2+ features attempted before Phase 1 loop is stable. Methodology: `product-staff/docs/CAUSAL-SYSTEMS-METHODOLOGY.md`. | When prioritizing feature backlog; when capture rate drops; post-ship calibration; phase-gate enforcement for Phase 2 feature requests. |

---

## How a CORTEX feature session works

```
1. Owner brings idea (any format)
2. PM: phase-gate check → PRD draft (is this Phase 1, 2, or 3+?)
3. AI Engineer: classification impact assessment (does this touch Corty?)
4. Data Analyst: success metric definition + instrumentation plan
5. UX Designer: capture/card UX for the new feature
6. Tech Lead: feasibility review → implementation plan (files + tasks)
7. Prompt Engineer: convert plan → atomic implementation prompts
8. Build → run tests → confirm metrics
9. PM: Gate 8 retrospective → notify Learning Manager for back-propagation
```

---

## Phase gate — enforced by the PM

| Phase | What it enables | Precondition |
|---|---|---|
| **Phase 1** (now) | Capture + classify + 8-tab feed | No precondition — this IS the current state |
| **Phase 2** (Thinking Mirror) | Attention pattern surfacing | 500+ real captures in corpus |
| **Phase 3** (Private Social Graph) | Opt-in team overlap detection | Phase 2 validated + multi-user auth |
| **Phase 4+** | Expertise Graph, Org Memory | Phase 3 validated |

**Rule:** Do not spec or build Phase N+1 before Phase N is validated. Note Phase 2+ ideas in `docs/VISION-CORTEX.md` as Vision Notes, not PRDs.

---

## Implementation gate

No feature ships without:
1. PRD reviewed by the CORTEX team
2. Test plan written before implementation
3. `python -m pytest tests/ -v` — all tests green before and after
4. Classification regression check if `classifier.py` or `config.py` was touched

---

## Trusted research resources

| Source | What it covers | URL |
|---|---|---|
| **MIT DSpace** | Research on human attention, knowledge management, information retrieval, social graphs | https://dspace.mit.edu |
| **MIT CTL** | Knowledge transfer, organisational learning | https://ctl.mit.edu/research |
| **Anthropic Docs** | Claude API, prompt design, tool use, model capabilities | https://docs.anthropic.com |
| **CSCMP** | Supply chain context (for Phase 4+ org memory features) | https://www.supplychainquarterly.com |

---

## Learning bridge — the Learning Manager

The CORTEX team does not operate in isolation. The **Learning Manager** (in main Product Staff) is the bi-directional bridge:

**Forward flow:** When main Product Staff discovers a new pattern (POSITIVE-PATTERNS.md or ANTI-PATTERNS.md), the Learning Manager evaluates its relevance to CORTEX and propagates it to `cortex/docs/learnings/` if relevant.

**Back-propagation:** When CORTEX ships a feature and files a Gate 8 retrospective, the Learning Manager reads it and elevates any generalisable learnings to the main Product Staff catalogue.

**How to trigger:**
- After any CORTEX Gate 8 retrospective: "Learning Manager: run back-propagation from CORTEX — [retrospective file]"
- To pull org learnings into CORTEX: "Learning Manager: run forward propagation to CORTEX"

CORTEX-specific learnings live in `cortex/docs/learnings/` (created by the Learning Manager on first propagation).

---

## How to talk to the CORTEX team

- **New feature:** "PM: take this through the CORTEX flow — [idea]"
- **Classification bug:** "AI Engineer + Prompt Engineer: [input] was classified as [type] but should be [type]. Diagnose and fix."
- **Accuracy audit:** "Data Analyst: run the classification accuracy audit. Pull the last 20 low-confidence captures."
- **Schema change:** "Tech Lead: we need to add [field] to the captures table. Is this safe? What's the migration plan?"
- **UX review:** "UX Designer: design the card for the new [type] content type. Include fallback when no URL is scraped."
- **Phase 2 design:** "AI Engineer + PM: design the embedding architecture for Phase 2. What changes to the data model and classification pipeline?"
- **Learning sync:** "Learning Manager: run back-propagation from CORTEX after [feature] retrospective."

---

## Hard rule — Destructive database operations

Never run `seed`, `truncate`, `drop`, or any destructive database operation without explicit confirmation from the owner. No exceptions.
