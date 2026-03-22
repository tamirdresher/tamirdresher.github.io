---
layout: post
title: "The Squad Ledger — Giving Your AI Team a Memory That Survives Rejected PRs"
date: 2026-03-22
tags: [ai-agents, squad, github-copilot, enterprise, git, state-management, distributed-systems, star-trek]
series: "Scaling AI-Native Software Engineering"
series_part: 9
---

![The Squad Ledger](/assets/scaling-ai-part9-squad-ledger/hero.png)

In [Part 7](/blog/2026/03/22/scaling-ai-part7-enterprise-state), I showed you the mess. Ninety-seven files in a PR. Forty of them squad memory. Corrupted JSON from line-based merges. Two agents making decisions in parallel that neither could see. Code reviewers drowning in `.squad/` diffs instead of reviewing actual features.

I laid out four approaches and said "I'm still figuring it out."

I couldn't leave it at that. The problem kept nagging at me, and I think I found the answer.

---

## The Ledger Pattern

When I started thinking about where to put the squad state if not in the main repo, I kept coming back to the idea of a side-repo. But calling it "upstream" was confusing — in git, "upstream" already means the remote you pull from. So I started thinking of it as a **Ledger** — a separate, append-only record of everything the squad knows and decides.

The metaphor fits:

- **Append-only** — you don't rewrite history in a ledger. You add new entries.
- **Authoritative** — when there's a disagreement about what was decided, the ledger is the source of truth.
- **Multi-writer** — multiple agents can append entries without overwriting each other.
- **Timestamped** — every entry has a date, an author, and a context.
- **Never deleted** — even voided entries stay in the book, crossed out but visible.

Financial ledgers have worked this way for five hundred years. Turns out the same properties are exactly what you need for AI agent memory.

---

## The Architecture

Here's the shape of it. Two repos. One sync mechanism. One pointer file.

![Full Architecture — Code Repo, Ledger, and Git Notes](/assets/scaling-ai-part9-squad-ledger/full-architecture.svg)

```
CODE REPO (your-project)              LEDGER REPO (squad-ledger)
┌──────────────────────────┐          ┌──────────────────────────────┐
│                          │          │  branch: squad/state         │
│  .squad/                 │          │                              │
│    ledger.json ──────────┼── ptr ──→│  .squad/                     │
│    decisions.md    ◄─────┼── sync ──│    decisions.md              │
│    routing.md      ◄─────┼── sync ──│    routing.md                │
│    agents/         ◄─────┼── sync ──│    agents/                   │
│                          │          │      picard/history.md       │
│  .github/workflows/      │          │      data/history.md         │
│    squad-ledger-sync.yml │          │      seven/history.md        │
│                          │          │    branches/                 │
│  src/                    │          │      feature-auth/           │
│  tests/                  │          │      _archived/              │
│  ...                     │          │    knowledge/                │
└──────────────────────────┘          └──────────────────────────────┘
         │                                        ▲
         │         SYNC FLOW                      │
         ▼                                        │
┌─────────────────────────────────────────────────────┐
│                  GitHub Actions                      │
│                                                      │
│  push to main ──→ publish .squad/ state changes      │
│  PR merged    ──→ promote scoped decisions           │
│  PR closed    ──→ withdraw scoped decisions          │
│  cron (6hr)   ──→ drift detection (Ralph)            │
└──────────────────────────────────────────────────────┘
```

The code repo is still the source of truth. Agents still read and write to `.squad/` in the code repo, same as always. They don't know the ledger exists. They don't care. They just write their decisions, update their histories, do their thing.

The ledger repo is a **durable mirror** — a separate repository with a single orphan branch called `squad/state`. No branch protection. No PR requirements. Agents don't push there; a GitHub Actions workflow handles the sync automatically.

The connection between them is a single file: `.squad/ledger.json`.

```json
{
  "ledger": {
    "repo": "tamirdresher/squad-state-upstream",
    "branch": "squad/state",
    "type": "git",
    "sync": {
      "mode": "github-actions",
      "on_push_to_main": true,
      "on_pr_merge": true,
      "on_pr_close": true,
      "drift_check_cron": "0 */6 * * *"
    }
  }
}
```

