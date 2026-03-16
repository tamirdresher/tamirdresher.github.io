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

- **John Doe** (@j__ohndoe) — Human Squad Member
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
  - Routes to: John Doe (human), Tamir (human)

- **Data** (AI Code Expert)
  - Role: Code analysis, review, implementation
  - Scope: Go operators, C# tooling, code quality
  - Routes to: John Doe (human, for design), Worf (human, for security)
```

See what happened there? **John Doe isn't just "the guy who reviews PRs." He's a Squad member.** So is Worf. So is B'Elanna. They have charters, expertise areas, and scopes — just like the AI agents.

The routing rules in `.squad/routing.md` define when AI squad members pause and escalate to human squad members:

```markdown
## Routing Rules

### Architecture Decisions
- **Trigger:** Changes to CRD schemas, API contracts, multi-repo dependencies
- **Route to:** @j__ohndoe (human)
- **AI action:** Analysis + recommendations, then pause for human approval

### Security Reviews
- **Trigger:** Authentication, secrets, network policies, supply chain changes
- **Route to:** @worf-security (human)
- **AI action:** Automated scans + findings, then pause for human sign-off

### Go Operator Code
- **Trigger:** Reconciler logic, Kubernetes client code, controller changes
- **Route to:** Data (AI) → @j__ohndoe (human review)
- **AI action:** Implementation, tests, then PR for human review

### Documentation
- **Trigger:** READMEs, troubleshooting guides, API docs, design docs
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

The first thing I did after creating the team? I told them to **scan everything**. Every file, every pattern, every architectural decision buried in commit history. I gave them links to our internal documentation, our internal reference materials, architecture decision records, troubleshooting guide references — literally every piece of context a new team member would need to ramp up. And you know what? They indexed it all. Built their own knowledge base from scratch. By the time they started their first task, they already understood our conventions, our error handling patterns, our testing approach — better than most humans do in their first month.

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
- Conventional Commits for all messages

I didn't tell them any of this. They *figured it out* by reading the code. That's the moment I realized this wasn't just automation — it was genuine pattern recognition applied to our codebase.

### Step 2: Index Internal Documentation

We have troubleshooting guides, architecture docs, and tribal knowledge scattered across:
- Internal documentation pages
- Team wiki on Azure DevOps
- README files in 12 different repos
- Teams threads (yes, really)

I gave Seven (AI docs expert) links to our internal documentation, Azure DevOps wiki, and every internal reference I could think of — troubleshooting guides, architecture docs, deployment procedures, even the tribal knowledge buried in old design docs that nobody reads anymore. I told her:

```
Index everything. Build a knowledge base of:
- How our platform works
- Common failure patterns
- Deployment procedures
- Regulatory compliance requirements
```

She created `.squad/knowledge/` with markdown summaries of all critical docs. Now when any squad member works on a task, they have instant access to our institutional knowledge — the stuff that normally takes months of hallway conversations and Teams scrolling to absorb.

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

Now when we add a new AI agent to the squad (or when I or someone else on the team add a new *human* engineer), they go through the same onboarding. Human or AI, everyone learns the same conventions. The onboarding plan IS the knowledge base, and the knowledge base is always up to date because the squad maintains it.

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

Here's what surprised me most about how this played out in practice.

