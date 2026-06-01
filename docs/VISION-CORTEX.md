# CORTEX — Product Vision Document

**Version:** 2.1  
**Date:** 2026-06-01  
**Author:** Akash Raj  
**Status:** Living Document  
**Changelog v2.1:** Added CORTEX as Public Platform section (GitHub analogy, HR manager use case, CORTEX Recruiter revenue tier). Expanded Vector H (Intent Profile) with public profile layer and HR buyer persona. Updated moat with Public Profile Depth and Recruiter Network Effect. Added P7 (Public Platform) to phases table. Added 10-year success horizon.  
**Changelog v2.0:** Added communal boards, intent profiling, ambient capture, Slack integration, and pre-meeting ideation. Expanded the causal chain. Added three new expansion vectors (G, H, I). Added Surface Area model. Updated moat and phase table.

---

## North Star

> **CORTEX is the operating system for what humans actually pay attention to — and what they intend to do about it.**

Not what people say they care about. Not their job title. Not their LinkedIn endorsements.  
What they *actually* capture, return to, and act on — day after day. Across every surface they inhabit: a browser tab, a Slack message, an email they can't reply to yet, a YouTube video they want to share with friends.

---

## The Problems Worth Solving

### 1. Intent Loss — The Most Expensive Invisible Problem

You read an email on your commute. The sender needs a response with Q2 data you don't have on your phone. You can't reply now. Your options: mark as unread (forgotten in 48 hours), star it (lost in 200 starred emails), write a sticky note (analog, no reminder), or make a mental note (gone before you reach a laptop).

None of these are intelligent. All of them fail. The intent — "reply to Priya with the Q2 revenue breakdown" — dies in transit between the moment you formed it and the moment you could act on it.

This happens a dozen times a day, to every knowledge worker. It costs hours per week in re-discovery, missed threads, and the cognitive tax of carrying half-formed intentions mentally.

### 2. Thought Capture — Valuable Ideas Die in Transit

A PM sees a sharp product teardown on LinkedIn at 9am. Two taps to save, gone by noon. A job post surfaces at the right moment, sits in a browser tab for three days, expires. A product idea sparked mid-commute gets half-typed into a Notes app, never revisited. A YouTube on getting better at badminton gets lost in browser history.

Tools are either too structured (Notion forces taxonomy before you understand what something is) or too lossy (WhatsApp self-chats have no recall mechanism). Nothing sits in between: **raw capture + intelligent organization**.

### 3. Pre-Meeting Ideation Waste — Teams Generate Ideas in the Wrong Room

A Search Product team meeting starts. The agenda: brainstorm ideas to improve the product. For the first 45 minutes, everyone sits around a whiteboard generating ideas — ideas that each person had already formed, individually, across the prior two weeks, in different physical and mental contexts. On a commute. In a 1:1. Reading a competitor's changelog at 11pm.

Those ideas weren't captured anywhere shared. So the team reconvenes and restarts from zero. The meeting is not a synthesis session — it's a recall exercise. The most creative individual thoughts never make it into the room because they were lost before the meeting happened.

### 4. Group Intelligence — Community Context Without Group Chat Noise

You're in a badminton group with friends. You find a great training video. You want to share it. Your options: send to the WhatsApp group (noise for everyone, buried in 200 other messages), share individually (effort), post to Instagram (wrong audience). None of these share with *context* — they just broadcast.

What if pushing that video to CORTEX meant it automatically reached the people for whom it's relevant, based on shared context? The badminton group gets it. Your work colleagues don't. No manual routing. Context does the work.

### 5. Institutional Knowledge Loss — What the Org Knows Walks Out the Door

The knowledge that actually matters in a product organization lives nowhere. It's in a Slack thread no one can find, a document shared once and forgotten, a retiring PM's head. Teams reinvent constantly because there's no ambient record of what colleagues were paying attention to, what shaped a decision, or what someone learned from a failure.

---

## The Core Insight — Expanded

**Attention is the most honest signal of value. Intent is the most actionable.**

What a person captures unprompted tells you what they know. What they intended to do with it tells you what they're becoming. The gap between stated preference (résumé, profile) and revealed preference (attention + intent) is where trust breaks down in hiring, team formation, and knowledge markets.

CORTEX closes that gap in two layers:
- **Attention layer:** what you chose to pay attention to, over time
- **Intent layer:** what you meant to do — reply to, learn from, share with, act on — when you couldn't act immediately