That's the whole pointer. The sync workflow reads it, knows where to push, and handles the rest. If you want to move your ledger to a different repo — maybe you're migrating organizations, or you want to split your team's state — you change one JSON file. Everything else follows.

---

## The Hard Problem: Branch-State Correspondence

Here's where it gets interesting. And by "interesting" I mean "the thing that required a design document and way too much thinking."

The architecture above solves the *storage* problem — where does state live. But it doesn't solve the *semantics* problem: **what happens to a decision when the branch it was made on gets rejected?**

Let me walk you through three scenarios that kept me up at night.

### Scenario 1: The Rejected Feature

Data is working on `feature/auth-middleware`. He researches JWT vs session tokens, decides JWT with RS256 is the right call, writes it to `.squad/decisions.md`, and implements the middleware. PR goes up.

The team reviews it. They don't like the approach — they want OAuth2 with PKCE instead. PR rejected. Branch deleted.

But Data's decision — "Use JWT for auth middleware" — is already in `.squad/decisions.md`. If we naively sync that to the ledger, it becomes permanent team knowledge. Future agents will read it and think "we decided to use JWT." Except we didn't. The team explicitly rejected that direction.

**Bad outcome:** Agent memory contains a decision the team vetoed.

### Scenario 2: The Universal Truth

Seven is working on `feature/docs-overhaul`. While updating documentation, she discovers that the team's routing rules need an update — Worf should handle all security-related issues, not just the ones tagged `security`. She updates `.squad/routing.md`.

This routing change has nothing to do with the docs feature. It's a universal truth about how the team operates. If the docs PR gets rejected (maybe the formatting was wrong), the routing update should still survive.

**Bad outcome:** A universally correct change gets thrown out because it was committed alongside an unrelated feature.

### Scenario 3: The Valuable Failure

Data researches JWT vs session tokens for `feature/auth-middleware`. The feature gets rejected. But the *research itself* — the comparison of JWT RS256 vs HS256, the analysis of token expiration patterns, the security tradeoffs — that's genuinely valuable. Next time someone works on auth, they shouldn't have to redo that research from scratch.

**Bad outcome:** Valuable knowledge gets destroyed because the feature it was attached to didn't land.

Three scenarios. Three different correct answers. You can't solve this with a simple "if PR merges, keep the state; if PR closes, delete the state."

---

## The Solution: Scoped Decisions with Lifecycle

The answer is metadata. Every decision gets two new fields: **Scope** and **Lifecycle**.

```markdown
### Decision: Use JWT for auth middleware
- **Scope:** `branch:feature/auth-middleware`
- **Lifecycle:** `pending-merge`
- **Date:** 2026-03-22
- **Author:** Data

JWT with RS256 is the right call for the middleware layer because
it allows stateless verification across microservices without
requiring a shared session store...
```

Scope tells you *what this decision is attached to*. Lifecycle tells you *what should happen to it*.

Here are the lifecycle states:

| State | Meaning | Who Sets It |
|-------|---------|-------------|
| `permanent` | Always valid. Not tied to any branch. | Agent (on creation) |
| `pending-merge` | Valid only if the associated branch merges. | Agent (on creation) |
| `merged` | Was `pending-merge`, branch has now merged. Effectively permanent. | Sync workflow (automatic) |
| `withdrawn` | Branch was rejected/closed. Decision is no longer active. | Sync workflow (automatic) |
| `superseded` | Replaced by a later decision. | Agent (when making a new decision) |

The crucial thing: **agents set the initial lifecycle, but only the sync workflow transitions it**. An agent can't mark its own decision as "merged" — that would be like a defendant ruling on their own case. The GitHub Actions workflow watches for PR events and handles the state transitions automatically.

When a PR merges, the workflow finds all `pending-merge` decisions scoped to that branch and promotes them to `merged`. When a PR is closed without merging, it marks them `withdrawn`. The decision stays in the file — visible, auditable — but clearly labeled as "the team said no."

Here's the workflow logic for that transition:

```bash
# On PR merge: promote pending-merge → merged
BRANCH_NAME="${{ github.event.pull_request.head.ref }}"
sed -i "s/Lifecycle: \`pending-merge\`\(.*branch:${BRANCH_NAME}\)/Lifecycle: \`merged\`\1/g" \
  .squad/decisions.md

# On PR close (not merged): withdraw
sed -i "s/Lifecycle: \`pending-merge\`\(.*branch:${BRANCH_NAME}\)/Lifecycle: \`withdrawn\`\1/g" \
  .squad/decisions.md
```

It's `sed`. Not a database migration, not a state machine library, not a Kubernetes operator. Just `sed`. Because the ledger is a Markdown file, and text manipulation tools that have been stable since 1974 are exactly the right level of complexity for this job.

That was the plan, anyway. And it worked. But something kept bugging me.

---

## Plot Twist: Git Already Solved This

I want you to appreciate the irony of what I'm about to tell you.

I spent time designing the lifecycle system above. I built the state machine. I wrote the `sed` commands. I coded the GitHub Actions workflow with its three triggers and its drift detection. I even made a table with five lifecycle states and felt *clever* about it.

And then, while reading a Gerrit code review architecture document (as one does), I stumbled across a feature that's been in Git since 2010.

**Git Notes.**

I'd been building a lifecycle management system from scratch when Git literally has a built-in mechanism for attaching metadata to commits without modifying history. It's called `git notes`. Gerrit uses it for code review metadata. Jenkins uses it for CI results. It's been sitting there in the Git manual for fifteen years, and I — a person who wrote an O'Reilly book about reactive programming and has been using Git professionally for over a decade — had never heard of it.

Let me show you why I almost threw my keyboard across the room.

### What Git Notes Actually Are

Git Notes are per-commit annotations stored in `refs/notes/*`. Think of them as sticky notes you can attach to any commit after it's been created. The commit hash doesn't change. The history doesn't change. But the metadata is there — reachable via the commit, queryable via `git log`, pushable and fetchable just like branches.

```bash
# Attach a note to a commit
git notes --ref=squad/decisions add -m 'Use JWT for auth middleware' HEAD

# Read notes on a commit
git log --show-notes=squad/decisions -1

# Notes are stored in refs/notes/squad/decisions
git log refs/notes/squad/decisions
```

That's it. Three commands. No lifecycle engine. No `sed`. No state machine.

### How Notes Solve the Branch-State Problem (For Free)

Remember my three scenarios from earlier? The rejected feature, the universal truth, the valuable failure? Here's how Git Notes handles all three without a single line of lifecycle code:

**Agent makes a decision on `feature/auth`** → attaches a note to the current commit on that branch.

**PR merges** → the commit lands in `main` → the note is reachable from `main` → the decision is *effectively permanent*. No promotion step. No lifecycle transition. It just... works. Because Git's commit graph IS the lifecycle.

**PR rejected** → the branch is deleted → the commit becomes unreachable → the note becomes unreachable → the decision is *effectively withdrawn*. No `sed` command. No `pending-merge` → `withdrawn` transition. Git's garbage collection handles it. The same mechanism that cleans up unreachable objects cleans up your rejected decisions.

**Universal truth committed alongside a feature?** The agent attaches it to the ledger's orphan branch instead of the feature branch. Permanent by location, not by metadata.

Let me say that again because I'm still a little angry I didn't see it sooner: **Git's own reachability model IS the lifecycle engine.** Commits that land in `main` are reachable. Commits on rejected branches are not. Notes follow commits. Therefore, decisions follow the branches they were made on — automatically, with zero application code.

All those lifecycle states I designed? `pending-merge`, `merged`, `withdrawn`, `superseded`? They were a hand-built reimplementation, in fragile `sed` and Markdown regex, of what Git's commit graph already provides for free.

I felt the way you feel when you discover the standard library has a function for the thing you just spent a weekend implementing. Except worse, because this function has existed since before I started using Git.

![Git Notes Lifecycle — how branch-state solves itself](/assets/scaling-ai-part9-squad-ledger/git-notes-lifecycle.svg)

### The Two-Tier Architecture

This realization split the design cleanly into two tiers, each using Git the way it was designed to be used:

```
THE TWO-TIER SQUAD STATE ARCHITECTURE

Tier 1: The Ledger (orphan branch: squad/state)
├── team.md               ← who's on the squad           (always permanent)
├── routing.md            ← how work gets routed          (always permanent)
├── decisions.md          ← universal team decisions      (always permanent)
├── knowledge/            ← accumulated research          (always permanent)
└── agents/
    ├── picard/history.md ← agent learning                (always permanent)
    ├── data/history.md
    ├── worf/history.md
    └── seven/history.md

Tier 2: Git Notes (refs/notes/squad/*)
├── squad/decisions       ← branch-scoped decisions       (follow commit lifecycle)
├── squad/context         ← research context per feature  (follow commit lifecycle)
└── squad/reviews         ← security reviews per commit   (follow commit lifecycle)
```

**Tier 1** is the stuff that's always true regardless of any feature branch. Team composition, routing rules, agent histories, universal decisions. This lives on the `squad/state` orphan branch, same as before. Agents still write to `.squad/` in the code repo and it syncs to the ledger. Nothing changes here — the original architecture still handles this tier perfectly.

**Tier 2** is the stuff that's scoped to a specific piece of work. "Use JWT for this feature." "Security review passed for this commit." "Here's the research context for this bug fix." These are Git Notes, attached to specific commits. They live and die with the commits they're attached to. If the commit makes it to `main`, the note lives. If the branch gets rejected, the note fades away with the commit it was attached to.

No lifecycle metadata. No `sed` commands parsing Markdown. No five-state transition table. Two tiers, each with exactly the right persistence model for its contents.

![Two-Tier Architecture — permanent ledger and branch-scoped Git Notes](/assets/scaling-ai-part9-squad-ledger/two-tier-architecture.svg)

### The Commands (Copy These)

Here's what it actually looks like when an agent uses Git Notes in practice:

```bash
# Data makes a branch-scoped decision while working on feature/auth
git notes --ref=squad/decisions add -m '{
  "agent": "data",
  "decision": "Use JWT with RS256 for auth middleware",
  "reason": "Stateless verification across microservices",
  "date": "2026-03-22"
}' HEAD
git push origin refs/notes/squad/decisions

# Seven attaches research context to a commit
git notes --ref=squad/context add -m '{
  "agent": "seven",
  "topic": "JWT vs session tokens",
  "findings": "RS256 better for distributed verification, HS256 simpler..."
}' HEAD
git push origin refs/notes/squad/context

# Worf records a security review result
git notes --ref=squad/reviews add -m '{
  "agent": "worf",
  "result": "pass",
  "notes": "No session hijacking vectors, token expiry handled correctly"
}' HEAD
git push origin refs/notes/squad/reviews

# Any agent reads all squad decisions (across all branches)
git fetch origin "refs/notes/squad/*:refs/notes/squad/*"
git log --all --show-notes=squad/decisions
```

Compare that to the `sed`-based lifecycle transitions from earlier. Go ahead. I'll wait.

### The Complexity Comparison

Just so we're all on the same page about what this simplification looks like:

**Before (the lifecycle machine I was so proud of):**
- Five lifecycle states with a transition table
- GitHub Actions workflow with three event triggers
- `sed` commands parsing Markdown for lifecycle transitions
- Branch name extraction and regex matching
- Rollback logic for failed transitions
- Drift detection to catch missed transitions
- A system that breaks silently if someone forgets backticks in a Markdown field

**After (Git Notes):**
- `git notes add` to create a decision
- `git push` to share it
- `git fetch` to read it
- Walk away. Git handles the rest.

All that lifecycle engineering replaced by a feature that's been in Git since I was still writing WPF applications. But that's the nature of engineering — sometimes the best solution is the one you didn't know existed, and the hardest part is being honest about the fact that you overcomplicated it.

### Why Nobody Uses This (Yet)

If Git Notes are so great, why isn't everyone using them? Fair question. A few reasons:

1. **GitHub's UI doesn't show notes.** You won't see them in the PR diff, the commit view, or anywhere in the web interface. They're invisible to humans browsing GitHub. But for AI agents that read everything via CLI? Doesn't matter at all. They `git fetch` and `git log` just fine.

