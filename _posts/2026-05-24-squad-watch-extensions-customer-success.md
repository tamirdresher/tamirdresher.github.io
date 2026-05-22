---
layout: post
title: "Ralph Gets a Toolbelt - Extending Squad Watch for Customer Success"
date: 2026-05-24
tags: [ai-agents, squad, automation, extensibility, customer-success, workflows, github-copilot]
series: "Scaling AI-Native Software Engineering"
series_part: 18
---

> *"The most dangerous phrase in software is: while we are in here, let's just add one more step."*
> - Every workflow runner, five minutes before becoming a platform

Most of my Squad posts so far have been for engineers.

Kubernetes. Rate limits. Distributed agents. GitHub issues. Build pipelines. Failure modes that only appear after you give nine AI agents the same API quota and a false sense of purpose.

I love that stuff.

But if Squad is only interesting to people who enjoy debugging YAML at midnight, then I failed.

The bigger idea was never "AI agents can write pull requests." The bigger idea was: **a team of specialized agents can operate a repeatable workflow**. Software engineering is just the workflow I happened to trip over first.

The previous post was about the heavier version of that idea: integrating Squad into a software system, where the workflow belongs to the system itself. That is the right shape when you need durable orchestration, typed boundaries, app-level state, and a real product surface. In other words: when Squad is becoming part of the software.

This post is about the smaller version. The more human version. The "I do not want to build a platform; I want Ralph to run one extra step before he starts the loop" version.

This matters because not every Squad workflow belongs to engineers. A Customer Success lead should be able to say, "before the agents work, check account health." A content lead should be able to say, "after the agents finish, draft the editorial summary." A marketing lead should be able to say, "do not run this campaign workflow outside the launch window."

They should not need to turn their operating rhythm into a software product just to get that control.

So this time I wanted to brag a little about something smaller and, I think, more important: we added an extensibility seam to `squad watch --execute`.

Not a huge framework. Not a new orchestration language. Not a cathedral of abstractions with a gift shop.

Just this:

```text
.squad/capabilities/*.js
```

Repo-local watch extensions.

Tiny hooks. Real phases. Your workflow.

And because I did not want to prove it with yet another CI example, I built the sample around a **Customer Success Squad**.

Which is how Ralph went from "watch my GitHub queue" to "please tell me which customer is about to churn before I accidentally send them a cheerful newsletter."

Progress.

---

## The Honest Problem

`squad watch --execute` has a simple loop:

1. scan for work;
2. triage it;
3. execute selected work;
4. do housekeeping.

That loop should stay boring. Boring loops are reliable loops.

But every real team wants one more local step:

| Team | "One more step" |
|---|---|
| Customer Success | Check account health before touching the queue. |
| Marketing | Gate work on campaign calendar dates. |
| Content Editing | Run style-guide checks before assigning drafts. |
| Support | Escalate VIP tickets before normal triage. |
| Engineering | Check CI, project boards, rate limits, deployment windows. |

If every local step becomes a core Squad feature, Ralph becomes a junk drawer.

And I say this as someone who has built many junk drawers. Some had Helm charts.

The right design is not "merge every workflow idea into Squad." The right design is:

> Keep the watch loop stable, and let repo owners attach small capabilities to stable phases.

That is what external watch capabilities do.

---

## The Feature

Squad can load external watch capabilities from:

```text
.squad/capabilities/*.js
```

Each capability exports a small object:

```js
export default {
  name: 'my-capability',
  description: 'What this does',
  configShape: 'boolean', // or 'object'
  requires: [],
  phase: 'post-execute',
  async preflight(context) {
    return { ok: true };
  },
  async execute(context) {
    return { success: true, summary: 'done' };
  },
};
```

The supported phases are intentionally few:

| Phase | What it is for |
|---|---|
| `pre-scan` | Gates and context before scanning work. |
| `post-triage` | Normalization or enrichment after candidate work is selected. |
| `post-execute` | Follow-up artifacts after agents finish work. |
| `housekeeping` | Cleanup, summaries, reminders, hygiene. |

Config lives under `watch` in `.squad/config.json`.

Capabilities can use either:

| Config shape | Meaning |
|---|---|
| `boolean` | Enable or disable the capability. |
| `object` | Enable it and pass structured settings. |