Together, these form something no profile can claim: a behavioral record of who you actually are, built one unforced moment at a time.

---

## Where CORTEX Goes: The Causal Chain

```
Phase 1: Personal Tool
  ↓  Single user. Paste box. Corty classifies. Corpus grows.
     Capture habit forms — the only precondition that matters.

Phase 2: Thinking Mirror
  ↓  CORTEX reflects your attention patterns back to you.
     "You've saved 23 things about Swiggy's ops model over 6 months."
     "Your idea backlog is 78% delivery-adjacent."
     "You have 14 unacted intents older than 7 days."

Phase 3: Ambient Capture
  ↓  The capture surface expands beyond the browser tab.
     Corty joins Slack. Gmail integration captures email intents.
     Browser extension captures from any webpage.
     You capture wherever you are — not just when you're at a desk.

Phase 4: Communal Boards
  ↓  Opt-in group contexts. Context-aware relay.
     Badminton group captures go to the badminton group.
     Search Product team's pre-meeting ideas land in a shared board.
     The right content reaches the right people automatically — no manual routing.

Phase 5: Private Social Graph
  ↓  Opt-in signal sharing within a trusted team.
     "Three of you are all reading about the same pricing pattern."
     "No one on the team is paying attention to compliance risk."
     Overlap detected without raw capture exposure.

Phase 6: Observational Expertise Graph
  ↓  Revealed-preference reputation, not stated-preference credentials.
     You become findable for what you actually know.
     Intent Profile: what you've been moving toward, not just where you've been.

Phase 7: Expertise Market
  ↓  The graph enables routing: who should review this spec?
     Who should interview this candidate? Who has actually solved this?

Phase 8: Org Memory Infrastructure
  ↓  AI agents query CORTEX to find human context before acting.
     The corpus becomes the org's long-term memory layer.
     Any app can push intent to CORTEX via API.
```

Each phase unlocks the next. Phase 3 (Ambient Capture) requires Phase 1 habit. Phase 4 (Communal Boards) requires Phase 3's capture surface. You cannot seed Phase 6 retroactively — the corpus must be real.

---

## The Nine Expansion Vectors

### Vector A — Team Idea Pollination
**What:** Surface serendipitous overlap across a team's private capture streams.  
**The concrete case:** A Search Product team has a meeting next Thursday. Instead of spending the first 45 minutes generating ideas from scratch, every member has been dropping observations into a shared CORTEX board for two weeks. The meeting starts with 30 ideas already structured, tagged, and ready for evaluation. The meeting becomes a synthesis session, not a recall exercise.  
**The unlock:** The best ideas form in different places — physical and mental. CORTEX captures them where they form, not where the meeting happens.

### Vector B — Cross-Functional Translation
**What:** The same captured item surfaces differently for different roles.  
**How it creates value:** An engineer saves a technical architecture doc. CORTEX surfaces the product implication to the PM, and the deployment risk to the DevOps lead — same source, role-aware synthesis.  
**The unlock:** Reduced translation cost across the org; fewer "did anyone think about X?" moments in reviews.

### Vector C — Decision Provenance
**What:** Track what shaped a decision, not just what the decision was.  
**How it creates value:** Six months after a product call, a new team member asks "why did we choose X?" CORTEX traces the research, the competitive signals, the conversations that informed it.  
**The unlock:** Institutional memory that doesn't walk out the door when senior people leave.

### Vector D — Observational Expertise Graph *(Biggest Structural Bet)*
**What:** A reputation layer built from revealed preference, not stated credential.  
**How it creates value:** Every capture signals what you're paying attention to. Over thousands of captures, a picture emerges — not "PM at Swiggy for 3 years" but "has absorbed 200+ items about on-demand logistics, pricing under uncertainty, and dark store ops."  
**The unlock:** Hiring that finds the person who *actually* knows the domain.  
**Why it's defensible:** LinkedIn can copy the interface. They cannot copy 18 months of your unfiltered attention corpus.

### Vector E — Org Memory as AI Infrastructure
**What:** CORTEX becomes the human-context layer that AI agents query before acting.  
**How it creates value:** Before a Product Staff agent writes a competitive analysis, it queries CORTEX: "What has Akash already observed about this competitor?" The agent's output is grounded in what the team actually knows, not what the internet says.  
**The unlock:** AI that operates with organizational memory, not just training data.

### Vector F — The Private Layer Guarantee
**What:** A hard architectural principle: your personal corpus is never shared without your explicit, per-item consent.  
**How it creates value:** Trust is the only thing that makes people capture honestly. CORTEX must be the safest place you've ever put a thought.  
**The unlock:** Real signal. Everything else depends on this.

