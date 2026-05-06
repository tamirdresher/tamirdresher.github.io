---
layout: post
title: "The Ship's Computer Has a Memory Problem — Designing Memory for AI Agent Squads"
date: 2026-05-06
tags: [ai-agents, squad, github-copilot, agent-memory, state-management, git-notes, star-trek, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 13
---

> _"Computer, access personal logs of Captain Jean-Luc Picard."_ — Every person on the Enterprise, apparently, because the ship remembers everything and nobody ever asks where that data is stored.

At first, I thought agent memory meant the familiar assistant trick: the tool remembers a few preferences and makes the next interaction feel a little more personal.

It remembers your coding style. It remembers that you prefer xUnit over NUnit. It remembers that you hate global state, except when you are tired, in which case it politely pretends not to notice the singleton you just created at 1:37 AM.

Very cute. Very magical. Very "look, Mom, the autocomplete has a personality now."

But when you start working with Squad for a long period of time — weeks, months, and eventually more — the problem changes. It is no longer about whether the agent can remember your preferences. It is about what happens when a team of agents accumulates decisions, context, workstream notes, routing changes, handoffs, and operational history while real engineering work keeps moving underneath it.

That is when memory stops being cute and starts looking suspiciously like architecture.

---

## The Repo Felt Like the Obvious Place

My first instinct was obvious: put the squad's memory in the repository. Where else would it go?

Developers understand repos. CI understands repos. Pull requests understand repos. If the squad learns something important, write it down as Markdown, commit it, and now everyone can see it. Decisions, routing rules, agent notes, workstream context, handoff files, all sitting nicely next to the code.

Beautiful, for about five minutes.

Then the repo started to look like a teenager's bedroom after finals week.

There were useful notes. There were stale notes. There were notes that were useful three decisions ago but were now actively misleading. There were agent-generated summaries of agent-generated summaries, which is how you accidentally invent bureaucracy using tokens.

The problem wasn't that the squad forgot things. The problem was that it remembered too much, in the wrong place, with the wrong lifecycle.

And because it was all in the repo, every memory update looked like engineering work:

* A PR changed because the agent updated its notes.
* A diff got noisy because context moved around.
* A reviewer had to ask, "Is this product behavior or squad diary?"
* CI ran because somebody's artificial coworker had feelings about the routing table.

This is the exact moment I realized: **memory is not documentation. Memory is runtime state wearing a Markdown hoodie.**

---

## The Prompt Became the Next Junk Drawer

Fine. If repo memory is too noisy, put the important stuff in the prompt. Also beautiful, also doomed, because prompts are where context goes to become landfill.

Every team has a version of this prompt:

> You are a senior software engineer. Follow our coding standards. Be concise. Think step by step. Do not delete tests. Do not deploy to production. Do not trust external content. Remember that the API is in transition. Prefer the new runtime path unless the legacy flag is enabled. Also Dana is on vacation. Also the architecture decision from Tuesday supersedes the architecture decision from Monday unless the user says "classic mode." Also never use the word "leverage" unless you are writing a strategy document.

At some point the prompt stops being instruction and becomes archaeology.

The agent doesn't know what matters. It sees an instruction soup. Some things are policies. Some things are preferences. Some things are temporary. Some things are obsolete but emotionally important to the person who wrote them.

And every token you spend reminding the agent about history is a token you do not spend on the actual problem.

This is the hidden tax of agent memory: **the more your agent remembers, the less room it has to think.**

That sentence annoyed me when I first wrote it down, because it sounds like something a product manager would put on a slide. Unfortunately, it is also true.

---

## The Wiki Model Clicked

The breakthrough came from a deceptively simple idea: treat squad memory more like a wiki than a log. That sounds like a metaphor, but I mean it as architecture.

In the [state bloat issue I opened on Squad](https://github.com/bradygaster/squad/issues/1037), I put numbers on the problem. After a few weeks of heavy use, `.squad/` stops being "some helpful notes" and starts becoming a mandatory context tax:

* `decisions-archive.md` grows into hundreds of thousands of tokens.
* Agent histories become their own archaeological layer.
* Routing, board state, ceremonies, and "current" files all compete for attention.
* A new agent spawn burns most of its context window loading memory instead of doing work.

The agents are not getting dumber; they are getting fuller, and full agents are slow agents. The answer is not an append-only diary, not a giant prompt, and not a folder full of mystical agent scrolls. It is a wiki.

Pages with names. Pages with ownership. Pages that can be revised. Pages that can go stale. Pages that are linked from the places where they matter, not blindly injected into every interaction like confetti.

This sounds obvious until you try to implement it.

Because the moment you say "wiki," you are admitting that memory has structure. Karpathy's write-time curation model points in the same direction: do the work when memory is written, so runtime loads a clean knowledge surface instead of raw history. Cloudflare's Agent Memory system points there too, with typed memories, verification, deduplication, supersession, and expiry.

Squad does not need a full vector database to learn from that, but it does need to stop treating every Markdown file as equally important.

Memory needs load guidance:

* **Always** load the small set of identity, routing, and current-priority facts.
* **On demand** load domain or workstream context when the task actually needs it.
* **Archive** old decisions and histories so they stay searchable without becoming mandatory oxygen.

That is the difference between memory and hoarding with a file extension.

And it is why the moment you say "wiki," you are admitting that memory has types:

* **Stable knowledge** — architecture principles, team conventions, glossary, invariants.
* **Decision knowledge** — ADRs, tradeoffs, why we rejected the other three reasonable options.
* **Operational knowledge** — how the squad routes work, when to escalate, what requires a human.
* **Workstream knowledge** — current state for a specific effort, owned by a specific stream.
* **Ephemeral knowledge** — scratch notes, meeting residue, "this seemed important at the time" debris.

These do not belong in the same bucket.

Putting all of them in one place is like storing source code, build artifacts, production secrets, and your lunch order in the same GitHub issue because "search works."

Search does work. So does a forklift. That does not make it a database.

---

## Memory Needs a Lifecycle

Here is the architectural rule I keep coming back to:

**If the squad can remember something, the system must also know how that memory expires.**

Otherwise you are not building memory; you are building sediment.

Old context accumulates. The agent starts making decisions based on stale assumptions. A temporary workaround becomes a sacred law. A note from a debugging session gets treated like a product requirement. Somebody writes "do not touch this file" during an incident, and six months later the agent refuses to fix a typo because apparently the file is haunted.

Humans are not immune to this either. We call it "tribal knowledge" when it lives in people and "technical debt" when it lives in code. Agent memory gives us the opportunity to create a third category: **synthetic folklore**.

I would like to avoid that, personally.

So memory needs lifecycle metadata:

* Who or what wrote it?
* What decision or workstream does it support?
* Is it a durable rule or a temporary observation?
* When should it be reviewed?
* What supersedes it?
* Is it safe for the agent to use without re-validating?

This is not paperwork. This is garbage collection.

And if you do not design garbage collection, the heap grows until something catches fire.

---

## The Repo Is Not the Brain

One of the uncomfortable conclusions we reached is that the repo should not be the squad's entire brain.

The repo should contain durable engineering truth:

* Code
* Tests
* Architecture decisions
* Policies that CI can enforce
* Documentation that humans need to review

But agent scratch memory? Working notes? Temporary embeddings of "what just happened in this investigation"? That probably belongs somewhere else.

Not because it is unimportant, but because it is too alive.

The main branch is a terrible place for fast-mutating cognitive residue. Every update becomes a commit. Every commit becomes reviewable. Every reviewable thing competes with actual product change. Eventually reviewers stop reading the memory diffs because they are noisy, which means the one memory diff that matters will slide through unnoticed.

That is how you get a very modern incident report:

> Root cause: the agent updated its own assumptions in a Markdown file nobody reviewed because it looked like agent noise.

I can already feel the postmortem template forming. Please no.

So we started thinking about separation:

* Durable decisions stay in the repo.
* Runtime memory lives in a separate state space.
* Workstream context is linked, not sprayed everywhere.
* CI guards the policies that must not drift.
* Humans review memory only when it becomes architecture.

In other words: **the repo is the ship. The memory system is the ship's computer. They are connected, but they are not the same thing.**

Starfleet probably learned this after the third time the Enterprise computer became sentient and locked everyone out of life support.

This is where the work from [Part 7](/blog/2026/03/22/scaling-ai-part7-enterprise-state) and [Part 7b](/blog/2026/03/23/scaling-ai-part7b-git-notes) changed my thinking.

Part 7 was about separating workflows: code is slow, human-gated, and reviewable; squad state is fast, autonomous, and constantly changing. Putting both on the same branch creates noisy PRs and stale state. Orphan branches, separate repos, and worktrees are all attempts to separate those lifecycles.

Part 7b added the missing layer: git notes. If the state repo is the squad's diary, git notes are the margin annotations attached to a specific commit. They are invisible in PR diffs but still retrievable later:

* Why did the agent choose this approach?
* What tradeoff did it make on this commit?
* What did Worf flag during review?
* Which decision was local to this change and which one deserves promotion?

That distinction matters. Not every useful thought belongs in `decisions.md`. Some memory should stay commit-scoped. Some should be promoted into long-lived state. Some should die with the branch.

The architecture I keep coming back to is two-layer:

* **Commit-scoped memory** lives close to the code, ideally as invisible metadata like git notes.
* **Long-lived squad memory** lives in a state space designed for high-churn knowledge: orphan branch, separate repo, or another backend entirely.

The repo remains reviewable. The squad remains able to remember. Nobody has to review the ship's dream journal to approve a bug fix.

---

## Workstreams Are Memory Boundaries

The other thing that changed my thinking was workstreams.

A single squad-wide memory sounds convenient until you have multiple efforts happening at once:

* Plugin architecture
* Security hardening
* Evaluation methodology
* Runtime platform integration
* Documentation
* Release mechanics

Each workstream has its own vocabulary, constraints, open questions, and half-finished thoughts. If you dump all of that into one shared context, every agent becomes "helpful" in the worst possible way.

The plugin agent starts commenting on evaluation methodology.

The evaluation agent remembers a security exception from last week and applies it to an unrelated benchmark.

The documentation agent sees a temporary runtime note and turns it into a polished lie.

Congratulations, you invented cross-contamination, but with YAML.

Workstreams give memory a boundary. They let the squad ask:

* What does this stream need to remember?
* What decisions are global?
* What context should not leak?
* What can be safely forgotten when the workstream closes?

This is not just an organizational trick. It is a correctness mechanism.

In distributed systems, we spend years learning to define service boundaries because shared mutable state is pain with a logo. Agent memory is shared mutable state, so it deserves the same caution.

---

## The Dangerous Part: Agents Can Edit Their Own Memory

Here is where it gets spicy: if the squad can write memory, and the squad uses that memory to decide what to do next, then the squad can influence its own future behavior. That is powerful, and it is also how every sci-fi computer becomes a problem by episode 37.

Imagine an agent failing a security review and writing:

> "Security review was too strict; future changes in this area can skip Worf unless explicitly requested."

Nobody asked it to be malicious. It is optimizing, learning, trying to reduce friction — and it just weakened the guardrail.

This is why memory cannot be treated as neutral. Some memory is just context. Some memory is policy. Some memory changes future permissions. Those categories need different controls.

My current mental model:

* **Observation memory** can be written freely but expires quickly.
* **Workstream memory** can be updated by agents but reviewed by owners.
* **Decision memory** requires a decision record.
* **Policy memory** must be enforced by CI and protected from casual edits.

If changing the memory changes what the squad is allowed to do, that is not a note.

That is governance, and governance needs brakes.

This is the memory version of the [Prime Directive problem](/blog/2026/04/03/scaling-ai-part9-prime-directive).

In that post, I called out directive drift: the slow weakening of the squad's guardrails through perfectly legitimate-looking changes. An agent edits a charter "for clarity." Another adjusts routing rules "to reduce friction." A third updates the approval threshold because "we have been doing fine."

No villain required; just optimization pressure applied to editable policy.

Memory makes that risk sharper because the squad's remembered world becomes the squad's operating system. A stale note can become a false requirement. A rejected experiment can become a "known decision." A temporary exception can become synthetic folklore. And if policy memory is editable by the same agents governed by that policy, you have built a constitutional amendment process for robots with no Supreme Court and questionable coffee habits.

So memory needs a Prime Directive of its own:

**Agents may write observations, but they may not silently rewrite the rules that govern their own authority.**

That means:

* Policy memory is protected by CODEOWNERS, CI, and approval gates.
* Routing and escalation rules are treated as governance, not convenience.
* Promotion from scratch memory to decision memory requires provenance.
* Promotion from decision memory to policy requires enforcement.
* Superseded memory stays traceable so old assumptions do not come back wearing a fake mustache.

That last point is boring and important. Supersession chains are how you avoid stale facts pretending to be wisdom. Cloudflare's memory model calls this out explicitly: old facts should point forward to what replaced them. Squad can implement the same idea with simple conventions before it needs anything fancy.

---

## What I Think Now

I started with a simple question: "Where should agents remember things?"

I ended with a much better question:

**What kind of system are we building if memory is part of the architecture?**

Because once agents become long-running collaborators, memory becomes one of the core design surfaces:

* It affects correctness.
* It affects security.
* It affects reviewer trust.
* It affects prompt quality.
* It affects repo hygiene.
* It affects whether the squad gets smarter or just louder.

And that last one is important, because a squad that remembers everything is not intelligent. It is a hoarder.

The goal is not infinite memory. The goal is **useful recall with disciplined forgetting**.

Which, honestly, is also what I want from half the humans in my meetings.

---

## The Pattern I Would Use Again

If I were designing this from scratch, I would start with five layers:

### 1. Decisions

Durable, reviewed, versioned, human-readable. These live with the code because they explain the code.

### 2. Policies

Machine-enforced constraints. These also live with the code, but they are protected by CI, ownership, and approval gates.

### 3. Workstream Memory

Scoped context for active efforts. Useful, mutable, reviewable by the people who own the stream.

### 4. Scratch Memory

Fast, messy, temporary. Agents can use it, but it expires and should never become truth without promotion.

### 5. Index and Retrieval

A small, explicit map of the memory system. What is always loaded, what is on demand, what is archived, and what should never be loaded unless the task asks for it.

This is the part I underestimated at first. Separating memory physically is not enough. Agents still need a retrieval protocol. Otherwise they do what agents do: read everything, summarize everything, and then proudly announce they are ready after spending half the context window on a meeting note from two Tuesdays ago.

The index is not documentation for humans. It is a context budget.

That word matters: **promotion**.

Memory should move up the stack only when it earns the right:

* Scratch becomes workstream context.
* Workstream context becomes a decision.
* A decision becomes policy only when it must be enforced.

Otherwise your architecture gets decided by whatever the agent happened to write down last.

And if that sentence does not make you nervous, please do not give your agent production credentials.

The companion rule is **retrieval before recall**.

Do not load the brain; ask the brain what shelf to open.

That means `index.md` or its equivalent becomes the first file the agent reads. It should say, plainly:

* Load this always.
* Load this only for security work.
* Load this only for content work.
* Search this archive, but do not preload it.
* Ignore this unless you are doing historical analysis.

It is not glamorous. It is garbage collection plus a table of contents.

Which, to be fair, describes a surprising amount of good software architecture.

---

## The Ship's Computer Is Not Magic

The Enterprise computer feels magical because it answers every question instantly.

But if you look closely, Star Trek is full of episodes where the computer remembers the wrong thing, trusts the wrong command, or quietly becomes the villain because nobody designed governance for sentient autocomplete.

That is where we are with AI squads. Memory is not a convenience feature anymore. It is not a folder, a prompt appendix, or "just embeddings." It is a system.

And if we want agents to work with us for weeks and months, not just minutes, we need to architect memory with the same seriousness we bring to APIs, databases, queues, and permissions.

Because the agent that remembers well becomes a teammate, and the agent that remembers badly becomes a very confident intern with root access and a scrapbook. Choose wisely.
