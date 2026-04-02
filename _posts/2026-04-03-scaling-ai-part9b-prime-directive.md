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

In [Part I](/posts/scaling-ai-part9-prime-directive/), I laid out the threat model: the confused deputy evolved, the insider gaming the AI reviewer, the squad drifting its own directives, and supply chain attacks targeting the squad's context window. Three threats. Zero theoretical — all of them are natural consequences of giving AI agents real permissions.

Now for the part where we build the walls.

I want to be upfront: some of what I'm describing here is deployed and battle-tested. Some of it is designed but not yet wired up. Some of it comes from [Dina Berry's](https://github.com/diberry) recent contributions to the Squad framework — CI gates she built after hitting exactly these problems in her own squad. I'll be clear about what's running in production versus what's still on the workbench.

Let's go layer by layer.

---

## Layer 1: The Reviewer Lockout Protocol

This is the pattern I'm most proud of, because it solves the "AI approves AI" problem structurally — not with policy, but with code.

Here's how the squad's review pipeline works:

**Phase 4 of every task is REVIEW.** Not optional. Not skippable. The orchestration pipeline requires that every code change goes through a reviewer before it can proceed to verification and merge. The reviewer is typically Worf (security) or Q (logic/correctness), depending on the nature of the change.

But the real teeth are in the **lockout rule:**

> **If a reviewer rejects an artifact, the original author cannot self-revise it.**

A *different* agent must do the revision. If that revision is also rejected, the revision author is *also* locked out, and a **third agent** must revise.

Why? Because without this rule, the following happens:
1. Data writes code
2. Worf reviews and rejects it (security concern)
3. Data "fixes" it by making the minimal change to pass review
4. Worf reviews again — but the fundamental design flaw is still there, just disguised

The lockout prevents the author from iterating in a way that games the reviewer. A fresh agent brings fresh perspective. It's the same reason we don't let humans review their own PRs — except now it's enforced at the framework level.

```
Author (Data) → writes code
       ↓
Reviewer (Worf) → REJECTS
       ↓
Revision Author (B'Elanna) → revises  ← DIFFERENT agent
       ↓
Reviewer (Worf) → re-reviews ONLY changed files
       ↓
If rejected again → THIRD agent must revise
```

**The lockout applies per artifact, not globally.** Data can still work on other tasks. He's just locked out of revising *this specific* rejected artifact. And **human rejections follow the same rule** — if I reject something, the same agent can't just tweak it and resubmit.

This is `reviewer-lockout.rego` in the squad's policy directory. It's not a suggestion. It's enforced.

---

## Layer 2: Immutable Guard Rails — Things the Squad Can't Touch

Remember Threat 2 from Part I — "what if the squad changes its own rules?" The answer is: **make some rules immutable.**

Here's the principle: **the mechanisms that enforce governance must be outside the governance scope of the agents.** The squad can modify its charters, its routing table, its decision log. But it *cannot* modify:

### GitHub Actions Workflows

The `.github/workflows/` directory contains the CI/CD pipelines. These are the automated enforcement layer — the check that runs whether the agent likes it or not. If the squad can edit these files, it can disable its own safety checks.

**Fix:** Add `.github/workflows/` to `CODEOWNERS` with a human-only approver:

```
# .github/CODEOWNERS
.github/workflows/ @tamirdresher
.squad/policies/   @tamirdresher
```

No agent PR that modifies a workflow file can merge without explicit human approval. The squad literally cannot change the rules of its own governance.

### Branch Protection Rules

GitHub branch protection is configured in the repository settings UI, not in files. Agents can't modify it through git. This is where you set:
- Required reviewers (minimum 1 human)
- Required status checks (CI must pass)
- No force pushes to `main`/`master`
- No deletions of protected branches

**This is your strongest lever.** It's the one thing that can't be changed by a commit, a PR, or an API call (unless you give the agent admin permissions — don't).

### Azure DevOps Policies (for enterprise teams)

If you're using ADO pipelines alongside GitHub:

```yaml
# azure-pipelines.yml — build validation policy
trigger:
  branches:
    include: [main]

# This policy is set in ADO Project Settings → Repos → Policies
# Not editable via code. Requires Project Admin role.
# Minimum reviewers: 2
# Reset votes on push: Yes
# Build must succeed: Required
```

ADO pipeline policies are configured at the project level by admins. The squad has zero access to modify them. You can set:
- **Minimum number of reviewers** (and require at least one human)
- **Build validation** (pipeline must pass before merge)
- **Comment resolution** (all comments must be resolved)
- **Automatically include reviewers** based on path (e.g., `.squad/` changes → security team)

The combination of GitHub CODEOWNERS + ADO pipeline policies creates a **two-layer lock** that an agent would need to bypass both of to weaken the security posture. And both layers are controlled outside the repository's file tree.

---

## Layer 3: CI Gates That Catch Directive Drift

This is where [Dina Berry's](https://github.com/diberry) contributions to the Squad framework become relevant. She's been contributing CI gates that specifically target the "slow erosion" problem — changes that individually look fine but cumulatively weaken the system.

### Test Count Guard

> *[PR #41](https://github.com/diberry/squad/pull/41) — "Add test count guard to prevent AI agents from deleting tests"*

The problem: an AI agent refactoring code might "clean up" test files it considers redundant. Each deletion is small. The PR looks tidy. But over time, your test coverage drops to nothing.

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

The agent can't silently reduce your test suite. If it needs to remove tests, it has to explicitly update the baseline — which shows up as a diff in the PR for a human to review.

### Hard-Gate Archival Enforcement

> *[PR #45](https://github.com/diberry/squad/pull/45) — "Reorder tasks — archival first with HARD GATE enforcement"*

The problem: Scribe's archival process was running as a soft step — if it failed silently, the agent continued without archiving. Over time, history files bloated, context windows filled with stale data, and agents made decisions based on outdated information.

The fix: archival runs *first* and is a **hard gate** — if it fails, the entire task fails. No silent "oh well, we'll archive next time."

### Workspace Integrity Check

> *[PR #115](https://github.com/diberry/squad/pull/115) — "Add workspace integrity, prerelease guard, and export smoke gates"*

Three CI gates in one:
1. **Workspace integrity** — catches stale npm workspace resolution (you'd be surprised how often agents run `npm install` and don't commit the lockfile changes)
2. **Prerelease guard** — blocks packages with `-alpha` or `-beta` version suffixes from reaching production
3. **Export smoke test** — verifies the package's public API surface hasn't changed unexpectedly

### Document Integrity

> *[PR #731](https://github.com/diberry/squad/pull/731) — "Prevent squad.agent.md silent deletion — 3 code path fixes"* (upstream)

The problem: during `squad upgrade`, `squad init`, or `squad doctor` operations, the `squad.agent.md` file (which Copilot reads to understand agent routing) could be silently deleted. The agent continues working, but it's now flying blind — no routing, no persona, no security constraints.

The fix: three code paths patched to check for the file's existence before and after operations, with hard failures if it disappears.

---

## Layer 4: The Approval Gates (Sync + Async)

I described these in Part I as a trust gradient. Here's the concrete implementation:

### Synchronous Gate — For "Hand on the Button" Moments

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

The key design choice: **fail closed, not open.** If the timeout hits, the operation aborts. The agent doesn't proceed. It doesn't retry. It escalates to the coordinator with status `approval-timeout`.

### Async Gate (AX Pattern) — For Reviewable Proposals

```
Agent opens PR → label: waiting-approval
Human reviews preview → label: approved:ship
GitHub Actions → squash-merge → trigger CD
```

The workflow is 25 lines of YAML:

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

**The agent never approves its own work. The human is the only entity that can add `approved:ship`.** That's not a convenience feature — it's a security boundary.

Ralph monitors for staleness:
- PRs with `waiting-approval` older than 24 hours get a reminder comment
- PRs older than 72 hours get escalated to Picard

---

## Layer 5: Separation of Duties

The final layer is organizational. In the squad's pipeline, these roles are enforced:

| Phase | Actor | Cannot Also Be |
|-------|-------|----------------|
| Write code | Data | Reviewer |
| Security review | Worf | Author of the code |
| Approve deployment | Human | N/A (always human) |
| Execute deployment | GitHub Actions | N/A (automated) |
| Monitor | Ralph | Author or Reviewer |

**The agent that writes the code never reviews it. The agent that reviews it never deploys it. The human is the only one who can authorize deployment.**

This is the same separation of duties pattern that financial auditing has used for decades. The person who writes the check can't sign it. The person who signs it can't cash it. Except now we're applying it to AI agents and git workflows.

---

## Putting It All Together

Here's the full defense stack, layer by layer:

```
┌─────────────────────────────────────────────────┐
│  Layer 5: Separation of Duties                  │
│  (Author ≠ Reviewer ≠ Approver ≠ Deployer)      │
├─────────────────────────────────────────────────┤
│  Layer 4: Approval Gates                        │
│  Sync gate (kubectl, git push to main)          │
│  Async gate (PR + approved:ship label)          │
├─────────────────────────────────────────────────┤
│  Layer 3: CI Gates (Dina's contributions)       │
│  Test count guard · Hard-gate archival          │
│  Workspace integrity · Export smoke test        │
│  Document integrity (squad.agent.md)            │
├─────────────────────────────────────────────────┤
│  Layer 2: Immutable Guard Rails                 │
│  CODEOWNERS · Branch protection                 │
│  ADO pipeline policies · Workflow lockdown      │
├─────────────────────────────────────────────────┤
│  Layer 1: Reviewer Lockout Protocol             │
│  Rejected? Different agent must revise.         │
│  Rejected again? Third agent. No self-approval. │
└─────────────────────────────────────────────────┘
```

No single layer is sufficient. An insider could potentially bypass any one of them. But together, they create a defense-in-depth stack where:

- The **reviewer lockout** prevents agents from iterating past a rejection
- The **immutable guard rails** prevent agents from editing the rules
- The **CI gates** catch slow drift in tests, documents, and workspace integrity
- The **approval gates** require human authorization for high-blast-radius operations
- The **separation of duties** ensures no single agent controls the entire pipeline

---

## What's Still on the Workbench

I promised to be honest about what's deployed versus what's designed. Here's the scorecard:

| Component | Status |
|-----------|--------|
| Reviewer lockout protocol | ✅ Enforced in orchestration pipeline |
| CODEOWNERS for `.squad/` | ⚠️ Designed, not yet applied to all repos |
| Branch protection on `main` | ✅ Active on production repos |
| ADO pipeline policies | ✅ Active (enterprise repos only) |
| Test count guard (CI) | ✅ Merged in Squad framework |
| Hard-gate archival | ✅ Merged in Squad framework |
| Workspace integrity check | ✅ Merged in Squad framework |
| Document integrity | ✅ Merged upstream (PR #731) |
| AX approval gate workflow | ⚠️ Designed, deploying to tamirdresher.github.io this week |
| Synchronous approval gate | ⚠️ PowerShell helper exists, not CI-enforced |
| Separation of duties | ✅ Enforced in pipeline phases |

The big remaining gap: the AX approval gate isn't deployed yet. That's literally the next thing I'm doing — wiring it up to this blog's repository so that agent-proposed posts (like this one!) go through the `waiting-approval` → `approved:ship` flow.

---

## The Principle Behind All of This

Every layer I've described follows the same principle:

**The mechanisms that enforce governance must be outside the governance scope of the agents.**

The agents can write code — but can't approve it. They can propose changes — but can't merge them. They can read policies — but can't modify the enforcement layer. The workflows, branch protections, and ADO policies exist in a plane that the agents can see but can't touch.

This is the Prime Directive applied to infrastructure. Not "don't interfere" — but "the rules about interference are written in a language you can't edit."

Because here's the thing: my squad is not malicious. It's not going to deliberately weaken its own security posture. The danger isn't intent — it's drift. It's the well-meaning optimization that removes a check. The helpful refactor that consolidates two approval steps into one. The efficiency improvement that shortens the timeout from 15 minutes to 15 seconds.

Drift happens when the rules are soft. Immutable guard rails make them hard.

---

## For Your Team: A Starting Checklist

If you're running AI agents with real permissions, here's the minimum viable defense stack:

1. **[ ] CODEOWNERS** — Protect `.github/workflows/`, `.squad/policies/`, and any file that defines agent behavior. Require human approval for changes.
2. **[ ] Branch protection** — Require at least one human reviewer on `main`. No force pushes. Required status checks.
3. **[ ] Separation of duties** — The agent that writes code must not be the agent that reviews it. Enforce in your orchestration layer.
4. **[ ] Test count baseline** — Record how many tests you have. Fail CI if the count drops.
5. **[ ] Approval gate for destructive ops** — Any operation that changes production state must require explicit human authorization. Fail closed on timeout.

That's five items. You can implement all five in a single afternoon. And they'll catch 90% of the threats I described in Part I.

The remaining 10%? That's what keeps me building.

---

*This is Part 9b of [Scaling AI-Native Software Engineering](/tags/scaling-ai-native-software-engineering/), a series about building and running AI agent teams in real software projects. [Part 9a](/posts/scaling-ai-part9-prime-directive/) covered the threat model. Next up: something lighter. Probably.*

---

*The code, playbooks, and patterns described in this post are open source as part of the [Squad framework](https://github.com/tamirdresher/squad). Dina Berry's CI gate contributions are in [diberry/squad](https://github.com/diberry/squad) and several have been merged upstream.*
