---
layout: post
title: "The Squad Ledger — Giving Your AI Team a Memory That Survives Rejected PRs"
date: 2026-03-22
tags: [ai-agents, squad, github-copilot, enterprise, git, state-management, distributed-systems, star-trek]
series: "Scaling AI-Native Software Engineering"
series_part: 9
---

![The Squad Ledger](/assets/scaling-ai-part9-squad-ledger/hero.png)

> *"A library is not a luxury but one of the necessities of life."*
> — Henry Ward Beecher (who clearly never dealt with merge conflicts in his library's card catalog)

In [Part 7](/blog/2026/03/22/scaling-ai-part7-enterprise-state), I showed you the mess. Ninety-seven files in a PR. Forty of them squad memory. Corrupted JSON from line-based merges. Two agents making decisions in parallel that neither could see. Code reviewers drowning in `.squad/` diffs instead of reviewing actual features.

I laid out four approaches and said "I'm still figuring it out."

Well, I figured it out. This post is the solution.

---

## Why "Upstream" Was the Wrong Word

Before I get into the architecture, let me tell you about a naming disaster that cost me three days of confusion.

When I first built the state synchronization system, I called the external repo "upstream." As in, `.squad/upstream.json` pointed to the repo where shared state lived. The scripts were called "sync upstream." The config file was `upstream-config.json`.

The problem? In git, "upstream" already means something very specific: *the remote you pull from*. When I said "push state upstream," half my team thought I meant `git push origin`. The other half thought I meant the parent Squad repo (Brady's `bradygaster/squad`). Nobody thought I meant "the separate repo where agent memory lives."

Three days of "wait, which upstream?" later, I killed the word entirely.

The new name: **Ledger**.

It's not poetry. It's accounting. And that's exactly the right metaphor:

- **Append-only** — you don't rewrite history in a ledger. You add new entries.
- **Authoritative** — when there's a disagreement about what was decided, the ledger is the source of truth.
- **Multi-writer** — multiple agents can append entries without overwriting each other.
- **Timestamped** — every entry has a date, an author, and a context.
- **Never deleted** — even voided entries stay in the book, crossed out but visible.

Financial ledgers have worked this way for five hundred years. Turns out the same properties are exactly what you need for AI agent memory. Who knew double-entry bookkeeping would be relevant to my Star Trek–themed automation setup.

---

## The Architecture

Here's the shape of it. Two repos. One sync mechanism. One pointer file.

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

Here's where it gets interesting. And by "interesting" I mean "the thing that took me two weeks and a design document to figure out."

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

Three commands to set it up in your own project:

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

That's it. Next time you merge a PR that touches `.squad/`, the sync fires automatically. Decisions get promoted or withdrawn based on PR outcomes. Ralph checks for drift every six hours.

---

## The Honest Version

Here's what's still rough. I'm not going to pretend this is production-hardened at scale.

**The sed-based lifecycle transitions are fragile.** If a decision entry doesn't exactly match the expected format — extra whitespace, different quoting, a typo in the scope line — the `sed` command silently does nothing. I've already had one case where a decision stayed as `pending-merge` after its branch merged because Data wrote `Scope: branch:feature/auth` (no backticks) instead of ``Scope: `branch:feature/auth` ``. The fix is a more robust parser, but right now it's regex-on-markdown, and we all know how that movie ends.

**Concurrent branch merges can race.** If two PRs merge within seconds of each other, both sync workflows try to clone the ledger, modify it, and push. One will fail with a non-fast-forward error. The GitHub Action doesn't retry. This is the same "git push as consensus" pattern from [Part 8](/blog/2026/04/01/scaling-ai-part8-vinculum) — except here, the loser's state changes just... don't sync until the next push-to-main event or the drift check catches it. It's eventually consistent, which is fine for decisions but annoying for people who want immediate confirmation.

**The `merge=union` strategy isn't bulletproof.** It works great for decisions — self-contained blocks separated by `---` dividers. It works terribly for JSON, which is why we exclude JSON state files from the ledger sync entirely. But even for Markdown, if two agents add decisions with the exact same heading on the same line number, union merge can produce duplicates. In practice this is rare. In theory it's a bug waiting to happen.

**Agent compliance is voluntary.** The Golden Rules say agents should always add scope and lifecycle metadata. But agents are LLMs. They sometimes forget. They sometimes format it differently. There's no schema enforcement — it's Markdown conventions all the way down. A validation step in the sync workflow would catch malformed entries, but I haven't built it yet.

**If I were starting over**, I'd probably use a structured format (YAML frontmatter for decisions instead of inline Markdown fields). The human-readability of pure Markdown is nice, but the parseability cost is real. `sed` on Markdown is writing poetry with a chainsaw — it can be done, but it's not what either tool was designed for.

---

## What This Actually Solves

Let me circle back to the problems from [Part 7](/blog/2026/03/22/scaling-ai-part7-enterprise-state):

| Problem | Before | After |
|---------|--------|-------|
| PRs cluttered with squad state | 40+ `.squad/` files in every PR | Zero — state syncs independently |
| Agent decisions lost on PR rejection | Decisions either persisted incorrectly or were deleted entirely | Withdrawn decisions stay visible but inactive |
| Parallel agents with stale state | Each branch had its own copy, no cross-branch visibility | Shared ledger with scoped metadata |
| JSON merge corruption | Git line-merge on JSON = broken state | JSON excluded from sync, Markdown with `merge=union` |
| Reviewer cognitive overload | "Why is there 700 lines of orchestration log in my auth PR?" | Code PRs only contain code |

Is it perfect? No. Is it significantly better than what I had? Absolutely. The code reviewers on my team no longer have to wade through agent diaries to find the actual feature changes. The agents can remember things without asking permission first. And when a feature gets rejected, the team's collective knowledge doesn't get thrown out with the bathwater.

The ledger pattern turned out to be one of those solutions that feels obvious in retrospect — of course you should separate things with different update frequencies and different lifecycle semantics. That's just database normalization applied to files. But it took running a squad in an enterprise context for a couple of months to make the problem painful enough to solve properly.

Sometimes the best engineering is just accounting with better tooling.

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

*The [ledger repo](https://github.com/tamirdresher/squad-state-upstream) and [example consumer](https://github.com/tamirdresher/squad-upstream-example) are both public. The design document that drove this solution is in my working repo. The `sed` commands are real, the edge cases are real, and the three corrupted JSON files I mentioned in Part 7 were definitely real. Follow me on [Twitter/X @tamir_dresher](https://twitter.com/tamir_dresher) for updates on the series.*
