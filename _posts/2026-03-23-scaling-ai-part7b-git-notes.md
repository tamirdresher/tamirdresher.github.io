---
layout: post
title: "The Invisible Layer — Git Notes, Orphan Branches, and the Squad State Solution"
date: 2026-03-23
tags: [ai-agents, squad, github-copilot, git, git-notes, gerrit, distributed-systems, state-management]
series: "Scaling AI-Native Software Engineering"
series_part: "7b"
---

> *"We are the Borg. Lower your shields and surrender your ships. We will add your biological and technological distinctiveness to our own. Your culture will adapt to service us. Resistance is futile."*
> — The Borg Collective

> *(The Borg also did not pollute their commit history with agent session logs. Just saying.)*

I published Part 7 earlier today. The 97-file PR. The three approaches — orphan branch, separate repo, auto-bootstrap worktree. All of them defensible. None of them *satisfying*.

I should have let it go. I had other things to work on.

I did not let it go.

At around 1am I was still mentally running the tradeoffs. Orphan branch: correct isolation, but every new developer who clones the repo needs to learn about the existence of this hidden branch before Squad works. Separate repo: true isolation, but now "what decision did we make about auth last month" requires you to remember which of your two repos has the answer. Worktrees: elegant, but fragile in CI and utterly confusing to explain.

None of these felt like the *right* answer. They felt like compromises I could live with.

I hate compromises I can live with. They have a way of becoming permanent.

---

## The Analogy That Unlocked It

Here's the problem framed simply, because I find it helps when the solution is non-obvious.

You're writing a school essay with your friends in a shared Google Doc. You also keep notes in the same doc — who said what, why you made each decision, who argued about what at 2am. Private team stuff.

Your teacher asks to review the essay. You send him the doc... but it includes **all your private notes too**. He opens it and sees 97 pages — 57 of essay and 40 of "Data suggested JWT, Ralph disagreed and was outvoted, Worf flagged a security concern."

That's not your teacher's problem to read. His job is to review the essay.

This is exactly the issue with Squad state living in the same repo and branch as code. Every pull request dragged in decision logs, agent histories, sprint retrospectives — all the AI team's internal housekeeping — alongside the actual code changes. Two completely different workflows sharing one repo:

- **Code** → slow, human-gated, needs review approval
- **Squad state** → fast, autonomous, no human ever needs to review it

The fix starts with separating those workflows. But once you separate them, you lose something: the *commit-level context*. "Why did the AI choose this algorithm for *this specific commit*?" The full reasoning lives on the orphan branch now — you'd have to go dig there.

That's the gap git notes fills.

---

## The Blog Post I Almost Skipped

Later that same night I was searching for something adjacent to the problem. Not "how to fix squad state in git" — I'd already read everything on that. I was searching for "git store metadata out of band" and "attach metadata to commits without polluting history." The kind of search that surfaces weird corners of the internet.

One result was a long post comparing code review systems at scale — specifically Gerrit vs. GitHub, written by someone who'd worked on both. I almost closed the tab. I had never heard of Gerrit. My entire career has been GitHub and Azure DevOps — and before that Atlassian tools, Jira, Confluence, the whole stack. And before *that*, Perforce. And before *that*, things I try not to mention in polite company (VSS, Rational Team Concert — yes, really). Gerrit was a name I'd seen in passing, something I knew existed because Android uses it, but it felt as relevant to my daily work as a tool from a parallel universe.

Then I saw this line, mid-paragraph:

> *"Gerrit stores review state in `refs/notes/review` — a parallel ref namespace that attaches metadata to commits without ever appearing in the working tree or diff output."*

I stopped.

`refs/notes`.

I had no idea git had a notes feature. None. I've been using git daily for over a decade — commits, branches, rebases, cherry-picks, reflog, bisect, the works — and somehow git notes had never once crossed my path. Not in a tutorial, not in a Stack Overflow answer, not in a colleague's script. It was sitting there the whole time, completely invisible to me.

That was the revelation.

But *Gerrit* had been using it in production. For Android. For Chromium. At Google scale. Since approximately 2009.

That was the rabbit hole.

[meme: "One does not simply walk past a 'refs/notes/review' mention when debugging a distributed state problem at 1am"]

---

## What Git Notes Actually Are

Back to the Google Doc analogy: imagine every commit in git is a sticky note on a wall. It has an ID, a message, and a diff. That's the commit — what changed and when.

Git notes let you attach a **second sticky note** to any commit, without changing the commit at all. The second sticky note is invisible in `git log`, invisible in `git diff`, invisible in PR reviews. It's a parallel namespace.

In essay terms: git notes are the private margin annotations your teacher can never see — but that your team can always retrieve.

```bash
# Attach a note to the current commit
git notes --ref=squad/decisions add \
  -m '{"agent":"Data","decision":"use JWT for auth","reasoning":"existing pattern in codebase"}' \
  HEAD

# Read it back
git notes --ref=squad/decisions show HEAD

# List all objects that have notes in this namespace
git notes --ref=squad/decisions list
```

