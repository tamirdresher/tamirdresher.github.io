---
layout: post
title: "How I Secure and Harden My AI Agent Squad"
date: 2026-03-24
tags: [ai-agents, squad, security, github-copilot, supply-chain, devsecops, hardening]
series: "Scaling AI-Native Software Engineering"
series_part: 8
---

> *"If you want AI agents to act like team members, you have to treat them like team members — including giving them the right access controls, onboarding them with least privilege, and holding them accountable."*
> — paraphrased from [Harvard Business Review, March 2026](https://hbr.org/2026/03/to-scale-ai-agents-successfully-think-of-them-like-team-members)

There's a paper in HBR right now about scaling AI agents. The core argument is deceptively simple: **treat your AI agents like team members**. Give them roles. Give them accountability. Define what they can and can't touch. Bring them into your processes the same way you'd onboard a new engineer.

I read it and immediately thought: *I've been doing this backwards.*

When a new developer joins my team, the first thing we do is provision the minimum access they need. Not "give them everything and figure out permissions later." We don't hand them the production database credentials on day one. We audit their access. We define what repositories they can write to. We don't let them approve their own pull requests.

When I launched Squad, I handed the agents everything.

Admin GitHub tokens. Keys to infrastructure. Unrestricted tool access. I was so focused on *can they do the work* that I forgot to ask *what should they be allowed to do*.

This is the story of how I fixed that.

---

## The Wake-Up Call

It started with a routine code scan.

A few weeks into running Squad at full capacity — 8+ agents, multiple machines, 10-15 PRs per day — Worf (our security guardian) flagged something: a Google API key was sitting in a file that had been committed to the repo. Not a production key, but a real key, one that could be abused.

GitHub immediately notified us via secret scanning. The key was revoked. I cleaned up the file. Closed in two PRs: [#1420](https://github.com/tamirdresher_microsoft/tamresearch1/pull/1420) and [#1437](https://github.com/tamirdresher_microsoft/tamresearch1/pull/1437).

But I wasn't satisfied with just fixing the symptom. The real question was: *how did a live API key end up in a committed file in the first place?*

The answer was uncomfortable: because I hadn't established clear guardrails around what agents should and shouldn't write to disk. The agent was trying to be helpful, documenting a configuration step. It didn't know that "helpful documentation" and "embedding credentials" are mutually exclusive.

That was the start of a more systematic approach to securing the squad.

---

## The Threat Model

Before you can defend against anything, you have to name what you're defending against. Here's what keeps me up at night with an AI agent squad:

**Credential exposure.** Agents have access to secrets to do their jobs. They might reference those secrets in output — logs, docs, comments, error messages. Unlike a human who intuitively knows a token is sensitive, an agent just sees a string. Without explicit guardrails, it might write that string somewhere it shouldn't.

**Supply chain attacks.** Our CI/CD runs on GitHub Actions. If an action we depend on is compromised — or if we're referencing a moving tag like `actions/checkout@v4` instead of a pinned SHA — a malicious update could execute arbitrary code in our pipelines. The agent squad uses CI extensively. A supply chain compromise would be catastrophic.

**Command injection.** Agents often construct shell commands programmatically. If they interpolate unsanitized input into a command string, an attacker who controls that input can execute arbitrary code. We hit exactly this bug in our Bitwarden client integration, fixed in [commit b9a828e](https://github.com/tamirdresher_microsoft/tamresearch1/commit/b9a828e).

**Capability creep.** Without explicit restrictions, agents tend to use whatever tools are available. An agent with a browser shouldn't necessarily be allowed to authenticate to new services. An agent with git access shouldn't be able to push to production branches. The capabilities exist; they just need to be constrained.

**Prompt injection.** A more exotic threat, but a real one: if an agent reads content from untrusted sources (GitHub comments, issue bodies, external APIs) and that content contains instructions crafted to manipulate the agent's behavior, you have a prompt injection. This is a real concern I've been researching deeply. My research squad produced a detailed adversarial security review ([issue #376](https://github.com/tamirdresher_microsoft/tamresearch1/issues/376)) that analyzed the landscape. The findings were sobering: studies show AI-generated code carries 1.57x more security vulnerabilities than human-written code. Standard SAST scanners catch surface-level issues but miss multi-step exploit chains and business logic flaws that are characteristic of AI-generated code. I haven't built dedicated prompt injection defenses yet, but the research is shaping my roadmap — more on that below.

---

## What I Do About It

### 1. Worf Is Always Watching

Every squad has a role definition that says what each agent owns. Worf owns security. His charter is blunt:

> *"Paranoid by design. Assumes every input is hostile until proven otherwise."*

Worf reviews security-sensitive PRs before they merge. He runs periodic CodeQL analysis. He was the one who caught and fixed 6 high-severity vulnerabilities in our Learn MCP server in a single pass. The fix went in as a batch: [PR #1199](https://github.com/tamirdresher_microsoft/tamresearch1/pull/1199).

Having a dedicated security role means security isn't an afterthought that gets bolted on at the end of a sprint. It's part of the team, showing up the same way an engineer shows up.

### 2. Supply Chain Hardening

The most impactful thing I did in a single PR: pinned all GitHub Actions to commit SHAs instead of mutable version tags.

Before:
```yaml
- uses: actions/checkout@v4
- uses: actions/setup-node@v4
```

After:
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
- uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af  # v4.1.0
```

When you reference a tag, GitHub resolves it at runtime. Someone compromises the upstream action, updates the tag — your pipeline runs their code. When you pin to a SHA, you're running exactly what you audited. It can't change without your PR.

I automated this with Dependabot. New SHA-pinned versions get automatically submitted as PRs for review. I don't have to chase it manually. [PR #1433](https://github.com/tamirdresher_microsoft/tamresearch1/pull/1433) pinned everything; Dependabot keeps it current.

### 3. Capability Restrictions via `machine-capabilities.json`

Every machine that runs Squad declares exactly what it can do in a capabilities manifest. This isn't just about routing work to the right hardware — it's a security boundary.

```json
{
  "hostname": "CPC-tamir-WCBED",
  "capabilities": {
    "browser": true,
    "gpu": false,
    "personalGH": true,
    "emuGH": false,
    "azureSpeech": false
  }
}
```

An agent running on a machine without `emuGH` can't authenticate to the EMU GitHub org. Not because we wrote permission checks everywhere — because the credential isn't there. Principle of least privilege, enforced at the machine level.

Ralph (our work-claiming daemon) uses this manifest to route issues to capable machines. An issue tagged `requires:browser` won't be claimed by a headless DevBox. The capability system is both a scheduling mechanism and a security boundary.

### 4. Secret Scanning as a Safety Net

I have GitHub's secret scanning enabled across all repos. It catches high-entropy strings that look like tokens or keys and alerts immediately. The Google API key incident was caught within hours of the commit, before any CI ran.

This is the fallback. The goal is never to commit secrets. But humans (and agents) make mistakes. Having an automated backstop that detects and alerts beats finding out six months later in a breach report.

### 5. CodeQL in the Pipeline

Our CI runs CodeQL analysis on every PR. It catches a class of bugs that code review often misses: command injection, SQL injection, path traversal, improper input handling. When the Bitwarden aac-client had a command injection vulnerability, CodeQL caught it in a PR. The fix was straightforward once the issue was named.

The key insight: code review scales to humans, but agents submit PRs faster than humans review. Automated static analysis scales with the number of PRs. You can't review 15 PRs per day manually with the same rigor as 2. But CodeQL doesn't slow down.

One caveat: CodeQL is free for public repositories on GitHub. For private repos, you need GitHub Advanced Security (GHAS), which is a paid feature. If you're running Squad on a public repo, you get this for free. Private repo users should evaluate whether GHAS is worth the investment — for an AI squad that generates 10-15 PRs per day, I'd argue it's essential.

---

## Practical Lessons Learned

**Name the threat before you build the defense.** Vague "we should be more careful about security" never gets implemented. "Agents can write API keys to documentation files" is a concrete threat you can address.

**Secrets don't belong in agent context.** Agents don't need to know a credential to use it. I refactored the credential handling so agents call a secret retrieval function and receive a token that's valid for one operation — they never see the underlying secret.

**Make the safe path the easy path.** Supply chain hardening felt like toil until I automated it with Dependabot. Now PRs that update pinned SHAs show up automatically. The secure thing is also the zero-effort thing.

**Treat the agent log as untrusted output.** An agent that logs "retrieved token: sk-proj-abc123..." is a credential exposure waiting to happen. I redact tokens from all logs before they're written, the same way you'd redact PII.

---

## What I'm Evaluating: AI-Specific Threat Defenses

The research-376 adversarial security review didn't just identify problems — it proposed a 3-tier security architecture for AI-generated code:

- **Tier 1 (Fast, <60s):** Semgrep + Gitleaks + Trivy for rapid PR feedback. These run on every push and catch the obvious stuff — leaked secrets, known CVEs in dependencies, common vulnerability patterns.
- **Tier 2 (Deep, <5min):** CodeQL + Snyk for semantic analysis. These understand data flow, can trace a user input through multiple function calls to a dangerous sink, and catch the more subtle bugs that pattern matching misses.
- **Tier 3 (Adversarial, <2min):** An LLM-powered agent that constructs attack chains from aggregated findings across Tier 1 and Tier 2. Instead of isolated "this line is vulnerable" warnings, it builds a narrative: "An attacker could manipulate this input, which flows through this function, bypasses this check, and reaches this sink — here's a concrete exploit."

I haven't built this yet. It's a proposal from my research squad. But the research highlights a real gap — no existing tool in the deterministic SAST arsenal constructs concrete attack narratives. They flag individual issues. They don't chain them into exploits. That's the kind of analysis you need when AI agents are generating code at scale, because the vulnerabilities they introduce tend to be subtle and interconnected rather than obvious single-point failures.

I'm evaluating how to embed these defenses into the Squad framework itself — Brady's [bradygaster/squad](https://github.com/bradygaster/squad) repo — so that every Squad installation gets security-by-default. You shouldn't have to discover each of these protections and wire them up yourself. They should ship as part of the framework.

There's another threat vector that keeps coming up in my research: **indirect prompt injection**. If an agent reads a malicious GitHub issue comment that contains instructions designed to manipulate behavior, that's an indirect prompt injection. My research squad identified this as a key risk area. Defenses include input sanitization, separating instruction from data channels, and having agents validate their own actions against their charter before executing. These are patterns I'm actively evaluating.

The goal is to make Squad secure by default — so when someone installs it, they get these protections without having to discover and implement each one themselves. Brady and I are evaluating which of these defenses should ship as part of the core framework.

---

## What's Coming

I'm working on per-agent scoping for AKS workload identity — each agent gets its own managed identity with only the Azure resources it needs. No shared credentials. No "one compromise exposes everything." The spike landed in [#1399](https://github.com/tamirdresher_microsoft/tamresearch1/pull/1402).

I'm also building a formal security review gate into the squad's PR process. Worf reviews security-relevant changes before merge. The criteria are explicit: anything touching credentials, CI configuration, network policies, or external API calls gets routed through him.

And embedding the adversarial security patterns from my research into the Squad framework — making security a built-in feature, not a bolt-on.

---

The HBR article is right. Treat agents like team members. But don't just give them the interesting parts of team membership — the autonomy, the output, the speed. Give them the boring parts too: the access reviews, the permission scoping, the security accountability.

That's what it actually means to run AI agents in production.

---

*Part of the [Scaling AI-Native Software Engineering](/tags/scaling-ai-native-software-engineering) series. Previous: [The Invisible Layer — Git Notes and Squad State](/2026/03/23/scaling-ai-part7b-git-notes.html).*