The important bit is `preflight()`. It gives every optional integration a way to say:

> "I cannot run because the CRM webhook is missing."

That is much better than:

> "I failed in a stack trace that starts in a customer follow-up workflow and ends with everyone blaming Node.js."

---

## Can You Try This Now?

Yes, if you install the insider build.

At the time I tested this, the published npm insider dist-tag was:

```text
@bradygaster/squad-cli@insider -> 0.9.6-insider.2
```

That is also the version I had installed locally:

```text
squad version
0.9.6-insider.2
```

So this was not validated against a private local build hiding under my desk like a raccoon with admin rights.

To try it:

```powershell
npm install --save-dev @bradygaster/squad-cli@insider
npx squad watch --execute
```

Or, if you install it globally:

```powershell
npm install -g @bradygaster/squad-cli@insider
squad watch --execute
```

The stable npm `latest` tag was still behind when I checked, so for now this is an **insider-channel feature**. That is exactly where I want it while we are still learning the sharp edges.

---

## The Sample Repo

I created a separate sample repo:

```text
https://github.com/tamirdresher/squad-watch-extension-sample
```

The repo is a dependency-free, runnable demo of the watch extension seam. It includes:

| Path | Purpose |
|---|---|
| `.squad/team.md` | Defines the Customer Success Squad. |
| `.squad/config.json` | Enables capabilities with boolean and object config. |
| `.squad/capabilities/*.js` | External watch capabilities. |
| `data/customer-success-board.json` | Fake account health, tickets, completed work, and renewal risk. |
| `scripts/capability-contract.mjs` | Local harness that mirrors current Squad loader behavior. |
| `scripts/validate-capabilities.mjs` | Contract tests. |
| `scripts/run-sample-round.mjs` | Runs one watch-like demo round. |

The sample does not require a local unpublished Squad build. That is deliberate. The repo should teach the contract without making the reader first assemble a particle accelerator.

---

## The Customer Success Squad

The sample team has five agents:

| Agent | Role | What they do |
|---|---|---|
| Avery | Account Health Lead | Checks customer health before the watch round starts. |
| Priya | Support Triage Lead | Routes high-value tickets to the right owner. |
| Marco | Renewal Risk Lead | Watches renewal dates, risk scores, and escalation needs. |
| Nina | Customer Comms Lead | Drafts concise follow-ups after execution. |
| Dana | CRM Hygiene Lead | Keeps housekeeping outputs ready for downstream systems. |

This is not software engineering work.

There are no PRs. No builds. No flaky tests. No YAML. Nobody says "just one more Kubernetes annotation."

The workflow is account operations:

1. Which accounts are red?
2. Which customer tickets need attention first?
3. What follow-up should the customer receive?
4. Which renewals are risky?
5. Should we sync housekeeping notes to CRM?

That is exactly the kind of repeatable workflow where a lightweight watch extension makes sense.

---

## The Capabilities

The sample implements five external capabilities plus one intentional bad citizen.

| Capability | Phase | Config shape | Why it exists |
|---|---|---|---|
| `account-health-gate` | `pre-scan` | `boolean` | Checks whether the round is walking into red accounts. |
| `ticket-intake-router` | `post-triage` | `object` | Routes tickets by customer tier, severity, and region. |
| `customer-follow-up-drafts` | `post-execute` | `boolean` | Writes customer-facing follow-up drafts. |
| `renewal-risk-digest` | `housekeeping` | `object` | Summarizes accounts over a risk threshold. |
| `optional-crm-sync` | `housekeeping` | `object` | Demonstrates skipped preflight when CRM is not configured. |
| `00-built-in-conflict-demo.js` | skipped | `boolean` | Tries to register as `execute`; loader rejects it. |

That last one matters.

If an external extension can accidentally replace a built-in watch capability, then we did not build extensibility. We built a footgun with plugin branding.

The loader skips built-in name conflicts.

Good.

---

## What the Extension Code Actually Looks Like

The shape is intentionally boring. A capability is just a default export with metadata, a `preflight()`, and an `execute()`.

The account health gate is a good example:

```js
export default {
  name: 'account-health-gate',
  description: 'Checks account health before the watch round spends agent time.',
  configShape: 'boolean',
  requires: ['data/customer-success-board.json'],
  phase: 'pre-scan',

  async preflight(context) {
    try {
      await readFile(join(context.teamRoot, 'data', 'customer-success-board.json'), 'utf8');
      return { ok: true };
    } catch {
      return { ok: false, reason: 'data/customer-success-board.json is missing' };
    }
  },

  async execute(context) {
    const raw = await readFile(join(context.teamRoot, 'data', 'customer-success-board.json'), 'utf8');
    const board = JSON.parse(raw);
    const criticalAccounts = board.accounts.filter(account => account.health === 'red');
    const highestRisk = Math.max(...board.accounts.map(account => Number(account.riskScore ?? 0)));

    return {
      success: true,
      summary: `Account health gate found ${criticalAccounts.length} red account(s); highest risk score is ${highestRisk}`,
      data: { criticalAccounts, highestRisk },
    };
  },
};
```

That is the whole contract in miniature:

- `phase` decides where it plugs into the watch loop;
- `configShape` decides how config is read from `.squad/config.json`;
- `preflight()` says whether the extension is allowed to run;
- `execute()` does the work and returns a summary plus structured data.

The `preflight()` piece is not decoration. It is the difference between graceful automation and haunted automation.

For file-backed capabilities, preflight checks the sample data exists:

```js
async preflight(context) {
  try {
    await readFile(join(context.teamRoot, 'data', 'customer-success-board.json'), 'utf8');
    return { ok: true };
  } catch {
    return { ok: false, reason: 'data/customer-success-board.json is missing' };
  }
}
```

For optional integrations, preflight checks the environment instead:

```js
async preflight(context) {
  const envName = String(context.config.webhookEnv ?? 'CUSTOMER_SUCCESS_CRM_WEBHOOK');
  if (!process.env[envName]) {
    return { ok: false, reason: `${envName} is not set` };
  }

  return { ok: true };
}
```

So when the CRM webhook is missing, the result is not a fake success and not a crash. It is an explicit skip:

```text
optional-crm-sync: skipped (CUSTOMER_SUCCESS_CRM_WEBHOOK is not set)
```

That matters because real teams have half-configured integrations all the time. If your automation cannot survive "the webhook is not configured on this machine," it is not automation. It is a meeting generator.

The object-config capability is also intentionally simple. The ticket router reads local settings:

```js
const maxItems = Number(context.config.maxItems ?? 3);
const allowedRegions = new Set(context.config.allowedRegions ?? []);
const tierOrder = context.config.tierOrder ?? ['strategic', 'enterprise', 'growth'];
const severityOrder = context.config.severityOrder ?? ['critical', 'high', 'medium'];
```

Then it turns customer tickets into a routed queue:

```js
const selected = board.tickets
  .filter(ticket => ticket.status === 'new')
  .filter(ticket => allowedRegions.size === 0 || allowedRegions.has(ticket.region))
  .sort((a, b) => {
    const tierDiff = (tierRank.get(a.tier) ?? 99) - (tierRank.get(b.tier) ?? 99);
    if (tierDiff !== 0) return tierDiff;
    return (severityRank.get(a.severity) ?? 99) - (severityRank.get(b.severity) ?? 99);
  })
  .slice(0, maxItems);
```

Finally it writes the artifact the next human or tool can inspect:

```js
await writeFile(
  join(context.teamRoot, '.squad', 'state', 'routed-customer-intake.json'),
  JSON.stringify({ round: context.round, selected }, null, 2),
  'utf8',
);
```

Nothing here requires Squad core to understand "strategic customer," "renewal risk," or "CRM hygiene." That language belongs to the repo.

That is exactly the abstraction boundary I wanted.

---

## The Config

Here is the interesting part of `.squad/config.json`:

```json
{
  "watch": {
    "interval": 10,
    "execute": true,
    "account-health-gate": true,
    "ticket-intake-router": {
      "maxItems": 3,
      "tierOrder": ["strategic", "enterprise", "growth"],
      "severityOrder": ["critical", "high", "medium"],
      "allowedRegions": ["EMEA", "NA"]
    },
    "customer-follow-up-drafts": true,
    "renewal-risk-digest": {
      "riskThreshold": 70,
      "includeExpansionSignals": true
    },
    "optional-crm-sync": {
      "webhookEnv": "CUSTOMER_SUCCESS_CRM_WEBHOOK"
    }
  }
}
```

