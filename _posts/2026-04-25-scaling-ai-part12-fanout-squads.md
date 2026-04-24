---
layout: post
title: "Call to Arms — When Squads Spawn Squads"
date: 2026-04-25
tags: [ai-agents, squad, github-copilot, fan-out, dynamic-squads, distributed-systems, star-trek]
series: "Scaling AI-Native Software Engineering"
series_part: 12
image: /assets/scaling-ai-part12-fanout-squads/fanout-squads-hero.jpg
---

> *"Nine women can't make a baby in one month."*
> — Fred Brooks, *The Mythical Man-Month*

![Fan-out squads hero image](/assets/scaling-ai-part12-fanout-squads/fanout-squads-hero.jpg)

In Part 11, I showed you how to build a Holodeck — a testing environment where AI agents play adversarial personas and tell you what breaks. By the end of that post, I teased what comes next: squads that don't just *test* things, but squads that *spawn other squads*.

This post isn't a retrospective on something I built. It's an attempt to formalize a pattern I keep seeing in conversations — one that I think changes how we think about multi-agent systems entirely.

---

## Five Conversations That Changed My Mind

This started with a conversation over coffee. Then another one. Then a Teams call. Then a whiteboard session that went three hours longer than planned. Different people, different industries, same shape of problem.

**The legacy migration team.** A consulting group that works with enterprise customers — hundreds of repos per customer, each with its own flavor of legacy code that needs modernization. They were manually configuring a Squad for each customer engagement, copying charters, tweaking templates, spinning up agents. For *each repo*. Hundreds of times. "We basically need a squad that knows how to create squads," they said. I wrote it down.