---

### Vector G — Communal Boards *(New)*
**What:** Opt-in group contexts where CORTEX automatically routes captures to the right audience based on shared context — without manual addressing.

**The concrete cases:**
- **Badminton group:** You push a badminton training video to your CORTEX mainboard. The context: you're in a "Badminton & Health" group with 5 friends. CORTEX classifies the capture, matches it to the group context, and relays it to the group — without you having to choose who to send it to, when, or through which app.
- **Product team board:** The Search Product team creates a shared CORTEX board for the upcoming feature brainstorm. For two weeks before the meeting, every team member drops observations — articles, competitor screenshots, user feedback snippets — into the board. By the time the meeting happens, 40+ structured ideas are already waiting. The first agenda item is not "let's brainstorm" but "let's prioritize."
- **City events:** A group of friends share a CORTEX board for "things happening in Bangalore." Anyone drops an event link; the group sees it in context.

**The core mechanic:** You capture once. CORTEX routes to the right group based on context, not manual addressing. The intelligence is in the routing, not in the user's effort.

**What makes this different from a group chat:**
| Group chat | Communal Board |
|---|---|
| You choose who gets it | Context model routes it |
| Chronological stream | Classified and tagged |
| No memory | Persistent and searchable |
| Noise for irrelevant members | Only relevant captures reach each group |
| One medium (text/media) | Any capture type (URL, text, intent) |

**The unlock:** Shared ambient intelligence without group chat noise. The right content reaches the right people in the right context — automatically.

---

### Vector H — Intent Profile *(New)*
**What:** Over time, what you've captured, intended, and acted on forms a behavioral profile — not just what you've absorbed (attention), but what you were moving toward (intent).

**The distinction from the Expertise Graph:**
- **Attention corpus** → what you paid attention to. Backward-looking. "What do you know?"
- **Intent profile** → what you meant to do with it. Forward-looking. "What are you building toward?"

**How it forms:**
Every capture carries intent. A job post = intent to apply. A learning article = intent to build a skill. A product idea = intent to build something. An email intent = intent to reply with specific information. Over hundreds of captures, a pattern of intentions emerges: the domains where you're actively building, the gaps you're trying to close, the opportunities you're moving toward.

**Why it matters:**
A CV tells you where someone has been. The Expertise Graph tells you what they know. The Intent Profile tells you what they're becoming. That third layer is where the real signal lives for:
- Hiring: not just "has X done Y" but "X has been actively developing in Y for 9 months — they're arriving at this role with momentum"
- Team formation: who is moving toward the skill the project needs, even if they don't have it yet
- Personal development: CORTEX becomes a mirror for your own trajectory — "here's where your intentions are concentrated, and here's where they're scattered"

**Privacy architecture (non-negotiable):**
The Intent Profile is built locally. It never leaves CORTEX without explicit, opt-in, user-controlled sharing. No profiling without consent. No employer access without explicit sharing. The user controls what is visible, to whom, and for how long.

**The Public Profile Layer:**
When CORTEX becomes a public platform — like GitHub or LinkedIn — users can opt in to making their Intent Profile public. What this produces is unlike anything that exists today:

| Platform | What it shows | Problem |
|---|---|---|
| **LinkedIn** | Where you worked, what you claim | Stated preference; easily gamed; static |
| **GitHub** | What you actually built (code) | Only works for engineers; not applicable to PMs, designers, strategists |
| **CORTEX** | What you actually learned and intended | Revealed preference; behavioral; dynamic; applicable to every knowledge worker |

A PM's CORTEX public profile doesn't say "5 years in product." It says: "Has been paying close attention to on-demand logistics for 14 months. Has captured 43 learning items tagged 'pricing strategy.' Has 12 product ideas in the supply chain space. Has actively been closing a gap in SQL proficiency over the last 8 months." That is a fundamentally different hiring signal.

**The HR Manager use case:**
When CORTEX is public, HR managers and talent acquisition teams gain a new kind of search: not "find me PMs with 5 years of fintech experience" (LinkedIn) but "find me someone who has been genuinely, demonstrably paying attention to fintech for the last 2 years and is actively learning towards it." The intent profile is the signal. The corpus is the proof.

