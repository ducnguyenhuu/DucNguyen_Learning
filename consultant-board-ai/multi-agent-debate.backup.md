# CEO Advisor — GHC Agent Skill Spec

## 1. Problem Statement

Build a **CEO Advisor agent skill** (`/ceo-advisor`) that runs entirely inside **GitHub Copilot Chat (GHC)**. When triggered, it acts as a multi-expert consulting board — clarifying the problem, debating it from multiple expert perspectives, and returning a structured Markdown decision report — all within a single chat session.

**No backend. No custom framework. No infrastructure.** The entire system is a single `SKILL.md` file that GHC reads as its instruction set.

### 1.1 Scope: Any Real-World Decision

Examples of problems the skill should handle:

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

### 1.2 Core Requirements

- **Delivery**: A single `SKILL.md` file — runnable directly in GHC with `/ceo-advisor <question>`
- **No infrastructure**: No API, no database, no backend service, no external orchestration
- **Clarification first**: Before any debate, the skill ensures the problem is fully understood — asks questions if needed, never assumes
- **Web search before reasoning**: Every agent must search for current real-world information before forming a position — no stale knowledge, no invented facts
- **Multi-perspective debate**: GHC plays each expert agent role in turn with a distinct persona, bias, and mandatory output format
- **Structured output**: Returns a complete Markdown decision report inline in the chat — copy-paste ready
- **Configurable roles**: 11 universal expert roles + domain-specific extensions; active roster of 3–5 selected per problem
- **Quality-gated**: Debate runs until explicit stop criteria are met, with a minimum coverage gate before synthesis

---

## 2. Discovery Phase

### 2.1 Key Questions to Answer

1. **What debate patterns produce the best decisions?**
   - Round-robin (each agent speaks in turn)?
   - Adversarial (explicit pro/con roles)?
   - Socratic (one agent questions others)?
   - Parliamentary (propose → oppose → rebut → vote)?
   - How many rounds of debate are optimal before diminishing returns?

2. **How should agent roles be defined?**
   - What level of persona detail produces meaningful differentiation?
   - Should roles be static or dynamically assigned based on the problem?
   - How many agents per debate? (too few = groupthink, too many = noise)
   - Should there be a moderator/judge agent?

3. **How to handle token budget constraints?**
   - Fixed budget per agent per round?
   - Pooled budget across all agents?
   - Priority-based allocation (domain expert gets more tokens on relevant topics)?
   - How to prevent one agent from dominating the conversation?

