---
layout: post
title: "From Personal Repo to Work Team — Scaling Squad to Production"
date: 2026-03-11
tags: [ai-agents, squad, github-copilot, scaling, team-workflows, productivity]
series: "Scaling AI-Native Software Engineering"
series_part: 1
---

By now you know the story. In [Part 0](/blog/2026/03/10/organized-by-ai), I told you how Squad became the first productivity system I didn't abandon after three days. Now I'll show you how Ralph and my Star Trek crew assimilated my backlog while I slept.

That was the personal repo. My playground. My experimental sandbox where Picard could make architecture decisions at 2 AM and nobody would complain.

Then came the question I'd been avoiding: *Can I bring this to my actual job?*

My team at Microsoft manages a large-scale infrastructure platform — the kind where real Azure services depend on what we ship. We have code review standards, security scanning, compliance requirements, deployment gates. Six engineers, each with deep expertise. Production systems that can't tolerate "my AI agent had an interesting idea at 3 AM."

This isn't a playground. Could Squad actually work here?

Turns out: yes. But not by copy-pasting my personal setup. The breakthrough wasn't teaching Squad to work *around* my team — it was teaching Squad to work *with* them.

![Resistance is futile](/assets/scaling-ai-part1-first-team/borg-resistance-is-futile.jpg)
*"Resistance is futile. Your work team will be assimilated. Probably."*

---

## Wait, What About My Team?

Here's the problem: In my personal repo, I'm the only human. Picard runs the show. Data writes code. Seven writes docs. Nobody needs permission because there's nobody to ask.

But on a real engineering team? That's six humans with opinions, expertise, and merge authority. You can't just drop an AI team into that and say "assimilate the backlog."

Actually... you kind of can. But only if you do the one thing that changes everything:

**You make the humans part of the Squad.**

---

## Human Squad Members — Not a Workaround, The Whole Point

Remember in Part 0 when I showed you the Squad casting system? Picard as Lead, Data as Code Expert, Worf on Security? That works great when you're the only human.

But here's what I did for the work repo: I added our *real engineers* to `.squad/team.md`.

**Human Squad Members:**

```markdown
## Human Members

- **[Brady Gaster](https://github.com/bradygaster)** (@bradygaster) — Human Squad Member
  - Role: Engineering Lead
  - Expertise: Squad architecture, platform design, Go/C#
  - Scope: Architecture review, cross-team coordination, Squad framework itself

- **Tamir Dresher** (@tamirdresher) — Human Squad Member  
  - Role: AI Integration Lead
  - Expertise: AI workflows, DevOps automation, C#/.NET
  - Scope: Squad adoption, agent orchestration, integration patterns

- **Worf** (@worf-security) — Human Squad Member
  - Role: Security & Compliance
  - Expertise: Compliance & security, supply chain security, threat modeling
  - Scope: Security reviews, compliance validation, infrastructure hardening

- **B'Elanna Torres** (@belanna-infra) — Human Squad Member
  - Role: Infrastructure
  - Expertise: Kubernetes, Azure networking, CI/CD
  - Scope: Cluster operations, deployment automation, infrastructure code
```

**AI Squad Members:**

```markdown
## AI Agents

- **Picard** (AI Lead)
  - Role: Architecture & Orchestration
  - Scope: Task decomposition, design review, delegation
  - Routes to: Brady (human), Tamir (human)

- **Data** (AI Code Expert)
  - Role: Code analysis, review, implementation
  - Scope: Go operators, C# tooling, code quality
  - Routes to: Brady (human, for design), Worf (human, for security)
```

