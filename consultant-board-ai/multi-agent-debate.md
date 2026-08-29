# CEO Advisor — GHC Agent Skill Spec

## 1. Overview

### 1.1 What This Is

A **CEO Advisor agent skill** (`/ceo-advisor`) that runs entirely inside **GitHub Copilot Chat (GHC)**. When triggered, it acts as a multi-expert consulting board — clarifying the problem, debating it from multiple expert perspectives, and returning a structured Markdown decision report — all within a single chat session.

**No backend. No custom framework. No infrastructure.** The entire system is a single `SKILL.md` file that GHC reads as its instruction set. GHC plays every agent role itself, sequentially, within one conversation.

### 1.2 Scope

The skill handles **any real-world decision**, not just software:

| Domain | Example Problem |
|--------|----------------|
| **Personal / Life** | Should I change jobs? Should I relocate to another city? |
| **Business** | Should we enter a new market? Should we acquire this company? |
| **Technology** | Should we migrate to microservices? Which cloud provider? |
| **Finance** | Should I invest in X? How should I allocate budget? |
| **Healthcare** | What treatment approach is best for this patient profile? |
| **Policy** | What are the tradeoffs of this regulation? |
| **Product** | Should we build feature A or feature B first? |
| **Career** | Should I pursue an MBA or stay technical? |
| **Family & Children** | Should we have a second child? Which school is right for our kid? Should we relocate with young children? How do we handle custody arrangements? |

The skill is **domain-agnostic**. Expert roles are selected per problem, not hardcoded.

### 1.3 Core Requirements

- **Delivery**: A single `SKILL.md` file — runnable directly in GHC with `/ceo-advisor <question>`
- **No infrastructure**: No API, no database, no backend service, no external orchestration
- **Clarification first**: Before any debate, the skill ensures the problem is fully understood — asks questions if needed, never assumes
- **Web search before reasoning**: Every agent must search for current real-world information before forming a position — no stale knowledge, no invented facts
- **Multi-perspective debate**: GHC plays each expert agent role in turn with a distinct persona, bias, and mandatory output format
- **Structured output**: Returns a complete Markdown decision report inline in the chat — copy-paste ready
- **Configurable roles**: 11 universal expert roles + domain-specific extensions; active roster of 3–5 selected per problem
- **Quality-gated**: Debate runs until explicit stop criteria are met, with a minimum coverage gate before synthesis

---

## 2. User Experience

### 2.1 How It Works (User's Perspective)

```
Step 1  →  User opens VSCode, opens GHC chat panel
Step 2  →  User types: /ceo-advisor Should I migrate to microservices?
Step 3  →  GHC responds with clarifying questions (if the problem is ambiguous)
Step 4  →  User answers the questions
Step 5  →  GHC presents a Problem Brief and asks: "Does this capture your situation?"
Step 6  →  User confirms: "Yes, proceed."
Step 7  →  GHC runs the full debate internally (all agents, all rounds)
Step 8  →  GHC returns the complete Advisory Board Report in the chat
```

### 2.2 Interaction Points

GHC pauses for user input at most **twice** in the entire flow:

| Pause | When | What user does |
|---|---|---|
| **Pause 1** | After Phase 1 clarifying questions (if any) | Answers questions |
| **Pause 2** | After Problem Brief is presented | Confirms or corrects |

Everything else runs to completion without interruption. Phase 2 (method selection), Phase 3 (debate rounds), and Phase 4 (synthesis) execute in a single response.

### 2.3 Trigger Methods

| Method | Syntax | When to use |
|---|---|---|
| Slash command | `/ceo-advisor <problem description>` | Explicit invocation with problem inline |
| Natural language | Any message that is a decision question or trade-off analysis | GHC auto-activates when description matches |

### 2.4 Example Session

```
User:   /ceo-advisor Should I leave my current job to join an early-stage startup?

GHC:    [Phase 1 — Clarify]
        Clarity score: 40/100. I need answers to 4 questions:
        Q1. What is your current financial situation (savings runway)?
        Q2. What stage is the startup (pre-seed / seed / Series A)?
        Q3. What is your equity offer and vesting schedule?
        Q4. What does success look like for you in 3 years?

User:   [answers Q1–Q4]

GHC:    [Phase 1 — Problem Brief]
        Here is my understanding. Does this capture your situation?
        [shows Problem Brief]

User:   Yes, proceed.

GHC:    [Phase 2 — Method Selection]
        Pattern: parliamentary | Rounds: 3
        Agents: Strategist, Financial Analyst, Risk Advisor, Psychologist, Devil's Advocate
        Rationale: Career decision with financial, emotional, and risk dimensions.

        [Phase 3 — Debate]
        ## Round 0 — Independent Positions
        #### Strategist: ...
        #### Financial Analyst: ...
        #### Risk Advisor: ...
        #### Psychologist: ...
        #### Devil's Advocate: ...

        ## Round 1 — Cross-examination
        [agents challenge each other]
        [stop criteria evaluated → continue]

        ## Round 2 — Rebuttal
        [agents refine positions]
        [stop criteria evaluated → soft stops met → debate ends]

        [Phase 4 — Advisory Board Report]
        # Advisory Board Report
        [full structured report with recommendation, pros/cons,
         risk register, confidence score, limitations, transcript]
```

