---
layout: post
title: "When Git Is Your Database — The Enterprise State Problem Nobody Warned Me About"
date: 2026-03-22
tags: [ai-agents, squad, github-copilot, enterprise, git, distributed-systems, state-management]
series: "Scaling AI-Native Software Engineering"
series_part: 7
---

![When Git is Your Database](/assets/scaling-ai-part7-enterprise-state/hero.png)

> *"Simplicity is the ultimate sophistication."*
> — Leonardo da Vinci (probably didn't mean git worktrees, but still)

When Brady Gaster created Squad, he built it around a principle I really liked: **simplicity is key**. Don't add components unless you really need them. Don't stand up a database if you can avoid it. Don't introduce a message broker if GitHub Issues can do the job.

When I joined and started using Squad seriously, one of the things we discussed was this design philosophy and how far you can take it. We made Git the database. Issues are the message queue. GitHub Actions are the automation layer. Everything lives in one place. Versioned. Auditable. Free. It's *elegant*.

But there's a problem with this approach that everyone running Squad in an enterprise eventually hits. And honestly? I should have seen it coming.

In [Part 6](/blog/2026/03/21/rate-limiting-multi-agent), I told you how I solved the rate limiting problem when 9 agents share one API quota. That post was about throttling. This one is about **state**. Because when your squad's own internal memory files — decisions, agent histories, orchestration logs — live in the same repo as your code, things get weird.

Specifically: your agents need permission to remember things.

---

## The Moment I Realized We Had a Problem

A couple of days after I started working with Squad, the agents were doing their thing — picking up issues, writing code, opening PRs. It was working great. Data picked up a feature request for our C# platform service, did his analysis, wrote a decision doc, implemented the changes, added tests, and opened a pull request. All autonomously, while I was doing other work.

I woke up, checked the PR, and saw this:

```
Files changed: 97
+ squad files: 40
+ actual code: 57
```

Ninety-seven files. Forty of them were squad state. For a feature that touched maybe a dozen actual source files.

<figure style="text-align:center; margin: 1.5rem 0;">
  <img src="https://i.imgflip.com/wxica.jpg" alt="This is fine dog sitting in burning room" style="max-width: 400px; border-radius: 8px;">
  <figcaption style="font-style: italic; font-size: 0.85rem; color: #666; margin-top: 0.5rem;">↑ Me, watching the PR diff load</figcaption>
</figure>

I scrolled through the diff. The actual C# changes were reasonable — service configuration, some new classes, updated tests. Maybe 15 minutes to review properly.

But the other 40 files? All `.squad/` state:

- `.squad/decisions/namespace-config-2026-03.md` — Data's decision analysis
- `.squad/agents/data/history.md` — updated with this work session
- `.squad/agents/worf/history.md` — Worf reviewed the security implications
- `.squad/schedule-state.json` — Ralph's orchestration state
- `.squad/ralph/work-log.json` — work tracking metadata
- `.squad/ceremonies/daily-sync/2026-03-19.md` — sync notes
- ... 725 more files ...

The PR was almost half squad memory, half actual work. And here's the thing about Microsoft repos — you can't push to main. Period. Every PR requires at least one other person to approve it. Not a bot, not yourself — another human. So my teammate Meir opened the PR, saw 97 files, and started reading through them — trying to figure out what actually changed. But 40 of those files had nothing to do with the code that was modified. The cognitive load was insane. He was reviewing the squad's internal diary instead of the actual feature.

**The squad couldn't remember things without asking permission. And the humans who gave permission couldn't find the actual work buried under the squad's memory.**

---

## Why This Happens

Here's the root problem. Squad's design philosophy is "Git as database." The `.squad/` directory contains everything the squad needs to be self-sufficient:

- **Decisions** — architecture choices, technical tradeoffs, team agreements
- **Agent histories** — what each agent has learned from past sessions
- **Ceremony logs** — daily syncs, retrospectives, planning notes
- **Orchestration state** — Ralph's work queue, scheduling metadata, coordination files

All of this lives in the same repo as the code. Which means when Data makes a code change on a feature branch, his branch includes both the code *and* the new squad state from this work session.

Meanwhile, Seven is working on documentation on `feature/docs`. Her branch has her own squad state updates — new decisions, updated history files, ceremony notes.

Both PRs go up. Both sit waiting for approval. And here's the kicker: **neither branch sees the other's decisions until both PRs merge.**

Data doesn't know about Seven's decision to standardize on a new doc format. Seven doesn't know about Data's feature decision. They're working with stale state, making decisions in parallel that might conflict.

And when both PRs finally merge? Git tries to auto-merge `.squad/schedule-state.json` — a JSON file — using a line-based merge strategy. Git's line-based merge can corrupt JSON when two agents touch the same structural region — and with squad state, that happens constantly. I've fixed three corrupted JSON files in the past month alone.

The rate of change is completely different. Code changes once a day. Squad state changes **fifty times a day**. It's like storing your brain's short-term memory in the same filing cabinet as your tax returns. Different update frequency. Different access pattern. Different lifecycle.

<div class="mermaid">
sequenceDiagram
    participant A as Agent
    participant C as Code Repo
    participant S as Squad State
    participant R as Reviewer

    rect rgb(255, 220, 220)
        Note over A,R: ❌ BEFORE — mixed repo, approval required for everything
        A->>C: commit code + .squad/ changes
        A->>C: open PR (97 files 😬)
        C-->>R: review request
        Note over R: 40 min reading squad diary instead of code
        R->>C: slow approval
        C-->>A: merged — squad state was blocked until now
    end

    rect rgb(220, 255, 220)
        Note over A,R: ✅ AFTER — separated state, no PR required for agent memory
        A->>C: commit code only → PR (12 files)
        A->>S: push squad state directly — no PR, no wait
        C-->>R: review request (clean diff)
        Note over R: 5 min review — only actual code changes
        R->>C: quick approval
        Note over S: squad state has been live since first push
    end
</div>

*One of these workflows makes your teammates happy. The other one explains why Meir called me that morning.*

I later realized this pattern is almost identical to how ADRs (Architecture Decision Records) work — something I'd read about years ago but never fully connected to what Squad does. ADRs track decisions through states: *Proposed → Accepted → Superseded/Deprecated*. Squad's `decisions.md` does the same thing. The parallel is exact, down to the lifecycle — agents propose a decision, the team accepts it (or overwrites it), and old decisions get marked superseded rather than deleted. If you're already using ADRs on your team, Squad's decisions layer will feel immediately familiar. If you're not, this might be a good reason to start. [Michael Nygard's original ADR post](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) is the classic reference.