This is the commercial anchor of CORTEX at scale. LinkedIn Recruiter generates ~$4B/year by selling access to stated credentials. CORTEX Recruiter would sell access to revealed credentials — a categorically stronger signal for a market that is deeply tired of CV inflation, keyword stuffing, and endorsed skills no one actually has.

**Privacy architecture (non-negotiable):**
The Intent Profile is private by default. It never goes public without explicit user action. Public profiles show only what the user has chosen to surface — specific domains, specific skills, specific time ranges. The underlying raw corpus (the actual captures) is never exposed. Only the pattern — the attention graph and intent trajectory — is surfaced. The user controls the resolution.

**The unlock:** The gap between stated preference (LinkedIn profile, CV) and revealed preference (attention + intent) is where trust collapses in professional contexts. The Intent Profile closes that gap — for the first time, with proof.

---

### Vector I — Ambient Capture *(New)*
**What:** The CORTEX capture surface expands to any context where intents form — not just a browser tab at a desk.

**The core insight:** Intents don't form when you're at a desk with a browser tab open. They form on a commute, in a meeting, reading an email, watching a video, scrolling Slack. The capture tool must be where the intent is — not where it's convenient for the product.

**The surfaces:**

**Slack (Phase 3 — first expansion):**
Corty joins as a Slack app. You share something with @Corty: a link, a note, a quick "remind me to do X tomorrow." Corty classifies it, adds it to your personal CORTEX, and if it's relevant to a shared board, routes it there. One natural action in an app you're already using. Zero context switch.

**Gmail / Email (Phase 3):**
You read an email. You can't reply now — you need Q2 data you don't have on your phone. Instead of marking as unread (forgotten) or making a mental note (lost), you tap "CORTEX this." You tell it: "remind me to reply with Q2 revenue breakdown — check every morning until done." CORTEX captures: the intent, the email thread reference, the specific information needed, and the reminder frequency. When you have the data, CORTEX reminds you. It doesn't stop reminding at a fixed time — it persists at the frequency you set until you mark it done.

**Browser Extension (Phase 3):**
Right-click on any text, image, or page. "Save to CORTEX." The URL, the selected text, and the page context are captured and classified — without opening a new tab, without navigating anywhere.

**Mobile — Share Sheet (Phase 3):**
From any app on mobile, tap Share → CORTEX. The item is captured, classified, and synced. No separate CORTEX app open required.

**Voice (Phase 4):**
"Hey Corty, remind me to follow up with Vikas about the WizCommerce proposal on Thursday." Voice → transcription → classification → reminder. The intent forms out loud; CORTEX captures it.

**API — Any App (Phase 5+):**
CORTEX exposes a capture API. Any application can push an intent or capture to CORTEX. The personal OS for attention becomes infrastructure: email clients, calendar apps, project management tools, and AI agents all route intents through CORTEX.

**The Gmail example in full:**
> You're on the metro. You open Gmail. You see Priya's message asking for the Q2 revenue breakdown. You can't reply — the data is on your laptop. Your current options: mark as unread, star it, mental note.
>
> With CORTEX: you tap "Remind me via CORTEX." You type: "Reply to Priya — Q2 revenue breakdown. Check every morning." CORTEX captures: Priya's thread, your intended response, and your preferred reminder frequency. Every morning, your CORTEX shows: "Intent pending: Reply to Priya with Q2 data." It stays there until you mark it complete. You never lose the intent. You never miss the thread. You never carry it mentally.

**Why this is different from existing tools:**
| Tool | Problem |
|---|---|
| Mark as unread | Gets buried; no context preserved |
| Star / flag | No reminder; no context |
| Calendar invite | Wrong tool for non-time-bound intents |
| Sticky note | No intelligence; no reminder |
| Mental note | Gone within 24 hours |
| CORTEX intent | Captures context, persists, reminds at custom frequency, closes the loop |

---

## CORTEX as Public Platform — The GitHub Moment

At the personal level, CORTEX is a private tool. At the public level — when users opt in — it becomes professional infrastructure. This is the GitHub moment for knowledge workers.

**The analogy:**

GitHub launched as a code hosting tool. It became a professional identity platform — your GitHub profile is now more credible to a hiring engineer than your CV. Not because GitHub designed it that way, but because the corpus of actual work became the most honest signal of capability. Senior engineers stopped updating their résumés. Their GitHub profile said it all.

CORTEX follows the same arc — for every knowledge worker, not just engineers:
- A product manager's CORTEX profile shows their genuine learning trajectory, their attention patterns, their product ideas, their intent gaps
- A designer's CORTEX profile shows the inspiration they've absorbed, the UX problems they've been thinking about, the craft they've been developing
- A strategist's profile shows the market signals they've been tracking, the frameworks they've been internalizing, the decisions they've been studying