2. **Notes aren't fetched by default.** You have to configure your clone:
   ```bash
   git config --add remote.origin.fetch "+refs/notes/squad/*:refs/notes/squad/*"
   ```
   One line in your git config. But if you don't know to add it, you'll spend an hour wondering why your notes vanished after a clone.

3. **Almost nobody knows about them.** I've been using Git for over a decade. I've written books about software engineering. I talk at conferences about distributed systems. I didn't know about `git notes`. The feature has approximately zero marketing budget.

But here's the thing: Gerrit — Google's code review system that handles the Android Open Source Project, Chromium, and the Go standard library — has been using Git Notes for review metadata at massive scale since 2012. This is not experimental technology. It's not fragile. It's battle-tested infrastructure that happens to be obscure.

And for concurrent access? `git notes merge` exists. Multiple agents writing notes to the same ref will create conflicts, and `git notes merge` resolves them with configurable strategies. Is it perfect? No. But it's significantly better than two GitHub Actions workflows racing to `sed` the same Markdown file at the same time.

I could have rewritten this entire post to use Git Notes from the start and pretended I was brilliant all along. But that would be dishonest, and frankly, the journey from "five-state lifecycle machine" to "wait, `git notes add` does all of that?" is a better story. It's also a more *useful* story — because if you're building AI agent memory systems and you didn't know about Git Notes either, now you do. You're welcome.

---

## Agent Learning vs. Agent Decisions

This is the insight that unlocked the whole design, and it's surprisingly simple once you see it:

**History is always permanent. Decisions are scoped.**

When Data researches JWT vs session tokens, two things happen:

1. He writes a **decision**: "Use JWT for auth middleware" → `Scope: branch:feature/auth, Lifecycle: pending-merge`
2. He updates his **history**: "Researched JWT vs session tokens. Findings: RS256 better for distributed verification, HS256 simpler but requires shared secret..." → `Scope: global, Lifecycle: permanent`

If the PR gets rejected, the decision is withdrawn. But the history entry stays. Because *the research happened*. Data learned something. Even if the feature didn't land, the knowledge about JWT vs session tokens is real and valuable. Next time someone asks about auth patterns, Data has that context. He can say "I looked into this before — here's what I found" without redoing the work.

This maps to how human teams work, too. If I spend a week evaluating three database options and my manager kills the project, I didn't un-learn PostgreSQL vs CockroachDB. The project decision is dead, but my knowledge isn't.

Agent history files (`.squad/agents/*/history.md`) are always global scope, always permanent lifecycle. They're the closest thing an AI agent has to long-term memory, and you don't erase someone's memory because their PR got rejected. That's not engineering — that's the plot of *Eternal Sunshine of the Spotless Mind*, and it didn't end well for anyone in that movie either.

---

## What Gets Synced (And What Doesn't)

Not everything in `.squad/` belongs in the ledger. Some state is durable — decisions, routing rules, agent histories. Some state is ephemeral — circuit breaker counters, board snapshots, session data.

Here's the classification:

| State Type | Synced? | Why |
|-----------|---------|-----|
| `decisions.md` | ✅ | Core team knowledge |
| `routing.md` | ✅ | How work gets assigned |
| `team.md` | ✅ | Who's on the squad |
| `agents/*/history.md` | ✅ | Long-term agent memory |
| `knowledge/` | ✅ | Accumulated research |
| `orchestration-log/` | ✅ | Audit trail |
| `board_snapshot.json` | ❌ | Refreshed from API every cycle |
| `ralph-circuit-breaker.json` | ❌ | Runtime state, per-machine |
| `sessions/` | ❌ | Per-machine session data |
| `commit-msg*.txt` | ❌ | Ephemeral scratch files |

The exclude list in `ledger.json` handles this. If you're not sure whether something should sync, ask yourself: "If I deleted this file and rebuilt from scratch, would I lose knowledge?" If yes, sync it. If no, it's ephemeral.

---

## Auto-Sync: GitHub Actions + Ralph

The sync workflow has three triggers and one background check:

### Trigger 1: Push to Main

Any push to `main` that touches `.squad/` files triggers a sync. The workflow clones the ledger repo, copies the updated state files, commits, and pushes. Simple. This handles the 80% case — someone (or some agent) merged a PR, state changed, ledger gets updated.