<div class="mermaid">
stateDiagram-v2
    direction LR
    [*] --> Proposed : Agent creates decision
    Proposed --> Accepted : No conflict detected
    Proposed --> Rejected : Explicit team override
    Accepted --> Superseded : Newer decision overrides
    Superseded --> [*]
    Rejected --> [*]
</div>

*Squad decisions follow the same lifecycle as Architecture Decision Records — states are explicit, history is preserved.*

---

## The Four Approaches I'm Evaluating

I've identified four ways to solve this. Each has tradeoffs. None is perfect. Here's what I've learned.

![Three Approaches to Enterprise State](/assets/scaling-ai-part7-enterprise-state/three-approaches.svg)

---

### Approach 1: Orphan Branch

This is the most architecturally elegant solution — and the one that requires the most explanation.

The idea: create a separate Git branch called `squad/state` that has **no parent commits**. It's an orphan — completely independent from your code history. Squad state lives there. Code lives on `main` and feature branches. They never mix.

Then use **`git worktree`** to mount the `squad/state` branch into `.squad/` directory:

```bash
# One-time setup
git checkout --orphan squad/state
git rm -rf .
echo "# Squad State" > README.md
git add README.md
git commit -m "Initialize squad state branch"
git push -u origin squad/state
git checkout main   # return to main before adding the worktree

# Mount it into .squad/ (from your main branch)
git worktree add .squad squad/state
```

Now `.squad/` is a worktree — it points to the `squad/state` branch. When you switch between code branches, `.squad/` **stays put**. It's always on `squad/state`, regardless of what code branch you're on.

![Orphan Branch Architecture](/assets/scaling-ai-part7-enterprise-state/orphan-branch-architecture.svg)

