---
layout: post
title: "The Collective — Organizational Knowledge for AI Teams"
date: 2026-03-05
tags: [ai-agents, squad, github-copilot, scaling, star-trek, borg]
series: "Scaling AI-Native Software Engineering"
series_part: 2
---

> *"We are the Borg. We will add your technological distinctiveness to our own."*
> — The Borg, Star Trek: The Next Generation

In [Part 1](/2026/03/04/scaling-ai-part1-first-team.html), I set up my first Squad team — Riker, Troi, Data, Worf, and Geordi — on a single repo and watched them tear through a backlog in parallel. It was incredible. Then I did what any excited engineer does: I set up Squad on a second repo.

And the second team didn't know *anything* the first team had learned.

Data in `auth-service` had figured out our retry pattern, our error handling conventions, our logging format. Data in `token-manager` — same character, same role — stared at me blankly when I mentioned any of it. Each repo's Squad was an island. An isolated drone without a Collective.

That's when I realized: the hard problem of scaling AI teams isn't making them work in one repo. It's making them share knowledge the way a real engineering organization does.

## The Real Shape of Software Orgs

Here's something the "just use a monorepo" crowd glosses over: most real software organizations don't live in a monorepo. They look like this:

**Organization: Platform Engineering**
- Architecture standards, coding conventions, security policies
- "All services use managed identity," "TypeScript for all new services," "OpenAPI spec for every API"

**Team: Auth Team**
- Owns: `auth-service`, `identity-provider`, `token-manager`
- Domain expertise: "JWT v1 is deprecated, migrate to v2," "OAuth flows must use PKCE"

**Team: Payments Team**
- Owns: `payments-api`, `billing-service`, `invoice-generator`
- Domain expertise: "PCI compliance requires field-level encryption," "All monetary values stored as integers in cents"

**Team: Infrastructure Team**
- Owns: `deploy-tools`, `monitoring-config`, `infra-as-code`
- Domain expertise: "Terraform modules follow our naming convention," "All alerts route through PagerDuty"

Each level produces knowledge that should flow down. Architecture standards are universal. Domain expertise is team-wide. Implementation details are repo-specific. This isn't overhead — it's how engineering organizations actually function. And when you set up Squad on each of those repos, each team gets its own AI squad. But without shared context, those squads are drones without a Collective.

## The Problem Without Upstream

Here's what happened to me. I set up Squad on `auth-service` and told Data: "Always use managed identity for Azure resources. Never use connection strings with secrets."

Data nods. He remembers. Every time he touches Azure code in `auth-service`, he uses managed identity. Perfect.