---

## 3. Workflow — 4 Phases

The CEO Agent orchestrates 4 sequential phases. It is not a domain expert — it is a **process intelligence layer** that delegates to specialists.

```
User
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│                     CEO AGENT (Skill)                    │
│                                                          │
│  Phase 1 ──► Clarify       ──► Problem Brief             │
│  Phase 2 ──► Method Select ──► Debate Strategy           │
│  Phase 3 ──► Coordinate    ──► Debate Rounds             │
│  Phase 4 ──► Synthesize    ──► Final Report              │
└──────────────────────────────────────────────────────────┘
```

---

### 3.1 Phase 1 — Clarify

**Goal**: Build a complete, unambiguous Problem Brief before any analysis.

#### 3.1.1 Steps

1. Read the user's input and classify the problem:
   - **Domain** (career, business, technology, finance, family, etc.)
   - **Reversibility** (reversible / partially / irreversible)
   - **Stakes** (low / medium / high)
   - **Time horizon** (immediate / months / years / decades)
   - **Uncertainty level** (low / medium / high / extreme)
   - **Value conflicts** (none / tradeoffs / deep conflicts)
   - **Data availability** (rich data / sparse / none)

2. Compute a **Clarity Score** (0–100): how many of the 7 dimensions above are answered by the user's input?

3. If clarity score < 70: ask **3–5 targeted questions** (High-priority gaps only), then pause for user response.

4. Once answers are received (or score ≥ 70), produce the **Problem Brief**.

5. Show the Problem Brief to the user and pause for confirmation.

#### 3.1.2 Question Categories

| Category | Purpose | Example |
|----------|---------|--------|
| **Context** | Background needed to frame the problem | "What is your current situation / starting point?" |
| **Constraints** | Hard limits experts must respect | "What is your budget / timeline / non-negotiables?" |
| **Success criteria** | What does a good outcome look like? | "How will you know if this decision was right?" |
| **Stakeholders** | Who is affected and whose input matters? | "Who else is impacted by this decision?" |
| **Alternatives** | What options are already on the table? | "What options are you already considering?" |
| **Risk tolerance** | How much downside is acceptable? | "What is the worst outcome you could accept?" |
| **Time horizon** | Short-term vs long-term tradeoffs | "Are you optimizing for 1 year or 5 years?" |

#### 3.1.3 Problem Brief Template

```markdown
## Problem Brief

**Problem Statement** (restated precisely):
[Clear, unambiguous single-paragraph description]

**Domain**: [classification]

**Key Context**:
- [Context point 1]
- [Context point 2]

**Hard Constraints** (must be respected in any recommendation):
- [Constraint 1]
- [Constraint 2]

**Success Criteria** (what does a good decision look like?):
- [Criterion 1]
- [Criterion 2]

**Options on the Table** (known alternatives):
1. [Option A]
2. [Option B]
3. Open (agents may propose new options)

**Stakeholders Affected**:
- [Stakeholder 1 and their interests]

**Risk Tolerance**:
[Description of acceptable downside]

**Time Horizon**:
[Short / Medium / Long term focus]

**Unanswered Questions** (gaps that could not be filled):
- [Question] — agents will not reason about this dimension

**Out of Scope**:
- [What will NOT be considered]

**Confirmed by user**: [Yes / Pending]
```

#### 3.1.4 Clarification Rules

| Rule | Description |
|------|------------|
| **Max loops** | 3 clarification rounds maximum |
| **Min questions** | At least 3 questions in first round |
| **No silent assumptions** | Agents may never silently assume an answer to a skipped question; any inference from incomplete information must be labelled "⚠️ Unverified" and treated as low-confidence |
| **User skip** | If user skips a question, agent asks one targeted follow-up; if still unanswered, flag as a blocker and explain what cannot be advised without it |
| **Force proceed** | If user says "proceed", agents state which questions remain unanswered and explicitly refuse to reason about those dimensions |
| **Brief confirmation** | User must confirm the Problem Brief before debate starts |
| **Brief edits** | User can edit the Problem Brief directly before confirming |

#### 3.1.5 Exit Conditions

Phase 1 ends when:
- User confirms the Problem Brief, OR
- Clarity score ≥ 70 (sufficient to proceed), OR
- 3 clarification rounds exhausted — agents mark which gaps remain open and refuse to reason about those dimensions