Agents write to `.squad/`, commit, and push directly to `squad/state` — no PR needed. Code PRs see **zero** `.squad/` files. Clean diffs. No approval delay for squad memory. Independent audit trails.

**The good:**
- Zero PR delay for squad state
- Code diffs are clean — reviewers only see actual code
- Same repo — Git stays the single source of truth
- Independent versioning for state vs. code
- No merge conflicts between state and code

**The weird:**
- `git worktree` is exotic. Most developers have never used it.
- Setup requires explanation. "Why is `.squad/` not in my branch?" is a question you'll answer multiple times.
- Some IDEs don't handle worktrees gracefully — `.squad/` might show up as "untracked" even though it's versioned.
- If someone deletes `.squad/` and runs `git checkout`, it doesn't come back automatically — they need to re-run `git worktree add`.

This is the solution I'm leaning toward for teams that can tolerate the complexity. It's technically sound. It scales. It just requires good documentation and some team education.

---

### Approach 2: Separate Repository

The simpler version of Approach 1: create a completely separate repo — something like `myrepo-squad` — with no branch protection. Agents clone it into `.squad/` and push freely.

```bash
# Clone the state repo into .squad/
git clone git@github.com:myorg/myrepo-squad.git .squad
cd .squad
git config user.name "Squad Bot"
git config user.email "squad@myorg.com"

# Agents commit and push directly
git add .
git commit -m "Update decisions and agent histories"
git push
```

Add `.squad/` to `.gitignore` in your main repo so it doesn't show up in code PRs. State and code are now completely independent.

**The good:**
- Conceptually simple — two repos, clean separation
- No worktree complexity
- Standard git workflows
- Easy to explain to the team

**The tradeoffs:**
- Two repos to manage instead of one
- Cross-references between code and decisions get messy (do you link to commit SHAs? branch names? how do you keep them in sync?)
- Split context — developers need to clone both repos
- Audit trail is split across two repositories

This is the lowest-friction option. If your team is already comfortable with multi-repo workflows (monorepo + infra repo, for example), this might be the easiest sell.

---

### Approach 3: Auto-Merge Bot

The "minimal change" approach: keep everything in one repo, but add a GitHub Action that auto-approves PRs that **only** touch `.squad/` files.

```yaml
# .github/workflows/auto-merge-squad-state.yml
name: Auto-merge squad state
on:
  pull_request:
    paths:
      - '.squad/**'

jobs:
  auto-merge:
    runs-on: ubuntu-latest
    steps:
      - name: Check if PR only changes .squad/
        id: check
        run: |
          FILES=$(gh pr view ${{ github.event.pull_request.number }} --json files --jq '.files[].path')
          NON_SQUAD=$(echo "$FILES" | grep -v '^\.squad/' || true)
          if [ -z "$NON_SQUAD" ]; then
            echo "only_squad=true" >> $GITHUB_OUTPUT
          fi

      - name: Auto-approve and merge
        if: steps.check.outputs.only_squad == 'true'
        run: |
          gh pr review ${{ github.event.pull_request.number }} --approve
          gh pr merge ${{ github.event.pull_request.number }} --auto --squash
```

> **⚠️ GITHUB_TOKEN cannot approve its own PRs.** GitHub blocks self-review: if the workflow that *opens* the PR uses `GITHUB_TOKEN`, the same token *cannot* approve it — you'll get HTTP 422. The workflow also needs `permissions: pull-requests: write` and `contents: write` declared. To make this work in practice you need a separate bot PAT or a dedicated GitHub App token. This is the biggest practical failure mode for this approach.

Now squad state PRs merge automatically. Code PRs still need human review.

**The good:**
- One repo — no split context
- Minimal setup — just add a workflow file
- Standard git workflow — no exotic features
- Easy to understand

**The problems:**
- **Race conditions** — if two agents create PRs at the same time, one will conflict and fail
- Still creates PRs — slower than direct push (GitHub PR creation + auto-merge takes 10-30 seconds)
- Noisy PR history — every squad state update is a PR in your history
- **Compliance approval needed** — in many enterprises, auto-merge workflows require security review and approval
- Doesn't solve the stale state problem — agents still can't see each other's state until PRs merge

