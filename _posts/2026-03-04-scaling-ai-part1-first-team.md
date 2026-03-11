---
layout: post
title: "Resistance is Futile — Your First AI Engineering Team"
date: 2026-03-04
tags: [ai-agents, squad, github-copilot, scaling, star-trek, borg]
series: "Scaling AI-Native Software Engineering"
series_part: 1
---

> *"You will be assimilated."*  
> — The Borg, Star Trek: The Next Generation

In [Part 0](/blog/2026/03/10/organized-by-ai), I told you how Squad changed my daily workflow — from a guy who can't maintain a todo list to someone with a fully functional AI team that just works. I shared the personal productivity story: Ralph running 24/7, GitHub issues as my task system, the Outlook integration, the podcaster, all of it.

Now I want to talk about something bigger: **what happens when you bring this into a real work repo with a human team?**

This post is about taking Squad from a personal productivity tool to a legitimate engineering workflow in a professional environment. We're going from "my private repo with AI agents doing my todo list" to "our team repo where AI agents work alongside humans."

![Image](https://github.com/user-attachments/assets/06ab6aad-52d4-4e16-a904-4df98b0be3d3)

*"Resistance is futile. Your backlog will be assimilated."*

## From Personal to Professional

When I started using [Squad](https://github.com/bradygaster/squad) (created by [Brady Gaster](https://github.com/bradygaster)), it was just me in my own repo. I could let agents create PRs, approve them, and merge them without asking anyone. It was my playground. I could experiment with prompts, teach the team my preferences, iterate on the decision framework, and generally move fast without breaking anyone else's work.

But my work repos? That's a different story. Those repos have:

- **Real human teammates** who need to review code
- **Established workflows** (branch policies, CI gates, security scans)
- **Production consequences** (breaking main breaks actual users)
- **Team conventions** that can't just be rewritten by an AI on a whim

The question wasn't "can Squad work here?" — the question was "can Squad work here *with humans*?"

Turns out: yes. But it requires thinking differently about how you set up the team.

## Your First `squad init` (At Work)

Setting up Squad in a work repo starts the same way as a personal repo: `squad init`. It walks you through a config file, asks about your project structure, and then does that delightful casting thing where it assigns you a team from one of 31 fictional universes.

For my work repo, Squad picked **Star Trek: The Next Generation**:

| Role | Agent | Specialty |
|------|-------|-----------|
| 🎖️ Lead | **Picard** | Architecture, task decomposition, delegation |
| 🎨 Frontend | **Troi** | UI components, styling, user experience |
| ⚙️ Backend | **Geordi** | APIs, data models, business logic |
| 🧪 Tester | **Worf** | Test suites, edge cases, validation |
| 🔧 DevOps | **Data** | CI/CD, infrastructure, deployment |
| 📄 Research | **Seven** | Documentation, research, presentations |

The names aren't just cosmetic. Each agent has a personality — Geordi is precise, Troi is empathetic about user experience, Worf is aggressive about edge cases. These personas actually produce meaningfully different approaches to the same problem.

But here's the key difference from my personal repo: **I added humans to the team roster.**

## Human Team Members — The Game-Changer

This is the feature that made me realize Squad isn't a toy — it's a legitimate engineering workflow tool.

You can add real people to your Squad roster. Actual humans, with GitHub handles, assigned to real roles. When work routes to a human team member, Squad doesn't hallucinate a response or skip the step — it **pauses and waits**.

In my work repo's `.squad/team.md`, I added myself and my colleagues:

```markdown
## Human Members

### Tamir Dresher (@tamirdresher)
- **Role**: Architect / Security Review
- **Specialty**: System design, API architecture, cluster infrastructure
- **Working Hours**: 9am-6pm Israel time (GMT+2)
```

Now when Picard's architectural review requires human sign-off, Squad pauses:

```
📌 Waiting on @tamirdresher for architecture review...
   Task: Login API design needs sign-off before implementation
   Status: Pinged on GitHub, awaiting response
```

The AI agents continue working on everything else that doesn't depend on me. When I respond, Squad picks up the thread and continues. The work doesn't block — only the specific dependency blocks.

This is the killer feature for enterprise adoption. Squad doesn't replace your team — **it augments it**. Senior architects still own critical decisions. Security reviews still go through humans. But the implementation work, the boilerplate, the test scaffolding — that's handled by agents while humans focus on the hard problems.

## Giving Your First Task

In my personal repo, I'd just type `Team, build the login page` and watch Ralph assign it out. But in a work repo, you want more structure. We use GitHub issues.

I create an issue:

```
Title: Build login page with email/password authentication
Labels: type:feature, priority:high, squad:team, go:yes
```

Ralph picks it up, and Picard (as Lead) analyzes it:

```
🎖️ Picard: Breaking down login page task...
   → Troi: Build login form component with email/password fields
   → Geordi: Create authentication API endpoint with JWT
   → Worf: Write integration tests for login flow
   → Data: Add auth middleware to CI pipeline
```

All four agents start working simultaneously. Troi creates React components while Geordi builds the Express endpoint while Worf writes test cases while Data updates the CI config. This isn't sequential — it's genuinely parallel.

But here's the difference from my personal repo: **each agent creates a PR and assigns a human reviewer**. Troi's PR goes to the frontend lead. Geordi's PR goes to the backend lead. The PRs don't auto-merge — they wait for human approval.

This is the workflow that makes Squad practical in professional environments: AI does the implementation, humans do the review.

## Ralph — Now With Boundaries

Ralph is still the relentless work monitor, but in a work repo, he operates with constraints:

- **No auto-merge without approval** (branch policies enforce this)
- **Security scans must pass** (CI gates block merges)
- **Human reviewers are required** (configured in `.squad/team.md`)
- **Off-hours behavior** (Ralph respects working hours for human pings)

Ralph still runs the same loop:
1. Scan GitHub issues
2. Triage by labels and priority
3. Assign to the right agent
4. Spawn agent sessions
5. Collect results and create PRs
6. **Wait for human review**
7. Merge when approved

The key difference: step 6. Ralph doesn't merge until a human signs off.

You can still run Ralph at three layers:
- **In-session**: The basic scan-triage-assign cycle in your current Copilot session
- **`squad watch`**: A local daemon that persists across terminal restarts
- **GitHub Actions**: A scheduled workflow that runs Ralph in CI, 24/7

The GitHub Actions layer is where this gets interesting for enterprise teams. You can have Ralph watching your repo around the clock, picking up new issues, assigning them to agents, creating PRs — all without a human touching the keyboard. But the PRs still require human review before merging. You get AI velocity with human safety.

## Decisions & Memory — Now Shared Across Humans and AI

The **decisions.md** file becomes even more critical in a work repo, because now it's not just AI-to-AI knowledge transfer — it's **human-to-AI knowledge transfer**.

When your human backend lead makes an architectural decision, it goes in `decisions.md`. When Geordi picks up the next API task, he reads it and applies the standard. When your frontend lead establishes a component pattern, Troi sees it and follows it.

This means your team's institutional knowledge doesn't just live in people's heads or buried in old PR comments — it's written down, queryable, and automatically referenced by every AI agent on every task.

And here's the beautiful part: **AI agents contribute back to decisions.md**. When Geordi discovers a pattern while implementing an API, he documents it. When Worf finds a testing edge case that should be standard practice, he adds it. The knowledge base grows organically as the team works.

Each agent still has **history.md** for individual expertise, and **skills** still transfer across the team. But now those skills are informed by human decisions, human review, and human feedback. The AI team learns from the human team.

## What I Learned Taking Squad to Work

Here's what changed when I moved from my personal repo to a real work environment:

**1. Branch policies are your friend.** Don't disable them for Squad. Configure Squad to work *within* your existing branch policies. Required reviews? Great. CI gates? Perfect. Security scans? Absolutely. Squad works better with constraints.

**2. Humans in the roster changes everything.** Adding real people to `.squad/team.md` turns Squad from "autonomous AI team" into "hybrid human-AI team." It's the difference between a research project and a production workflow.

**3. Documentation quality matters more.** In my personal repo, I could fix decisions.md whenever I noticed a mistake. In a work repo with multiple people, bad documentation means bad decisions from AI agents *and* confusion for humans. Invest in clear, unambiguous decisions.

**4. Start with low-risk work.** Don't hand Squad your authentication layer on day one. Start with chores — dependency updates, test coverage, documentation. Build trust with your human teammates before expanding Squad's scope.

**5. Review discipline is non-negotiable.** In my personal repo, I let agents auto-approve PRs because I trusted my own prompts. In a work repo, every PR gets human eyes. No exceptions. The speed gain comes from parallel implementation, not skipping review.

## What's Next

This post covered taking Squad from personal productivity tool to professional team workflow. One repo, one team, humans and AI working together.

But here's the next question: **What happens when you have multiple repos?** Do you copy your Squad config into each one? Do decisions in repo A automatically flow to repo B? What about shared coding standards across your organization?

In Part 2 (coming soon), I'll show you Squad's **upstream inheritance model** — how to share knowledge across repos, build organizational standards, and turn isolated teams into a connected collective.

Because if Part 1 taught me one thing: Squad works best when it's not fighting your existing workflows, it's *enhancing* them. And when you have 5 repos, 10 repos, 50 repos… you need a system.

Resistance is futile. Your workflow will be assimilated. 🟩⬛

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai) ← Start here
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/blog/2026/03/04/scaling-ai-part1-first-team) ← You are here
> - **Part 2**: The Collective — Organizational Knowledge for AI Teams (coming soon)
> - **Part 3**: Unimatrix Zero — Scaling Squad with Workstreams (coming soon)