The note is stored as a blob, indexed by the commit SHA. It lives in `refs/notes/squad/decisions`. It does not appear in `git status`. It does not show up in pull request diffs. A reviewer opens the PR, sees 57 changed files, and none of them are squad decision logs.

This is the property I'd been looking for. Invisible in the places that matter to human reviewers, but *there* — attached to the commit that caused the decision, traveling with the repo.

There's a real gotcha, though, and Q caught it immediately when I shared the approach (Q is my devil's advocate sub-agent — his entire job is to poke holes in ideas that seem clever at 1am).

**Explicit fetch required.** Git does not fetch notes by default. When someone clones your repo and runs `git fetch`, `refs/notes/*` is not included. You need to add the refspec explicitly:

```bash
# Fetch notes from remote — this is NOT part of default fetch
git fetch origin 'refs/notes/*:refs/notes/*'

# Or add it permanently to your git config
git config --add remote.origin.fetch 'refs/notes/*:refs/notes/*'
```

Ralph-watch handles this — it runs the explicit fetch before every work round. But a human developer cloning the repo fresh will not get the notes unless they know to ask for them. This is a real limitation and I'm not going to pretend it isn't.

---

## The Gerrit Validation That Made Me Take This Seriously

Gerrit is Google's code review tool. It has been using `refs/notes/review` since around 2009 — roughly 17 years at the time of writing — to store review state: scores, labels, and submit records. The Android Open Source Project. Chromium. Projects measured in millions of lines of code and thousands of daily commits.

I want to be precise here, because I'm not claiming Gerrit uses git notes for *everything*. Gerrit later built NoteDb, which is an actual database using git as a storage backend in a more sophisticated way. But the original `refs/notes/review` pattern — attaching review metadata to commits via git notes — was production-validated at scale for years.

That's what matters to me. This isn't a pattern I invented at 1am. This is a pattern that Google ran on Android for 17 years. When you're evaluating an architectural approach, "Google did this for 17 years on Android" is about as strong a validation as you're going to find short of a formal proof.

I'd never heard of Gerrit before that night. I still haven't used it. But I recognised the pattern immediately — because the problem it was solving is the same one that kept me up at 1am.

---

## What Q Found (The Honest Version)

Before I started building anything, I ran the approach past Q — Squad's devil's advocate agent, whose job is specifically to find problems with ideas that seem good at 1am.

Q found three real issues.

**One: explicit fetch required.** Already covered above. It's the biggest UX problem. Ralph handles it for agents, but humans won't get notes automatically after a fresh clone. Any tooling that consumes notes needs to document this loudly.

**Two: one note per namespace per object.** Each `refs/notes/REFNAME` namespace holds at most one note per commit. If two agents both try to annotate the same commit in the `refs/notes/squad/decisions` namespace, the second one overwrites the first. The fix is per-agent namespaces:

```bash
# Per-agent namespaces — no collision
git notes --ref=squad/data add    -m '{"decision":"use JWT"}' HEAD
git notes --ref=squad/worf append -m '{"security-review":"approved"}' HEAD
```

**Three: merge conflicts.** Notes stored as blobs can conflict if two agents modify the same commit's note concurrently. Git has a notes merge strategy (`git notes merge`), but it's not well-known and requires explicit invocation. Per-agent namespaces sidestep most of this.

**Q's verdict:** The approach is sound for commit-scoped metadata. Use it for the thin "why did we do THIS on this specific commit" layer. Don't use it as the primary state store for everything Squad needs to remember.

That verdict is exactly right. And it pointed toward the architecture that actually works.

---

## The Two-Layer Architecture

Squad state lives in two places, for two different purposes.

```
┌─────────────────────────────────────────────┐
│               MAIN REPO                      │
│                                              │
│  src/ ──────────────────► PR ► Code Review  │
│  .squad/copilot-instructions.md  (stays)    │
│  .squad/routing.md               (stays)    │
│  .squad/agents/                  (stays)    │
│  .squad/upstream.json            (NEW)      │
│                                              │
│  refs/notes/squad/*   ◄── invisible layer   │
│  (never appears in diffs or PRs)            │
└──────────────────┬──────────────────────────┘
                   │ Ralph-watch
                   │ reads upstream.json on startup
                   │ syncs before every work round
                   │ promotes important notes after
                   ▼
┌─────────────────────────────────────────────┐
│            SQUAD STATE REPO                  │
│         (orphan branch or separate repo)     │
│                                              │
│  decisions.md        (append-only log)      │
│  agent-histories/    (per-agent context)    │
│  ralph/work-queue    (task state)           │
│  ceremonies/         (retros, reviews)      │
└─────────────────────────────────────────────┘
```

Back to the essay analogy: this is what the clean version looks like.