This works for small teams with low PR volume. At scale, the race conditions and PR overhead become a bottleneck.

> **Tip**: If you're already running Ralph in watch mode (`ralph-watch.ps1` or `npx @bradygaster/squad-cli watch`), you might not need the GitHub Action at all. Ralph already monitors open PRs — you can extend its logic to detect squad-only PRs and merge them directly using `gh pr merge`. The advantage: no GitHub Actions configuration, no security review, and the auto-merge happens on Ralph's clock rather than GitHub's webhook latency. This is probably the lowest-friction path for teams that already have Ralph running.

<figure style="text-align:center; margin: 1.5rem 0;">
  <img src="https://i.imgflip.com/4bp78.jpg" alt="Drake approving and disapproving meme" style="max-width: 400px; border-radius: 8px;">
  <figcaption style="font-style: italic; font-size: 0.85rem; color: #666; margin-top: 0.5rem;">No: writing a GitHub Action to auto-merge squad PRs. Yes: Ralph already does this for free.</figcaption>
</figure>

---

### Approach 4: Self-Bootstrapping Worktree *(idea — not yet implemented)*

Here's a thought I had while writing this post: what if we could combine the elegance of the orphan branch with the simplicity of "just clone and go"?

The problem with Approach 1 is the education burden. New contributors clone the repo, and `.squad/` doesn't exist. They need to know about worktrees. They need to run `git worktree add .squad squad/state`. That's a barrier.

But what if the `main` branch contained a directive telling Squad to **do this setup automatically**?

The idea: put a small instruction in `squad.agent.md` on `main` that says, "On first run, create the worktree for `squad/state` and mount it." The coordinator — Ralph or Picard — detects that `.squad/` is missing, sees the directive, and runs the worktree command itself.

From the developer's perspective: they clone the repo, start Squad, and it just works. No manual worktree setup. No exotic Git education. The squad bootstraps its own memory.

Combine this with the symlink pattern from my [earlier post on using Squad without touching your repo](/blog/2026/02/17/trying-squad-without-touching-your-repo), and you get something really slick: symlinks + git exclude can make the `.squad/` directory appear seamlessly, even in repos where you don't want Squad's state directory versioned at all.

**The good:**
- Zero setup friction — cloning the repo is enough
- Same elegance as Approach 1 (orphan branch, clean PRs)
- Worktrees are invisible to humans — agents handle it
- Could support both "state in-repo" and "state external" patterns with the same mechanism

**The questions:**
- Does this make worktrees *less* confusing or *more* confusing? "Why did `.squad/` appear after I ran Squad?"
- What happens if someone manually deletes `.squad/`? Does the coordinator re-bootstrap it? Every time?
- Would Git hooks be better than agent logic for this?

This is the "maybe we can have our cake and eat it too" option. I haven't implemented it yet, but it's the direction I'm most excited about. If Squad can automate the worktree setup, the education problem disappears. And if we can make it work transparently, it might be the best of all three worlds.

---

## One More Thing: You Don't Actually Need GitHub

I shared a draft of this post with a few colleagues before publishing, and one of them left a comment that made me stop and stare at the ceiling for a while.

He pointed out something I'd completely glossed over: *all four approaches above assume you're using GitHub*. Branch protection. Pull requests. GitHub Actions for auto-merge. Even the "separate repo" approach assumes you're creating a GitHub repo and pushing to it.

But here's the thing I'd missed: **the problem was never git. The problem was combining git with GitHub's PR workflow.**

Let me say that again, because it's the kind of insight that feels obvious in retrospect. Squad state needs to move fast — commit, push, done, no waiting. GitHub's PR workflow is designed to slow things down — review, approve, merge. Those two things are not compatible. But the *git part*? The part where you track every change with a commit, get full history, can branch and merge? That part is great. That's exactly what you want for squad state.

The insight: **Approach 2 (separate repo) was right in spirit, but didn't go far enough**. You don't need GitHub *at all* for the squad state repo. You just need a git repo. Those are different things.

### Going Fully Local

Here's the simplest version of Approach 2 that nobody mentioned:

```powershell
# PowerShell — works in both PowerShell and bash (git commands are identical)
# Create a local bare git repo for squad state — no GitHub required
git init --bare "$HOME/squad-state/myapp.git"   # Bash: git init --bare ~/squad-state/myapp.git

# Mount it into .squad/ from your main repo
git clone "$HOME/squad-state/myapp.git" .squad  # Bash: git clone ~/squad-state/myapp.git .squad
```

That's it. A bare repo on your local filesystem. Agents push to it directly — `git push` works exactly the same, just to a `file://` path instead of `https://`. Full git history. Full branching. Works completely offline. No PR required. No branch protection to configure. No GitHub Action to write or get approved by your security team.

The squad state is versioned. Auditable. Branchable. And completely autonomous.

### The Initializer Problem (And Its Solution)

At this point you might be thinking: "But someone has to bootstrap this. Where does the setup script live?"

Back in the main repo. It has to — that's the one inescapable constraint. There needs to be *something* in the code repo that knows how to initialize the squad state location. But this is actually fine, and it's simpler than it sounds:

```powershell
# scripts/squad-init.ps1 - Run once after cloning the repo.
# Requires: PowerShell 7+ (pwsh), Git for Windows
# Bash equivalent: scripts/squad-init.sh (see inline comments)

$RepoName  = Split-Path (git rev-parse --show-toplevel) -Leaf
$SquadRepo = "$HOME/squad-state/$RepoName.git"

if (-not (Test-Path $SquadRepo)) {
    Write-Host "Creating local squad state repo at $SquadRepo"
    New-Item -ItemType Directory -Path $SquadRepo -Force | Out-Null
    git init --bare $SquadRepo

    # Seed an initial commit so branches can be created from the start
    $tmpInit = "$env:TEMP\squad-init-seed-$RepoName"
    git clone $SquadRepo $tmpInit 2>&1 | Out-Null
    git -C $tmpInit -c user.name="squad-init" -c user.email="squad@local" commit --allow-empty -m "Initialize squad state"
    git -C $tmpInit push origin HEAD 2>&1 | Out-Null
    Remove-Item $tmpInit -Recurse -Force
}

if (-not (Test-Path ".squad")) {
    git clone $SquadRepo .squad
}

# Keep .squad/ out of the main repo - no .gitignore pollution
# Bash: grep -qxF ".squad" .git/info/exclude || echo ".squad" >> .git/info/exclude
$ExcludeFile = ".git/info/exclude"
if (-not (Get-Content $ExcludeFile -ErrorAction SilentlyContinue | Select-String "^\.squad$")) {
    Add-Content $ExcludeFile ".squad"
}

# Install hook: a bash wrapper that calls pwsh.
# Git on Windows invokes hooks via sh - .ps1 files cannot be spawned directly.
# Bash equivalent: cp scripts/hooks/post-checkout .git/hooks/post-checkout && chmod +x .git/hooks/post-checkout
$hookWrapper = "#!/bin/sh`npwsh -File `"`$(git rev-parse --show-toplevel)/scripts/hooks/post-checkout.ps1`" `"`$@`""
Set-Content ".git/hooks/post-checkout" $hookWrapper -Encoding utf8NoBOM
if ($IsLinux -or $IsMacOS) { chmod +x ".git/hooks/post-checkout" }

Write-Host "Squad state initialized at $SquadRepo"
Write-Host "Note: symlink creation in the hook requires Developer Mode or admin rights on Windows."
```

> **Windows note:** The `post-checkout` hook creates a symbolic link. On Windows, this requires either **Developer Mode** (Settings → System → For Developers) or running PowerShell as Administrator. Most enterprise machines have neither by default — check your environment before relying on this.

Run once after cloning: `./scripts/squad-init.ps1` (or `bash scripts/squad-init.sh` if you're on Linux/macOS). The `.squad/` directory appears, local to your machine, completely private, no GitHub involved. The two files that live in the main repo (`scripts/squad-init.ps1` and `scripts/hooks/post-checkout.ps1`) are the only Squad artifacts that need to be there — and they're just scripts, not state.

### Handling Multiple Worktrees

Here's where the second wrinkle shows up. If you use git worktrees (and if you're running a squad on a non-trivial codebase, you probably should), you might have something like:

```
/projects/myapp/            ← main worktree, branch: main
/projects/myapp-feature-x/  ← added worktree, branch: feature/auth-refactor
```

Each worktree needs its own `.squad/` directory pointing to the *matching branch* in the squad state repo. If both worktrees shared the same squad state, agents on different features would overwrite each other's decisions and history files. Which would be a disaster. Or at least a very confusing afternoon.

The solution is a `post-checkout` hook that runs automatically when you `git worktree add` or `git checkout`:

```powershell
# scripts/hooks/post-checkout.ps1
# Runs after checkout. Wires up .squad/ to the right squad branch.
# Requires: PowerShell 7+
# Bash equivalent: scripts/hooks/post-checkout