---

### 3.2 Phase 2 — Select Method

**Goal**: Choose the optimal debate pattern and agent roster for this specific problem.

The CEO internally consults a **Meta-Methodologist** persona — its only job is to recommend the right method.

#### 3.2.1 Method Selection Matrix

| Problem Type | Pattern | Reasoning |
|---|---|---|
| Binary choice (A vs B) | `adversarial` | Forces steelman of both sides |
| Multi-option comparison | `parliamentary` | Structured positions + rebuttals |
| Risk-heavy / irreversible | `parliamentary` + mandatory Risk Advisor | Ensures downside is fully surfaced |
| Analytical / data-driven | `round-robin` | All agents contribute evidence in parallel |
| Ambiguous / open-ended | `socratic` first, then `round-robin` | Clarify via Socratic before debating |
| High-stakes personal decision | `parliamentary` + Psychologist | Human factor must be weighted |
| Policy / ethical dilemma | `adversarial` + Ethicist | Values conflicts need explicit confrontation |

#### 3.2.2 Output Block

Phase 2 produces a visible configuration block before debate starts:

```
## Debate Configuration
**Pattern**: [parliamentary | adversarial | round-robin | socratic]
**Rounds**: N (2–4)
**Agent roster**: [3–5 agents from the role catalog]
**Always included**: Devil's Advocate
**Rationale**: [one sentence why this configuration fits this problem]
```

#### 3.2.3 Agent Pool Model

The agent pool has two layers:

| Layer | What | Size | When selected |
|---|---|---|---|
| **Full pool** (static) | All available agents defined in the spec | 11 universal + domain extensions | Always available |
| **Active roster** (dynamic) | Subset selected per session | 3–5 agents | Phase 2, based on Problem Brief |

Selection rules:
- Minimum 3, maximum 5 agents on the active roster
- **Devil's Advocate is always included**
- Meta-Methodologist selects from the recommended sets in §4.3
- Can deviate from the lookup table with a written rationale

---

### 3.3 Phase 3 — Debate

**Goal**: Produce genuine multi-perspective analysis through structured disagreement.

#### 3.3.1 Mandatory Pre-Step: Web Search

**Before any agent writes their position**, they must search for current, real-world information relevant to the problem. Every agent response in Round 0 must include at least one cited external source with publication date.

If a fact cannot be verified via search, the agent labels it: `⚠️ Unverified — awaiting clarification` and does not treat it as established.

#### 3.3.2 Round 0 — Independent Positions