**What the HR manager sees:**

Today, hiring a senior PM involves: a CV (stated), a LinkedIn (stated + endorsed), a portfolio (curated, may not be current), interviews (performs under pressure, may not reflect day-to-day thinking).

With a public CORTEX profile, a hiring manager sees:
- *Domain attention:* "This candidate has been paying attention to payments infrastructure for 22 months — not as a job title, but as sustained curiosity and learning."
- *Intent trajectory:* "They have 8 product ideas in the B2B SaaS space in the last quarter. They're actively building toward this."
- *Skill gap closures:* "They identified a gap in financial modeling 6 months ago and have been systematically capturing learning content in that area since."
- *Depth vs. breadth:* "Are they a specialist (deep attention in one domain) or a generalist (broad but consistent attention across many)?"

None of this is self-reported. All of it is earned through behavior — one capture at a time, when no one was watching.

**The revenue architecture:**

| Tier | User | What they get | Revenue model |
|---|---|---|---|
| **Personal (Free)** | Individual user | Private corpus, personal classification, 8-tab feed | Free — builds the corpus |
| **Pro** | Power user | Public profile (opt-in), ambient capture (Slack, Gmail, browser), Thinking Mirror | Subscription |
| **Team** | Small teams (2–20) | Communal boards, pre-meeting ideation, overlap detection | Per-seat subscription |
| **Enterprise** | Orgs (50+ users) | Org memory, decision provenance, role-aware synthesis, admin controls | Enterprise contract |
| **CORTEX Recruiter** | HR managers & talent teams | Search public Intent Profiles by attention domain, intent trajectory, skill gap closures | Seat-based access (like LinkedIn Recruiter) |

The Recruiter tier is the highest-value monetisation layer. A company paying $10,000/year for LinkedIn Recruiter access to stated credentials will pay the same — or more — for access to revealed credentials that are demonstrably harder to fake.

**The network effect that powers it:**

Every user who makes their profile public makes CORTEX Recruiter more valuable for every HR manager. Every HR manager who uses CORTEX Recruiter gives every user more reason to maintain a public profile. This is the same loop that made LinkedIn indispensable — except CORTEX's signal is behaviorally grounded, which makes the network effect compounding rather than commoditising.

LinkedIn's moat degraded because stated credentials inflated. Endorsements became meaningless. Keywords got stuffed. The signal rotted as the network grew. CORTEX's moat strengthens as it grows — because behavioral signals are harder to inflate at scale. The corpus takes years to build and cannot be seeded retroactively.

---

## The Moat

| Layer | What It Is | Why It's Hard to Copy |
|---|---|---|
| **Capture Habit** | Daily use makes the corpus real | Requires months of friction-free UX; can't be retroactively seeded |
| **Corpus Depth** | Thousands of unfiltered attention signals | Only earned over time; synthetic data doesn't substitute |
| **Intent Signal** | Forward-looking behavioral profile | Forms over hundreds of acted and unacted intents; no shortcut |
| **Surface Network** | Slack, Gmail, browser, mobile — everywhere intent forms | More surfaces = more habit = more data = harder to switch |
| **Overlap Graph** | Shared captures across a team | Network effect; value compounds as more team members join |
| **Public Profile Depth** | Behavioral credentials visible to employers | Years of corpus; impossible to seed retroactively; gets stronger with time |
| **Recruiter Network Effect** | Every public profile makes Recruiter more valuable; every hire makes profiles more credible | Bidirectional flywheel — same loop that made LinkedIn indispensable, but with stronger signal |
| **Revealed Reputation** | Expertise + intent built from behavior, not credentials | Cannot be gamed by keyword stuffing or endorsement inflation |

**GitHub shows what you built. LinkedIn shows where you worked. CORTEX shows what you actually learned and what you're becoming** — proved by what you chose to pay attention to and act on, unprompted, when no one was watching.

---

## What CORTEX Is and Is Not

**CORTEX IS:**
- A raw capture layer: anything goes in, Corty organizes it
- A personal intelligence mirror: your attention and intent reflected back
- A communal intelligence layer: group contexts, shared boards, context-aware relay
- An ambient capture surface: wherever you are, wherever intent forms
- A privacy-first system: your corpus is yours; sharing is always explicit