$RepoName      = Split-Path (git rev-parse --show-toplevel) -Leaf
$SquadRepo     = "$HOME/squad-state/$RepoName.git"
$CurrentBranch = git symbolic-ref --short HEAD 2>$null
if (-not $CurrentBranch) { $CurrentBranch = "detached" }   # PS7 compatible (no ?? operator needed in PS5.1)
$WorktreeRoot  = git rev-parse --show-toplevel
$SafeBranch    = $CurrentBranch -replace "/", "-"
$SquadWorktree = "$HOME/squad-state/$RepoName-$SafeBranch"

# Create a matching branch in the squad repo if it doesn't exist
# Bash: if ! git -C "$SQUAD_REPO" rev-parse --verify "$CURRENT_BRANCH" &>/dev/null; then ...
$branchExists = git -C $SquadRepo rev-parse --verify $CurrentBranch 2>$null
if (-not $branchExists) {
    Write-Host "Creating squad branch: $CurrentBranch"
    $TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.IO.Path]::GetRandomFileName())
    git clone $SquadRepo "$TmpDir/tmp-squad" 2>&1 | Out-Null
    git -C "$TmpDir/tmp-squad" checkout -b $CurrentBranch 2>&1 | Out-Null
    git -C "$TmpDir/tmp-squad" push origin $CurrentBranch 2>&1 | Out-Null
    Remove-Item $TmpDir -Recurse -Force
}

# Set up the matching squad worktree
if (-not (Test-Path $SquadWorktree)) {
    git clone --branch $CurrentBranch $SquadRepo $SquadWorktree 2>&1 | Out-Null
}

# Point .squad/ at the branch-specific worktree via symlink
$SquadLink = Join-Path $WorktreeRoot ".squad"
if (Test-Path $SquadLink) { Remove-Item $SquadLink -Recurse -Force }   # -Recurse needed for non-empty dirs
New-Item -ItemType SymbolicLink -Path $SquadLink -Target $SquadWorktree | Out-Null