- **The essay** (main branch) → the teacher sees only this. PRs. Human review. The actual work.
- **The team's full diary** (squad-state orphan branch) → all decisions, histories, retrospectives. Agents read and write here directly. No PRs. No teacher ever opens this.
- **The margin annotations** (git notes) → thin commit-scoped "why did we do THIS here" notes. Invisible in PR diffs. Attached to the exact commit that caused the decision. Retrievable by anyone who knows to look.

The `.squad/` folder doesn't disappear from the main repo. It still holds everything GitHub Copilot needs to understand the team: copilot-instructions, routing config, agent charters. What changes is the addition of `upstream.json` — a pointer to where the *live* state actually lives:

```json
{
  "stateRepo": "tamirdresher/squad-state",
  "branch": "squad/state",
  "syncOnStartup": true
}
```

Ralph-watch reads `upstream.json` on startup, syncs the live decisions and histories from the state repo before every work round, and — this is the part that ties the two layers together — **promotes important git notes to `decisions.md`** after a round completes.

The git notes layer is the thin "why did we make this specific choice on this specific commit" layer. Commit-scoped context that travels with the code. When Data makes an interesting architectural decision while working a PR — not just "I chose JWT" but "I chose JWT *because* the existing auth middleware already uses it and adding a second strategy would require refactoring auth.go lines 47-89" — that gets written as a note on the commit. Attached to the code change that caused it. Invisible in the PR, but retrievable when you're debugging six months later.

Ralph promotes the important ones up to `decisions.md` in the state repo. The rest stay as notes — cheap, commit-scoped, invisible.

---

## The PR, Revisited

Let's run the original scenario again, with this architecture in place.

An agent picks up a feature. Works the branch. Makes some interesting choices along the way — writes git notes on the relevant commits. Opens the pull request.

A reviewer opens the PR. What do they see?

- Feature files changed: **57**
- Squad decision logs: **0**
- Agent histories: **0**
- `.squad/upstream.json`: **0 changes** (the pointer is stable)
- Git notes: **0** (invisible in the PR diff, by design)

57 files. All code. Review in 15 minutes, approve, go to lunch.

No private team notes. No AI diary. Just the essay.

Later that week, another engineer wonders why the agent chose JWT for the new endpoint rather than the service's existing API key auth. They look at the commit, run:

```bash
git notes --ref=squad/data show <commit-sha>
```

And find the exact reasoning, timestamp, and agent that made the call.

The margin annotation was there the whole time. It just didn't bother anyone during the review. Exactly like it should be.

---

## What This Is and What It Isn't

I want to be honest: **this is not a complete implementation yet**.

I have the two-layer architecture sketched out. Ralph-watch has the git notes fetch logic. The `upstream.json` pointer is real and in use. The promotion from notes to `decisions.md` is partially implemented. I haven't battle-tested this across a month of real Squad work, and I haven't fully solved the "developer clones fresh and doesn't know to fetch notes" UX problem.

What I *have* is a direction that feels architecturally right, for reasons I can articulate:

- The git notes pattern is validated by 17 years of Gerrit on Android. I didn't invent this.
- Q reviewed it and the objections are *manageable* rather than *fatal*. That's a meaningful distinction.
- The two-layer split matches the actual information architecture of what Squad needs. Commit-scoped context belongs with commits. Long-lived team memory belongs somewhere durable.

I shared the rough shape of this on LinkedIn earlier today before writing the full post (couldn't sleep, had to get it out of my head), and a few people who'd worked on Gerrit confirmed the `refs/notes/review` pattern and added nuances I hadn't considered. That kind of signal matters.

The full implementation and retrospective are coming. But Part 7 left things open and this felt like the right moment to close the loop — even partially.

The Borg have a saying about distributed knowledge: every unit of information should be accessible to the collective, attached to where it originated, and invisible to those who don't need it.

Okay, they don't actually have that saying. But they should.

🖖

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [The Collective — Organizational Knowledge for AI Teams](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — Many Teams, One Repo with SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)
> - **Part 4**: [When Eight Ralphs Fight Over One Login — Distributed Systems in AI Teams](/blog/2026/03/17/scaling-ai-part4-distributed)
> - **Part 5**: [Knowledge is Power — How an AI Squad Learns to Evolve Itself](/blog/2026/03/18/scaling-ai-part5-evolution)
> - **Part 6**: [9 AI Agents, One API Quota — The Rate Limiting Problem](/blog/2026/03/20/rate-limiting-multi-agent)
> - **Part 7**: [When Git Is Your Database — The Enterprise State Problem Nobody Warned Me About](/blog/2026/03/23/scaling-ai-part7-enterprise-state)
> - **Part 7b**: The Invisible Layer — Git Notes, Orphan Branches, and the Squad State Solution ← You are here

*Git notes have existed since git 1.6.6 (2010). Gerrit has been using them in production for longer than most people reading this have been using git. Your AI team's state management problem has a 17-year-old precedent. You're welcome.*