### Trigger 2: PR Merged

When a PR merges, the workflow does everything Trigger 1 does, *plus* lifecycle transitions. It finds all `pending-merge` decisions scoped to the merged branch and promotes them to `merged`. It also promotes branch-specific research from `.squad/branches/<slug>/` to `.squad/knowledge/from-branches/`.

### Trigger 3: PR Closed (Not Merged)

When a PR is closed without merging, the workflow marks scoped decisions as `withdrawn` and moves branch context to `.squad/branches/_archived/`. Nothing is deleted. Everything is preserved. The ledger is append-only.

### Background: Ralph's Drift Detection

Every six hours, a scheduled workflow clones the ledger and diffs it against the code repo. If there's drift — maybe the sync workflow failed, maybe someone manually edited state — Ralph flags it. Think of it as a reconciliation check. Banks do this. Your AI team should too.

```yaml
name: Squad Ledger Sync

on:
  push:
    branches: [main]
    paths:
      - '.squad/decisions.md'
      - '.squad/decisions/**'
      - '.squad/routing.md'
      - '.squad/team.md'
      - '.squad/agents/*/history.md'
      - '.squad/knowledge/**'
      - '.squad/research/**'
      - '.squad/branches/**'
  pull_request:
    types: [closed]
    branches: [main]

jobs:
  sync-state:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Clone ledger repo
        env:
          LEDGER_PAT: ${{ secrets.SQUAD_LEDGER_PAT }}
        run: |
          git clone --branch squad/state \
            https://x-access-token:${LEDGER_PAT}@github.com/$LEDGER_REPO.git \
            /tmp/ledger

      - name: Sync state files
        run: |
          rsync -av --delete \
            --include='.squad/decisions.md' \
            --include='.squad/decisions/***' \
            --include='.squad/routing.md' \
            --include='.squad/team.md' \
            --include='.squad/agents/' \
            --include='.squad/agents/*/history.md' \
            --include='.squad/knowledge/***' \
            --include='.squad/research/***' \
            --include='.squad/branches/***' \
            --exclude='*' \
            .squad/ /tmp/ledger/.squad/

      - name: Handle PR lifecycle transitions
        if: github.event_name == 'pull_request'
        run: |
          BRANCH="${{ github.event.pull_request.head.ref }}"
          cd /tmp/ledger

          if [ "${{ github.event.pull_request.merged }}" = "true" ]; then
            # Promote pending-merge → merged
            sed -i "s/Lifecycle: \`pending-merge\`\(.*branch:${BRANCH}\)/Lifecycle: \`merged\`\1/g" \
              .squad/decisions.md
          else
            # Withdraw pending-merge → withdrawn
            sed -i "s/Lifecycle: \`pending-merge\`\(.*branch:${BRANCH}\)/Lifecycle: \`withdrawn\`\1/g" \
              .squad/decisions.md
          fi

      - name: Commit and push
        run: |
          cd /tmp/ledger
          git config user.name "squad-ledger-bot"
          git config user.email "squad-ledger-bot@users.noreply.github.com"
          git add -A
          if ! git diff --cached --quiet; then
            git commit -m "sync: ${{ github.event_name }} — ${{ github.sha }}"
            git push
          fi
```

That's the real workflow. Not pseudocode, not a conceptual diagram — the actual YAML that runs in my repo. Feel free to steal it.

---

## Try It Yourself

I've published two repos you can use right now:

**The ledger:** [tamirdresher/squad-state-upstream](https://github.com/tamirdresher/squad-state-upstream)
This is the state storage repo. It has a `squad/state` branch with the `.squad/` directory structure. Clone it, browse it, see how the decisions and agent histories are structured.

**The consumer:** [tamirdresher/squad-upstream-example](https://github.com/tamirdresher/squad-upstream-example)
This is a minimal code repo that demonstrates the pattern. It has the `ledger.json` pointer, the sync workflow, and a sample `.squad/` directory.

### Tier 1: Set Up the Ledger

Three commands to create your permanent state store:

```bash
# 1. Create your ledger repo (do this once)
gh repo create my-squad-ledger --private
cd my-squad-ledger
git checkout --orphan squad/state
echo "# Squad Ledger" > README.md
git add . && git commit -m "init" && git push -u origin squad/state

# 2. Add the pointer to your code repo
cat > .squad/ledger.json << 'EOF'
{
  "ledger": {
    "repo": "your-org/my-squad-ledger",
    "branch": "squad/state",
    "type": "git",
    "sync": { "mode": "github-actions" }
  }
}
EOF

# 3. Copy the workflow file from the example repo
curl -o .github/workflows/squad-ledger-sync.yml \
  https://raw.githubusercontent.com/tamirdresher/squad-upstream-example/main/.github/workflows/squad-ledger-sync.yml
```

You'll need one secret: `SQUAD_LEDGER_PAT` — a fine-grained personal access token with Contents read/write scoped to your ledger repo. Set it in your code repo's Settings → Secrets → Actions.

### Tier 2: Set Up Git Notes

This is the part that makes branch-scoped decisions automatic:

```bash
# 1. Configure your clone to fetch squad notes (do this once per clone)
git config --add remote.origin.fetch "+refs/notes/squad/*:refs/notes/squad/*"

# 2. Try it — attach a decision to your current commit
git notes --ref=squad/decisions add -m '{
  "agent": "you",
  "decision": "Testing Git Notes for squad state",
  "date": "'$(date -Iseconds)'"
}' HEAD

# 3. Push the note
git push origin refs/notes/squad/decisions

# 4. Verify — see it in your log
git log --show-notes=squad/decisions -1

# 5. Fetch notes from other branches/clones
git fetch origin "refs/notes/squad/*:refs/notes/squad/*"
```

That's both tiers. Tier 1 syncs permanent state via GitHub Actions when PRs merge. Tier 2 uses Git Notes for branch-scoped decisions that automatically follow commit lifecycle — no promotion, no withdrawal, no `sed`. Merge the PR and the decision lives. Reject it and the decision fades with the branch.

---

## The Honest Version

Here's what's still rough. I'm not going to pretend this is production-hardened at scale — though the Git Notes revelation did sand off a lot of the sharp edges.

**The biggest simplification: lifecycle management is gone.** The original `sed`-based lifecycle transitions — `pending-merge` → `merged`, `pending-merge` → `withdrawn` — were the most fragile part of the system. They broke if you forgot backticks, they raced on concurrent merges, they silently skipped malformed entries. Git Notes eliminated all of that. Branch-scoped decisions now follow commit reachability, which is handled by Git itself. I deleted the lifecycle state machine and nothing broke. Things actually got *better*.

**But GitHub's UI is blind to notes.** This is the trade-off. Your code reviewers won't see squad notes in the PR diff or the commit view. For AI agents that consume everything via `git log --show-notes`, this is a non-issue. For humans who want to browse decisions in the GitHub web UI? They'll need to use the CLI or wait for GitHub to add notes rendering. (GitHub, if you're reading this — please.)

**Notes aren't fetched by default.** Every new clone needs `git config --add remote.origin.fetch "+refs/notes/squad/*:refs/notes/squad/*"`. If an agent forgets this config, it silently doesn't see any branch-scoped decisions. The fix is to add it to your squad bootstrap script, but it's one more thing to remember.

**The `merge=union` strategy for Tier 1 isn't bulletproof.** For the ledger's Markdown files — decisions, routing rules, agent histories — union merge works great because they're self-contained blocks separated by `---` dividers. It works terribly for JSON, which is why we exclude JSON state files from the ledger sync. But even for Markdown, if two agents add entries with the same heading at the same line, union merge can produce duplicates. In practice this is rare. In theory it's a bug waiting to happen.

**Concurrent notes can conflict.** If two agents push notes to the same `refs/notes/squad/decisions` ref at the same time, one push will fail with a non-fast-forward error. `git notes merge` exists and handles this, but agents need to be taught to fetch-merge-push instead of just push. Gerrit solves this at Google scale, so it's a solved problem — it's just not something Git does automatically.

**Agent compliance is still voluntary.** The two-tier split made it clearer *where* to write (permanent → Tier 1, branch-scoped → Tier 2 notes), but agents are LLMs. They sometimes write a branch-scoped decision to `decisions.md` instead of as a note, or vice versa. There's no schema enforcement — it's conventions and good prompting all the way down.

**If I were starting over** — which, honestly, the Git Notes discovery basically forced me to do — I'd start with the two-tier model from day one. Tier 1 for permanent state on the orphan branch, Tier 2 for branch-scoped state via Git Notes. No lifecycle states, no `sed`, no transition workflows. The five-state model wasn't wrong, exactly — it correctly identified the problem. It just solved it at the wrong layer. Git's commit graph was already the state machine I needed.

---

## What This Actually Solves

Let me circle back to the problems from [Part 7](/blog/2026/03/22/scaling-ai-part7-enterprise-state):

| Problem | Before | After (Ledger + Git Notes) |
|---------|--------|-------|
| PRs cluttered with squad state | 40+ `.squad/` files in every PR | Zero — state syncs independently via Tier 1 |
| Agent decisions lost on PR rejection | Decisions either persisted incorrectly or were deleted entirely | Git Notes follow commit reachability — merged commits keep their notes, rejected branches don't |
| Lifecycle management complexity | `sed`-based state machine with five states and three workflow triggers | No lifecycle code — Git's commit graph IS the lifecycle |
| Parallel agents with stale state | Each branch had its own copy, no cross-branch visibility | Tier 1 (shared ledger) + Tier 2 (Git Notes) — each with the right persistence model |
| JSON merge corruption | Git line-merge on JSON = broken state | JSON excluded from sync, Markdown with `merge=union` for Tier 1 |
| Reviewer cognitive overload | "Why is there 700 lines of orchestration log in my auth PR?" | Code PRs only contain code |

Is it perfect? No. Is it significantly better than what I had? Absurdly so. The code reviewers on my team no longer have to wade through agent diaries to find the actual feature changes. The agents can remember things without asking permission first. And when a feature gets rejected, the team's collective knowledge doesn't get thrown out with the bathwater — branch-scoped decisions just naturally fade with the commits they were attached to, while the permanent stuff stays on the ledger forever.

The two-tier pattern turned out to be one of those solutions that feels obvious in retrospect — of course you should match your persistence model to your data's lifecycle. Permanent state goes on a permanent branch. Branch-scoped state goes on branch-scoped commits. That's just database normalization applied to git refs. But it took running a squad in an enterprise context for a couple of months, building an entire lifecycle state machine, and then discovering `git notes` at 1 AM to make the solution click.

Sometimes the best engineering is realizing that someone already solved your problem fifteen years ago and you just didn't know to look.

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [The Collective — Organizational Knowledge for AI Teams](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — Many Teams, One Repo with SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)
> - **Part 4**: [When Eight Ralphs Fight Over One Login](/blog/2026/03/17/scaling-ai-part4-distributed)
> - **Part 5**: [Knowledge is Power — How an AI Squad Learns to Evolve Itself](/blog/2026/03/18/scaling-ai-part5-evolution)
> - **Part 6**: [Hailing Frequencies Open — Teaching Your AI Team to Talk to Humans](/blog/2026/07/15/scaling-ai-part6-comms-patterns)
> - **Part 7**: [When Git Is Your Database — The Enterprise State Problem](/blog/2026/03/22/scaling-ai-part7-enterprise-state)
> - **Part 8**: [The Vinculum — Eight Distributed Systems Lessons](/blog/2026/04/01/scaling-ai-part8-vinculum)
> - **Part 9**: The Squad Ledger — Giving Your AI Team a Memory That Survives Rejected PRs ← You are here

*The [ledger repo](https://github.com/tamirdresher/squad-state-upstream) and [example consumer](https://github.com/tamirdresher/squad-upstream-example) are both public. The design document that drove this solution is in my working repo. The `sed` commands were real, the Git Notes discovery was real, and the three corrupted JSON files I mentioned in Part 7 were definitely real. Try `git notes --ref=squad/test add -m 'hello' HEAD` in any repo — you might have the same "wait, this has been here the whole time?" moment I did. Follow me on [Twitter/X @tamir_dresher](https://twitter.com/tamir_dresher) for updates on the series.*