**CORTEX IS NOT:**
- A note-taking app: Notion and Obsidian are for structured thinking. CORTEX is for raw capture. You never touch taxonomy.
- A social network: there is no feed, no follower count, no engagement metric, no performance. Sharing is always opt-in, granular, and purposeful.
- A search engine: web crawlers index the internet. CORTEX indexes *you*. The value is human curation, not comprehensiveness.
- A group chat: communal boards route by context, not by broadcast. The intelligence is in the routing.
- A replacement for judgment: CORTEX surfaces patterns and routes intents. The human decides; CORTEX ensures they decide with full context and zero lost threads.

---

## The Biggest Single Bet

**Vector D + Vector H together: Observational Expertise Graph × Intent Profile.**

Separately, each is valuable. The Expertise Graph shows what someone knows. The Intent Profile shows what they're becoming. Together, they produce something that has never existed: a **dynamic, manipulation-resistant, behaviorally-grounded professional identity** — updated every time someone captures a thought, not every time they update a CV.

The professional reputation system as we know it is broken in two ways:
1. It measures inputs (where you studied, who you worked for), not outputs (what you actually know)
2. It's static (updated when job-hunting, not when learning)

CORTEX is the first system that can fix both. The corpus updates continuously. The profile reflects what you're learning, not just where you've been. And because it's built from unforced captures rather than self-reported achievements, it cannot be gamed.

That is a new product category. Not a better LinkedIn. Not a smarter CV. A behavioral record of professional growth — for the first time, with proof.

---

## The Phases in Practice

| Phase | Trigger | Core Product Change | Moat Established |
|---|---|---|---|
| **P1: Personal (Now)** | 1 user, daily habit | Single paste box, AI classification, 8-tab feed | Capture habit |
| **P2: Thinking Mirror** | Corpus > 500 items | Attention pattern surfacing, topic heatmaps | Corpus depth |
| **P3: Ambient Capture** | Slack + Gmail integration | Corty on Slack, email intent capture, browser extension | Surface network |
| **P4: Communal Boards** | 2–5 person group opts in | Group contexts, context-aware relay, pre-meeting boards | Overlap graph begins |
| **P5: Private Social Graph** | 5–20 person team | Overlap detection, role-aware synthesis, decision provenance | Overlap graph matures |
| **P6: Expertise Graph** | Cross-team or org | Observational expertise routing + Intent Profile (opt-in) | Reputation signal |
| **P7: Public Platform** | CORTEX goes public (like GitHub) | Public Intent Profiles; CORTEX Recruiter for HR; behavioral credentials | Public profile depth + recruiter flywheel |
| **P8: Expertise Market** | Cross-org or open | Problem routing, expertise findability, skill gap closing | Revealed reputation moat |
| **P9: Org Memory** | AI-native orgs | Org memory API for AI agents; capture as infrastructure | Ecosystem lock-in |

---

## Success at Each Horizon

**12 months:** One user, 1,000+ captures. Classification accuracy > 85%. At least 3 times where CORTEX surfaces a connection the user would not have made themselves. Zero lost intents (all reminders completed or consciously dismissed).

**3 years:** A team of 5–10 using CORTEX with communal boards and opt-in sharing. Pre-meeting ideation boards reduce meeting brainstorming time by > 50%. Slack integration is the primary capture surface (more captures via Slack than the web app). At least one case where the overlap graph surfaces a missed alignment before it became a missed opportunity.

**7 years:** The Observational Expertise Graph exists alongside the public Intent Profile. A PM can be found not because of their title, but because CORTEX knows they've been paying attention to on-demand logistics for four years and have been actively closing skill gaps in that domain for six months. The Intent Profile is a recognized professional credential — employers ask for it, candidates share it willingly.

**10 years:** CORTEX Recruiter is a category. HR managers at forward-thinking companies no longer post jobs and wait — they search public CORTEX profiles for candidates whose attention and intent trajectories match what the role requires. A candidate's CORTEX profile is as expected in a job application as their LinkedIn. The behavioral credential is standard. CV inflation has a natural ceiling for the first time — because the corpus cannot be faked.

---

## The One-Sentence Pitch

*CORTEX is where professionals capture what they actually care about and what they intend to do about it — and over time, that corpus becomes the most honest record of who they are, what they know, what they're building toward, and who they'd work best with.*

---

*This is a living document. Each phase must be validated before the next is built. Do not build communal boards before the personal capture habit is real. Do not build the Intent Profile before the attention corpus is deep. The phases are a sequence, not a menu.*
