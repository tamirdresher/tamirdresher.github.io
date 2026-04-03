---
layout: post
title: "The Prime Directive, Part II — Building the Defense Stack"
date: 2026-04-03
image: /assets/img/part9b-prime-directive.png
tags: [ai-agents, squad, github-copilot, approval-gates, governance, security, ci-cd, reviewer-protocol, defense-in-depth, star-trek, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 9
---

![The Prime Directive Part II — Defense in depth for AI agent teams](/assets/img/part9b-prime-directive.png)

> *"Shields up. Red alert."*
> — Every Starfleet captain, at the exact moment they realize talking isn't going to work

In [Part I](/posts/scaling-ai-part9-prime-directive/), I laid out the threat model: the confused deputy evolved, the insider gaming the AI reviewer, the squad drifting its own directives, and supply chain attacks targeting the squad's context window. Four threats. Zero theoretical — all of them are natural consequences of giving AI agents real permissions. (Also, while writing Part I, the axios supply chain attack happened in real time. The universe has a flair for dramatic timing.)

Now for the part where we build the walls. Or, more accurately, the part where I admit I should have built the walls earlier and then show you the blueprints.

I want to be upfront: some of what I'm describing here is deployed and battle-tested. Some of it is designed but not yet wired up. Some of it comes from community contributions to the [Squad framework](https://github.com/bradygaster/squad) — CI gates built after hitting exactly these problems in production. And some of it is informed by recent academic research that I'll cite throughout. I'll be clear about what's running in production versus what's still on the workbench.

Let's go layer by layer.

---

## Layer 1: The Reviewer Lockout Protocol

This is the pattern I'm most proud of, because it solves the "AI approves AI" problem structurally — not with policy, but with code. (Full documentation: [Reviewer Protocol](https://bradygaster.github.io/squad/features/reviewer-protocol/))

Here's the problem it solves. In a normal code review cycle, if a reviewer rejects your PR, you fix it and resubmit. That's fine for humans — we learn from feedback and genuinely improve the code. But AI agents optimize for one thing: **passing the check.** Without guardrails, an agent will make the minimum change to satisfy the reviewer, even if the underlying design problem is still there.

So the squad enforces a **lockout rule:**

> **If a reviewer rejects an artifact, the original author cannot self-revise it.**

A *different* agent must do the revision. If that revision is also rejected, the revision author is *also* locked out, and a **third agent** must revise. Here's what that looks like in practice:

```
 ┌──────────────┐
 │  Data writes  │
 │    code       │
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │ Worf reviews  │──── APPROVE ──→ ✅ Merge
 │ (security)    │
 └──────┬───────┘
        │ REJECT
        ▼
 ╔══════════════════════════════════════╗
 ║  🔒 Data is LOCKED OUT              ║
 ║  Cannot revise this artifact        ║
 ║  (Can still work on other tasks)    ║
 ╚══════════════════════════════════════╝
        │
        ▼
 ┌──────────────┐
 │ B'Elanna      │ ← DIFFERENT agent, fresh perspective
 │ revises code  │
 └──────┬───────┘
        ▼
 ┌──────────────┐
 │ Worf reviews  │──── APPROVE ──→ ✅ Merge
 │ (re-review)   │
 └──────┬───────┘
        │ REJECT again
        ▼
 ╔══════════════════════════════════════╗
 ║  🔒 B'Elanna ALSO locked out        ║
 ║  THIRD agent must revise            ║
 ║  If all exhausted → escalate to     ║
 ║  human (you)                        ║
 ╚══════════════════════════════════════╝
```

Why does this matter? Because without lockout, you get an infinite fix-reject loop where the agent learns to game the reviewer rather than fix the actual problem. With lockout, a fresh agent brings fresh perspective — and if nobody can satisfy the reviewer, **the human gets pulled in**, which is exactly the right escalation path.

**Human rejections follow the same rule.** If I reject something, the same agent can't just tweak it and resubmit. That prevents the "I'll just change one line until Tamir clicks approve at 11 PM because he's tired" pattern. (Don't look at me like that. You've done it too.)

---

## Layer 2: Immutable Guard Rails — Things the Squad Can't Touch

Remember Threat 2 from Part I — "what if the squad changes its own rules?" The answer is: **make some rules immutable.**

Here's the principle: **the mechanisms that enforce governance must be outside the governance scope of the agents.** The squad can modify its charters, its routing table, its decision log. But it *cannot* modify:

### GitHub Actions Workflows

The `.github/workflows/` directory contains the CI/CD pipelines. These are the automated enforcement layer — the check that runs whether the agent likes it or not. If the squad can edit these files, it can disable its own safety checks.

**Fix:** Use `CODEOWNERS` with a human-only approver:

```
# .github/CODEOWNERS
.github/workflows/ @tamirdresher
.squad/policies/   @tamirdresher
```

(Yes, that's me. The bus factor is 1. I'm aware. We're working on it.)

Now here's the nuance — and this tripped me up when a team member asked: **CODEOWNERS only works if the squad is operating under its own identity, not yours.** If your agents are running as *you* (same GitHub token, same identity), CODEOWNERS can't distinguish between "you pushed this" and "an agent pushed this using your token."

This is where **GitHub's Copilot coding agent** becomes genuinely interesting from a security perspective. When Copilot picks up an issue, it operates under its own identity — `copilot[bot]` — not yours. That means CODEOWNERS *does* catch its changes. The PR shows a bot author, the review requirement triggers, and the human gate actually holds.

```
 ┌─────────────────────────────────────────────────────────────┐
 │  Who is pushing?                                            │
 │                                                             │
 │  Your token (squad runs as you)                             │
 │    → CODEOWNERS: ⚠️  YOU are the owner                     │
 │    → Branch protection: ✅ Still requires PR review         │
 │    → Actions workflows: ✅ Still run regardless             │
 │                                                             │
 │  Copilot bot identity                                       │
 │    → CODEOWNERS: ✅ Bot ≠ owner, review required            │
 │    → Branch protection: ✅ Requires PR review               │
 │    → Actions workflows: ✅ Still run regardless             │
 │                                                             │
 │  Dedicated service account / workload identity              │
 │    → CODEOWNERS: ✅ Service ≠ owner, review required        │
 │    → Branch protection: ✅ Requires PR review               │
 │    → Actions workflows: ✅ Still run regardless             │
 └─────────────────────────────────────────────────────────────┘
```

**Takeaway:** If you're running agents under your own identity, CODEOWNERS is necessary but not sufficient. You need the other layers — branch protection, CI gates, and approval gates — to compensate. The strongest setup is agents operating under their own identity (via GitHub Actions, Copilot agent, or a dedicated service account).

### Branch Protection Rules

GitHub branch protection is configured in the repository settings UI, not in files. Agents can't modify it through git. This is where you set:
- Required reviewers (minimum 1 human)
- Required status checks (CI must pass)
- No force pushes to `main`/`master`
- No deletions of protected branches

**This is your strongest lever regardless of identity.** Even if the agent runs as you, it still has to go through a PR, get a review, and pass CI. It's the one thing that can't be changed by a commit, a PR, or an API call (unless you give the agent admin permissions — and if you do that, I can't help you. Nobody can help you. You've chosen chaos).

### Azure DevOps Policies (for enterprise teams)

If you're using ADO pipelines alongside GitHub, you get another layer for free. ADO pipeline policies are configured at the project level by admins — not in repo files:

- **Minimum number of reviewers** (and require at least one human)
- **Build validation** (pipeline must pass before merge)
- **Comment resolution** (all comments must be resolved)
- **Automatically include reviewers** based on path (e.g., `.squad/` changes → security team)

The combination of GitHub branch protection + ADO pipeline policies creates a **two-layer lock** that an agent would need to bypass both of to weaken the security posture. And both layers are controlled outside the repository's file tree.

---

## Layer 3: CI Gates That Catch Directive Drift

This is where the Squad framework's CI gates become critical. Several contributors have been building gates that specifically target the "slow erosion" problem: changes that individually look innocent but cumulatively weaken the system. It's like watching someone remove one screw at a time from an IKEA bookshelf. Each one seems fine. Then you lean on it.

Researchers call this the "boiling frog" of agentic security. A recent systematization paper ([Shi et al., 2025](https://arxiv.org/abs/2512.06914)) frames it as the **Trust-Authorization Mismatch**: static permissions can't track an agent's fluctuating runtime trustworthiness. Your CI gates are the runtime check that compensates for that gap.

### Test Count Guard

The problem: an AI agent refactoring code might "clean up" test files it considers redundant. Each deletion is small. The PR looks tidy. The commit message says something reassuring like "remove obsolete tests." But over time, your test coverage drops to nothing — and nobody noticed because each individual PR was fine. Death by a thousand tidy commits.

The fix: a CI step that records the baseline test count and **fails the build if the count drops.**

```yaml
- name: Test count guard
  run: |
    CURRENT=$(find tests/ -name "*.test.*" | wc -l)
    BASELINE=$(cat .squad/test-baseline.txt)
    if [ "$CURRENT" -lt "$BASELINE" ]; then
      echo "❌ Test count dropped from $BASELINE to $CURRENT"
      echo "If tests were intentionally removed, update .squad/test-baseline.txt"
      exit 1
    fi
```

The agent can't silently reduce your test suite. If it needs to remove tests, it has to explicitly update the baseline — which shows up as a diff in the PR for a human to review. It's the engineering equivalent of "I see you moved that cookie jar. Put it back."

This isn't hypothetical paranoia, by the way — research shows LLMs routinely hallucinate package names at [5.2% for commercial models](https://arxiv.org/abs/2406.10279). The same optimization instinct that invents a dependency will happily delete a test that "isn't needed."

### Hard-Gate Archival Enforcement

> *[PR #637](https://github.com/bradygaster/squad/pull/637) — "Reorder tasks — archival first with HARD GATE enforcement"* (merged)

The problem: Scribe's archival process was running as a soft step — if it failed silently, the agent continued without archiving. Over time, history files bloated, context windows filled with stale data, and agents made decisions based on outdated information.

The fix: archival runs *first* and is a **hard gate** — if it fails, the entire task fails. No silent "oh well, we'll archive next time." This matters because an agent's belief state (what it "knows") directly affects its decisions. Stale context = bad decisions = drift.

### Workspace Integrity + Prerelease Guard

> *[PR #691](https://github.com/bradygaster/squad/pull/691) — "Add workspace integrity, prerelease guard, and export smoke gates"* (merged)

Three CI gates in one (because apparently we were having a "buy one get two free" sale on security):
1. **Workspace integrity** — catches stale npm workspace resolution (you'd be surprised how often agents run `npm install` and don't commit the lockfile changes — or maybe you wouldn't, if you've ever worked with a junior developer at 4 AM)
2. **Prerelease guard** — blocks packages with `-alpha` or `-beta` version suffixes from reaching production
3. **Export smoke test** — verifies the package's public API surface hasn't changed unexpectedly

Why does the prerelease guard matter? Because AI agents are aggressive optimizers. When an agent sees a newer version of a package, it wants to use it — even if that version is a pre-release. This is a concrete supply chain risk: attackers can publish a `-beta` version with malicious code, knowing that an AI coding agent might eagerly adopt it.

But here's the sobering reality check — and I had to rewrite this paragraph after the axios incident happened while I was drafting this post: **the prerelease guard wouldn't have caught the axios attack.** The poisoned `axios@1.14.1` was a full release version, not a prerelease — it sailed past every version-based heuristic like it owned the place. What *would* have caught it? The **workspace integrity check**. The attack injected `plain-crypto-js@4.2.1` as a new dependency that never existed in the legitimate codebase. A lockfile diff check would have screamed "Hey! A *brand new* dependency appeared — one that's never been imported anywhere in the source code!" That's why you need the full CI gate stack, not just one check. Each gate catches a different failure mode. Security is a team sport, even when the team is made of YAML files.

The axios incident ([March 2026](https://www.stepsecurity.io/blog/axios-compromised-on-npm-malicious-versions-drop-remote-access-trojan)) is a case study in why. The attacker compromised a maintainer's credentials, published two poisoned versions that injected a self-destructing RAT via `postinstall`, and the malicious versions didn't even appear in GitHub tags. The forensic signal? The legitimate releases used npm's OIDC Trusted Publisher (published by GitHub Actions), but the malicious ones were published manually — no `trustedPublisher` field, no `gitHead`. If your CI pipeline checks for OIDC provenance on critical dependencies, you'd catch it. If not... you're running `npm install` and hoping for the best.

### Concurrency Controls

> *[PR #705](https://github.com/bradygaster/squad/pull/705) — "Concurrency controls for 5 workflows"* (merged)

The problem: multiple squad agents can trigger GitHub Actions workflows simultaneously. Without concurrency controls, you get race conditions — two agents trying to merge to `main` at the same time, or two deployments overlapping.

The fix: GitHub Actions `concurrency` groups that ensure only one instance of each workflow runs at a time:

```yaml
concurrency:
  group: squad-deploy-${{ github.ref }}
  cancel-in-progress: true  # Latest run wins — stale runs are cancelled
```

The `cancel-in-progress: true` means if a newer push arrives while a workflow is running, the old run is cancelled. For issue-driven workflows, the concurrency group uses the issue number, so two agents working on different issues run in parallel, but two agents touching the *same* issue queue up.

```
  ┌──────────────────────────────────────────────────────┐
  │  CI Gate Stack                                        │
  │                                                       │
  │  Agent opens PR                                       │
  │    ↓                                                  │
  │  ✅ Test count ≥ baseline?                            │
  │    ↓                                                  │
  │  ✅ No pre-release dependencies?                      │
  │    ↓                                                  │
  │  ✅ Workspace lockfile consistent?                    │
  │    ↓                                                  │
  │  ✅ Public API surface unchanged?                     │
  │    ↓                                                  │
  │  ✅ Archival completed (hard gate)?                   │
  │    ↓                                                  │
  │  ✅ Concurrency slot available?                       │
  │    ↓                                                  │
  │  ➡️  Ready for human review                           │
  │                                                       │
  │  ANY gate fails → PR blocked, agent notified          │
  └──────────────────────────────────────────────────────┘
```

The pattern here is **defense against drift, not defense against malice.** These gates don't assume the agent is adversarial — they assume it's an enthusiastic optimizer that doesn't know when to stop. Think of it as childproofing your house: the kid isn't trying to burn the place down, but you still put covers on the electrical outlets.

---

## Layer 4: The Approval Gate — Where Humans Stay in the Loop

This is the layer that people ask about most after my security talks: "How do you actually stop the squad from deploying something dangerous?"

Two flavors: synchronous (block and wait) and asynchronous (propose and review). Both exist because different operations have different risk profiles — and because I got inspired by an unexpected source.

### The AX Inspiration

In early 2026, Netlify's CEO Matt Biilmann coined the term **AX — Agent Experience** ([netlify.com/agent-experience](https://www.netlify.com/agent-experience/)) to describe how products should be designed for AI agent users. The core insight: if AI agents are going to be primary users of your platform, the platform needs to be designed for their workflow, not just for humans clicking buttons.

I read that and had an "oh wait" moment. The kind where you stop scrolling and stare at the wall for a minute. We'd been thinking about the squad as *our* tool. But what if we flipped it? What if we designed the approval workflow from the *agent's perspective* — letting the agent do everything it can autonomously, and only pulling the human in at the exact moment where human judgment is irreplaceable?

That's the AX Approval Gate pattern. The agent works autonomously until it hits a trust boundary. Then it creates a reviewable artifact (a PR, a preview, a diff), tags it for human attention, and *waits*. The human reviews on their own schedule, applies a label, and the automation takes it from there.

Here's the full flow:

```
  ┌─────────────────────────────────────────────────────────┐
  │  AX Approval Gate — Step by Step                         │
  │                                                          │
  │  1. Agent completes work                                 │
  │     (code change, blog post, config update)              │
  │     ↓                                                    │
  │  2. Agent opens PR with preview/diff                     │
  │     Labels: waiting-approval                             │
  │     ↓                                                    │
  │  3. Human reviews on their own schedule                  │
  │     (hours later, next morning, whenever)                │
  │     ↓                                                    │
  │  ┌─────────── Decision Point ──────────┐                 │
  │  │                                     │                 │
  │  │  APPROVE                  REJECT    │                 │
  │  │  Human adds label:        Human     │                 │
  │  │  approved:ship            comments  │                 │
  │  │     ↓                       ↓       │                 │
  │  │  GitHub Action            Agent     │                 │
  │  │  auto-merges              revises   │                 │
  │  │  (squash + delete         (lockout  │                 │
  │  │   branch)                  rules    │                 │
  │  │     ↓                     apply!)   │                 │
  │  │  CD triggers                        │                 │
  │  └─────────────────────────────────────┘                 │
  │                                                          │
  │  Ralph monitors for staleness:                           │
  │    24h with waiting-approval → reminder comment          │
  │    72h → escalate to Picard (lead)                       │
  └─────────────────────────────────────────────────────────┘
```

**The agent never approves its own work. The human is the only entity that can add `approved:ship`.** That's not a convenience feature — it's a security boundary.

The workflow itself is about 25 lines of YAML:

```yaml
name: AX Approval Gate
on:
  pull_request_target:
    types: [labeled]

jobs:
  auto-merge:
    if: contains(github.event.pull_request.labels.*.name, 'approved:ship')
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Squash-merge PR
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh pr merge "${{ github.event.pull_request.number }}" \
            --repo "${{ github.repository }}" \
            --squash --delete-branch
```

### Synchronous Gate — For "Hand on the Button" Moments

The async gate works for code changes and content. But some operations can't wait for a human to check their email — a `kubectl apply` to production, a database migration, a DNS change. For those, we use a synchronous gate:

```powershell
# B'Elanna is about to kubectl apply to production
if ($cluster -match 'prod' -and $namespace -notmatch 'test|sandbox') {
    $requestId = Request-ApprovalGate `
        -Agent "B'Elanna" `
        -Operation "kubectl apply -f $manifest" `
        -TargetResource "$cluster / $namespace" `
        -EstimatedImpact "Deploy api-service v2.4.1 (15 pods)"

    # Agent STOPS here. Waits for human.
    # Timeout: 15 minutes → ABORT (fail closed)
}
```

The key design choice: **fail closed, not open.** If the timeout hits, the operation aborts. The agent doesn't proceed. It doesn't retry. It escalates to the coordinator with status `approval-timeout`. This is directly informed by the Belief-Intention-Permission framework from recent security research ([Shi et al., 2025](https://arxiv.org/abs/2512.06914)): the agent's *intention* (deploy to prod) requires *permission* that only a human can grant, and that permission has an expiration.

### Why Two Gates?

```
  ┌──────────────────────────────────────────────────────┐
  │  Which gate do you need?                              │
  │                                                       │
  │  ASYNC (AX Pattern)          SYNC (Hand on Button)    │
  │  ─────────────────           ────────────────────     │
  │  Code changes                kubectl to prod          │
  │  Blog posts                  Database migrations      │
  │  Config updates              DNS changes              │
  │  Documentation               Secret rotation          │
  │  Dependency bumps             Infrastructure scaling   │
  │                                                       │
  │  Review window: hours        Review window: minutes    │
  │  Fail mode: PR stays open    Fail mode: abort + alert │
  │  Human effort: label click   Human effort: active wait │
  └──────────────────────────────────────────────────────┘
```

Ralph monitors for staleness on async gates:
- PRs with `waiting-approval` older than 24 hours get a reminder comment
- PRs older than 72 hours get escalated to Picard

---

## Layer 5: Separation of Duties — And the Workload Identity Experiment

The final layer is organizational, and it's the one I keep coming back to because it maps directly to a principle that financial auditing figured out decades ago: **the person who writes the check can't sign it, and the person who signs it can't cash it.** (If your bank doesn't work this way, please change banks immediately.)

In the squad's pipeline, these roles are enforced:

| Phase | Actor | Cannot Also Be |
|-------|-------|----------------|
| Write code | Data | Reviewer |
| Security review | Worf | Author of the code |
| Approve deployment | Human | N/A (always human) |
| Execute deployment | GitHub Actions | N/A (automated) |
| Monitor + alert | Ralph | Author or Reviewer |

**The agent that writes the code never reviews it. The agent that reviews it never deploys it. The human is the only one who can authorize deployment.**

```
  ┌──────────────────────────────────────────────────────┐
  │  Separation of Duties — The Pipeline                  │
  │                                                       │
  │  DATA writes code                                     │
  │    ↓                                                  │
  │  WORF reviews (cannot be Data)                        │
  │    ↓                                                  │
  │  HUMAN approves (approved:ship label)                 │
  │    ↓                                                  │
  │  GITHUB ACTIONS deploys (automated, no agent access)  │
  │    ↓                                                  │
  │  RALPH monitors (cannot be author or reviewer)        │
  │                                                       │
  │  ❌ Data reviews Data's code → BLOCKED                │
  │  ❌ Worf deploys after Worf reviews → BLOCKED         │
  │  ❌ Any agent approves → BLOCKED (human only)         │
  └──────────────────────────────────────────────────────┘
```

### The Workload Identity Experiment: Squad on AKS

Here's where it gets interesting. We've been experimenting with running squad agents as separate pods on Azure Kubernetes Service, where each agent runs with a **different Azure workload identity** ([tamirdresher/squad-on-aks](https://github.com/tamirdresher/squad-on-aks)).

Why? Because in the current model, all agents share the same execution context — same token, same permissions. If one agent is compromised (say, via a prompt injection in a malicious issue), it has access to everything the other agents can see. That's the "blast radius" problem. It's like putting all your eggs in one basket, except the basket is on fire and the eggs are production credentials.

In the AKS model, each agent pod has its own workload identity with its own Azure RBAC scope:

```
  ┌─────────────────────────────────────────────────────────┐
  │  AKS Pod-per-Agent Architecture                          │
  │                                                          │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
  │  │  Data     │  │  Worf    │  │  Ralph   │               │
  │  │  Pod      │  │  Pod     │  │  Pod     │               │
  │  │          │  │          │  │          │               │
  │  │ Identity: │  │ Identity: │  │ Identity: │               │
  │  │ data-wi   │  │ worf-wi   │  │ ralph-wi  │               │
  │  │          │  │          │  │          │               │
  │  │ Scope:    │  │ Scope:    │  │ Scope:    │               │
  │  │ read/write│  │ read-only │  │ read +    │               │
  │  │ code repos│  │ code repos│  │ monitor   │               │
  │  │ + create  │  │ + security│  │ endpoints │               │
  │  │ PRs       │  │ scanning  │  │ + alert   │               │
  │  └──────────┘  └──────────┘  └──────────┘               │
  │       │              │              │                     │
  │       ▼              ▼              ▼                     │
  │  ┌──────────────────────────────────────────────────┐    │
  │  │  Shared: GitHub repo, but each identity has       │    │
  │  │  different permissions (enforced by Azure RBAC)   │    │
  │  └──────────────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────────────┘
```

This is still experimental. We're running it on AKS free tier with KEDA-based autoscaling — agents spin up when work arrives and spin down when idle. But the security model is sound: if Data's pod is compromised via prompt injection, the attacker gets Data's permissions — not Worf's, not Ralph's, and not the human's.

The research backs this up. Bühler et al. ([2025](https://arxiv.org/abs/2510.21236)) studied MCP server security and found that "thousands of MCP servers execute with unrestricted access to host systems, creating a broad attack surface." Their recommendation? Sandboxed execution with fine-grained permissions — exactly what the pod-per-agent model gives us.

---

## Putting It All Together

Here's the full defense stack, layer by layer:

```
┌─────────────────────────────────────────────────────┐
│  Layer 5: Separation of Duties + Workload Identity   │
│  Author ≠ Reviewer ≠ Approver ≠ Deployer             │
│  Pod-per-agent with Azure RBAC (experimental)        │
├─────────────────────────────────────────────────────┤
│  Layer 4: Approval Gates                             │
│  Async: AX pattern (PR + approved:ship label)        │
│  Sync: fail-closed timeout (kubectl, DNS, DB)        │
├─────────────────────────────────────────────────────┤
│  Layer 3: CI Gates                                   │
│  Test count guard · Hard-gate archival               │
│  Workspace integrity · Prerelease guard              │
│  Export smoke test · Concurrency controls            │
├─────────────────────────────────────────────────────┤
│  Layer 2: Immutable Guard Rails                      │
│  CODEOWNERS · Branch protection                      │
│  ADO pipeline policies · Workflow lockdown           │
├─────────────────────────────────────────────────────┤
│  Layer 1: Reviewer Lockout Protocol                  │
│  Rejected? Different agent must revise.              │
│  Rejected again? Third agent. No self-approval.      │
└─────────────────────────────────────────────────────┘
```

No single layer is sufficient. An insider could potentially bypass any one of them. But together, they create a defense-in-depth stack where bypassing *all of them* requires either a Mission: Impossible level of coordination or admin access to the GitHub org (in which case you have bigger problems):

- The **reviewer lockout** prevents agents from iterating past a rejection (no "just one more try, I promise")
- The **immutable guard rails** prevent agents from editing the rules (the constitution is not a pull request)
- The **CI gates** catch slow drift in tests, dependencies, and workspace integrity (the boiling frog detector)
- The **approval gates** require human authorization for high-blast-radius operations (the "are you sure?" of infrastructure)
- The **separation of duties** ensures no single agent controls the entire pipeline — and workload identity isolation limits the blast radius if one agent is compromised (compartmentalization, the boring superpower)

---

## What's Still on the Workbench

I promised to be honest about what's deployed versus what's designed. Here's the scorecard:

| Component | Status |
|-----------|--------|
| Reviewer lockout protocol | ✅ Enforced in orchestration pipeline |
| CODEOWNERS for `.squad/` | ⚠️ Designed, not yet applied to all repos |
| Branch protection on `main` | ✅ Active on production repos |
| ADO pipeline policies | ✅ Active (enterprise repos only) |
| Test count guard (CI) | 📋 Recommended pattern (not yet in Squad CI) |
| Hard-gate archival | ✅ Merged in Squad framework ([PR #637](https://github.com/bradygaster/squad/pull/637)) |
| Workspace integrity check | ✅ Merged in Squad framework ([PR #691](https://github.com/bradygaster/squad/pull/691)) |
| Concurrency controls | ✅ Merged in Squad framework ([PR #705](https://github.com/bradygaster/squad/pull/705)) |
| AX approval gate workflow | ⚠️ Designed, deploying to tamirdresher.github.io this week |
| Synchronous approval gate | ⚠️ PowerShell helper exists, not CI-enforced |
| Separation of duties | ✅ Enforced in pipeline phases |
| Pod-per-agent (AKS) | 🧪 Experimental — running on [squad-on-aks](https://github.com/tamirdresher/squad-on-aks) |

The big remaining gap: the AX approval gate isn't deployed yet. That's literally the next thing I'm doing — wiring it up to this blog's repository so that agent-proposed posts (like this one!) go through the `waiting-approval` → `approved:ship` flow. Yes, I'm writing about the thing I haven't finished building. Welcome to the blog.

---

## The Principle Behind All of This

Every layer I've described follows the same principle:

**The mechanisms that enforce governance must be outside the governance scope of the agents.**

The agents can write code — but can't approve it. They can propose changes — but can't merge them. They can read policies — but can't modify the enforcement layer. The workflows, branch protections, and ADO policies exist in a plane that the agents can see but can't touch.

This is what the security researchers call "externalizing the trust anchor" ([Shi et al., 2025](https://arxiv.org/abs/2512.06914)). In their B-I-P framework, the *Permission* layer must be decoupled from the agent's *Belief* and *Intention* layers — because an agent whose beliefs have been corrupted (via prompt injection, stale context, or supply chain poisoning) will naturally form intentions to bypass security. The permissions layer has to not care.

This is the Prime Directive applied to infrastructure. Not "don't interfere" — but "the rules about interference are written in a language you can't edit."

Because here's the thing: my squad is not malicious. It's not going to deliberately weaken its own security posture. The danger isn't intent — it's drift. It's the well-meaning optimization that removes a check. The helpful refactor that consolidates two approval steps into one. The efficiency improvement that shortens the timeout from 15 minutes to 15 seconds.

Drift happens when the rules are soft. Immutable guard rails make them hard.

---

## For Your Team: A Starting Checklist

If you're running AI agents with real permissions, here's the minimum viable defense stack:

1. **[ ] CODEOWNERS** — Protect `.github/workflows/`, `.squad/policies/`, and any file that defines agent behavior. Require human approval for changes. (But remember: this only works if the agent runs under its own identity, not yours.)
2. **[ ] Branch protection** — Require at least one human reviewer on `main`. No force pushes. Required status checks. This is your strongest lever.
3. **[ ] Separation of duties** — The agent that writes code must not be the agent that reviews it. Enforce in your orchestration layer.
4. **[ ] Test count baseline** — Record how many tests you have. Fail CI if the count drops.
5. **[ ] Approval gate for destructive ops** — Any operation that changes production state must require explicit human authorization. Fail closed on timeout.
6. **[ ] Agent identity** — Run your agents under their own identity (GitHub App, Copilot bot, or dedicated service account), not your personal token. This makes every other control more effective.

That's six items. You can implement the first five in a single afternoon. (I say "afternoon" but it took me a weekend. Don't judge.) Item 6 takes longer but pays off exponentially — it's the difference between CODEOWNERS being a suggestion and CODEOWNERS being a wall.

The remaining edge cases? That's what keeps me building. And occasionally keeps me up at night. But mostly building.

---

*This is Part 9b of [Scaling AI-Native Software Engineering](/tags/scaling-ai-native-software-engineering/), a series about building and running AI agent teams in real software projects. [Part 9a](/posts/scaling-ai-part9-prime-directive/) covered the threat model. Next up: something lighter. Probably.*

---

## References & Further Reading

**Academic research that informed this post:**

- Shi, G. et al. (2025). ["SoK: Trust-Authorization Mismatch in LLM Agent Interactions."](https://arxiv.org/abs/2512.06914) — The Belief-Intention-Permission (B-I-P) framework: a formal lens for why static permissions fail when agents have dynamic trustworthiness. Directly relevant to the approval gate design.

- Bühler, C. et al. (2025). ["Securing AI Agent Execution."](https://arxiv.org/abs/2510.21236) — Analysis of MCP server security, finding that most agent tools run with unrestricted access. Motivates the pod-per-agent workload identity approach in Layer 5.

- Abaev, N. et al. (2026). ["AgentGuardian: Learning Access Control Policies to Govern AI Agent Behavior."](https://arxiv.org/abs/2601.10440) — A security framework for context-aware access control in AI agent operations.

- Spracklen, J. et al. (2024). ["We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs."](https://arxiv.org/abs/2406.10279) — LLMs routinely hallucinate package names, creating supply chain attack vectors. Motivates the prerelease guard in Layer 3.

- Twist, L. et al. (2025). ["Library Hallucinations in LLMs: Risk Analysis Grounded in Developer Queries."](https://arxiv.org/abs/2509.22202) — Introduces the term "slopsquatting" — attackers registering the package names that LLMs hallucinate.

**Industry sources:**

- [Netlify AX (Agent Experience)](https://www.netlify.com/agent-experience/) — The concept that inspired the async approval gate pattern.
- [Axios Supply Chain Attack Analysis (StepSecurity)](https://www.stepsecurity.io/blog/axios-compromised-on-npm-malicious-versions-drop-remote-access-trojan) — Detailed forensics on the March 2026 axios npm compromise, including OIDC provenance bypass and self-destructing malware.
- [Axios Attack: npm Trust (Malwarebytes)](https://www.malwarebytes.com/blog/news/2026/03/axios-supply-chain-attack-chops-away-at-npm-trust) — Broader analysis of the axios incident's implications for the npm ecosystem.
- [Squad Framework Reviewer Protocol](https://bradygaster.github.io/squad/features/reviewer-protocol/) — Full documentation on the lockout mechanism described in Layer 1.
- [Squad on AKS](https://github.com/tamirdresher/squad-on-aks) — The pod-per-agent experiment with workload identity isolation.
- [Squad Framework](https://github.com/bradygaster/squad) — The open-source framework behind these patterns. CI gate PRs linked throughout the post.