Now I open `token-manager` — same team, different repo. I start a new Squad session. Data is there (I cast him again because he's great at infrastructure). I ask him to set up an Azure Key Vault connection.

He reaches for a connection string.

*"Data, we talked about this. Managed identity."*

*"I have no record of that decision."*

Because I didn't talk about this — not with *this* Data. This Data lives in a different repo. He has no memory of what I told the other Data. I'm repeating myself, and I'll keep repeating myself across every repo in every team.

Multiply this by an organization with thirty repos across five teams. You're not engineering anymore — you're a broken record, repeating "use managed identity" and "always add structured logging" and "error responses follow RFC 7807" to every new Squad you spin up. It's the AI equivalent of writing coding standards in a wiki that nobody reads.

## Upstream Inheritance

Squad's answer is **upstream inheritance** — a hierarchical knowledge system that mirrors how real organizations work. Each repo has its own `.squad/` directory, and you connect repos to shared knowledge sources using `squad upstream add`:

```bash
# In the auth-service repo:
squad init
squad upstream add https://github.com/acme/platform-squad.git --name org
squad upstream add https://github.com/acme/auth-team-squad.git --name team
```

This creates a hierarchy without any special global directory:

```
acme/platform-squad.git            ← Org level (a regular repo with .squad/)
  .squad/
    decisions.md                   ← "Always use managed identity"
                                     "TypeScript for all new services"
                                     "APIs follow OpenAPI spec"
    skills/                        ← Shared patterns: error handling,
                                     logging, API conventions
    routing.md                     ← Default routing rules

acme/auth-team-squad.git           ← Team level (another repo with .squad/)
  .squad/
    decisions.md                   ← "JWT v1 deprecated, migrate to v2"
                                     "OAuth flows must use PKCE"
    skills/                        ← Auth-specific patterns:
                                     token rotation, session management

auth-service/.squad/               ← Repo level
  decisions.md                     ← Repo-specific decisions
  agents/                          ← This repo's team (Riker, Data, etc.)
```

When Squad starts a session, it reads the repo's own `.squad/` context, then reads each upstream in order. An agent working in `auth-service` knows about the org-wide TypeScript policy AND the team-level JWT deprecation AND the repo-specific implementation decisions. All without you saying a word.

The resolution model is **closest-wins**: later upstream entries override earlier ones, and the repo's own context always takes priority. If the org says "use REST for all APIs" but the Payments Team's `billing-service` needs gRPC for performance, the repo-level decision overrides the org-level one — for that repo only. Org-wide defaults still apply everywhere else.

Decisions cascade down. Overrides are local. You get organizational consistency with team-level autonomy.

## Connecting a Repo to Its Upstream

Here's the thing the diagram above doesn't show: **upstream inheritance isn't automatic.** When you create a new repo and run `squad init`, Squad doesn't magically know where to look for org or team knowledge. You have to tell it — by adding upstreams after init.

Squad supports three types of upstream sources:

```bash
# 1. Git repository — cloned and cached locally
squad upstream add https://github.com/acme/platform-squad.git --name org

# 2. Local directory — read live at session start, no sync needed
squad upstream add ../org-practices/.squad --name org-local

# 3. Export file — a snapshot from squad export
squad upstream add ./exports/snapshot.json --name snapshot
```

You manage upstreams with a small set of commands:

```bash
squad upstream list              # See what's connected
squad upstream remove org        # Disconnect an upstream
squad upstream sync              # Update all git-based upstreams
squad upstream sync org          # Update a specific git upstream
```

Here's what `squad upstream list` looks like in practice:

```
Name      Source                                              Type
────      ──────                                              ────
org       https://github.com/acme/platform-squad.git          git
team      https://github.com/acme/auth-team-squad.git         git
local     ../shared-practices/.squad                          local
```

**What happens under the hood:**

1. **Git upstreams** get cloned to `.squad/_upstream_repos/{name}` (this directory is gitignored). Updated when you run `squad upstream sync`.
2. **Local upstreams** are read **live** at session start — no sync step needed. Change the source, and the next session picks it up.
3. **Export files** are static snapshots, useful for pinning a known-good version of shared knowledge.

**What happens on each session start:**

1. Squad reads the repo's own `.squad/` context — decisions, skills, wisdom, casting policy, routing.
2. Squad reads each upstream in order and merges inherited context using closest-wins resolution.
3. The repo's own context always takes priority over any upstream.

**What gets inherited:** Skills, Decisions, Wisdom, Casting Policy, and Routing rules all flow down from upstreams automatically at session start.

**The flow is one-directional: upstream flows DOWN.**

Agents in a repo can *read* upstream decisions and skills, but they never *write* back to upstream. From the repo's perspective, upstream knowledge is read-only. If Data discovers a great pattern in `auth-service` and you want the whole team to benefit, you don't push it up automatically — you export it and contribute it back manually:

```bash
# Export a skill from this repo
squad export --skill azure-keyvault-identity -o keyvault-skill.json

# Then add the exported skill to the team's upstream repo
# (commit it there so every downstream repo picks it up on next sync)
```

This is deliberate. Upstream knowledge is curated, not crowdsourced. You don't want every repo-level experiment polluting the team's shared knowledge. Promotion is a conscious decision — like a code review for organizational knowledge.

## What Gets Shared (And What Doesn't)

Not everything flows through the hierarchy. Squad is deliberate about what crosses boundaries and what stays local.

**What gets shared:**

- **Decisions** — Policies, conventions, architectural principles. "All APIs use OpenAPI spec." "Error responses follow RFC 7807." These are the laws of the org, the regulations of the team, and the local customs of the repo.
- **Skills** — Reusable patterns with confidence levels. A retry-with-exponential-backoff skill. A structured-logging-setup skill. An Azure-managed-identity-connection skill.
- **Wisdom** — Accumulated context and lessons learned. "Last time we changed the token format, three downstream services broke." "The billing API has a 500ms SLA."
- **Casting Policy** — Default team shapes and role assignments. "Security-related issues always route to Worf." "Database migrations go to Data."
- **Routing rules** — Work distribution patterns. "Frontend bugs go to Geordi." "API design tasks go to Riker."

**What does NOT get shared:**

- **Agent identities** — Each repo casts its own team. Riker in `auth-service` and Riker in `payments-api` are different instances. They share knowledge through the hierarchy, not through some telepathic link.
- **History** — An agent's conversation history is personal to that agent in that repo. What Data discussed with you about `auth-service`'s token rotation stays in `auth-service`.
- **Orchestration logs** — Task assignment, parallel execution state, session artifacts — all repo-specific.

Think of it like the Borg: individual drones have their own hardware and local task state. The Collective shares directives, tactics, and accumulated knowledge. No drone needs to know what another drone had for breakfast.

## Skills Flow Upstream

Here's where the Collective analogy gets real.

Data is working in `auth-service` and discovers a pattern: every time we connect to Azure Key Vault, we need to handle the `ManagedIdentityCredential` fallback chain in a specific way. He captures it as a **skill** — a reusable pattern with steps, context, and confidence metadata.

Initially, the skill is **low confidence**. One observation, one repo.

Two weeks later, Geordi is working in `token-manager` — a different repo, same team. He hits the same Azure Key Vault pattern. Squad suggests Data's skill. Geordi uses it. Confidence bumps to **medium**.

A month later, Troi in `identity-provider` uses it too. The team runs a skill review ceremony. The pattern is validated across three repos. Confidence hits **high**.

Now you promote it. Export the skill from `auth-service` and commit it to the team's upstream repo — `acme/auth-team-squad`. Every repo that lists that upstream picks it up on the next `squad upstream sync`. Any new repo the Auth Team creates just needs `squad upstream add https://github.com/acme/auth-team-squad.git --name team` and the pattern is there from day one.

```bash
# In auth-service: export the validated skill
squad export --skill azure-keyvault-identity -o keyvault-skill.json

# In the auth-team-squad repo: add it and push
# (every downstream repo inherits it on next sync)
```

Is the pattern useful beyond the Auth Team? Commit it to the org-level upstream repo — `acme/platform-squad`. Now the Payments Team's Squad knows it. Infrastructure Team's Squad knows it. The entire org benefits from one agent's discovery in one repo. Skills flow UP manually (export → commit to upstream repo) but flow DOWN automatically (read at session start).

The Collective learns. One drone's adaptation becomes everyone's advantage.

## Practical Example

Let's walk through a concrete scenario.

I'm leading the Platform Engineering org. I create an org-level upstream repo — `acme/platform-squad` — run `squad init` in it, and set org-wide decisions:

```markdown
## Org Decisions
- All APIs must publish an OpenAPI specification
- TypeScript for all new services
- Structured logging with correlation IDs on every request
```

Riker is working in `auth-service`. He builds a new `/tokens` endpoint. He automatically generates an OpenAPI spec, writes it in TypeScript, and adds correlation ID logging. He didn't need to be told — he inherited the org decisions.

Data is working in `payments-api`. He builds a `/invoices` endpoint. Same thing — OpenAPI spec, TypeScript, correlation IDs. Two different repos, two different teams, same standards. No copy-paste, no wiki nobody reads, no "we forgot to tell the new team."

Worf is working in `infra-tools`. He builds a Terraform validation CLI. The org decision says "TypeScript for all new services" — but this isn't a service, it's a CLI tool, and the team decides Go is a better fit. The repo-level decision overrides the org default. Worf builds it in Go. The org-wide logging and OpenAPI decisions? Those still apply where relevant.

Now the real payoff: Troi is setting up Squad on a brand new repo — `session-manager`, just created yesterday. She runs `squad init`, adds the upstreams, casts her team, and starts working:

```bash
squad init
squad upstream add https://github.com/acme/platform-squad.git --name org
squad upstream add https://github.com/acme/auth-team-squad.git --name team
```

On her very first task, her agents already know about the OpenAPI requirement, the TypeScript policy, the logging standard, the JWT v2 migration, and every high-confidence skill the Auth Team has accumulated over months — because Squad read every upstream at session start and loaded all of it.

Day one, and she's operating with the Collective's full knowledge. No onboarding lag, no "go read the wiki," no repeating yourself for the thirty-first time. Two `upstream add` commands, and the entire hierarchy is connected.

## Plugin Marketplace

The Borg don't just assimilate internally — they assimilate across species, across civilizations, across the galaxy. Squad's plugin marketplace is the same idea applied to community knowledge.

```bash
squad plugin marketplace browse
```

Pre-built knowledge packages, ready to install:

- **azure-best-practices**: Managed identity patterns, resource naming conventions, cost optimization skills
- **react-testing**: Component testing strategies, mock patterns, accessibility checks
- **api-design**: REST conventions, error response formats, pagination patterns, rate limiting
- **security-hardening**: Input validation, OWASP patterns, dependency scanning, secret detection

Installing a plugin adds its skills to your Squad's knowledge base at whatever level you choose — org-wide, team-level, or just one repo. Your agents immediately benefit from patterns that the community has validated across thousands of projects.

And it flows both ways. That Azure Key Vault managed identity skill that Data discovered and your org promoted? If it's generic enough, publish it as a plugin. Other Squad teams worldwide benefit. The Collective grows beyond your organization.

## What's Next

Upstream inheritance solves the organizational knowledge problem. Your AI teams share context the way real engineering orgs should — hierarchically, deliberately, with local autonomy and global consistency.

But there's another scaling challenge I haven't addressed:

*What happens when multiple teams need to work on the same repo simultaneously?*

My `squad-tetris` project has a frontend team, a backend team, and a cloud infrastructure team. They're all working in the same codebase. If I spin up three Squad sessions, will they step on each other's toes? Will they pick up each other's issues? Will merge conflicts bring everything crashing down?

In [Part 3: "Unimatrix Zero — Scaling Squad with Workstreams"](/2026/03/06/scaling-ai-part3-streams.html), I'll share the results of running three AI teams on one repo in three Codespaces simultaneously — what worked, what broke, and the Workstreams feature that makes it actually viable.

Spoiler: it broke spectacularly before it worked beautifully. 🟩⬛

![Borg collective](/assets/scaling-ai-part2-collective/borg-collective.png)
*"We will add your organizational distinctiveness to our own."*