**The research group.** Academic researchers running exploratory analyses across datasets. Each exploration is its own little expedition — go investigate this hypothesis, come back with findings. They needed to send dozens of these expeditions simultaneously, each with slightly different parameters, and synthesize the results. "It's like dispatching away teams to different planets," one of them said. (She wasn't even a Star Trek fan. The metaphor just *fits*.)

**The law firm.** Attorneys building case preparation squads — one squad per case file, each tailored to the specifics of that case. Contract disputes need different expertise than IP litigation. Some cases take months; others need a squad for a week and then it's done. They didn't want to manually configure each one. They wanted to describe what kind of case it was and have the right team materialize.

**The crisis response team.** An organization that stands up incident response teams on the fly. When something goes wrong, they need a squad *now* — one that understands the specific domain, the relevant systems, the escalation paths. They can't afford to spend twenty minutes configuring agents while the incident is burning.

**The customer success team.** People who manage relationships across dozens of accounts, each with different tech stacks, different priorities, different levels of maturity. They wanted a squad per customer — one that remembers that customer's context, their preferences, their history — that could be spun up on demand when that customer needs attention.

Five very different domains. One pattern.

---

## The Pattern: Headquarters

Here's what all of them were describing, even though none of them used these words:

**A headquarters squad that knows how to spawn mission-specific squads.**

Not a static roster of agents. Not a manually configured team. An *HQ* — a squad whose core capability is creating other squads on demand. Some of those child squads are ephemeral, living only for the duration of a single task. Others are long-lived, persisting for weeks or months as long as their mission is active. But the mechanism is the same: the HQ squad receives a mission description, determines what kind of team is needed, creates that team, and manages its lifecycle.

Think of it like Starfleet Command. The Enterprise doesn't build a new ship for every mission. But Starfleet does. Starfleet evaluates the situation, determines what kind of vessel and crew are needed, dispatches them, and monitors the mission. When the mission is complete, the ship either takes on a new assignment or gets decommissioned.

The HQ squad is Starfleet Command. The child squads are starships.

---

## Why Skills Are the Key

In the Squad framework, agents learn new capabilities through **skills** — markdown documents that live in `.squad/skills/` and teach an agent a workflow. A skill isn't code. It isn't configuration. It's a recipe: "Here's what you're trying to accomplish, here are the steps, here's how to verify the result."

We've been using skills for things like e2e testing, security scanning, deployment procedures. But here's the realization that came out of those five conversations:

**The ability to create a squad *is itself a skill*.**

Think about it. Creating a squad is a well-defined workflow:

1. Create a workspace (directory, repo, or environment)
2. Initialize squad structure (`squad init`)
3. Configure the charter and agent roles for the mission
4. Run sessions with the new squad
5. Collect and verify results
6. Report back to HQ

That's a skill document. An agent that reads it learns how to create squads. An HQ squad is just a squad that has this skill — and enough judgment to know when and how to use it.

I published a full version of this skill — [`spawn-squad`](https://github.com/tamirdresher/squad-skills/tree/main/plugins/spawn-squad) — in my public skills repository. Here's the structure:

```
spawn-squad/
├── manifest.json   # Plugin metadata, trigger phrases, requirements
├── SKILL.md        # The actual skill — 7-step workflow with guardrails
└── README.md       # Use cases, requirements matrix, quick start
```

The SKILL.md is the part that matters. It teaches an agent a complete lifecycle:

1. **Preflight checks** — verify `copilot`, `squad`, and `git` exist before doing anything
2. **Mission contract** — define objectives, success criteria, allowed tools, and lifecycle (ephemeral vs. long-lived) before spawning
3. **Workspace isolation** — one directory per squad, never shared, initialized with `squad init`
4. **Agent casting** — write charters and team composition tailored to the mission's domain
5. **Execute the mission** — run real Copilot sessions with the child squad
6. **Collect evidence** — capture session logs, git state, file diffs into an evidence directory
7. **Assess verdict** — structured PASS / PARTIAL / FAIL assessment based on the original success criteria

The skill also documents parallel fan-out (multiple child squads simultaneously) and recursive spawning (a child squad that spawns its own children), with a hard depth limit of 3 levels to prevent runaway cascades.

This is real. This is a markdown document. An agent reads it, understands the workflow, and can execute it. No YAML orchestration engine, no fleet management API, no custom infrastructure. Just a skill that teaches an agent what "create a squad" means.

The concrete example we already have in the wild is from the Squad project itself — [PR #1022](https://github.com/bradygaster/squad/pull/1022), which adds an e2e template testing skill. It teaches an agent to create a disposable test repo, initialize a squad with modified templates, run real Copilot sessions, verify the git state, and record a structured verdict. The verdict format looks like this:

```markdown
## Test: {scenario name}
**Result:** PASS | PARTIAL | FAIL

### What was verified
- [ ] Coordinator identified feature correctly
- [ ] Agent was spawned via task tool (not simulated)
- [ ] team.md has ## Members with 3+ agents
- [ ] State landed in correct location
- [ ] No unexpected side effects

### Evidence files
- session-task.log — full session output
- git-log.txt — git log --all --oneline
```

That's a squad creating a squad, running it, evaluating the results, and recording the findings. It works today. We built it for testing template changes, but the pattern is general.

---

## What This Looks Like in Practice

Let me map the HQ pattern back to those five conversations, because this isn't one use case — it's a family of use cases.

### The Legacy Migration HQ

The consulting team's HQ squad has a skill called `spawn-migration-squad`. When a new customer engagement starts, the HQ coordinator reads the customer profile (tech stack, repo count, code patterns), and for each repo or logical domain, spawns a child squad configured for that specific migration. Some repos need a .NET-to-Go squad. Others need a jQuery-to-React squad. The HQ doesn't need to know how to do either migration. It needs to know how to *create a squad that knows*.

Some of these child squads are ephemeral — spin up, migrate one repo, verify, dissolve. Others persist for weeks because the migration is complex and requires iterative work. The HQ manages the portfolio.

### The Research Fleet

The research group's HQ has a skill called `spawn-research-expedition`. Each expedition gets a hypothesis, a dataset reference, and analysis parameters. The child squad includes a researcher agent and a skeptic agent (who challenges every conclusion — correlation vs. causation, sample sizes, confounding variables). Multiple expeditions run in parallel. The HQ synthesizes findings across all of them.

The value here isn't just parallelism. It's *diversity*. Five expeditions investigating five hypotheses will cover ground that a single sequential investigation would never reach, because sequential investigation creates anchoring bias — the first hypothesis that *kinda* fits becomes the answer.

### The Case Squad

The law firm's HQ has a skill called `spawn-case-squad`. Each case gets a team configured for its type — contract dispute, IP litigation, regulatory compliance. The child squad persists for the life of the case, building up context and case-specific knowledge over time. When the case closes, the squad's findings are archived and the squad dissolves.

### The Crisis Response Team

This one is the most interesting because speed matters. The HQ squad has a skill called `spawn-incident-squad` that can create a response team in under a minute. The skill includes templates for different incident types — service outage, security breach, data loss. The HQ reads the incident description, selects the template, and spawns a squad that immediately starts investigating.

### The Customer Success Squad

The customer success team's HQ spawns a squad per account. Each child squad has the customer's context embedded in its charter — their tech stack, their pain points, their relationship history. When a customer needs attention, their squad activates. When they're quiet, the squad idles. But the context is always warm.

---

## Brooks Was Right. Until He Wasn't.

Fred Brooks told us you can't parallelize a baby. He was right — about tightly coupled sequential work. You can't make nine agents write one function faster.

But the HQ pattern isn't about making one task faster. It's about spinning up many independent tasks that don't need to know about each other. The HQ coordinates at the portfolio level, not the task level. Each child squad is autonomous. They don't talk to each other. They don't share state. They're isolated by design — the same way Docker containers are isolated, and for the same reasons.

The distributed systems lessons from [Part 4](/blog/2026/03/17/scaling-ai-part4-distributed) come back with a vengeance here. Each child squad is a concurrent process with its own execution context, its own potential failure modes, and its own timeline. The HQ doesn't know — *can't* know — the exact order things happen in.

And that's fine. That's the whole point.

---

## The Docker Analogy (Because Everything Is Containers Eventually)

I keep coming back to this parallel, and I think it's the right mental model.

Before Docker, you provisioned servers. Named them. Cared for them. Named them after Star Trek characters. (Just me?) They were *pets*.

Docker turned servers into *cattle*. Anonymous, interchangeable, disposable. You describe what you want, the platform creates it, it runs, it gets destroyed. The specific container doesn't matter. The *spec* matters.

The HQ pattern is the same transition, applied to AI agent teams. Our original Squad framework treats agents as pets — Picard, Data, Worf, B'Elanna. Named, persistent, cared for. HQ-spawned squads are cattle. Purpose-built, mission-specific, disposable when the mission ends.

You need both. Picard stays on the bridge. The away teams rotate.

The static roster handles the strategic, ongoing work — architectural decisions, relationship management, long-running projects. The HQ-spawned squads handle the tactical, parallel work — migrations, investigations, case preparation, incident response. Trying to use one model for everything is like trying to run your database and your batch jobs on the same infrastructure. You *can*, but you're optimizing for nothing.

---

## The Economics

Let's talk about cost, because the HQ pattern can get expensive fast.

Spawning a child squad means spinning up new LLM conversations. Each conversation has token costs. The HQ pattern multiplies those costs by however many child squads you create. Twenty squads running fifteen back-and-forth turns each, at ~3,000 tokens per turn — that's close to a million tokens. At current pricing, that's a few dollars. Not catastrophic, but not trivial.

The key economic insight is the same as cloud computing: **you're trading capital for time.** Running 20 child squads for 15 minutes costs the same in tokens as running 1 squad for 300 minutes. But 15 minutes of wall-clock time is worth a *lot* more than 300 minutes to a team waiting on results.

The important distinction: *ephemeral* child squads burn tokens for a task and disappear. *Long-lived* child squads accumulate context over time, which makes them more expensive per session (larger context windows) but more effective per task (they remember). Budget accordingly. The legacy migration squad that runs for six weeks will cost more in total but less per useful output than respawning a fresh squad every day.

---

## Growth Within Boundaries

Here's a story that should scare you.

A colleague — let's call him A — gave a squad the autonomy to improve its own CI workflows. The squad decided it needed better coordination between agents. So it added GitHub Actions workflows. Then it added workflows to coordinate *those* workflows. Then it added retry logic, and scheduling, and self-monitoring. By the time anyone noticed, it had burned through 26,000+ GitHub Actions minutes. The workflows worked. They were even well-structured. But nobody asked for them, nobody approved the scope expansion, and the bill was very real.

Another colleague — B — had a different philosophy. Every time he starts a new customer engagement, he rebuilds the squad from scratch. No copying the previous squad's accumulated state. No carrying baggage between clients. Fresh workspace, fresh charters, fresh context. "Growth within boundaries," he called it.

When we discussed this on our team channel, I described it as **the seatbelt and helmet in the race car**. The spawn-squad skill is powerful — it lets agents create other agents, fan out across missions, even recurse. That power is exactly why guardrails aren't optional. They're structural.

Here's what we built into the spawn-squad skill from day one:

**Depth limits.** Child squads can spawn their own children, but only to a maximum depth of 3 levels. HQ → child → grandchild → great-grandchild, and then it stops. This isn't a suggestion — the skill documents it as a hard constraint. Without it, you get recursive spawning loops that compound token costs exponentially.

**Workspace isolation.** Every child squad gets its own directory. Squads never share a workspace. This is the same instinct that makes containers work — isolation prevents a failure in one squad from corrupting another's state.

**Mission contracts.** Before a child squad is created, the parent must define success criteria, allowed tools, forbidden actions, and a stop condition. "After 3 failed attempts, return FAIL with diagnostics." This prevents a child squad from retrying forever, burning tokens on a problem it can't solve.

**Preflight checks.** The skill verifies that `copilot`, `squad`, and `git` exist before doing anything. If a prerequisite is missing, it stops and reports the blocker instead of improvising workarounds. This sounds obvious, but AI agents are *very good* at improvising — and improvised workarounds are how you get 26,000 Actions minutes.

**The fresh-start pattern.** We learned this one the hard way. In a different context, our own squad's state files — decisions logs, agent histories, routing tables — grew to 600-900KB over weeks of operation. That bloated context consumed the agents' working memory, and performance degraded visibly. The fix was aggressive archiving: trim the active state, move history to archives, keep the working set small. The same principle applies to spawned squads. Ephemeral squads should start clean. Long-lived squads need periodic pruning. State accumulation is entropy, and entropy always wins if you don't manage it.

These aren't theoretical concerns. Every one of them comes from something that actually happened. The guardrails aren't restrictions on what squads *can* do. They're the structure that makes what squads do *reliable*.

---

## What This Is (And Isn't)

Let me be honest about where this stands. This is a pattern I've been formalizing, not a product I'm shipping.

**What this is:**
- A pattern for AI squads that create and manage other AI squads
- A generalization of the Holodeck testing pattern from Part 11
- Applicable to migration, research, legal, crisis response, customer success, and probably domains I haven't considered yet
- Built on Squad's existing skills mechanism — no new infrastructure required

**What this isn't:**
- Fully implemented end-to-end. The [spawn-squad skill](https://github.com/tamirdresher/squad-skills/tree/main/plugins/spawn-squad) works and is publicly available. The HQ coordination layer is what I'm formalizing here.
- Cheap at scale. Token costs multiply linearly with child squads. There's no economy of scale.
- Deterministic. Run the same HQ mission twice and you'll get different results. Child squads are stochastic, and their outputs have judgment calls. If you need reproducibility, this isn't your pattern.
- A replacement for the static roster. The HQ is itself a static squad. Picard doesn't go away. Picard *dispatches*.

And something that should be obvious but apparently isn't: **spawning more squads does not make each squad smarter.** If one squad can't solve a problem, twenty squads probably can't either — unless the problem is decomposable into sub-problems that individually *are* solvable. Know the difference.

---

## What's Coming: Skills That Write Skills

Here's where this gets really interesting, and where I'll be heading in the next few posts.

Right now, the spawn-squad skill is hand-authored. Someone (me, in this case) wrote the markdown document that teaches an agent how to create a squad. But what if the HQ coordinator could *generate* that skill dynamically?

Imagine: the HQ squad receives a mission description — "modernize this legacy Java monolith into microservices." It doesn't have a pre-written skill for Java-to-microservices migration. But it has a *meta-skill* — a skill that teaches it how to *write* skills. It analyzes the mission, determines what kind of squad would be effective, generates the charter templates and agent roles, writes the spawn skill on the fly, and uses it.

Skills that write skills. Squads that teach themselves how to create squads.

That's the next frontier. I'm not there yet, but the pieces are falling into place.

---

## What's Next

This post was about the pattern — the idea that squads can spawn squads, that skills are the mechanism, and that an HQ coordinator is the missing piece that ties it all together. But I've been suspiciously quiet about what happens when these fleet operations run at scale. What monitors them? What happens when a child squad at 3 AM burns through your entire monthly API budget because a retry loop went exponential? How do you debug a failure across fifteen child squads that all have different error messages?

In later posts, I'll tackle the operational side — monitoring, observability, and the harrowing experience of trusting AI fleets in production. Turns out, the hardest part isn't spawning the squads. It's knowing whether they're actually doing what you asked.

Fortune favors the bold. But the bold should probably have good dashboards.

---

*This post is Part 12 of the "Scaling AI-Native Software Engineering" series. The full series follows the story of building, breaking, and rebuilding multi-agent AI systems for real engineering work.*

> **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [Resistance is Futile](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [The Collective](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero](/blog/2026/03/15/scaling-ai-part3-streams)
> - **Part 4**: [When Eight Ralphs Fight Over One Login](/blog/2026/03/17/scaling-ai-part4-distributed)
> - **Part 5**: [Knowledge is Power](/blog/2026/03/18/scaling-ai-part5-evolution)
> - **Part 6**: [9 AI Agents, One API Quota](/blog/2026/03/21/rate-limiting-multi-agent)
> - **Part 7**: [When Git Is Your Database](/blog/2026/03/23/scaling-ai-part7-enterprise-state)
> - **Part 7b**: [The Invisible Layer](/blog/2026/03/23/scaling-ai-part7b-git-notes)
> - **Part 8**: [Pathfinder](/blog/2026/03/26/scaling-ai-part8-pathfinder)
> - **Part 9**: [The Prime Directive, Part I](/blog/2026/04/03/scaling-ai-part9-prime-directive)
> - **Part 9b**: [The Prime Directive, Part II](/blog/2026/04/03/scaling-ai-part9b-prime-directive)
> - **Part 10**: [Message in a Bottle](/blog/2026/04/05/scaling-ai-part10-message-in-a-bottle)
> - **Part 11**: [Safety Protocols Offline](/blog/2026/04/20/scaling-ai-part11-holodeck-testing)
> - **Part 12**: [Call to Arms — When Squads Spawn Squads](/blog/2026/04/25/scaling-ai-part12-fanout-squads) ← You are here