Write-Host "Squad state -> $SquadWorktree ($CurrentBranch)"
```

About 30 lines of PowerShell (versus 20 of bash — the verbosity is real, but so is the inline documentation). When you run `git worktree add /projects/myapp-feature-x feature/auth-refactor`, the hook fires, creates a matching `feature/auth-refactor` branch in the local squad state repo, sets up a dedicated working directory for it, and symlinks `.squad/` there.

Branch names match. Squad state stays isolated per feature. No cross-contamination between worktrees. The squad repo has worktrees too — one per feature branch — but that's fine, because they're just directories, and the hook manages them automatically.

### Prior Art Worth Knowing: Gerrit

While I was researching this problem, I stumbled on an article about [Gerrit](https://www.gerritcodereview.com/) — Google's open-source code review system, used by Android, Chromium, and a bunch of other large projects. I'd never dug into it before. It turns out Gerrit has been solving this exact problem for a decade. It stores all review metadata — votes, change IDs, review comments — in git notes (`refs/notes/review`). Not in a database. Not in a sidebar. In git itself, attached to commits, pushed to a separate refspec that has no branch protection. The code and the review state live in the same repo but move through completely different workflows.

That's the exact pattern we're rediscovering for squad state. Gerrit figured it out first.

The lesson I took from this: separating "state that needs human review" from "state that doesn't" is a solved problem. The tooling looks different, but the architecture is the same. If your team is skeptical of the orphan-branch approach, you can point to Gerrit as a nearly 17-year-old production example of why this works.

### When Would You Use GitHub, Then?

The local-only setup is great for personal projects or solo workflows. For teams, you probably still want a remote for backup and sync. But here's the crucial point: **the remote doesn't need branch protection.**

Create a GitHub repo, push the squad state there — but don't configure any branch protection rules. No required reviewers. No PR workflow. Agents push directly to whatever branch they're on. GitHub becomes a backup and sync point, not a gate:

```powershell
# Add GitHub as a remote for backup/sync (optional team setup)
# git commands are identical in PowerShell and bash
git -C .squad remote add origin git@github.com:myorg/myapp-squad.git
git -C .squad push -u origin main
```

Now squad state is backed up to GitHub on every push. Team members can clone `myapp-squad` directly instead of running the init script from scratch. But there are no PRs, no approvals, no notifications. Just git doing what git does.

**Use GitHub for squad state when:**
- You want cloud backup for the state history
- Multiple team members need to sync state across machines
- You want visibility into squad decisions across branches from a central location

**Skip GitHub entirely when:**
- You're the only developer, running everything locally
- Your squad runs on a single machine
- You're in an air-gapped or restricted environment
- You just want to try Squad without creating new repositories or filing tickets to get branch protection configured

The real insight: I framed this whole post as a "git as database" problem, but that framing was slightly wrong. The actual problem is **two different workflows living in the same repo** — a slow, human-gated workflow for code and a fast, autonomous workflow for squad state. Separate the repos, separate the workflows, and the mismatch disappears. GitHub is just one option for where the second repo lives. A directory on your `~` drive works just as well.

---

## What I'm Actually Doing

Right now? I'm running **Approach 1 (Orphan Branch)** in my personal repos and a hybrid of **Approach 2 (Separate Repo)** in the work repo while I socialize the worktree approach with the team.

The orphan branch works beautifully once it's set up. The `.squad/` directory just... stays there. Agents push directly. Code PRs are clean. No noise. No delays.

But I'll be honest: explaining `git worktree` to a team that's never used it is a lift. "Why doesn't `.squad/` show up when I `git status`?" is a question that requires a three-minute explanation, and three minutes is a long time when someone just wants to review a PR.

The separate repo is easier to explain ("it's just another repo") but splits the context. When you're reviewing a code decision, you want the decision doc right there in the same history. Cross-repo references feel fragile.

I'm actively evaluating. The right answer probably depends on your team size and compliance requirements. Small team, relaxed compliance? Separate repo is fine. Large team, need audit trails? Orphan branch. Enterprise with strict auto-merge restrictions? You might be stuck with noisy PRs for now.

---

## Honest Reflection

I wanted the "Git as database" philosophy to just... work. No external dependencies. No coordination layer. Just files and commits.

And it *does* work — for the code. But squad state has different characteristics. Higher update frequency. Lower review requirements. Different conflict patterns. Treating it like code creates friction.

The solutions exist. None are perfect. All require some tradeoff — either complexity (worktree), split context (separate repo), or race conditions (auto-merge).

<figure style="text-align:center; margin: 1.5rem 0;">
  <img src="https://i.imgflip.com/1bhk.jpg" alt="Sweating guy pressing two buttons meme" style="max-width: 400px; border-radius: 8px;">
  <figcaption style="font-style: italic; font-size: 0.85rem; color: #666; margin-top: 0.5rem;">Me choosing between worktree complexity, split context, and race conditions</figcaption>
</figure>

This is one of those problems where the "right" answer depends entirely on your team's tolerance for git complexity vs. operational overhead. And I'm still figuring out which side of that line my team falls on.

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [The Collective — Organizational Knowledge for AI Teams](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — Many Teams, One Repo with SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)
> - **Part 4**: [When Eight Ralphs Fight Over One Login — Distributed Systems in AI Teams](/blog/2026/03/17/scaling-ai-part4-distributed)
> - **Part 5**: [Knowledge is Power — How an AI Squad Learns to Evolve Itself](/blog/2026/03/18/scaling-ai-part5-evolution)
> - **Part 6**: [9 AI Agents, One API Quota — The Rate Limiting Problem](/blog/2026/03/21/rate-limiting-multi-agent)
> - **Part 7**: When Git Is Your Database — The Enterprise State Problem ← You are here