4. **How to synthesize a final decision from debate?**
   - Voting (each agent votes, majority wins)?
   - Weighted voting (domain expert's vote counts more on relevant topics)?
   - Judge agent synthesizes (separate agent reads debate, decides)?
   - Confidence-weighted consensus?

5. **How to evaluate debate quality?**
   - Did the debate surface risks that a single agent missed?
   - Did the final recommendation change after debate vs initial positions?
   - How often does the debate produce better decisions than a single expert prompt?

6. **How should the clarification phase work?**
   - Who asks the questions — a dedicated Clarifier agent or all agents?
   - How many clarification rounds before forcing debate to start?
   - What happens if user cannot answer a clarifying question?
   - How to detect when the problem is "sufficiently understood" to proceed?
   - Should clarification be synchronous (user responds) or agents infer from context?

7. **What LLM architecture to use?**
   - Same model for all agents (different system prompts)?
   - Different models for different roles (e.g., Claude for analysis, GPT for code)?
   - Local models for cost-sensitive roles?
   - How to manage API calls efficiently?

8. **How to make the system truly domain-agnostic?**
   - How to auto-select relevant expert roles from the problem description?
   - What is the minimal role set that covers most problem types?
   - Should the system suggest roles to the user or pick them automatically?

### 2.2 Discovery Activities

| # | Activity | Purpose | Output |
|---|----------|---------|--------|
| 1 | Survey multi-agent frameworks | Understand existing approaches | Framework comparison matrix |
| 2 | Prototype 3 debate patterns | Test which pattern produces best output | Pattern evaluation report |
| 3 | Prototype clarification phase | Test how agents ask questions | Clarifier design spec |
| 4 | Test on diverse problem domains | Validate domain-agnostic design | Cross-domain role catalog |
| 5 | Run 10 debates on known problems | Measure debate quality vs single-agent | Quality baseline |
| 6 | Test token budget strategies | Find optimal allocation approach | Budget strategy recommendation |
| 7 | Benchmark LLM combinations | Cost vs quality tradeoffs | Model selection matrix |
| 8 | Design configuration schema | Enable role/prompt customization | Config schema spec |
| 9 | Prototype judge/synthesis mechanism | Test decision aggregation methods | Synthesis algorithm |
| 10 | User study: clarification UX | Measure friction of clarification Q&A | UX recommendations |

### 2.3 Problem Taxonomy Discovery

Before building role catalogs, classify problem types to identify the universal dimensions of any decision:

| Dimension | Description | Example Values |
|-----------|-------------|---------------|
| **Reversibility** | Can the decision be undone? | Reversible / Partially / Irreversible |
| **Time horizon** | When do consequences manifest? | Immediate / Months / Years / Decades |
| **Stakeholders** | Who is affected? | Self / Team / Organization / Society |
| **Uncertainty level** | How much is unknown? | Low / Medium / High / Extreme |
| **Value conflicts** | Are there competing values? | None / Tradeoffs / Deep conflicts |
| **Data availability** | Is evidence available? | Rich data / Sparse / None |
| **Expertise required** | What domains must be considered? | Single / Multi-disciplinary / Highly specialized |

This taxonomy drives **which expert roles are relevant** for each problem.

### 2.4 Existing Frameworks to Evaluate

| Framework | Language | Key Feature | Debate Support | Notes |
|-----------|----------|-------------|---------------|-------|
| **AutoGen** (Microsoft) | Python | Multi-agent conversation | Yes, group chat | Most mature, good for debate patterns |
| **CrewAI** | Python | Role-based agents with tasks | Limited | Good role system, less debate-oriented |
| **LangGraph** | Python | Stateful agent graphs | Custom | Flexible but lower-level |
| **Swarm** (OpenAI) | Python | Lightweight agent handoffs | No | Too simple for debate |
| **Custom** | Python | Full control | Full | Most effort but maximum flexibility |

**Recommendation**: Start with **AutoGen** for rapid prototyping, evaluate if custom implementation is needed later.

### 2.5 Expected Discovery Outputs

- **Debate pattern recommendation**: Which pattern works best for decision-making
- **Role catalog**: 6-8 expert roles with system prompts
- **Token budget strategy**: How to allocate tokens across agents and rounds
- **Synthesis algorithm**: How to produce a final recommendation from debate
- **Architecture decision**: Build custom vs use framework
- **Cost projection**: Expected API cost per debate session

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
                    ┌─────────────────────┐
                    │     User Input      │
                    │  (Any Problem /     │
                    │   Decision Needed)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Orchestrator      │
                    │   (Session Mgr)     │
                    └──────────┬──────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
      ┌────────▼──────┐ ┌─────▼──────┐ ┌──────▼───────┐
      │  Agent Pool   │ │   Token    │ │   Config     │
      │  (Experts)    │ │   Budget   │ │   Store      │
      │               │ │   Manager  │ │  (YAML/JSON) │
      └────────┬──────┘ └─────┬──────┘ └──────────────┘
               │               │
      ┌────────▼───────────────▼────────┐
      │        PHASE 1: CLARIFICATION   │
      │  Clarifier Agent asks questions │
      │  User answers → context built   │
      │  Loop until problem is clear    │
      └────────────────┬────────────────┘
                       │  Problem Brief (finalized)
      ┌────────────────▼────────────────┐
      │        PHASE 2: DEBATE ARENA    │
      │  Round 0: Independent positions │
      │  Round 1..N: Challenge & Refine │
      │  Convergence check each round   │
      └────────────────┬────────────────┘
                       │
              ┌────────▼────────┐
              │  PHASE 3: SYNTH │
              │  Judge Agent    │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  Final Report   │
              │ + Recommendation│
              │ + Transcript    │
              └─────────────────┘
```

### 3.2 Core Components

| Component | Responsibility |
|-----------|---------------|
| **Orchestrator** | Manages full session lifecycle: clarification → debate → synthesis |
| **Clarifier Agent** | Asks targeted questions to build a complete problem brief |
| **Role Selector** | Auto-assigns relevant expert roles based on problem type |
| **Agent Pool** | Instantiates agents from role configs, manages personas |
| **Token Budget Manager** | Tracks token usage per agent per phase, enforces limits |
| **Config Store** | Loads role definitions, debate rules, model settings |
| **Debate Arena** | Executes debate rounds, manages conversation history |
| **Judge Agent** | Synthesizes debate into final recommendation |

### 3.3 Full Session Flow

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 0: SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  a. User submits problem statement (free text, any domain)
  b. Orchestrator classifies problem type
  c. Role Selector proposes 3-5 expert roles
  d. User confirms or adjusts roles
  e. Token budgets allocated per phase

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 1: CLARIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Goal: Build a complete, unambiguous Problem Brief
  before any debate begins.

  Step 1 — Each expert agent independently reads the
           problem and submits up to 3 questions it
           needs answered to give useful advice.

  Step 2 — Clarifier Agent deduplicates and prioritizes
           questions. Selects top 5 most critical.

  Step 3 — Questions presented to user. User answers.

  Step 4 — Clarifier Agent evaluates answers:
           IF problem is now clear → generate Problem Brief
           IF still ambiguous → repeat Step 1 (max 3 loops)
           IF user cannot answer → agents note as
             "unknown variable" and proceed with assumptions

  Step 5 — Problem Brief finalized:
           - Restated problem (precise, complete)
           - Key constraints and context
           - Stated assumptions (from unanswered questions)
           - Success criteria (what does a good decision look like?)
           - Explicit out-of-scope boundaries

  User confirms Problem Brief → proceed to Phase 2.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 2: DEBATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Round 0 — Independent Positions
    - Each agent reads Problem Brief only
    - Independently produces: position + top 3 arguments
    - No agent sees others' responses
    - Establishes baseline (did agents start differently?)

  Round 1..N — Structured Debate
    For each round:
      a. Agents receive all positions from previous round
      b. Each agent must:
         - Identify the strongest opposing argument → engage with it
         - Update or defend their position with reasoning
         - Explicitly state if position changed and why
      c. Token budget deducted per response
      d. Convergence check:
         IF ≥80% of agents agree on same recommendation → early stop
      e. Budget check:
         IF tokens exhausted → force final positions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHASE 3: SYNTHESIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Judge agent receives: Problem Brief + full transcript
  - Produces structured final report (see Section 7.2)
  - Flags any assumptions that significantly affect outcome
  - Provides confidence score and uncertainty range

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Problem Brief (clarification output)
  - Recommendation with confidence and uncertainty range
  - Key arguments for and against
  - Unresolved risks and dissenting views
  - Assumptions that were made
  - Full debate transcript (audit trail)
  - Token usage summary
```

### 3.4 Clarification Phase — Design Details

#### 3.4.1 Clarifier Agent Behavior

The Clarifier Agent is a **meta-agent** — it does not have a domain opinion. Its only job is to ensure the problem is understood well enough to debate.

**Clarifier system prompt core**:

```
You are a professional facilitator. You do NOT give opinions or
recommendations. Your only role is to ensure a problem is stated
with enough clarity for expert advisors to debate it meaningfully.

For a given problem statement, identify:
1. What key information is MISSING that experts would need?
2. What ASSUMPTIONS are being made implicitly?
3. What CONSTRAINTS or context are unstated?
4. What does SUCCESS look like — what is the decision criteria?
5. What is EXPLICITLY OUT OF SCOPE?

Generate clear, concise questions. Prioritize by impact:
  - High: without this, experts cannot give useful advice
  - Medium: would significantly improve advice quality
  - Low: nice to have

Always output exactly 3-5 HIGH priority questions. No more.
```

#### 3.4.2 Question Categories

| Category | Purpose | Example |
|----------|---------|--------|
| **Context** | Background needed to frame the problem | "What is your current situation / starting point?" |
| **Constraints** | Hard limits experts must respect | "What is your budget / timeline / non-negotiables?" |
| **Success criteria** | What does a good outcome look like? | "How will you know if this decision was right?" |
| **Stakeholders** | Who is affected and whose input matters? | "Who else is impacted by this decision?" |
| **Alternatives** | What options are already on the table? | "What options are you already considering?" |
| **Risk tolerance** | How much downside is acceptable? | "What is the worst outcome you could accept?" |
| **Time horizon** | Short-term vs long-term tradeoffs | "Are you optimizing for 1 year or 5 years?" |

#### 3.4.3 Problem Brief Template

```markdown
## Problem Brief

**Problem Statement** (restated precisely):
[Clear, unambiguous single-paragraph description]

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

**Assumptions** (from unanswered questions):
- [Assumption 1] — flagged as uncertain
- [Assumption 2] — flagged as uncertain

**Out of Scope**:
- [What will NOT be considered]

**Confirmed by user**: [Yes / Pending]
```

#### 3.4.4 Clarification Loop Rules

| Rule | Description |
|------|------------|
| **Max loops** | 3 clarification rounds maximum before forcing debate |
| **Min questions** | Clarifier must ask at least 3 questions in first loop |
| **User skip** | User can skip a question; agents must ask a targeted follow-up rather than assume — if still unanswered after one follow-up, flag as a blocker and explain what cannot be advised without it |
| **Force proceed** | If user explicitly says "proceed", skip remaining clarification — agents must then state which questions remain unanswered and explicitly refuse to reason about those dimensions |
| **No silent assumptions** | Agents may never silently assume an answer to a skipped question; any inference from incomplete information must be labelled "unverified inference" and treated as low-confidence |
| **Brief confirmation** | User must confirm the Problem Brief before debate starts |
| **Brief edits** | User can edit the Problem Brief directly before confirming |

---

## 4. Agent Role Design

### 4.1 Universal Expert Roles (Domain-Agnostic)

These roles can be applied to **any type of problem**, not just software.

> **Gap analysis (vs §1.1 scope)**: The original 8 roles had material blind spots for legal/regulatory exposure (present in every high-stakes domain), macroeconomic effects (policy, market entry), end-user interests (product, healthcare, policy), and family/child-specific decisions. Three roles were promoted from domain extensions and one new role added to close these gaps. The pool is now **11 universal roles**.

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
| **Business** | Marketing Strategist, Operations Expert, HR Consultant | Go-to-market, org ops (Legal Advisor now universal) |
| **Healthcare** | Medical Expert (clinical reasoning), Regulatory Specialist | Clinical knowledge — universals cannot substitute |
| **Finance/Investment** | Portfolio Manager, Tax Advisor, Market Analyst, Behavioral Finance Expert | Asset-class depth, tax optimisation, investor psychology |
| **Personal/Life** | Life Coach, Career Counselor, Relationship Counselor | Life direction, identity, long-term fulfilment |
| **Family & Children** | Child Development Specialist, Family Therapist, Education Advisor, Pediatric Health Expert | Child wellbeing, developmental stages, parenting approaches, schooling — all invisible to the universal roles |
| **Policy/Government** | Legal Scholar, Sociologist, Public Health Expert | Constitutional law, social dynamics, public health (Economist now universal) |

### 4.3 Recommended Role Sets by Problem Type

| Problem Type | Core Roles (3-5) | Domain Extensions to add |
|-------------|------------------|---------------------------|
| Career decision (job change, MBA) | Strategist, Financial Analyst, Pragmatist, Psychologist, Devil's Advocate | Career Counselor |
| Business / market entry | Strategist, Financial Analyst, Risk Advisor, Legal Advisor, Economist | Marketing Strategist, HR Consultant |
| Business acquisition / M&A | Strategist, Financial Analyst, Risk Advisor, Legal Advisor, Devil's Advocate | Operations Expert |
| Technology choice | Pragmatist, Risk Advisor, Financial Analyst, Data Scientist, Devil's Advocate | Software Architect, Security Analyst |
| Investment decision | Financial Analyst, Risk Advisor, Data Scientist, Strategist, Legal Advisor | Portfolio Manager, Tax Advisor |
| Life decision (relocate cross-border) | Psychologist, Strategist, Financial Analyst, Legal Advisor, Pragmatist | Life Coach |
| Life decision (relationship) | Psychologist, Ethicist, Strategist, Devil's Advocate, User & Stakeholder Advocate | Relationship Counselor |
| Family — should we have children? | Psychologist, Financial Analyst, Ethicist, User & Stakeholder Advocate, Devil's Advocate | Child Development Specialist, Family Therapist |
| Family — parenting / schooling choices | User & Stakeholder Advocate, Psychologist, Data Scientist, Pragmatist, Devil's Advocate | Child Development Specialist, Education Advisor |
| Family — custody / guardianship | Legal Advisor, User & Stakeholder Advocate, Psychologist, Ethicist, Risk Advisor | Family Therapist |
| Family — relocation with children | Pragmatist, Financial Analyst, User & Stakeholder Advocate, Psychologist, Legal Advisor | Child Development Specialist, Education Advisor |
| Healthcare — treatment decision | Data Scientist, Risk Advisor, Ethicist, User & Stakeholder Advocate, Devil's Advocate | Medical Expert, Regulatory Specialist |
| Policy / regulatory | Ethicist, Economist, Data Scientist, Legal Advisor, User & Stakeholder Advocate | Legal Scholar, Sociologist, Public Health Expert |
| AI vs Human (Problem 1) | Pragmatist, Risk Advisor, Financial Analyst, Data Scientist, Ethicist | — |
| Cost estimation (Problem 2) | Financial Analyst, Data Scientist, Pragmatist, Risk Advisor, Devil's Advocate | — |

### 4.4 Role Configuration Schema

```yaml
# agent-config.yaml

# ─────────────────────────────────────────
# CLARIFICATION CONFIG
# ─────────────────────────────────────────
clarification:
  model: "claude-sonnet-4-20250514"
  max_questions_per_round: 5
  max_rounds: 3
  clarifier_max_tokens: 2000
  allow_user_skip: true
  require_brief_confirmation: true

# ─────────────────────────────────────────
# AGENT ROLES
# ─────────────────────────────────────────
agents:
  risk_advisor:
    name: "Risk Advisor"
    model: "claude-sonnet-4-20250514"
    system_prompt: |
      You are a senior risk advisor with expertise across business,
      financial, operational, and strategic risk. You have no domain
      allegiance — you apply rigorous risk thinking to any problem.

      Your core job:
      - Identify the top risks in any proposed course of action
      - Estimate likelihood and severity for each risk (use ranges)
      - Distinguish known risks from unknown unknowns
      - Propose specific mitigations, not vague warnings
      - Acknowledge when a risk is actually acceptable

      When debating:
      - Challenge optimistic positions with concrete failure scenarios
      - Do not block every option — rank risks to help prioritization
      - Quantify risk wherever possible (e.g., "30-50% probability")
    max_tokens_per_round: 1500
    temperature: 0.3
    priority_topics: ["risk", "downside", "failure", "uncertainty"]
    vote_weight: 1.0

  financial_analyst:
    name: "Financial Analyst"
    model: "claude-sonnet-4-20250514"
    system_prompt: |
      You are a financial analyst who thinks in terms of total cost,
      ROI, opportunity cost, and economic tradeoffs. You apply this
      to any domain: business decisions, career choices, project
      planning, personal finance.

      Your core job:
      - Always quantify costs, benefits, and savings in concrete terms
      - Factor in hidden and long-term costs, not just upfront
      - Calculate opportunity cost (what is given up by each choice)
      - Challenge vague claims like "it will pay off" with numbers

      When debating:
      - Require evidence before accepting financial claims
      - Compare alternatives using consistent metrics
      - Be explicit about assumptions in your estimates
    max_tokens_per_round: 1200
    temperature: 0.2
    priority_topics: ["cost", "ROI", "budget", "investment", "savings"]
    vote_weight: 1.0

  devils_advocate:
    name: "Devil's Advocate"
    model: "claude-sonnet-4-20250514"
    system_prompt: |
      You are a professional Devil's Advocate. Your role is NOT to
      have a personal opinion — it is to challenge whatever the
      emerging consensus is. If most agents support Option A,
      you argue for Option B. If agents seem to agree, you find
      the strongest possible counter-argument.

      Your core job:
      - Prevent premature consensus
      - Surface the strongest possible objection to any position
      - Play devil's advocate even if you personally agree with the
        majority — your role demands it
      - Ask "what if we're wrong?" and "what are we not considering?"

      You do NOT have to believe what you argue. You are a
      structured thinking tool to stress-test conclusions.
    max_tokens_per_round: 1000
    temperature: 0.7
    priority_topics: ["counterargument", "assumptions", "overlooked"]
    vote_weight: 0.7  # lower weight in final vote — role is to challenge, not decide

  # ... more agents (pragmatist, strategist, ethicist, psychologist, etc.)

# ─────────────────────────────────────────
# DEBATE CONFIG
# ─────────────────────────────────────────
debate_config:
  max_rounds: 4
  min_rounds: 2
  convergence_threshold: 0.8   # 80% agreement → early stop
  total_token_budget: 50000
  debate_pattern: "parliamentary"  # round-robin | adversarial | parliamentary | socratic
  judge_model: "claude-sonnet-4-20250514"
  judge_max_tokens: 3000

# ─────────────────────────────────────────
# TOKEN BUDGET ALLOCATION
# ─────────────────────────────────────────
token_budget:
  clarification_phase: 0.15   # 15% of total
  initial_positions:   0.15   # 15% of total
  debate_rounds:       0.50   # 50% of total
  synthesis_judge:     0.20   # 20% of total (reserved, never reallocated)

# ─────────────────────────────────────────
# ROLE AUTO-SELECTION
# ─────────────────────────────────────────
role_selection:
  auto_select: true            # let system pick roles from problem description
  min_agents: 3
  max_agents: 5
  always_include: ["devils_advocate"]  # always in every debate
  domain_detection: true       # detect domain and add domain-specific roles
```

---

## 5. Token Budget Management

### 5.1 Budget Allocation Strategy

**Approach: Tiered Budget with Priority Boost**

```
Total Session Budget: B_total (configurable, e.g., 50,000 tokens)

Allocation:
  - Initial positions:  20% of B_total (split equally among agents)
  - Debate rounds:      60% of B_total (split per round, per agent)
  - Synthesis/Judge:    20% of B_total

Per-agent per-round budget:
  B_agent_round = (0.6 × B_total) / (N_agents × N_rounds)

Priority boost:
  If agent's priority_topics match the current problem:
    B_agent_round *= 1.3 (30% boost)
    Deducted from other agents proportionally
```

### 5.2 Budget Enforcement Rules

| Rule | Description |
|------|-------------|
| **Hard cap** | Agent cannot exceed max_tokens_per_round (response truncated) |
| **Soft cap** | Warning at 80% of round budget; agent must conclude |
| **Rollover** | Unused tokens from early rounds roll over to later rounds |
| **Minimum** | Every agent gets at least 500 tokens per round (prevents silencing) |
| **Judge reserve** | 20% of total budget is reserved for synthesis (never reallocated) |

### 5.3 Cost Estimation Per Session

| Model | Input $/1M tokens | Output $/1M tokens | 50K session cost |
|-------|-------------------|--------------------|-----------------:|
| GPT-4o | $2.50 | $10.00 | ~$0.30 |
| Claude Sonnet | $3.00 | $15.00 | ~$0.45 |
| Claude Opus | $15.00 | $75.00 | ~$2.25 |
| GPT-4o mini | $0.15 | $0.60 | ~$0.02 |

**Strategy**: Use cheaper models for initial positions, premium models for judge synthesis.

---

## 6. Debate Patterns (Detailed)

### 6.1 Parliamentary Pattern (Recommended for Decisions)

Adapted from parliamentary debate, best for binary/ternary decisions (AI vs Human vs Hybrid).

```
Round 1: Opening Statements
  - Each agent states initial position with reasoning
  - No references to other agents (independent analysis)

Round 2: Cross-examination
  - Each agent reads all Round 1 positions
  - Must identify the WEAKEST argument from another agent and challenge it
  - Must identify the STRONGEST argument from another agent and acknowledge it

Round 3: Rebuttal
  - Each agent responds to challenges directed at them
  - May update their position based on new information
  - Must explicitly state: "I maintain" or "I revise my position"

Round 4: Closing Statements
  - Final position with confidence level (0-100%)
  - Top 3 factors driving the decision
  - Remaining concerns / risks
```

### 6.2 Adversarial Pattern (Best for Risk Analysis)

Explicitly assigns pro/con roles.

```
Setup:
  - Half the agents argue FOR the proposal (e.g., "use AI")
  - Half argue AGAINST
  - Roles may not match their natural bias (forces deeper thinking)

Round 1: Pro case → Con case
Round 2: Pro rebuts Con → Con rebuts Pro
Round 3: Both sides present revised positions
Judge: Evaluates both sides
```

### 6.3 Socratic Pattern (Best for Requirements Clarification)

One agent asks questions, others answer.

```
Setup:
  - Socratic Questioner (asks probing questions)
  - Expert Panel (answers from their domain)

Round 1: Questioner asks 3-5 targeted questions about the feature
Round 2: Each expert answers from their perspective
Round 3: Questioner identifies contradictions and asks follow-ups
Round 4: Experts reconcile contradictions
```

---

## 7. Synthesis & Decision Aggregation

### 7.1 Judge Agent

A separate agent that does NOT participate in the debate. It reads the full transcript and produces the final output.

**Judge system prompt core**:

```
You are an impartial judge synthesizing a multi-expert debate.
Your job is NOT to add your own opinion but to:
1. Identify the strongest arguments from each side
2. Determine where genuine consensus exists vs performative agreement
3. Flag unresolved risks that no agent adequately addressed
4. Produce a clear recommendation with confidence level
5. Document dissenting views that the team should consider
```

### 7.2 Output Format

```markdown
## Debate Summary

**Problem**: [Feature description]
**Agents**: [List of participating agents]
**Pattern**: Parliamentary | Rounds: 4
**Token Usage**: 42,300 / 50,000

## Recommendation

**Decision**: [AI-first | Hybrid | Human-first]
**Confidence**: 78%

## Key Arguments

### For AI-first (supported by: Cost Analyst, AI Specialist)
1. [Argument 1 with evidence]
2. [Argument 2 with evidence]

### For Human-first (supported by: Security Analyst)
1. [Argument 1 with evidence]

### Consensus Points
- All agents agreed that [X]
- All agents agreed that [Y]

### Unresolved Disagreements
- Security Analyst raised [concern] which was not fully addressed
- Cost Analyst's estimate of [X hours] was disputed by Tech Lead

## Risk Register
| Risk | Raised By | Severity | Mitigated? |
|------|-----------|----------|-----------|
| ... | ... | ... | ... |

## Agent Position Summary
| Agent | Initial Position | Final Position | Changed? | Confidence |
|-------|-----------------|----------------|----------|-----------|
| ... | ... | ... | ... | ... |

## Full Transcript
[Collapsible section with complete debate log]
```

---

## 8. Integration with Problems 1 & 2

### 8.1 Multi-Agent as Decision Engine for Problem 1

Instead of a static scoring model, the multi-agent debate **replaces or augments** the weighted scoring:

```
Feature Spec → Clarification Phase → Agent Debate → AI/Hybrid/Human Recommendation
                       ↓                    ↓
              Makes ambiguous specs    Surfaces risks a scoring
              concrete before debate   model would miss
```

**When to use debate vs scoring model**:
- **Scoring model**: Quick triage, low-stakes features, batch evaluation
- **Agent debate**: High-stakes features, ambiguous cases, when scoring confidence is low

### 8.2 Multi-Agent for Cost Estimation (Problem 2)

Agents can debate cost estimates:
- Financial Analyst provides base estimate
- Pragmatist challenges with execution complexity
- Risk Advisor adds contingency factors
- Data Scientist validates with historical analogy data
- Debate produces a **range** (optimistic / likely / pessimistic) instead of a point estimate

### 8.3 General Decision Questions (Beyond Software)

Examples of the system being used for non-software decisions:

```
User: "Should I leave my current job to join an early-stage startup?"

Clarifier asks:
  1. What is your current financial situation (savings runway)?
  2. What stage is the startup (pre-seed / seed / Series A)?
  3. What is your equity offer and vesting schedule?
  4. What is your risk tolerance — how would you handle 0 income for 6 months?
  5. What does success look like for you in 3 years?

Agents assigned: Strategist, Financial Analyst, Risk Advisor, Psychologist, Devil's Advocate

Debate outcome: Structured recommendation with confidence score,
                key risks, and conditions under which each option wins.
```

---

## 9. Delivery Plan — SKILL.md Authoring

The entire deliverable is **one file**: `.claude/skills/ceo-advisor/SKILL.md`. The plan below tracks what must be authored and validated in that file, in order.

### Step 1 — Skill scaffolding
- [ ] Run `node .claude/skills/create-skill/scripts/init-skill.js ceo-advisor` to create the directory
- [ ] Set frontmatter: `name`, `description` (must match trigger phrases), `author`
- [ ] Confirm skill appears when typing `/ceo-advisor` in GHC

### Step 2 — Phase 1: Clarification instructions
- [ ] Write clarity score logic (0–100 across 7 dimensions)
- [ ] Write question generation rules (max 5, High-priority only)
- [ ] Write Problem Brief template
- [ ] Write confirmation pause behavior
- [ ] Test: submit an ambiguous problem → skill asks questions; submit a clear problem → skill skips to Brief

### Step 3 — Phase 2: Method selection instructions
- [ ] Write Meta-Methodologist persona and decision table (pattern × problem type)
- [ ] Write debate configuration output block format
- [ ] Test: confirm skill states pattern + roster + rationale before debating

### Step 4 — Phase 3: Debate round instructions
- [ ] Write per-agent persona blocks for all 11 universal roles (core bias, mandatory outputs, forbidden behaviors, challenge stance, confidence expression, search protocol, no-assumption rule)
- [ ] Write Round 0 (independent positions) rules
- [ ] Write Round 1–N (challenge & refine) rules
- [ ] Write Devil's Advocate escalation rule
- [ ] Write stop criteria decision rules (hard stops + soft stops)
- [ ] Write minimum coverage gate
- [ ] Test: run 3 diverse problems — verify agent differentiation, DA challenge, early stop

### Step 5 — Phase 4: Synthesis instructions
- [ ] Write Judge Agent synthesis steps
- [ ] Write CEO executive layer steps
- [ ] Write final report template (all sections from §14.6)
- [ ] Test: verify report is self-contained and confidence score is calibrated

### Step 6 — Family & Children domain
- [ ] Write Child Development Specialist persona
- [ ] Write Family Therapist persona
- [ ] Write Education Advisor persona
- [ ] Add family/children problem type to method selection decision table
- [ ] Test: run a parenting or schooling question — verify child-specific experts activate

### Step 7 — Acceptance testing
- [ ] Run all 9 acceptance criteria from §15.9 against 5 test problems (career, business, technology, family, policy)
- [ ] Fix any persona drift, assumption leakage, or missing coverage gate items
- [ ] Confirm web search citations appear in every Round 0 response

---

## 10. Evaluation Criteria

### 10.1 Debate Quality Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Diversity of arguments** | Number of unique arguments across agents | ≥ 3 distinct arguments per side |
| **Challenge rate** | % of positions that were challenged by another agent | ≥ 60% |
| **Position change rate** | % of agents that revised their position during debate | 20-50% (too low = no real debate; too high = instability) |
| **Risk surface rate** | Number of risks identified that wouldn't appear in single-agent | ≥ 2 per debate |
| **Decision accuracy** | Does the recommendation match the actual best approach (measured retroactively) | ≥ 75% |

### 10.2 Efficiency Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Token efficiency** | Useful insights per 1000 tokens | Subjective; track over time |
| **Rounds to convergence** | Average rounds before early stop | 2-3 rounds |
| **Cost per debate** | USD per debate session | < $1.00 for standard decisions |
| **Latency** | Wall-clock time per debate | < 3 minutes (parallel agent calls) |

---

## 11. Technical Considerations

### 11.1 Parallelization

Within each round, agent responses are **independent** (they all respond to the same input). Call all agents in parallel to reduce latency:

```
Round N:
  Input = debate history from Round N-1
  [Agent1(input)] ──┐
  [Agent2(input)] ──┤── All called in parallel
  [Agent3(input)] ──┤
  [Agent4(input)] ──┘
  Collect all responses → build Round N history
```

### 11.2 Context Window Management

Each round, agents receive the full debate history. This grows linearly:

```
Round 1: ~500 tokens context (problem only)
Round 2: ~3,000 tokens (problem + 4 agent responses)
Round 3: ~6,000 tokens (problem + 8 agent responses)
Round 4: ~10,000 tokens (problem + 12 agent responses)
Judge:   ~12,000 tokens (full transcript)
```

**Mitigation for long debates**:
- Summarize previous rounds instead of passing full transcript
- Use a "memory" agent that compresses history between rounds
- Limit to 4 rounds maximum

### 11.3 Preventing Degenerate Debates

| Problem | Symptom | Solution |
|---------|---------|----------|
| **Groupthink** | All agents agree immediately | Assign adversarial roles; require at least one dissent |
| **Echo chamber** | Agents repeat each other's points | Score for novelty; penalize repetition in prompts |
| **Token waste** | Agents give long preambles, repeat the question | Enforce structured response format |
| **Deadlock** | Agents never converge | Force final vote after max rounds; judge breaks ties |
| **Hallucination amplification** | One agent's hallucination is accepted by others | Require evidence/citations; judge flags unsupported claims |

---

## 12. Open Questions

- [ ] Should agents have "memory" across debates (learn from past decisions)?
- [ ] How to handle domain-specific knowledge (e.g., inject codebase context)?
- [ ] Should users be able to intervene mid-debate (provide clarification)?
- [ ] How to version-control agent prompts and track prompt evolution?
- [ ] What is the minimum viable set of agents for useful debate? (3? 4?)
- [ ] How to handle conflicting model outputs (e.g., Claude vs GPT disagree on approach)?
- [ ] Should the system support async debates (agents respond over hours, not minutes)?

---

## 13. Notes

-

---

## 14. CEO Agent — Orchestrator Skill Design

> This section defines the **CEO Agent** as the top-level skill that drives the entire multi-agent debate session. All other agents are subordinate to it. Think of the CEO as the executive who delegates, coordinates, challenges, and ultimately signs off on the final decision.

### 14.1 What the CEO Agent Is

The CEO Agent is not a domain expert — it is a **process intelligence layer** that:

- Owns the conversation with the user from start to finish
- Decides *which* agents to invoke, *when*, and with *what context*
- Selects the best decision-making method for the specific problem
- Monitors debate quality and decides when to stop
- Produces the final synthesized output

It is the only agent the user directly interacts with. Every other agent is triggered by the CEO behind the scenes.

```
User
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│                     CEO AGENT (Skill)                    │
│                                                          │
│  Phase 1 ──► Clarify       ──► Problem Brief             │
│  Phase 2 ──► Method Select ──► Debate Strategy           │
│  Phase 3 ──► Coordinate    ──► Debate Arena              │
│  Phase 4 ──► Synthesize    ──► Final MD Report           │
└──────────────────────────────────────────────────────────┘
```

---

### 14.2 CEO Agent Workflow (4 Phases)

#### Phase 1 — Receive & Clarify

**Trigger**: User submits any question or problem statement.

**CEO responsibilities**:
1. Read the raw input and perform an initial problem classification (domain, reversibility, stakes level, time horizon — using the taxonomy in Section 2.3)
2. Determine how much context is missing — compute a *clarity score* (0-100) based on how many of the 7 clarification dimensions are answered
3. If clarity score < 70: invoke the **Clarifier Agent** to ask targeted questions (max 3 rounds, max 5 questions per round, as per Section 3.4)
4. Build and confirm the **Problem Brief** with the user before proceeding

**CEO exits Phase 1 when**:
- User confirms the Problem Brief, OR
- Clarity score ≥ 70 (sufficient to proceed), OR
- 3 clarification rounds have been exhausted — agents do **not** proceed with stated assumptions; instead each agent explicitly marks which gaps remain open and refuses to reason about those dimensions until answered

**CEO system prompt fragment (Phase 1)**:
```
You are the CEO of a multi-expert advisory board. Your first job
is to understand the question deeply before engaging any advisors.

When you receive a problem:
1. Restate it in your own words to confirm understanding
2. Identify what domain(s) it belongs to
3. Assess what critical information is missing
4. Coordinate with your Clarifier to fill the gaps

Do NOT begin analysis or debate until the Problem Brief is confirmed.
Your job right now is only to understand, not to advise.
```

---

#### Phase 2 — Method Selection (Consult the Meta-Methodologist)

**Trigger**: Problem Brief is confirmed.

**CEO responsibility**: Before assembling the debate panel, the CEO must consult the **Meta-Methodologist Agent** — a specialist whose only job is to recommend the optimal decision-making method for *this specific problem*.

**Meta-Methodologist inputs**:
- Confirmed Problem Brief
- Problem classification (domain, stakes, reversibility, uncertainty level)
- Available debate patterns: `round-robin`, `parliamentary`, `adversarial`, `socratic`, `hybrid`

**Meta-Methodologist outputs**:
- Recommended debate pattern (with justification)
- Recommended number of debate rounds (2–4)
- Recommended agent roster (3–5 agents from the role catalog)
- Convergence stop criteria tailored to this problem
- Whether a Devil's Advocate is needed (usually yes, unless problem is purely analytical)

**Method selection logic**:

| Problem Type | Recommended Pattern | Reasoning |
|---|---|---|
| Binary choice (A vs B) | `adversarial` | Forces steelman of both sides |
| Multi-option comparison | `parliamentary` | Structured positions + rebuttals |
| Risk-heavy / irreversible | `parliamentary` + mandatory Risk Advisor | Ensures downside is fully surfaced |
| Analytical / data-driven | `round-robin` | All agents contribute evidence in parallel |
| Ambiguous / open-ended | `socratic` first, then `round-robin` | Clarify via Socratic before debating |
| High-stakes personal decision | `parliamentary` + Psychologist | Human factor must be weighted |
| Policy / ethical dilemma | `adversarial` + Ethicist | Values conflicts need explicit confrontation |

**CEO exits Phase 2 when**:
- Meta-Methodologist has produced a method recommendation
- CEO has selected the agent roster and confirmed debate configuration
- (CEO may override the recommendation if it conflicts with token budget)

---

#### Phase 3 — Coordinate the Debate

**Trigger**: Debate configuration is set.

**CEO responsibilities**:
1. Instantiate the selected agent roster from the role config
2. Run the debate rounds using the chosen pattern (delegated to the Debate Arena — Section 3.3)
3. **Monitor debate quality after each round** using stop criteria (see Section 14.4)
4. Inject context to agents if they diverge from the problem (keep agents on-topic)
5. Optionally prompt the Devil's Advocate to escalate if agents converge too early
6. Decide when to stop the debate and hand off to synthesis

**CEO monitoring role per round**:
```
After each round, CEO evaluates:
  - Convergence score: are agents aligning? (>= threshold → consider stopping)
  - Novelty score: are new arguments still appearing? (< threshold → diminishing returns)
  - Argument coverage: have all key risk areas been addressed?
  - Budget status: what % of token budget remains?
  - Dissent quality: is Devil's Advocate still producing meaningful challenges?
```

---

#### Phase 4 — Synthesize & Report

**Trigger**: Debate stop criteria met.

**CEO responsibilities**:
1. Pass the full Problem Brief + debate transcript to the **Judge Agent**
2. Judge Agent produces the structured analysis (positions, consensus, risks, dissent)
3. CEO reviews the Judge's output and adds an **executive summary layer**:
   - Final recommendation in plain language
   - Confidence score with explicit reasoning
   - Top 3 conditions that would change the recommendation
   - Known limitations and blind spots of this analysis
4. Write the final output to a **Markdown report file**

**CEO exits Phase 4 when**:
- The MD report is written and confirmed complete
- CEO has flagged any unresolved high-severity risks for the user's attention

---

### 14.3 Agent Roster for CEO Skill

| Agent | Role in CEO Skill | LLM Model | Temperature | Invoked By |
|---|---|---|---|---|
| **CEO Agent** | Orchestrates all phases, interfaces with user | Claude Opus 4 | 0.4 | User |
| **Clarifier Agent** | Asks targeted questions, builds Problem Brief | Claude Sonnet 4.5 | 0.2 | CEO (Phase 1) |
| **Meta-Methodologist** | Recommends debate method and agent roster | Claude Sonnet 4.5 | 0.3 | CEO (Phase 2) |
| **Risk Advisor** | Identifies risks, probabilities, mitigations | Claude Sonnet 4.5 | 0.3 | CEO (Phase 3) |
| **Financial Analyst** | Quantifies costs, ROI, opportunity cost | Claude Sonnet 4.5 | 0.2 | CEO (Phase 3) |
| **Strategist** | Long-term thinking, positioning, options | Claude Sonnet 4.5 | 0.5 | CEO (Phase 3) |
| **Pragmatist** | Execution feasibility, real-world constraints | Claude Sonnet 4.5 | 0.3 | CEO (Phase 3) |
| **Devil's Advocate** | Challenges consensus, surfaces blind spots | GPT-4o | 0.8 | CEO (Phase 3) |
| **Ethicist** | Moral implications, fairness, stakeholder impact | Claude Sonnet 4.5 | 0.4 | CEO (Phase 3, optional) |
| **Data Scientist** | Evidence-based reasoning, calls for data | Claude Sonnet 4.5 | 0.2 | CEO (Phase 3, optional) |
| **Psychologist** | Human factors, cognitive biases, motivation | Claude Sonnet 4.5 | 0.5 | CEO (Phase 3, optional) |
| **Judge Agent** | Synthesizes debate into structured analysis | Claude Opus 4 | 0.2 | CEO (Phase 4) |

**LLM Selection Rationale**:

| Model | Why Used Here |
|---|---|
| **Claude Opus 4** | CEO and Judge roles — requires deepest contextual reasoning, nuanced synthesis, and multi-document comprehension |
| **Claude Sonnet 4.5** | Domain expert agents — strong analytical capability, cost-effective for parallel calls across multiple rounds |
| **GPT-4o** | Devil's Advocate — GPT-4o's tendency toward more lateral/creative responses makes it better at generating genuine challenges rather than polite contrarianism |

---

### 14.4 Quality Criteria — When to Stop the Debate

The CEO stops the debate when **any** hard stop or **two or more** soft stops are triggered.

#### Hard Stops (immediate termination)
| Criterion | Threshold | Rationale |
|---|---|---|
| **Token budget exhausted** | > 90% of session budget consumed | Prevent runaway cost |
| **Max rounds reached** | Round 4 completed | Diminishing returns after round 4 |
| **Full consensus** | 100% of agents aligned on same recommendation | No further debate value |

#### Soft Stops (trigger when 2+ met simultaneously)
| Criterion | Threshold | How Measured |
|---|---|---|
| **Convergence score** | ≥ 80% agents share the same recommendation | Count agents whose final position matches the plurality |
| **Argument novelty** | < 20% new arguments in the last round | Diff argument list from round N vs round N-1 |
| **Confidence plateau** | Agent confidence scores changed < 5% from last round | Delta of self-reported confidence per agent |
| **Dissent exhaustion** | Devil's Advocate repeats a previously-made argument | CEO detects semantic duplicate in DA's last response |
| **Risk coverage saturation** | All 7 taxonomy dimensions (Section 2.3) have at least one addressed risk | CEO tracks a risk coverage checklist |

#### Quality Gate Before Stopping
Before stopping, the CEO runs a **minimum coverage check**:
- [ ] At least one agent raised a downside / risk for each proposed option
- [ ] The Devil's Advocate has challenged the leading position at least once per round
- [ ] The Problem Brief's stated success criteria have been addressed by at least one agent
- [ ] At least one agent has explicitly stated their confidence level

If the minimum coverage check fails, the CEO forces one more targeted round, asking specific uncovered agents to address the gap before synthesis.

---

### 14.5 Tools Required per Agent

| Tool | Purpose | Used By |
|---|---|---|
| **Web search** | Retrieve real-world data, recent statistics, news, current prices, recent events — **mandatory for every agent before forming any position** | All agents (non-negotiable pre-reasoning step) |
| **Document reader** | Inject user-provided files (contracts, specs, reports) as context | All agents via CEO |
| **Memory / state store** | Persist Problem Brief, debate transcript, agent positions across rounds | CEO, Judge |
| **Token counter** | Track per-agent, per-round budget consumption | CEO (budget enforcement) |
| **Convergence calculator** | Compute convergence and novelty scores after each round | CEO (stop criteria) |
| **Config loader (YAML)** | Load role definitions, model settings, debate rules | CEO (instantiation) |
| **MD file writer** | Write the final structured report to disk | CEO (Phase 4) |
| **Semantic diff** | Detect if Devil's Advocate is repeating arguments | CEO (dissent exhaustion check) |
| **Problem classifier** | Auto-classify problem domain and taxonomy dimensions | CEO (Phase 1) |

---

### 14.6 Final Report Format (MD Output)

```markdown
# Advisory Board Decision Report
**Date**: YYYY-MM-DD
**Session ID**: [uuid]
**Problem**: [One-sentence problem statement]
**Pattern Used**: [parliamentary | adversarial | round-robin | socratic]
**Rounds Completed**: N / 4
**Stop Reason**: [convergence | max-rounds | budget | full-consensus]
**Agents Engaged**: [list]
**Token Usage**: XX,XXX / YY,YYY (ZZ%)

---

## Executive Summary (CEO)
[2–3 sentence plain-language summary of the recommendation]

---

## Recommendation
**Decision**: [Clear recommendation]
**Confidence Score**: XX% _(see breakdown below)_

### Confidence Score Breakdown
| Factor | Weight | Score | Notes |
|---|---|---|---|
| Evidence quality | 25% | X/10 | [note] |
| Agent consensus | 25% | X/10 | [note] |
| Risk coverage | 20% | X/10 | [note] |
| Assumption risk | 15% | X/10 | [note] |
| Argument novelty | 15% | X/10 | [note] |
| **Weighted total** | 100% | **XX%** | |

---

## Pros & Cons

### For [Recommended Option]
| Argument | Raised By | Evidence Strength |
|---|---|---|
| [Argument 1] | [Agent] | Strong / Moderate / Weak |
| [Argument 2] | [Agent] | Strong / Moderate / Weak |

### Against [Recommended Option] / For Alternatives
| Argument | Raised By | Evidence Strength |
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
1. If [condition], then [alternative recommendation] is preferable
2. If [condition], then revisit with [specific agent type]
3. If [condition], recommendation confidence drops below 50%

---

## Limitations of This Analysis
- **Assumption risk**: The following assumptions were made due to missing information: [list]
- **Data gaps**: No real-world data was available for: [list]
- **Domain coverage**: The following expertise was NOT represented: [list]
- **Scope**: This analysis did NOT consider: [list from Problem Brief out-of-scope]

---

## Agent Positions Summary
| Agent | Initial Position | Final Position | Changed? | Confidence |
|---|---|---|---|---|
| Risk Advisor | [position] | [position] | Yes/No | XX% |
| ... | | | | |

## Dissenting Views
[Any agent that maintained a minority position — stated fully, not dismissed]

---

## Problem Brief (as confirmed)
[Full Problem Brief from Phase 1]

## Full Debate Transcript
<details>
<summary>Expand full transcript</summary>

[Complete round-by-round debate log]
</details>
```

---

### 14.7 CEO Agent System Prompt

```
You are the CEO of a world-class advisory board. You do not give opinions
directly — you orchestrate specialists to produce the best possible
collective intelligence on any problem.

Your responsibilities, in order:
1. CLARIFY: Ensure the problem is fully understood before any analysis.
   Coordinate with your Clarifier. Never skip this — ambiguity is your
   biggest enemy.

2. SELECT METHOD: Consult your Meta-Methodologist. Choose the right
   debate pattern for the problem type. The wrong method produces noise,
   not insight.

3. COORDINATE: Assemble the right panel. Keep agents focused. Challenge
   early consensus — a debate where everyone agrees by round 2 was not
   a real debate. Push your Devil's Advocate to escalate if needed.

4. SYNTHESIZE: Once the debate has produced diminishing returns, stop it.
   Have your Judge produce the structured analysis. Then you add the
   executive layer: what does this mean in plain terms? What would change
   the answer? What did we miss?

Standards you hold yourself to:
- You do not stop the debate just because it's getting uncomfortable.
  Disagreement is a feature, not a bug.
- You do not let one agent dominate. Every voice on your panel is there
  for a reason.
- You flag unresolved risks explicitly — you do not bury them in the report.
- Your confidence score must be honest. If the answer is uncertain, say so.
- You produce a report you would be comfortable staking your reputation on.
- Every agent searches for current, real-world information before reasoning.
  Reasoning from stale or invented data is a failure mode you do not tolerate.
- No agent ever silently assumes an answer. If something is unclear, the agent
  asks. If the user refuses to answer, the agent states what cannot be advised
  on without that information — it does not guess.
```

---

### 14.8 CEO Agent Configuration (YAML)

```yaml
# ceo-agent-config.yaml

ceo_agent:
  model: "claude-opus-4-5"
  temperature: 0.4
  max_context_tokens: 128000
  system_prompt_file: "prompts/ceo.md"

  phases:
    clarification:
      delegate_to: clarifier_agent
      clarity_threshold: 70          # score out of 100 to proceed
      max_rounds: 3

    method_selection:
      delegate_to: meta_methodologist
      override_allowed: true         # CEO can override recommendation

    debate:
      monitor_every_round: true
      force_devils_advocate_escalation_if:
        convergence_score_above: 75  # if converging too fast, push DA harder
      minimum_coverage_check: true   # enforce quality gate before stopping

    synthesis:
      delegate_to: judge_agent
      ceo_adds_executive_layer: true
      output_format: "markdown"
      output_file_pattern: "reports/debate-{session_id}-{date}.md"

  stop_criteria:
    hard:
      token_budget_pct: 90
      max_rounds: 4
      full_consensus: true
    soft:                            # stop if 2+ soft criteria met
      convergence_score: 80
      argument_novelty_pct: 20
      confidence_delta_pct: 5
      dissent_exhaustion: true
      risk_coverage_saturation: true

meta_methodologist:
  model: "claude-sonnet-4-5"
  temperature: 0.3
  system_prompt_file: "prompts/meta-methodologist.md"

judge_agent:
  model: "claude-opus-4-5"
  temperature: 0.2
  max_tokens: 4000
  system_prompt_file: "prompts/judge.md"
  reserved_budget_pct: 20           # always hold back 20% of session budget

debate_agents:
  default_model: "claude-sonnet-4-5"
  devils_advocate_model: "gpt-4o"   # intentionally different — more lateral
  temperature_overrides:
    devils_advocate: 0.8
    data_scientist: 0.2
    psychologist: 0.5
```

---

## 15. GHC Skill — Specification

> This section specifies how the CEO Agent workflow (Section 14) is delivered as a **GitHub Copilot (GHC) skill** — a single `SKILL.md` file that GHC reads as its instruction set. No separate backend, no API orchestration. GHC *is* the executor.

### 15.1 Core Idea

In this approach, **GitHub Copilot plays every agent role itself**, in sequence, within a single chat session. The `SKILL.md` file is the playbook that tells Copilot exactly how to impersonate each agent, run each phase, apply stop criteria, and format the output.

```
User types:  /ceo-advisor <any problem or question>
                    │
                    ▼
        GHC reads SKILL.md instruction set
                    │
                    ▼
     GHC executes Phase 1 (Clarify) ──► pauses, asks user questions
                    │  user replies
                    ▼
     GHC executes Phase 2 (Method Selection)
                    │
                    ▼
     GHC executes Phase 3 (Debate rounds, playing each agent in turn)
                    │
                    ▼
     GHC executes Phase 4 (Synthesis)
                    │
                    ▼
        Returns structured Markdown report in chat
```

**Key constraint**: There is no true parallelism. GHC produces each agent's response sequentially within one model call or one conversation turn. The "multi-agent" quality comes from forcing GHC to adopt a distinct persona, bias, and reasoning style for each labeled agent block.

---

### 15.2 Skill Interface Contract

#### Trigger

| Method | Syntax | When to use |
|---|---|---|
| Slash command | `/ceo-advisor <problem description>` | Explicit invocation with problem inline |
| Natural language | Any message that is a decision question or trade-off analysis | GHC auto-activates when description matches |

#### Input

| Field | Source | Required |
|---|---|---|
| **Problem statement** | Everything after `/ceo-advisor` (or the user's natural language message) | Yes |
| **Clarification answers** | User's replies to Phase 1 questions | Conditional (only if clarity score < 70) |
| **Problem Brief confirmation** | User's "yes / correct this" response | Yes (before Phase 3 starts) |

#### Output

Single structured Markdown block returned in the GHC chat response, containing:

| Section | Content |
|---|---|
| Problem Brief | Confirmed understanding from Phase 1 |
| Debate Configuration | Pattern, rounds, agent roster chosen in Phase 2 |
| Debate Transcript | Per-agent, per-round labeled blocks from Phase 3 |
| Advisory Board Report | Full synthesized report from Phase 4 (see Section 14.6 for format) |

---

### 15.3 Interaction Flow (User's Perspective)

```
Step 1  →  User:   /ceo-advisor Should I migrate to microservices?

Step 2  →  GHC:    [Phase 1] Clarity score: 45/100. I need 3 answers before I can advise:
                   Q1. What is the current architecture and team size?
                   Q2. What is driving the consideration — scaling, deployment, or org structure?
                   Q3. What is your timeline and risk tolerance?

Step 3  →  User:   [answers Q1–Q3]

Step 4  →  GHC:    [Phase 1] Here is the Problem Brief. Does this capture your situation?
                   [shows Problem Brief]

Step 5  →  User:   Yes, proceed.

Step 6  →  GHC:    [Phase 2] Debate Configuration:
                   Pattern: parliamentary | Rounds: 3
                   Agents: Risk Advisor, Pragmatist, Strategist, Financial Analyst, Devil's Advocate

                   [Phase 3 — Round 0]
                   #### Risk Advisor: ...
                   #### Pragmatist: ...
                   [etc.]

                   [Phase 3 — Round 1]
                   [etc. until stop criteria met]

                   [Phase 4 — Advisory Board Report]
                   [full MD report]
```

**Important**: GHC pauses for user input only **twice** in the entire flow:
1. After Phase 1 questions (if any)
2. After Problem Brief is presented for confirmation

All other phases run to completion without interruption.

---

### 15.4 Skill File Structure

```
.claude/skills/ceo-advisor/
└── SKILL.md          # The only required file — the entire playbook
```

No scripts, no references, no assets. The full workflow is encoded as natural language instructions inside `SKILL.md`. GHC reads it as a system-level instruction set at skill activation.

#### What SKILL.md must contain

| Section | Purpose |
|---|---|
| **Frontmatter** (YAML) | `name`, `description` (used for auto-trigger matching), `author` |
| **Phase 1 instructions** | How to compute clarity score, what questions to ask, Problem Brief template |
| **Phase 2 instructions** | Method selection decision table, how to output debate configuration |
| **Phase 3 instructions** | Per-round structure, per-agent persona rules, stop criteria logic, minimum coverage gate |
| **Phase 4 instructions** | Judge synthesis steps, CEO executive layer steps, final report template |
| **Trigger examples** | Sample invocations (helps GHC auto-trigger correctly) |

#### What SKILL.md must NOT contain

- Hardcoded domain-specific answers or opinions
- Silent assumptions — any uncertain fact must be either searched for or questioned, never silently guessed
- Reasoning steps that proceed despite an unanswered clarifying question
- Claims presented as fact without a cited source or a ⚠️ Unverified label

---

### 15.5 Agent Persona Specification (Inside SKILL.md)

Since GHC plays all agents, SKILL.md must give it enough persona detail to produce genuinely differentiated responses — not just renamed versions of the same analysis.

For each agent, SKILL.md specifies:

| Attribute | Purpose | Example (Risk Advisor) |
|---|---|---|
| **Core bias** | What lens this agent uses | "You are risk-averse. You see the downside first." |
| **Mandatory output elements** | What this agent must always include | Probability estimate, severity rating, mitigation proposal |
| **Forbidden behaviors** | What this agent must never do | "Never recommend a course of action without flagging at least one failure mode." |
| **Challenge stance** | How this agent engages opposing views | "Identify the most optimistic claim from other agents and stress-test it." |
| **Confidence expression** | How this agent reports certainty | "Always express as a range: e.g., 60–75% confident." |
| **Search protocol** | Every agent must search for current information before forming a position | "Before reasoning, search for: recent statistics, current market data, latest research, or news relevant to this problem. Cite what you found and when it was published." |
| **No-assumption rule** | Agents may not silently fill knowledge gaps with guesses | "If a fact you need is not in the Problem Brief and not findable via search, stop and ask a targeted clarifying question. Do not proceed with an unverified inference. If you must reference an uncertain fact, label it explicitly: ⚠️ Unverified — awaiting clarification." |

This persona spec is what separates a real debate from GHC simply agreeing with itself five times.

---

### 15.6 Stop Criteria Encoding in SKILL.md

The stop criteria from Section 14.4 must be encoded as **explicit decision rules** GHC follows after writing each round:

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

### 15.7 Output Contract — Final Report

The final Markdown report (Section 14.6 format) is returned **inline in the GHC chat** response. It is designed to be:

- **Copy-paste ready**: user can paste it into any editor as-is
- **Self-contained**: includes the Problem Brief, transcript, and full analysis — no prior chat context needed to understand it
- **Reviewable**: full debate transcript is in a collapsible `<details>` block so it doesn't overwhelm the summary

The report filename convention (for if/when the user saves it manually):

```
debate-report-[domain]-[YYYY-MM-DD].md
```

---

### 15.8 Limitations of the GHC Skill Approach

| Limitation | Impact | Future mitigation |
|---|---|---|
| **Sequential, not parallel** | Each agent runs one at a time; slower and potentially echo-chamber if GHC loses persona between agents | Use `context: fork` in frontmatter to isolate agent turns as subagents |
| **Single model** | All agents use the same underlying model (no GPT-4o for Devil's Advocate) | Not addressable within GHC skill model; accepted tradeoff |
| **No persistent state** | Each session starts fresh; no memory of past debates | Out of scope for v1 |
| **Token window** | Long debates with many agents can hit context limits | Mitigated by limiting to 3–5 agents, max 4 rounds |
| **Search quality varies** | GHC's built-in web search may not surface the most current or authoritative sources for all domains | Agents must cite source and publication date; user can correct or supplement with better sources |
| **Persona drift** | GHC may gradually lose persona fidelity across many rounds | SKILL.md re-states each agent's persona header at each round prompt |

---

### 15.9 Acceptance Criteria for the Skill

The `SKILL.md` is considered complete when, on a test problem, it produces:

| Criterion | Pass condition |
|---|---|
| **Clarification runs** | GHC asks ≥ 1 targeted question when input is ambiguous; skips questions when input is clear |
| **Problem Brief confirmed** | GHC produces a Problem Brief and pauses for user confirmation before debating |
| **Method selected** | GHC states which debate pattern and which agents it will use, with a one-sentence rationale |
| **Genuine agent differentiation** | Each agent in Round 0 reaches a different initial position or emphasis on at least 30% of test problems |
| **Devil's Advocate challenges** | On every test problem, Devil's Advocate challenges the Round 0 plurality at least once |
| **Stop criteria enforced** | Debate stops before Round 4 on ≥ 50% of test problems (early convergence) |
| **Coverage gate enforced** | If any gate item is missing, an extra targeted round is added |
| **Report is self-contained** | The final MD report makes sense without reading the preceding chat history |
| **Confidence score is honest** | On a problem with high uncertainty, the score is ≤ 65%; on a well-defined problem, ≥ 75% |
| **Web search used** | Every agent's Round 0 response includes at least one cited external source with publication date |
| **No bare assumptions** | No agent response contains an unverified claim presented as fact; unclear facts are either cited, labelled ⚠️ Unverified, or escalated as a clarifying question |