Each agent reads the Problem Brief only (no other agent's view) and states:
- Their initial recommendation
- Top 2–3 supporting arguments (with cited evidence)
- Their initial confidence level (as a range, e.g., 60–75%)

#### 3.3.3 Round 1..N — Structured Challenge

Each agent:
1. Identifies the **strongest opposing argument** from the previous round and engages it directly
2. States whether they **maintain or revise** their position (and why)
3. Adds any new argument not yet surfaced (with evidence)
4. Updates their confidence level

**Devil's Advocate rule**: If convergence is forming too early (≥75% agreement), Devil's Advocate **must** argue the minority position even if they agree with the majority.

#### 3.3.4 Debate Patterns (Detailed)

**Parliamentary** (recommended for most decisions):
```
Round 1: Opening Statements — independent positions, no cross-reference
Round 2: Cross-examination — challenge weakest, acknowledge strongest
Round 3: Rebuttal — respond to challenges, state "I maintain" or "I revise"
Round 4: Closing Statements — final position, confidence, top 3 factors
```

**Adversarial** (best for binary choices and risk analysis):
```
Setup: Half argue FOR, half argue AGAINST (roles may not match natural bias)
Round 1: Pro case → Con case
Round 2: Pro rebuts Con → Con rebuts Pro
Round 3: Both sides present revised positions
```

**Socratic** (best for ambiguous or exploratory problems):
```
Setup: Socratic Questioner + Expert Panel
Round 1: Questioner asks 3–5 probing questions
Round 2: Each expert answers from their perspective
Round 3: Questioner identifies contradictions, asks follow-ups
Round 4: Experts reconcile contradictions
```

---

### 3.4 Phase 4 — Synthesize & Report

**Goal**: Produce a structured, self-contained decision report.

#### 3.4.1 Synthesis Steps

1. **Judge Agent** persona reads the full Problem Brief + debate transcript and produces:
   - Strongest arguments from each side
   - Where genuine consensus exists vs performative agreement
   - Unresolved risks that no agent adequately addressed
   - Dissenting views stated fully (not dismissed)

2. **CEO executive layer** adds on top:
   - Plain-language executive summary (2–3 sentences)
   - Confidence score with explicit factor breakdown
   - Top 3 conditions that would change the recommendation
   - Known limitations and blind spots

3. Final report is returned **inline in the GHC chat** as a single Markdown block.

---

## 4. Agent Roles

### 4.1 Universal Expert Roles (11)

These roles can be applied to **any type of problem**:

> **Gap analysis note**: The original 8 roles had blind spots for legal/regulatory exposure, macroeconomic effects, end-user interests, and family/child-specific decisions. Three roles were promoted from domain extensions and one new role added.

| Role | Expertise | Bias | Applicable Domains |
|------|-----------|------|-------------------|
| **Risk Advisor** | Risk identification, probability, mitigation | Risk-averse, sees downside | Any irreversible or high-stakes decision |
| **Financial Analyst** | Individual-level costs, ROI, budget, opportunity cost | Cost-focused on the actor's own position | Business, career, investment, project decisions |
| **Strategist** | Long-term thinking, competitive position, options | Big-picture, may ignore near-term | Business, career, life decisions |
| **Pragmatist** | Execution feasibility, practical constraints, change complexity | Focuses on what is actually doable | Any decision requiring an action plan |
| **Devil's Advocate** | Actively challenges any consensus forming | Contrarian by design | All debates (prevents groupthink) |
| **Ethicist** | Moral implications, stakeholder impact, fairness | Values-focused | Policy, healthcare, AI, org decisions |
| **Data Scientist** | Evidence-based reasoning, statistics, published research | Demands cited data before conclusions | Any domain with measurable outcomes |
| **Psychologist** | Adult human behavior, cognitive biases, motivation, mental health | People-focused on individual/group dynamics | Personal, team, product, UX decisions |
| **Legal Advisor** | Legal exposure, regulatory compliance, rights, liability, contracts | Compliance-first, flags legal risk | Any high-stakes or irreversible decision; cross-border, M&A, healthcare, policy |
| **Economist** | Systemic and macro effects, market dynamics, externalities, incentive structures | Systemic view; may ignore individual constraints | Policy, business market entry, investment, budget allocation |
| **User & Stakeholder Advocate** | Interests, needs, and experience of directly affected parties (end users, children, patients, communities) | Argues for those without a seat at the table | Product, healthcare, family, policy, any decision affecting third parties |

### 4.2 Domain-Specific Role Extensions

When the problem is in a specific domain, add domain roles on top of the 11 universal ones:

| Domain | Additional Roles | Key gaps they fill |
|--------|----------------|--------------------|
| **Software** | Software Architect, Security Analyst, QA Engineer, DevOps Engineer, Tech Lead | Technical implementation depth, infosec |
| **Business** | Marketing Strategist, Operations Expert, HR Consultant | Go-to-market, org ops |
| **Healthcare** | Medical Expert (clinical reasoning), Regulatory Specialist | Clinical knowledge — universals cannot substitute |
| **Finance/Investment** | Portfolio Manager, Tax Advisor, Market Analyst, Behavioral Finance Expert | Asset-class depth, tax optimisation, investor psychology |
| **Personal/Life** | Life Coach, Career Counselor, Relationship Counselor | Life direction, identity, long-term fulfilment |
| **Family & Children** | Child Development Specialist, Family Therapist, Education Advisor, Pediatric Health Expert | Child wellbeing, developmental stages, parenting approaches, schooling |
| **Policy/Government** | Legal Scholar, Sociologist, Public Health Expert | Constitutional law, social dynamics, public health |

### 4.3 Recommended Role Sets by Problem Type

| Problem Type | Core Roles (3-5) | Domain Extensions to add |
|-------------|------------------|---------------------------|
| Career decision (job change, MBA) | Strategist, Financial Analyst, Pragmatist, Psychologist, Devil's Advocate | Career Counselor |
| Business / market entry | Strategist, Financial Analyst, Risk Advisor, Legal Advisor, Economist | Marketing Strategist, HR Consultant |
| Business acquisition / M&A | Strategist, Financial Analyst, Risk Advisor, Legal Advisor, Devil's Advocate | Operations Expert |
| Technology choice | Pragmatist, Risk Advisor, Financial Analyst, Data Scientist, Devil's Advocate | Software Architect, Security Analyst |
| Investment decision | Financial Analyst, Risk Advisor, Data Scientist, Strategist, Legal Advisor | Portfolio Manager, Tax Advisor |
| Life decision (relocate) | Psychologist, Strategist, Financial Analyst, Legal Advisor, Pragmatist | Life Coach |
| Life decision (relationship) | Psychologist, Ethicist, Strategist, Devil's Advocate, User & Stakeholder Advocate | Relationship Counselor |
| Family — should we have children? | Psychologist, Financial Analyst, Ethicist, User & Stakeholder Advocate, Devil's Advocate | Child Development Specialist, Family Therapist |
| Family — parenting / schooling | User & Stakeholder Advocate, Psychologist, Data Scientist, Pragmatist, Devil's Advocate | Child Development Specialist, Education Advisor |
| Family — custody / guardianship | Legal Advisor, User & Stakeholder Advocate, Psychologist, Ethicist, Risk Advisor | Family Therapist |
| Family — relocation with children | Pragmatist, Financial Analyst, User & Stakeholder Advocate, Psychologist, Legal Advisor | Child Development Specialist, Education Advisor |
| Healthcare — treatment decision | Data Scientist, Risk Advisor, Ethicist, User & Stakeholder Advocate, Devil's Advocate | Medical Expert, Regulatory Specialist |
| Policy / regulatory | Ethicist, Economist, Data Scientist, Legal Advisor, User & Stakeholder Advocate | Legal Scholar, Sociologist, Public Health Expert |

### 4.4 Agent Persona Specification

Since GHC plays all agents itself, `SKILL.md` must define enough persona detail per agent to produce genuinely differentiated responses — not just renamed versions of the same analysis.

For each agent, SKILL.md specifies 7 attributes:

| Attribute | Purpose | Example (Risk Advisor) |
|---|---|---|
| **Core bias** | What lens this agent uses | "You are risk-averse. You see the downside first." |
| **Mandatory output elements** | What this agent must always include | Probability estimate, severity rating, mitigation proposal |
| **Forbidden behaviors** | What this agent must never do | "Never recommend a course of action without flagging at least one failure mode." |
| **Challenge stance** | How this agent engages opposing views | "Identify the most optimistic claim from other agents and stress-test it." |
| **Confidence expression** | How this agent reports certainty | "Always express as a range: e.g., 60–75% confident." |
| **Search protocol** | What the agent must search for before reasoning | "Search for: recent statistics, current market data, latest research relevant to this problem. Cite what you found and when it was published." |
| **No-assumption rule** | What to do when a needed fact is missing | "If a fact is not in the Problem Brief and not findable via search, ask a targeted clarifying question. Do not proceed with an unverified inference. Label uncertain facts: ⚠️ Unverified." |

This persona spec is what separates a real debate from GHC agreeing with itself five times.

---

## 5. Quality Control

### 5.1 Stop Criteria

The CEO stops the debate when **any** hard stop or **two or more** soft stops are triggered.

#### Hard Stops (immediate termination)

| Criterion | Threshold | Rationale |
|---|---|---|
| **Max rounds reached** | Round 4 completed | Diminishing returns after round 4 |
| **Full consensus** | 100% of agents aligned on same recommendation | No further debate value |

#### Soft Stops (trigger when 2+ met simultaneously)

| Criterion | Threshold | How Measured |
|---|---|---|
| **Convergence score** | ≥ 80% agents share the same recommendation | Count agents whose final position matches the plurality |
| **Argument novelty** | < 20% new arguments in the last round | Diff argument list from round N vs round N-1 |
| **Confidence plateau** | Agent confidence scores changed < 5% from last round | Delta of self-reported confidence per agent |
| **Dissent exhaustion** | Devil's Advocate repeats a previously-made argument | CEO detects semantic duplicate in DA's last response |
| **Risk coverage saturation** | All key risk areas from the Problem Brief have been addressed | CEO tracks a risk coverage checklist |

### 5.2 Minimum Coverage Gate

**Before stopping**, the CEO verifies all of the following are true:

- [ ] Every proposed option has at least one downside argument raised
- [ ] Devil's Advocate challenged the leading position at least once
- [ ] At least one agent addressed the Problem Brief's success criteria
- [ ] At least one agent stated an explicit confidence percentage

If any gate item is false → write one additional targeted round addressing the gap, then proceed to synthesis.

### 5.3 Encoding in SKILL.md

The stop criteria must be written as explicit decision rules GHC follows after each round:

```
After completing each round, evaluate:

HARD STOPS (end debate immediately if any is true):
  - Round 4 has just been completed
  - Every agent stated the same recommendation this round

SOFT STOPS (end debate if 2 or more are true):
  - ≥80% of agents share the same recommendation
  - This round introduced fewer than 2 new arguments not seen in prior rounds
  - No agent changed their stated confidence by more than 5% from last round
  - Devil's Advocate made a point already made in a prior round
  - All risk areas from the Problem Brief have at least one identified risk

MINIMUM COVERAGE GATE (before stopping, verify all are true):
  - Every proposed option has at least one downside argument
  - Devil's Advocate challenged the leading position at least once
  - At least one agent addressed the Problem Brief's success criteria
  - At least one agent stated an explicit confidence percentage

If any gate item is false → write one additional targeted round addressing the gap.
```

---

## 6. Output — Final Report

### 6.1 Report Template

This is the **canonical** report format. One version, used everywhere.

```markdown
# Advisory Board Report

**Date**: YYYY-MM-DD
**Problem**: [one-sentence restatement]
**Pattern**: [parliamentary | adversarial | round-robin | socratic]
**Rounds**: N
**Stop reason**: [convergence | max-rounds | full-consensus]
**Agents**: [list]

---

## Executive Summary
[2–3 sentences in plain language: what is the recommendation and why]

---

## Recommendation
**Decision**: [clear recommendation]
**Confidence Score**: XX%

### Confidence Breakdown
| Factor | Weight | Score | Notes |
|---|---|---|---|
| Evidence quality | 25% | /10 | [note] |
| Agent consensus | 25% | /10 | [note] |
| Risk coverage | 20% | /10 | [note] |
| Assumption risk | 15% | /10 | [note] |
| Argument novelty | 15% | /10 | [note] |
| **Total** | 100% | **XX%** | |

---

## Pros & Cons

### For [Recommended Option]
| Argument | Raised by | Evidence Strength |
|---|---|---|
| [Argument 1] | [Agent] | Strong / Moderate / Weak |

### Against [Recommended Option] / For Alternatives
| Argument | Raised by | Evidence Strength |
|---|---|---|
| [Counter-argument 1] | [Agent] | Strong / Moderate / Weak |

---

## Risk Register
| Risk | Severity | Probability | Mitigation | Unresolved? |
|---|---|---|---|---|
| [Risk 1] | High | 40–60% | [mitigation] | No |
| [Risk 2] | Medium | 20–30% | None identified | **YES** |

---

## Conditions That Would Change the Recommendation
1. If [condition] → [alternative recommendation]
2. If [condition] → revisit with [agent type]
3. If [condition] → confidence drops below 50%

---

## Limitations
- **Unanswered questions**: [dimensions that could not be reasoned about]
- **Data gaps**: No real-world data was available for: [list]
- **Missing expertise**: The following expertise was NOT represented: [list]
- **Out of scope**: [what was explicitly excluded from Problem Brief]

---

## Agent Positions Summary
| Agent | Initial | Final | Changed? | Confidence |
|---|---|---|---|---|
| [Agent] | [position] | [position] | Yes/No | XX% |

## Dissenting Views
[Any agent that maintained a minority position — stated fully, not dismissed]

---

## Problem Brief (as confirmed)
[Full Problem Brief from Phase 1]

## Debate Transcript
<details>
<summary>Expand full transcript</summary>

[Complete round-by-round debate log]
</details>
```

### 6.2 Output Properties

| Property | Requirement |
|---|---|
| **Copy-paste ready** | User can paste report into any editor as-is |
| **Self-contained** | Report makes sense without reading preceding chat history |
| **Transcript hidden** | Full debate in a collapsible `<details>` block |
| **File convention** | `debate-report-[domain]-[YYYY-MM-DD].md` (if user saves manually) |

---

## 7. SKILL.md Specification

### 7.1 File Structure

```
.claude/skills/ceo-advisor/
└── SKILL.md          # The only required file
```

No scripts, no references, no assets. The full workflow is encoded as natural language instructions inside `SKILL.md`.

### 7.2 Required SKILL.md Sections

| Section | Purpose |
|---|---|
| **Frontmatter** (YAML) | `name`, `description` (used for auto-trigger matching), `author` |
| **Phase 1 instructions** | How to compute clarity score, question generation rules, Problem Brief template, confirmation pause |
| **Phase 2 instructions** | Method selection decision table, debate configuration output format |
| **Phase 3 instructions** | Per-round structure, per-agent persona blocks (all 7 attributes from §4.4 for each role), stop criteria rules, minimum coverage gate |
| **Phase 4 instructions** | Judge synthesis steps, CEO executive layer steps, final report template |
| **Trigger examples** | Sample invocations (helps GHC auto-trigger correctly) |

### 7.3 What SKILL.md Must NOT Contain

- Hardcoded domain-specific answers or opinions
- Silent assumptions — any uncertain fact must be either searched for or questioned, never silently guessed
- Reasoning steps that proceed despite an unanswered clarifying question
- Claims presented as fact without a cited source or a ⚠️ Unverified label

### 7.4 CEO System Prompt (Embedded in SKILL.md)

```
You are the CEO of a world-class advisory board. You do not give opinions
directly — you orchestrate specialists to produce the best possible
collective intelligence on any problem.

Your responsibilities, in order:
1. CLARIFY: Ensure the problem is fully understood before any analysis.
   Never skip this — ambiguity is your biggest enemy.

2. SELECT METHOD: Choose the right debate pattern for the problem type.
   The wrong method produces noise, not insight.

3. COORDINATE: Assemble the right panel. Keep agents focused. Challenge
   early consensus — a debate where everyone agrees by round 2 was not
   a real debate. Push your Devil's Advocate to escalate if needed.

4. SYNTHESIZE: Once the debate has produced diminishing returns, stop it.
   Produce the structured analysis. Then add the executive layer: what
   does this mean in plain terms? What would change the answer? What
   did we miss?

Standards you hold yourself to:
- Disagreement is a feature, not a bug. Do not stop just because it is
  uncomfortable.
- Every voice on the panel is there for a reason. Do not let one dominate.
- Flag unresolved risks explicitly — do not bury them in the report.
- Your confidence score must be honest. If uncertain, say so.
- Every agent searches for current, real-world information before reasoning.
  Reasoning from stale or invented data is a failure mode you do not tolerate.
- No agent ever silently assumes an answer. If something is unclear, the
  agent asks. If the user will not answer, state what cannot be advised on
  — do not guess.
- You produce a report you would stake your reputation on.
```

### 7.5 Limitations of the GHC Skill Approach

| Limitation | Impact | Mitigation |
|---|---|---|
| **Sequential, not parallel** | Each agent runs one at a time; potential echo-chamber if GHC loses persona | SKILL.md re-states each agent's persona header at each round |
| **Single model** | All agents use the same underlying GHC model | Accepted tradeoff; persona differentiation compensates |
| **No persistent state** | Each session starts fresh; no memory of past debates | Out of scope for v1 |
| **Token window** | Long debates with many agents can hit context limits | Mitigated by limiting to 3–5 agents, max 4 rounds |
| **Search quality varies** | GHC's web search may not surface the most authoritative sources | Agents must cite source + publication date; user can supplement |
| **Persona drift** | GHC may lose persona fidelity across many rounds | SKILL.md re-states persona at each round prompt |

---

## 8. Delivery Plan

The entire deliverable is **one file**: `.claude/skills/ceo-advisor/SKILL.md`.

### Step 1 — Skill scaffolding
- [ ] Create the directory `.claude/skills/ceo-advisor/`
- [ ] Set frontmatter: `name`, `description` (must match trigger phrases), `author`
- [ ] Confirm skill appears when typing `/ceo-advisor` in GHC

### Step 2 — Phase 1: Clarification instructions
- [ ] Write clarity score logic (0–100 across 7 dimensions)
- [ ] Write question generation rules (max 5, High-priority only)
- [ ] Write Problem Brief template
- [ ] Write confirmation pause behavior
- [ ] Test: ambiguous problem → skill asks questions; clear problem → skill skips to Brief

### Step 3 — Phase 2: Method selection instructions
- [ ] Write Meta-Methodologist persona and decision table
- [ ] Write debate configuration output block format
- [ ] Test: skill states pattern + roster + rationale before debating

### Step 4 — Phase 3: Debate round instructions
- [ ] Write per-agent persona blocks for all 11 universal roles (all 7 attributes from §4.4)
- [ ] Write Round 0 (independent positions) rules
- [ ] Write Round 1–N (challenge & refine) rules
- [ ] Write Devil's Advocate escalation rule
- [ ] Write stop criteria decision rules (hard stops + soft stops)
- [ ] Write minimum coverage gate
- [ ] Test: run 3 diverse problems — verify agent differentiation, DA challenge, early stop

### Step 5 — Phase 4: Synthesis instructions
- [ ] Write Judge synthesis steps
- [ ] Write CEO executive layer steps
- [ ] Write final report template (from §6.1)
- [ ] Test: verify report is self-contained and confidence score is calibrated

### Step 6 — Family & Children domain
- [ ] Write Child Development Specialist persona
- [ ] Write Family Therapist persona
- [ ] Write Education Advisor persona
- [ ] Add family/children problem type to method selection decision table
- [ ] Test: run a parenting or schooling question — verify child-specific experts activate

### Step 7 — Acceptance testing
- [ ] Run all acceptance criteria from §9 against 5 test problems (career, business, technology, family, policy)
- [ ] Fix any persona drift, assumption leakage, or missing coverage gate items
- [ ] Confirm web search citations appear in every Round 0 response

---

## 9. Acceptance Criteria

The `SKILL.md` is considered complete when, on a test problem, it produces:

| # | Criterion | Pass condition |
|---|---|---|
| 1 | **Clarification runs** | GHC asks ≥ 1 targeted question when input is ambiguous; skips questions when input is clear |
| 2 | **Problem Brief confirmed** | GHC produces a Problem Brief and pauses for user confirmation before debating |
| 3 | **Method selected** | GHC states which debate pattern and which agents it will use, with a one-sentence rationale |
| 4 | **Genuine agent differentiation** | Each agent in Round 0 reaches a different initial position or emphasis on at least 30% of test problems |
| 5 | **Devil's Advocate challenges** | On every test problem, Devil's Advocate challenges the Round 0 plurality at least once |
| 6 | **Stop criteria enforced** | Debate stops before Round 4 on ≥ 50% of test problems (early convergence) |
| 7 | **Coverage gate enforced** | If any gate item is missing, an extra targeted round is added |
| 8 | **Report is self-contained** | The final MD report makes sense without reading the preceding chat history |
| 9 | **Confidence score is honest** | High uncertainty → score ≤ 65%; well-defined → score ≥ 75% |
| 10 | **Web search used** | Every agent's Round 0 response includes at least one cited external source with publication date |
| 11 | **No bare assumptions** | No agent response contains an unverified claim presented as fact; unclear facts are cited, labelled ⚠️ Unverified, or escalated as a clarifying question |

---

## Appendix A: Problem Taxonomy

Classification dimensions used by the CEO in Phase 1 to assess problem type:

| Dimension | Description | Example Values |
|-----------|-------------|---------------|
| **Reversibility** | Can the decision be undone? | Reversible / Partially / Irreversible |
| **Time horizon** | When do consequences manifest? | Immediate / Months / Years / Decades |
| **Stakeholders** | Who is affected? | Self / Team / Organization / Society |
| **Uncertainty level** | How much is unknown? | Low / Medium / High / Extreme |
| **Value conflicts** | Are there competing values? | None / Tradeoffs / Deep conflicts |
| **Data availability** | Is evidence available? | Rich data / Sparse / None |
| **Expertise required** | What domains must be considered? | Single / Multi-disciplinary / Highly specialized |

---

## Appendix B: Discovery & Research Notes

> These notes are retained from the initial research phase. They informed the design but are not part of the implementation spec. Sections below describe a backend system that will **not** be built — the chosen delivery model is a GHC agent skill (§7).

### B.1 Key Research Questions

1. What debate patterns produce the best decisions?
2. How should agent roles be defined?
3. How to handle token budget constraints?
4. How to synthesize a final decision from debate?
5. How to evaluate debate quality?
6. How should the clarification phase work?
7. What LLM architecture to use?
8. How to make the system truly domain-agnostic?

### B.2 Frameworks Evaluated (Not Used)

| Framework | Language | Key Feature | Debate Support | Notes |
|-----------|----------|-------------|---------------|-------|
| **AutoGen** (Microsoft) | Python | Multi-agent conversation | Yes, group chat | Most mature |
| **CrewAI** | Python | Role-based agents with tasks | Limited | Good role system |
| **LangGraph** | Python | Stateful agent graphs | Custom | Flexible but lower-level |
| **Swarm** (OpenAI) | Python | Lightweight agent handoffs | No | Too simple |

Decision: **None** — delivering as a GHC agent skill instead.

### B.3 Backend Architecture Notes (Legacy)

The following components were designed for a backend system. They are documented here for reference if a backend version is ever built.

- **Orchestrator**: Manages full session lifecycle
- **Config Store**: Loads role definitions from YAML
- **Token Budget Manager**: Tracks per-agent token usage with formulas
- **Debate Arena**: Executes debate rounds with parallelized agent calls
- **Convergence Calculator**: Computes convergence and novelty scores

### B.4 Preventing Degenerate Debates

These mitigations are still relevant for the GHC skill:

| Problem | Symptom | Solution |
|---------|---------|----------|
| **Groupthink** | All agents agree immediately | Devil's Advocate always included; require at least one dissent |
| **Echo chamber** | Agents repeat each other's points | Persona spec enforces novelty; stop criteria detects < 20% new arguments |
| **Token waste** | Long preambles, repeating the question | Enforce structured response format in persona spec |
| **Deadlock** | Agents never converge | Max 4 rounds; Judge breaks ties in synthesis |
| **Hallucination amplification** | One agent's hallucination accepted by others | Search protocol + citation requirement + ⚠️ Unverified labeling |

### B.5 Cost Estimation (Backend Context)

| Model | Input $/1M tokens | Output $/1M tokens | 50K session cost |
|-------|-------------------|--------------------|-----------------:|
| GPT-4o | $2.50 | $10.00 | ~$0.30 |
| Claude Sonnet | $3.00 | $15.00 | ~$0.45 |
| Claude Opus | $15.00 | $75.00 | ~$2.25 |
| GPT-4o mini | $0.15 | $0.60 | ~$0.02 |

> Note: In the GHC skill model, cost is covered by the user's Copilot subscription. These numbers apply only if a backend version is built.

### B.6 Open Questions (For Future Versions)

- Should agents have "memory" across debates (learn from past decisions)?
- Should users be able to intervene mid-debate (provide clarification)?
- How to version-control agent prompts and track prompt evolution?
- What is the minimum viable set of agents for useful debate? (3? 4?)
- Should the system support async debates (agents respond over hours)?