I expected the AI squad members to be like junior developers — useful for grunt work, but needing constant supervision. What I got was something closer to having five teammates who never sleep, never complain about boring work, and actually *read the team conventions doc* before submitting a PR. (If you've managed engineers, you know that last part is the real miracle.)

The first thing I noticed was code reviews. When a PR comes in, Data does a first pass before any human sees it. Not a quick linting check — I mean a real review. He scans for unhandled errors, leaked contexts, missing tests, credentials in code, the whole thing. He checks everything against our team conventions in `.squad/decisions.md`. By the time John Doe or one of the other human squad members opens the PR, the obvious stuff is already flagged. It's like having a tireless reviewer who catches the things humans miss because they're on their fourth PR of the afternoon and just want to go home.

Then there's test scaffolding. This one genuinely changed how we ship features. For every new feature, Data generates the full test skeleton — unit tests, integration test structure, dependency injection setup, mocks, coverage tracking. He hands it off to a human squad member to fill in the business logic assertions. The "I'll add tests later" excuse? Dead. You can't say you'll add tests later when the test file is already there, waiting for you, with helpful comments about what to assert. It's the most passive-aggressive productivity boost I've ever experienced.

Seven handles documentation sync, and honestly, this is the one I underestimated the most. She watches for code changes that affect docs — CRD schema changes, new command flags, Helm chart modifications — and automatically drafts doc updates, creates a PR, and pings the human who authored the code change for review. Documentation drift used to be our quiet shame. Now it just... doesn't happen. Unlike my personal repo where Seven can merge docs freely, here she waits for a human squad member to approve. But the drafts are good enough that reviews take seconds.

Security scanning became continuous instead of a gate at the end. Worf (our human security lead) delegates the systematic scanning to AI squad members — dependency vulnerabilities, secrets detection, supply chain analysis, SBOM generation, compliance checks. Findings get logged in `.squad/decisions.md` with remediation steps. Critical issues pause the build and route to Worf for review. Security isn't something we bolt on at release time anymore. It's just... running. All the time.

And then there's cross-repo coordination, which used to be the thing I dreaded most. Our platform spans 12 repos. When a change in one repo affects others — an API contract change, a shared library update — Picard identifies the downstream impact, opens tracking issues in affected repos, creates a coordination plan with sequenced PRs, and monitors the rollout. Then hands the plan to John Doe for approval before execution. Multi-repo changes that used to take days of "hey, did you update repo X?" conversations now happen with a single approved plan.

The pattern across all of this is the same: AI squad members handle the systematic work. Human squad members handle judgment calls. Nobody wastes time on work the other can do better. And honestly? The humans got better at their jobs too, because they finally had time to think deeply about architecture instead of drowning in the daily grind.

---

## The First Real Test

Three weeks in, I connected Squad to our Kubernetes provisioning wizard repo. Matrix-themed squad this time: Morpheus as Lead, Trinity on Backend, Switch on Frontend, Dozer on Testing. I pointed them at our Microsoft Planner board (52 open tasks), configured each task to get its own git worktree, and said "go."

Five investigations launched simultaneously. I watched five terminal sessions spin up in parallel, each agent pulling a different Planner task into its own worktree.

Within the first hour, Dozer found a real bug: the MCP ClientID was misconfigured — we'd been passing the wrong value to our auth layer and nobody had caught it because the integration tests were mocking it. Trinity flagged that we had `gpt-4o` hardcoded in three places — a retirement risk since Azure OpenAI was deprecating that deployment name. Switch found an `onClick` handler in the React provisioning wizard that was wired up in JSX but had no implementation. Just an empty function sitting there, waiting to confuse someone.

None of these were hypothetical. These were real bugs in production-adjacent code that six humans had missed during regular reviews.

The most useful part wasn't the bugs themselves — it was the *speed*. Five parallel investigations, each in its own worktree, each producing a PR with tests. By end of day, I had five PRs ready for human review. On a normal day, that's a week of work across the team.

Teams notifications helped here too. Every time an agent needed human input or finished a task, I got a ping. I reviewed PRs from my phone during a meeting (don't tell my manager).

---

## Hidden Capabilities That Changed Everything

Once Squad was running on the work repo, I stumbled into features I hadn't seen in any docs. These weren't buried — I just hadn't needed them until I was operating at team scale.

### Export/Import: Seed New Repos Without Starting From Scratch

Squad configs can be exported from one repo and imported into another. This is how you seed new repos without starting from scratch — you take the team definitions, routing rules, knowledge base, and decision log from a working repo and transplant them.

```bash
squad export --output ./squad-template
```

This dumps your entire `.squad/` directory into a portable template. Then in a new repo:

```bash
squad import --from ./squad-template
```

The new repo gets your team structure, routing rules, conventions, and decision history — ready to customize. When we onboarded our second repo, what took two weeks the first time took twenty minutes.

### Aspire/OpenTelemetry Integration: The Missing Observability Layer

When running Squad agents through .NET Aspire (which I covered in a [previous post](/blog/2025/12/16/scaling-ai-agents-with-aspire-isolation.html)), you get full distributed tracing of agent operations. Each agent task shows up as a span in the Aspire dashboard. You can see token usage, API call latency, and which agent is doing what — all in the same place you monitor your actual services.

This was the missing observability layer. Before this, agent operations were a black box — you'd kick off five parallel tasks and just... hope. Now I can see that Data spent 45 seconds on a code review, used 12K tokens, made 3 API calls to the language model, and produced a review with 7 findings. When an agent task takes too long, I can see exactly where it's stuck. When costs spike, I can trace it to the specific agent and operation.

### Teams Notifications: Keep Humans in the Loop Without Context-Switching

Squad can notify your team channel when tasks complete, when it needs human review, or when something fails. Config is one line in `.squad/config.yml`:

```yaml
notifications:
  teams:
    webhook: <url>
```

That's it. Now when Picard finishes decomposing a task, when Data opens a PR for review, when Worf flags a security finding — your team gets a ping in Teams. No more checking terminals. No more "did the agent finish yet?" The notification includes a summary and a direct link to the PR or issue. This is what made the "reviewed PRs from my phone during a meeting" workflow possible.

---

## What's Next

This post covered one team with one Squad. But what happens when decisions in repo A should apply to repo B? When coding standards need to propagate across 12 repos without copy-paste?

In [Part 2](/blog/2026/03/12/scaling-ai-part2-collective), I'll show how Squad's upstream inheritance model turns isolated teams into a connected collective. The Borg analogy gets more apt. 🖖

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team) ← You are here
> - **Part 2**: [The Collective — Organizational Knowledge for AI Teams](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — Many Teams, One Repo with SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)