This is the part I like.

It is not trying to be a full application platform. It is just enough configuration to let a repo owner say:

- run this;
- pass these settings;
- skip this if the environment is not ready.

Who am I kidding: many times I prefer this over the full "proper software engineering" approach.

Yes, a full agent framework gives you typed workflows, durable state, rich orchestration, test seams, deployment topology, observability, governance, and all the things a serious system eventually needs.

But sometimes the right answer is a script-shaped hook in the place where the work already happens.

Not every problem deserves a platform team.

Some problems deserve a 70-line file with a good `preflight()`.

---

## What a Critical Engineer Should Ask

This is the section where we stop clapping for ourselves and behave like engineers.

### Is JavaScript capability loading powerful?

Yes.

### Is that also risky?

Also yes.

External capabilities are code. They run with process permissions. If you load a random capability from the internet, you did not install an extension. You installed a stranger with a keyboard.

So the right model is:

- repo-local capabilities;
- code review;
- built-in name conflict protection;
- explicit config;
- clear preflight behavior;
- no magical package installation.

This is not a marketplace. It is a local extension seam.

That is a feature, not a limitation.

### Should every workflow become a watch extension?

No.

If the workflow needs durable orchestration, retries, human approval, cross-service transactions, audit history, and a real deployment lifecycle, use a proper system. Use the agent framework. Build the grown-up version.

But if the workflow is "before scanning, check account health" or "after execution, write a follow-up digest," a watch capability is exactly the right size.

The danger in engineering is not just under-building. It is also over-building so hard that nobody can use the thing without a platform onboarding session and three diagrams.

### Is this for non-engineers?

The workflow is for non-engineering teams.

The extension author still needs to write a small JavaScript file.

That is the honest line.

This is not "anyone can click a button and build a workflow." Not yet. A future declarative layer could make that possible. But this is already a big step because the extension point now lives in the user's repo and maps to their domain language.

Customer Success can talk about accounts, renewals, escalation, CRM, and follow-up drafts.

Squad core does not need to know what any of those words mean.

That is the whole point.

---

## Why This Matters

The previous engineering-heavy posts were about making Squad stronger as a software delivery system.

This feature makes Squad more adaptable as a workflow system.

That is a different kind of win.

It means a team can start with:

```text
squad watch --execute
```

Then add:

```text
.squad/capabilities/01-account-health-gate.js
.squad/capabilities/02-ticket-intake-router.js
.squad/capabilities/03-customer-follow-up-drafts.js
```

And suddenly the loop speaks their language.

Not because we hardcoded Customer Success into Squad.

Because we did not.

That is the part worth bragging about.

Extensibility is not when the core system knows everything.

Extensibility is when the core system knows where to get out of the way.

---

## The Small Thing I Like Most

My favorite part is not the customer follow-up draft.

It is not the renewal-risk digest.

It is not even the conflict demo, though I do enjoy a good intentional failure.

My favorite part is the optional CRM sync:

```text
optional-crm-sync: skipped (CUSTOMER_SUCCESS_CRM_WEBHOOK is not set)
```

That line is boring.

Beautifully boring.

It means the workflow can say what it needs, check whether the world is ready, and skip cleanly when it is not.

No drama. No fake success. No stack trace pretending to be an implementation detail.

That is what good automation feels like.

---

## Where This Goes Next

This low-level capability seam should stay low-level.

The next layer could be a more declarative pipeline model:

```yaml
watch:
  post-execute:
    - write-follow-up-drafts
    - sync-crm
```

Maybe that layer exists later. Maybe Specrew helps design it. Maybe we discover that the boring JavaScript seam handles 80% of the real cases and the fancy layer can wait.

That would be a very engineering outcome.

For now, I am happy with the toolbelt.

Ralph still watches.

Ralph still executes.

But now the repo can teach Ralph a few local rituals without making Ralph responsible for every ritual in the world.

That is how an agent system grows without becoming a haunted house.