See what happened there? **[Brady Gaster](https://github.com/bradygaster) isn't just "the guy who reviews PRs." He's a Squad member.** So is Worf. So is B'Elanna. They have charters, expertise areas, and scopes — just like the AI agents.

The routing rules in `.squad/routing.md` define when AI squad members pause and escalate to human squad members:

```markdown
## Routing Rules

### Architecture Decisions
- **Trigger:** Changes to CRD schemas, API contracts, multi-repo dependencies
- **Route to:** @bradygaster (human)
- **AI action:** Analysis + recommendations, then pause for human approval

### Security Reviews
- **Trigger:** Authentication, secrets, network policies, supply chain changes
- **Route to:** @worf-security (human)
- **AI action:** Automated scans + findings, then pause for human sign-off

### Go Operator Code
- **Trigger:** Reconciler logic, Kubernetes client code, controller changes
- **Route to:** Data (AI) → @bradygaster (human review)
- **AI action:** Implementation, tests, then PR for human review

### Documentation
- **Trigger:** READMEs, runbooks, API docs, design docs
- **Route to:** Seven (AI) → @tamirdresher (human review)
- **AI action:** Draft, then ping human for review before merge
```

This is the breakthrough. In my personal repo, Squad was *my team* — AI agents working for me. In the work repo, Squad became *our team* — humans and AI working together, with clear escalation paths when human judgment is required.

The AI squad members handle grunt work. The human squad members handle judgment calls. Nobody wastes time on work the other can do better.

---

## But First: The Onboarding That Changed Everything

Before I gave them their first task, I did something that turned out to be the single most important step: I onboarded them. Just like you'd onboard a new hire, I told the squad to scan the entire repo — conventions, docs, architecture, patterns, everything. I gave them links to our internal documentation, internal reference materials, ADR channel, and any reference material I wanted them to know. They indexed it all and built their knowledge base before writing a single line of code.

It's like hiring five engineers who actually READ the onboarding docs. Except they didn't just read them — they synthesized them. They found patterns I didn't even know existed. They built a `.squad/knowledge/` directory with structured summaries of our standards, our tooling, our deployment process, our testing conventions. By the time they started their first actual task, they understood our codebase better than most people who've been here for months.

That's when it hit me: this wasn't just about automation. This was about knowledge transfer at scale.

---

## Teaching the Squad About Your Codebase

Here's the thing nobody tells you about AI agents: you can't just point them at a repo and say "go." That's like hiring a senior engineer and dropping them in on day one with no context, no wiki links, no architecture overview, and expecting production-quality PRs by lunch.

So I did what any engineering lead would do — I built an onboarding plan. Seriously. The same kind of onboarding plan I'd build for a new human team member joining our infrastructure platform team. Except this one was for my AI squad.

The first thing I did after creating the team? I told them to **scan everything**. Every file, every pattern, every architectural decision buried in commit history. I gave them links to our internal documentation, our internal reference materials, architecture decision records, runbook references — literally every piece of context a new team member would need to ramp up. And you know what? They indexed it all. Built their own knowledge base from scratch. By the time they started their first task, they already understood our conventions, our error handling patterns, our testing approach — better than most humans do in their first month.

This is the part that blew my mind: I was basically onboarding new team members, and they were *learning*. Not just following instructions — actually building an understanding of how we work. Here's how it went:

### Step 1: Scan the Repo

I gave Picard (AI Lead) a simple instruction:

```
Scan the entire repo. Look for patterns in:
- How we structure Go packages
- Testing conventions
- Error handling patterns
- Documentation style
- Commit message format
```

Picard delegated to Data (code expert) and Seven (docs expert), and within minutes they came back with a detailed analysis:
- Go tests always use table-driven patterns
- Error wrapping with `fmt.Errorf` + `%w`
- Kubernetes client-go patterns for reconcilers
- Markdown docs with runbooks in `/docs/runbooks/`
- Conventional Commits for all messages

I didn't tell them any of this. They *figured it out* by reading the code. That's the moment I realized this wasn't just automation — it was genuine pattern recognition applied to our codebase.

### Step 2: Index Internal Documentation

We have runbooks, architecture docs, and tribal knowledge scattered across:
- Internal documentation pages
- Team wiki on Azure DevOps
- README files in 12 different repos
- Slack threads (yes, really)

I gave Seven (AI docs expert) links to our internal documentation, Azure DevOps wiki, and every internal reference I could think of — runbooks, architecture docs, deployment procedures, even the tribal knowledge buried in old design docs that nobody reads anymore. I told her:

```
Index everything. Build a knowledge base of:
- How our platform works
- Common failure patterns
- Deployment procedures
- Regulatory compliance requirements
```

She created `.squad/knowledge/` with markdown summaries of all critical docs. Now when any squad member works on a task, they have instant access to our institutional knowledge — the stuff that normally takes months of hallway conversations and Slack scrolling to absorb.

### Step 3: Build the Onboarding Plan

With the scan and indexing complete, I asked Picard:

```
Build an onboarding plan for new squad members. What do they need to know?
```

Picard generated a structured onboarding doc (`.squad/onboarding.md`) covering:
- Repo structure and key packages
- Development workflow (branch strategy, PR process)
- Testing requirements
- Deployment process
- Where to find docs when stuck

Now when we add a new AI agent to the squad (or when [Brady Gaster](https://github.com/bradygaster) or I add a new *human* engineer), they go through the same onboarding. Human or AI, everyone learns the same conventions. The onboarding plan IS the knowledge base, and the knowledge base is always up to date because the squad maintains it.

I can't stress this enough: **this is the single most impactful thing I did**. Before any agent wrote a single line of code, they understood our world. They knew our patterns, our conventions, where to find docs, what our deployment process looks like. They were *ready*.

### Step 4: Continuous Learning

Squad's knowledge isn't static. Every decision we make gets logged in `.squad/decisions.md`:

```markdown
## Decision: Use testify for Go test assertions
- Date: 2026-02-15
- Context: Needed consistent assertion library across repos
- Decision: Standardize on testify/assert and testify/require
- Rationale: Better error messages, widely adopted in Kubernetes community
```

When a squad member (AI or human) makes a decision, it's recorded. When future tasks come up, squad members check `.squad/decisions.md` first. The knowledge base grows organically.

This is critical: **Squad doesn't just execute tasks — it learns your team's culture.**

---

---

## What AI Squad Members Actually Do

With routing rules in place, here's what our AI squad members handle:

### 1. Code Review Pre-Screening

When a PR is opened, Data (AI squad member) does the first pass:
- Scans for obvious issues (unhandled errors, leaked contexts, missing tests)
- Checks against team conventions (from `.squad/decisions.md`)
- Flags security concerns (credentials in code, unsafe resource access)
- Writes a review summary

Then routes to [Brady Gaster](https://github.com/bradygaster) or another human squad member if critical issues are found, or approves routine changes automatically.

**Impact:** Human squad members see PRs that already passed basic quality checks. We spend time on architecture and design, not hunting for forgotten error handling.

### 2. Test Scaffolding

For new Go operator features, Data (AI squad member) generates the test skeleton:
- Unit tests for reconciler logic
- Integration test structure
- Mock Kubernetes client setup
- Coverage tracking

Then hands off to a human squad member to fill in the business logic assertions.

**Impact:** New features ship with tests from day one. The "I'll add tests later" excuse doesn't work when Data already built the scaffolding.

### 3. Documentation Sync

Seven (AI squad member for docs) watches for code changes that affect documentation:
- CRD schema changes → update API reference
- New command flags → update CLI docs
- Helm chart changes → update deployment guide

Drafts the doc updates, creates a PR, and pings the human squad member who authored the code for review.

**Impact:** Documentation stays in sync with code because the sync is automatic. Docs debt doesn't accumulate. And unlike my personal repo where Seven can merge docs freely, here she waits for a human squad member to approve.

### 4. Security Scanning

Our human squad member Worf (the security lead) delegates continuous scanning to AI squad members:
- Dependency vulnerability scans
- Secrets detection
- Supply chain analysis (SBOM generation)
- Regulatory compliance checks

Findings are logged in `.squad/decisions.md` with remediation steps. Critical issues pause the build and route to Worf (human) for review.

**Impact:** Security isn't a gate at the end. It's continuous. Vulnerabilities are caught before they reach production, but a human squad member still makes the final call.

### 5. Cross-Repo Coordination

Our platform has 12 repos. When a change in one repo affects others (API contract change, shared library update), Picard (AI squad member, Lead):
- Identifies downstream impact
- Opens tracking issues in affected repos
- Creates a coordination plan with sequenced PRs
- Monitors the rollout across repos

Then hands the plan to [Brady Gaster](https://github.com/bradygaster) (human squad member, Engineering Lead) for approval before execution.

**Impact:** Multi-repo changes that used to take days of coordination now happen with a single approved plan. The AI squad member handles the sequencing and tracking. The human squad member owns the decision.

---

---

## The First Real Test: Regulatory Compliance Audit

Three weeks after integrating Squad into the work repo, we had a regulatory compliance audit. 47 infrastructure components to validate against security controls. Each component needed vulnerability scans, supply chain attestation, network isolation verification, secrets management audit, and documentation.

Normally this takes two human engineers a full week.

We gave it to the Squad — both AI and human members.

The AI squad members (Worf's delegation rules kicked in here) ran the scans, generated the SBOM, validated network policies, and produced the compliance report — 47 components, 200+ pages — in 6 hours.

Then routed the report to Worf (human squad member, Security Lead) for review.

Findings: 6 vulnerabilities (all patched within the same day), 2 missing network policies (fixed), 1 outdated dependency (upgraded). The report passed human review with minor edits.

**What we learned:**
1. AI squad members are excellent at systematic, repetitive validation work
2. Human squad members are still essential for edge cases and judgment calls
3. The handoff between AI squad members and human squad members needs to be seamless (which Squad's routing handles perfectly)

---

---

## What Doesn't Work (Yet)

Squad on a work repo isn't perfect. Here are the boundaries we've hit:

### 1. Architecture Decisions

AI squad members can *analyze* design trade-offs (performance vs. complexity, cost vs. scale), but they can't *decide* which trade-off to make. That requires understanding business priorities, team capacity, and long-term strategy.

**Current approach:** Picard (AI squad member) drafts the analysis, [Brady Gaster](https://github.com/bradygaster) (human squad member) makes the call. Works well.

### 2. Production Incidents

When a cluster goes down at 2 AM, AI squad members can gather logs, check recent changes, and surface likely root causes — but the final diagnosis and mitigation requires human judgment.

**Current approach:** Ralph pages the on-call human squad member with context. The human decides the fix. AI squad members execute the remediation steps.

### 3. Political/Organizational Context

AI squad members don't understand org dynamics. If a feature request comes from a VP, they treat it the same as a bug report from a junior engineer. That's technically correct, but politically naive.

**Current approach:** [Brady Gaster](https://github.com/bradygaster) and I (human squad members) triage issues with organizational context before AI squad members pick them up. AI handles execution, humans handle stakeholder management.

---

---

## How We Onboarded the Team (Without the Pitchforks)

Introducing AI squad members to a team that didn't sign up for them is tricky. Here's how we did it:

### Week 1: Observation Only
- Squad read-only access to the repos
- AI squad members ran analysis and drafted reports, but no PRs, no code changes
- Human squad members reviewed the output to build trust

### Week 2: Drafts and Suggestions
- AI squad members created draft PRs marked `WIP` with detailed explanations
- Human squad members reviewed, edited, and merged
- Feedback loop: when a draft needed changes, we updated `.squad/decisions.md` so the AI squad members learned team conventions

### Week 3: Delegated Work
- Low-risk tasks (documentation, test scaffolding, dependency updates) delegated to AI squad members with human review
- Critical work (architecture, security, production changes) still owned by human squad members

### Week 4: Full Integration
- Routing rules in place
- AI squad members handle routine work autonomously
- Human squad members focus on design, incidents, and high-judgment calls

**The key:** We never forced it. Engineers who wanted to join as human squad members did. Engineers who preferred traditional workflows weren't blocked. Over time, as people saw the value (faster reviews, better test coverage, docs that stay updated), adoption grew organically.

Resistance? Mostly futile. 🟩⬛

---

## Metrics: What Changed

After 6 weeks with Squad integrated into the work repo, here's what we measured:

| Metric | Before Squad | After Squad | Change |
|--------|-------------|-------------|---------|
| Average PR review time | 18 hours | 4 hours | -78% |
| PRs merged per week | 12 | 23 | +92% |
| Test coverage | 67% | 84% | +17 points |
| Documentation drift (outdated docs) | 22 files | 3 files | -86% |
| Security findings (avg per sprint) | 8 | 2 | -75% |
| Human time spent on toil (estimates, self-reported) | ~35% | ~12% | -66% |

The big wins:
- **Review latency dropped** because AI squad members pre-screened PRs
- **More PRs shipped** because test scaffolding and doc sync were automated by AI squad members
- **Security improved** because scanning was continuous (AI squad members) with human oversight (human squad member Worf)
- **Human squad members had more time** for architecture and design

The tricky part: measuring "quality of thought" on design decisions. Anecdotally, [Brady Gaster](https://github.com/bradygaster) and the human squad members report spending more time thinking deeply about architecture because they're not bogged down in toil. But that's hard to quantify.

---

---

## Cost: What This Actually Costs

Squad on a personal repo is basically free (assuming you have GitHub Copilot). Squad on a work repo with a team? There's a cost.

**Copilot seats:** 6 human squad members + 7 AI squad members = 13 concurrent Copilot sessions during peak hours. Copilot pricing is per-seat, so this matters.

**Compute:** Ralph's watch loop runs 24/7. Background monitoring, scheduled tasks, continuous scanning. We run this on a dedicated VM (Standard D4s v3 in Azure, ~$140/month).

**Token usage:** AI squad members are chatty. Decision logs, routing analysis, cross-repo coordination — all of it generates tokens. We don't have exact numbers (Copilot doesn't expose token-level billing), but anecdotally, our team's Copilot usage is 3-4x higher than before Squad.

**Human time to maintain:** ~4 hours/week (mostly Tamir and [Brady Gaster](https://github.com/bradygaster) — human squad members) to update routing rules, refine agent charters, and handle edge cases where AI squad members get confused.

**Total estimated cost:** ~$400/month (compute + human time). For a 6-person team shipping 23 PRs/week, that's roughly $17 per merged PR. We consider that a bargain.

---

---

## What's Next: When Work Teams Become a Collective

This post covered a single team (our infrastructure platform) with a single Squad — human squad members and AI squad members working together.

But we're already seeing the next challenge:

**What happens when multiple teams across Microsoft adopt Squad?** Do they each build isolated AI teams, or do they share knowledge? Can Squad in the Azure Kubernetes team learn from Squad in the Azure Networking team? What about organizational standards — coding conventions, security policies, architectural patterns — that should apply across all teams?

In Part 3, I'll cover **Squad upstreams** — how we're building a hierarchy of shared knowledge across teams, so that organizational context propagates down to every Squad without manual copy-paste.

From personal repo ([Part 0: Organized by AI](/blog/2026/03/10/organized-by-ai)) to **Part 1: Resistance is Futile** (this post!) to work team (coming next) to organizational scale (coming next).

The assimilation continues. 🖖

![We are the Borg](/assets/scaling-ai-part1-first-team/borg-resistance-is-futile.jpg)
*The assimilation continues. You have been warned.*

---

## Parallel Execution — The Borg Collective in Action

When Ralph assigns a multi-part task, he fans it out across the squad. Here's what a typical multi-agent assignment looks like:

```
→ Troi: Build React component for login page
→ Geordi: Create Express endpoint for authentication
→ Worf: Write integration tests for login flow
→ Picard: Add auth middleware to CI pipeline
```

All four agents start working simultaneously. Troi is creating React components while Geordi is building the Express endpoint while Worf is writing test cases while Picard is updating the pipeline config. This isn't sequential — it's genuinely parallel.

The first time I saw this happen, I just sat there watching the terminal. Four agents, four branches of work, all moving forward at once. The Borg assimilation metaphor isn't accidental — it really does feel like a collective consciousness descending on your codebase.

![Parallel execution diagram](/assets/scaling-ai-part1-first-team/parallel-execution.png)
*Squad's parallel execution flow: one task fans out to multiple agents working simultaneously.*

## Ralph — The Relentless Monitor

Every Squad has a secret member that doesn't show up in the casting table: **Ralph**. Ralph is the monitor — the tireless process that never sleeps, never takes a break, and never stops looking for work to do.

When you say "Ralph, go", here's what happens:

1. Ralph scans your GitHub issues
2. Triages them by labels and priority
3. Assigns them to the right agent based on role
4. Spawns agent sessions to do the work
5. Collects results and updates issues
6. Goes back to step 1

It's a loop, and it's relentless. Ralph doesn't stop until you tell him to stop or there's nothing left to do.

But Ralph isn't just one thing — he operates at three layers:

- **In-session loop**: The basic scan-triage-assign cycle running in your current Copilot session
- **`squad watch`**: A local daemon that persists across sessions, surviving terminal restarts
- **GitHub Actions heartbeat**: A scheduled workflow that runs Ralph in CI, fully unattended — your AI team works while you sleep

The GitHub Actions layer is the one that makes enterprise teams pay attention. You can have Ralph watching your repo 24/7, picking up new issues, assigning them to agents, and creating PRs — all without a human touching the keyboard. I've woken up to merged PRs that I never manually reviewed (though Squad does support required human review, which I'll get to).

![Ralph monitoring loop](/assets/scaling-ai-part1-first-team/ralph-loop.png)
*Ralph operates at three layers: in-session, local daemon, and GitHub Actions — from interactive to fully autonomous.*

## Decisions & Memory

Here's the thing that separates Squad from "just running multiple Copilot sessions": it has a shared brain.

**decisions.md** is the team's collective knowledge base. Every architectural decision, every convention, every "we tried X and it didn't work" gets recorded here. When an agent starts working on a task, it reads decisions.md first. When it makes a significant choice, it writes it back.

This means your team accumulates institutional knowledge. Session 1, Geordi decides to use bcrypt for password hashing. Session 5, Troi is building a password reset form and she already knows bcrypt is the standard because it's in decisions.md.

Each agent also has **history.md** — their individual learning. Geordi's history tracks every API he's built, every database schema decision, every performance optimization. Over time, agents develop genuine expertise in *your specific codebase*.

Then there are **skills** — reusable patterns that agents discover and share. When Geordi figures out your project's error handling pattern, he captures it as a skill. Next time Troi needs to handle errors in a frontend API call, that skill is available to her. Knowledge doesn't just persist — it flows across the team.

The team literally gets smarter session over session. That's not marketing copy — I've watched it happen. By session 10, my Squad was making decisions that would have taken a new human developer weeks to learn about the codebase.

![Decisions and memory system](/assets/scaling-ai-part1-first-team/decisions-memory.png)
*Squad's knowledge system: shared decisions flow to all agents, individual history builds expertise, and skills transfer across the team.*

## Human Team Members

This is the feature that made me realize Squad isn't a toy — it's a legitimate engineering workflow tool.

You can add humans to the Squad roster. Real people, with real GitHub handles, assigned to real roles. When work routes to a human team member, Squad doesn't hallucinate their response or skip the step — it **pauses and waits**.

I added myself to the roster as a human member. Now when Riker's Lead review needs my input, Squad pauses and pings me:

```
📌 Waiting on @tamirdresher for architecture review...
   Task: Login API design needs sign-off before implementation
   Status: Pinged on GitHub, awaiting response
```

The AI team continues working on everything else that doesn't depend on that human review. When I respond, Squad picks up the thread and continues.

This is the killer feature for enterprise adoption. It means Squad doesn't replace your team — it augments it. Senior architects can still own critical decisions. Security reviews still go through humans. But the implementation work, the boilerplate, the test scaffolding — that's handled by agents while humans focus on the hard problems.

"📌 Still waiting on Tamir for architecture review." I've seen this message more times than I'd like to admit. But it means the system is working correctly — it respects human authority in the loop.

## Features the Squad Blogs Don't Cover (From a User's Perspective)

Squad has a lot of surface area. Brady's docs and blog posts cover the architecture well — but here are the features I discovered as a practitioner that changed my daily workflow:

### Export/Import

I exported my team from one repo and imported into another. All the decisions and skills came with them. `squad export` packages your team's accumulated knowledge — decisions.md, skills, routing rules — into a portable bundle. `squad import` drops it into a new repo. Instead of repeating three weeks of learning, my new repo's Squad was productive from session one.

### `squad doctor`

Run `squad doctor` and it validates your entire setup — 9 checks covering config files, agent definitions, upstream connections, and more. All green means you're good. Anything wrong gets a clear diagnostic with a fix suggestion. I run it every time I modify the Squad config. It's saved me from "why isn't this working?" debugging sessions more times than I can count.

### Notifications

Squad pings me on Teams when it needs input. I don't have to watch the terminal. When Riker's review needs my sign-off, or Worf finds a test failure that requires a human decision, I get a notification on my phone. I respond in Teams, and Squad picks up the thread. This is what makes "human in the loop" actually practical — you're not chained to your desk watching agent output scroll by.

### OpenTelemetry + Aspire

I can see agent work in an Aspire dashboard. Traces, logs, metrics — full observability into what every agent is doing, how long tasks take, and where bottlenecks form. When Geordi spent 8 minutes on what should have been a 2-minute API endpoint, I could see exactly where the time went in the trace waterfall. This isn't just debugging — it's understanding your AI team's performance characteristics over time.

### Label Taxonomy

Squad's 7-namespace label system (`status:`, `type:`, `priority:`, `squad:`, `go:`, `release:`, `era:`) gives structure to the chaos. Before Squad, my GitHub issues were a flat list with inconsistent labeling. Now every issue has a clear lifecycle (`status:new` → `status:triaged` → `status:in-progress` → `status:done`), a type (`type:feature`, `type:bug`, `type:chore`), and Squad knows exactly how to route it. It's opinionated, and the opinions are right.

### Context Optimization

decisions.md was getting huge. After three weeks of accumulated decisions across multiple features, it had ballooned in token count. Squad auto-prunes it — consolidating redundant decisions, archiving stale ones, keeping the active context lean. I watched it go from 80K tokens down to 33K without losing any important context. My agents got faster because they weren't wading through outdated decisions about features that shipped two weeks ago.

### Remote Control

`squad start --tunnel` exposes your session via a devtunnel URL. Open it on your phone, and you're controlling your AI team from the couch. I built this integration and [wrote about it here](/blog/2026/02/26/squad-remote-control). It's become my default way to monitor Squad — kick off work at my desk, check progress from my phone during lunch.

## What's Next

This post covered a single repo with a single Squad team. But here's the question that kept me up at night after the first week:

*What happens when you have 5 repos? Do you copy-paste your Squad config into each one? Do decisions in repo A automatically apply to repo B? What about shared coding standards across your organization?*

In [Part 2: "The Collective — Sharing Knowledge Across Repos"](/blog/2026/03/12/scaling-ai-part2-collective), I'll show how Squad's upstream inheritance model turns isolated teams into a connected collective — and why the Borg analogy is even more apt than you think.

Resistance is futile. Your backlog will be assimilated. 🟩⬛

---

> 📚 **Series: Scaling Your AI Development Team**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: Resistance is Futile — Your First AI Engineering Team ← You are here
> - **Part 2**: The Collective — coming soon
> - **Part 3**: Unimatrix Zero — coming soon

