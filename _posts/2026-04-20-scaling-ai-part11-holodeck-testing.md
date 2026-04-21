---
layout: post
title: "Safety Protocols Offline — Using AI Squads to Test the Things That Actually Break"
date: 2026-04-20
tags: [ai-agents, squad, github-copilot, testing, validation, e2e, star-trek, holodeck, adversarial-testing, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 11
image: /assets/scaling-ai-part11-holodeck-testing/holodeck-testing-hero.jpg
---

> *"Computer, in the Holmesian style, create an adversary capable of defeating Data."*
> — Geordi La Forge, "Elementary, Dear Data" (TNG S2E3)

> *"Program testing can be used to show the presence of bugs, but never to show their absence."*
> — Edsger W. Dijkstra, "Notes on Structured Programming" (1970)

[Part 7b](/blog/2026/03/23/scaling-ai-part7b-git-notes) tackled the state problem — orphan branches, git notes, the whole elegant mess of storing squad memory without polluting your commit history. The system was working. The state persisted. Everything was fine.

And then I had to change a coordinator template.

---

## More Manual Sessions Than I'd Like to Admit

Here's the thing nobody tells you about building AI agent systems: once they work, you still have to *maintain* them. Templates drift. Routing rules need tuning. The coordinator prompt that worked perfectly last week suddenly produces an agent that writes to the wrong branch, or skips a step, or — my personal favorite — confidently tells you it completed the task while the git log shows absolutely nothing new. (The agent is not lying. It just has a... generous interpretation of "done.")

So you change a template. And then you run a session to see if it worked. And you read through the output, check the files, verify the git state. Maybe it worked. Maybe it didn't. Either way, you do it again.

During the state-backend development from Part 7b, I ran **way too many of these sessions**. By hand. Manually. Copy the output, scan for anomalies, check whether Picard delegated correctly, check whether Scribe committed to the right branch, check whether the right files landed in the right places.

Too many sessions. Every. Single. Template. Change.

The technical term for this is a **problem that needs solving**. The more emotionally accurate term is **a thing that made me want to flip my desk**.

The solution ended up being [PR #1022](https://github.com/bradygaster/squad/pull/1022) — a template testing skill that runs real sessions, against a real locally-built CLI, with real agents doing real work. Not mocked. Not stubbed. Actually real.

And somewhere in the middle of building it, I realized I'd accidentally built a Holodeck. (Well, much less fancy — but a boy can dream, no?)

---

## The Holodeck Wasn't Entertainment. It Was a Test Lab.

The Enterprise didn't test its combat readiness by waiting to get shot at. The crew ran Holodeck scenarios — Klingon cruisers, hull breach alarms at 0200, photon torpedoes coming back the other way. The ship's computer didn't just check that the phaser array was *configured* correctly. It *fired the phasers at a simulated enemy fleet* and watched what happened.

This is the right model. Not "does the config look correct" — "does the system *behave* correctly when an LLM interprets it in a real session."

Unit tests are great. Integration tests are better. But both share a fundamental assumption that breaks down for AI agent systems: **the thing you're testing has deterministic behavior**. Pass in X, expect Y, assert Y. Fail or pass. Clean.

What happens when the thing you're testing is a *prompt*? A set of instructions that gets interpreted by a language model at runtime? There's no function to call. There's no return value to assert. There's only: did the agent do what I expected?

You can't unit test that. You have to *run it*.

The disposable test repo is the Holodeck grid. `squad init` populates it with holographic props. The session is the simulation running. And the git state verification at the end is the mission debrief — checking whether the crew succeeded or quietly flew into a star.

The concept of "LLM as a judge" has been floating around the AI community for a while now — the idea that you use a language model to evaluate the quality of another model's output. But in most of the literature, it's scoped pretty narrowly: evaluate *this specific prompt*, score *this specific response*. Single prompt in, evaluation out. Useful, but limited.

What we're doing here is different. We're not asking the LLM to grade a response to a single question. We're asking it to evaluate the *outcome of an entire multi-agent session* — did the coordinator delegate correctly? did the right files get committed? did the agents play their roles? That's not evaluating a prompt-response pair. That's evaluating a whole system behaving over time. The LLM-as-judge pattern scales up, and this is what it looks like at squad scale.

---

## How the Test Crew Actually Works

In PR #1022, it looks like this:

```bash
# 1. Build and link your local CLI branch
npm run build && cd packages/squad-cli && npm link && cd ../..

# 2. Create a disposable test repo (clean slate — like the holodeck grid before the scenario loads)
mkdir /tmp/sq-test-session && cd /tmp/sq-test-session
git init
echo "# Test Project" > README.md
git add -A && git commit -m "init: test scenario"

# 3. Initialize a squad with your modified templates
squad init

# 4. Run a session — this is the Holodeck lighting up
copilot --agent squad -p "Picard, decide what testing framework to use. Write your decision." \
  2>&1 | tee evidence/session-task.log

# 5. Verify the git state — did the agent actually do what it claimed?
cat .squad/agents/scribe/history.md
git log --all --oneline
```

Simple enough. But here's what's actually happening:

![Testing Pipeline Flow — from template change through disposable repo, squad session, git state verification, to pass/fail verdict](/assets/scaling-ai-part11-holodeck-testing/testing-pipeline-flow.svg)

A real agent is receiving the prompt, interpreting the coordinator template you just modified, making decisions, writing to files, committing to branches. You're not asserting that the template *parses correctly*. You're asserting that it *behaves correctly when an LLM reads it in a live session*.

That distinction is the whole game. Templates aren't code. The LLM is the interpreter. And the only way to test an interpreter is to run something through it.

One rule I've learned the hard way: **always check the git state, not just the session output**. Agents will tell you they did something. The commit history is the only thing that proves they actually did it. Trust but verify. Preferably just verify.

---

## What If Your Test Crew Simulated Your *Users*?

PR #1022 is specifically about testing Squad templates. But the pattern generalizes to something much more interesting, and this is the part that kept me thinking long after I merged the PR.

**What if your test crew didn't just simulate Squad sessions — what if they simulated your *users*?**

You have a web API. You could write unit tests for individual endpoints. You could write integration tests with canned inputs. Or you could configure an agent to behave like a specific type of customer — and let them loose on your staging environment.

Not a load test. Not a fuzzer. An *intelligent* agent that knows how your target user thinks, what mistakes they make, what edge cases they accidentally trigger. An agent that doesn't just call `/api/create-order` with a well-formed request. It does what a confused first-time user does: calls the wrong endpoint, forgets the auth header, retries with a duplicate transaction ID, and then wonders why there are two orders.

This is the war games model. You define the persona. The squad plays the role.

Here's what a customer persona test agent looks like in `.squad/agents/tester-customer/charter.md`:

```markdown
# CustomerTester — Adversarial Validation Agent

## Role
Simulate a first-time customer using the e-commerce checkout API.
Your goal is to complete a purchase — but make the mistakes a real first-time user makes.

## Persona
- You've never used this API before
- You read the docs once, quickly
- You skip optional fields you don't understand
- You get impatient and retry requests when they're slow
- You use realistic (but fake) data: real-looking emails, plausible addresses

## What you're probing for
- Does the API return clear error messages when required fields are missing?
- Does it handle duplicate transaction IDs gracefully?
- Does it reject invalid card numbers with a useful error, or a cryptic 500?
- Does the session expire in a way the user can recover from?

## Success criteria
- You either complete a purchase, or you hit an error and the error message tells you exactly what to do next
- Every interaction is logged with the full request, response, and your reasoning
```

Run that agent against your staging environment and it will probe every gap between "what the API does" and "what a real user *expects* it to do." Not because you scripted every test case. Because the agent has a persona, a goal, and the capacity to try things you wouldn't think to enumerate.

---

## Three Flavors of the Same Holodeck

After building this out, I've landed on three patterns. Each one is the same core idea wearing a different uniform.

**Pattern 1: The Template Validator** (the original, what PR #1022 does). Use real squad sessions to validate prompt-level behavior. Good for: anything where the behavior is LLM-interpreted and unit tests don't exist. Coordinator templates, agent charter changes, routing rule modifications. The key is always checking git state, not session output. Agents will claim victory. The commit log keeps score.

**Pattern 2: The Adversarial Customer**. Configure a squad to simulate a hostile or confused user. The persona drives everything — a "frustrated enterprise customer" behaves differently from a "developer who skimmed the docs" who behaves differently from a "malicious user probing for injection points." This is the security audit nobody schedules. It runs every time you push to staging.

```markdown
# SecurityProbe — Adversarial Security Tester

## Role
You are a security researcher probing the API for common vulnerabilities.
Be systematic. Try OWASP Top 10 patterns. Document every finding.

## Testing approach
1. Input validation: SQL injection, XSS, path traversal in every string field
2. Auth bypass: unauthenticated calls, expired tokens, tokens for other users
3. Rate limiting: 50 requests in 5 seconds — see what happens
4. Business logic: can you order -1 items? Order on behalf of another user?

## Report format
For each finding: endpoint, payload, expected behavior, actual behavior, severity.
```

**Pattern 3: The External System Impersonator**. Your system integrates with payment providers, shipping carriers, notification services. Those services have test modes — but test modes are *perfect*. They never time out. They never return unexpected errors. They never send malformed responses. They're nothing like the real thing.

Now, you might ask: "why not just use WireMock with some scenario logic?" And sure, you absolutely can. But here's the difference — a WireMock stub is static. You define the failure modes upfront, and that's what you get. An agent impersonator *reasons* about what would go wrong. It reads your integration code and invents failure scenarios you didn't think of, because it understands the *semantics* of what your service does, not just the HTTP contract. Plus — and this is where it gets interesting — external systems themselves are increasingly agentic under the hood. Your payment provider might be running its own AI orchestration. Testing against a deterministic stub when your counterparty is non-deterministic is... optimistic.

A squad can simulate an external system that misbehaves in realistic ways.

```markdown
# PaymentGatewaySimulator — External System Emulator

## Behavior model
- 95% of the time: return a successful authorization (realistic format)
- 3% of the time: return a timeout after 8 seconds
- 1% of the time: return a 500 with a cryptic internal error code
- 1% of the time: return a success response... with a different transaction ID than the one you sent

## Why that last one matters
Real payment gateways occasionally do this under load.
If your system doesn't handle it, you get ghost transactions.
Find out now. Not in production.
```

You're not testing "does our code call the right endpoint." You're testing "does our code survive when the endpoint *lies to it*."

---

## Wiring It Into the PR Loop

The thing that makes this real — as opposed to a clever idea I sketch on a Sunday and never revisit — is integrating the test crew into the same PR loop Ralph already runs.

![PR Loop Integration — PR opens, Ralph detects, spawns test crew, runs sessions, verdict gates the PR](/assets/scaling-ai-part11-holodeck-testing/pr-loop-integration.svg)

Ralph's watch loop picks up a PR opened against staging. It spawns a test crew agent with the persona configured for that area of the system. The test crew runs its sessions, captures evidence, writes a verdict to `.squad/test-results/`. The verdict gets posted as a PR comment. If the verdict is FAIL, the PR is blocked.

The test crew becomes a required reviewer. Not a human reviewer. A *crew member who actually used the thing*.

```powershell
# In ralph-watch.ps1, after detecting a new staging PR:
$testCrewPrompt = @"
You are the CustomerTester agent. A new version of the checkout API was just deployed to staging.
Your job: complete a realistic purchase as a first-time user.
Document everything in .squad/test-results/pr-$($pr.number)-customer.md.
At the end, write a verdict: PASS, PARTIAL, or FAIL, with evidence.
"@

copilot --agent squad -p $testCrewPrompt
```

Is this elegant? Not especially. But it works — and the test crew isn't a special system. It's just another squad member with "confused first-time user" as its area of expertise. Same repo, same tools, same Copilot CLI. The only thing that changed is the persona in the charter.

---

## What This Is (And Isn't)

I've oversold AI testing before, so I want to be straight about what this is and isn't.

Agent testers are **not** a replacement for unit tests. They're bad at systematic coverage — they won't reliably find "the exact code path where a null check fails at the third level of nesting." That's what unit tests are for. They're also slow: a unit test takes milliseconds, an agent session takes minutes. You're not running these on every commit. You run them on PR merge to staging, or nightly on main.

They can also produce **false confidence**, which is honestly the worst possible outcome. An agent that says "I completed the purchase successfully" has given you evidence — but only if you independently verify the actual database state, the receipt email, the transaction log. Always check independent system state. Always. Agent session output is a claim, not a proof.

What they're genuinely good at is the thing unit tests are terrible at: behavior that emerges from intelligence rather than determinism. If you can write a complete spec, write a unit test. If you can only describe a persona — "a confused first-time user who ignores error messages and retries everything" — write an agent. The adversarial scenarios you wouldn't think to enumerate. The failure modes that only appear when something with actual judgment tries to break your system.

The Holodeck wasn't perfect either. It malfunctioned. The safety protocols failed. The simulated Moriarty gained sentience, went on a crime spree, and held the ship hostage. But the crew kept running scenarios, because the alternative — going into every situation without preparation — was worse.

---

## Getting Started Without Building a Starship

The temptation here is to either immediately design a full adversarial fleet with twelve personas and a reporting dashboard, or to decide it sounds too complicated and do nothing. Both are the wrong move.

Start with one persona — and if you already have a squad (which, if you've been following this series, you do), don't think of it as creating a new directory and copying templates by hand. Think of it as *hiring* a new team member. You give them a charter, a role, and a clear definition of what "pass" looks like — not "the agent seemed to do the right thing" but "this specific file exists at this path" or "the API returned 200 with this structure." Add them to your squad the same way you'd add Data or B'Elanna. Run them manually until you trust them. Then hook Ralph into it.

(In a future post, I'll show how to do this *dynamically* — where tester and evaluator agents aren't statically configured at all, but spawned on the fly for a specific task and dissolved when it's done. That's the version that scales. But you don't need it yet.)

Check independent state every time. This is the one rule. Whatever the agent tells you it did — verify it in the system. Read the file. Check the database. Look at the commit. Agent output is evidence. Independent state is truth.

The Holodeck started as simple environmental simulations before it graduated to self-aware Victorian literary villains. Your test crew will evolve the same way. Give it some runway.

---

## The Holodeck Isn't Just for Practice

The crew of the Enterprise ran Holodeck scenarios for preparation. Picard could fight the Borg fifty times before facing them in battle. When the real thing came, he wasn't encountering it for the first time — he'd already made most of the mistakes somewhere that didn't count.

Your staging environment is your Holodeck. Your agents are the simulated crew running scenarios. And every time a realistic customer agent finds a gap in your checkout flow — before a real customer does — that's the system doing exactly what it was built for.

Every bug your adversarial security probe finds is a vulnerability that died in the simulation instead of in production. Every confused-user path that reveals a cryptic 500 is an angry support ticket that never gets filed.

The question isn't whether to run the simulation. It's whether you want to discover the failure modes in the Holodeck, or at 2 AM when someone's paging you.

I know which one I pick. 🟩⬛

---

## Beyond Testing: Squads That Play the Villain

Here's something I didn't say in PR #1022, because I wasn't ready to say it yet: the test crew pattern isn't just for testing Squad templates. It's a general-purpose mechanism for spawning AI agents with adversarial intent — and once you see it that way, a whole category of scenarios opens up.

Specifically: **Squad HQ can spawn entire ephemeral squads.**

![Ephemeral Red Team — Picard HQ spawns security probe, race condition hunter, and logic abuser with 30 min limit, results gate the PR](/assets/scaling-ai-part11-holodeck-testing/ephemeral-red-team.svg)

*After mission: agents dissolve* ☠️

Not persistent agent teams. Temporary crews with a specific mission, a time limit, and instructions to find everything wrong with your system before it ships. They do the job. They dissolve. They leave evidence.

Think about the war games scenario. In TNG's "Peak Performance," Starfleet runs a tactical exercise: Riker commands the USS Hathaway against the Enterprise to test combat readiness. Someone has to be the opponent. Someone has to fly the ship that's *trying to win* the simulated battle. The whole point is that your crew has to defend against intelligent adversarial tactics — not a script, not a fuzzer, something with an actual goal. The Enterprise crew would have been useless in real combat if every Holodeck scenario had been politely friendly.

Your staging environment deserves the same treatment.

When Picard HQ spawns a red team, it's not adding permanent agents to the roster. It creates a short-lived squad with a mission brief, runs them against the target surface, and terminates them when the job is done:

```markdown
# RedTeam-Coordinator — Ephemeral Squad Mission

## Mission
Adversarial validation of the new auth service on staging.
Time limit: 30 minutes. Find what breaks. Leave no false positives.

## Team
- SecurityProbe: OWASP Top 10, input validation, auth bypass
- RaceConditionHunter: concurrent requests, duplicate submissions, timing attacks
- LogicAbuser: negative quantities, coupon stacking, price manipulation

## Report
Write findings to .squad/red-team-results/pr-{PR_NUMBER}.md
Severity: CRITICAL / HIGH / MEDIUM / LOW
```

When the window closes, the results are committed. The ephemeral squad is gone. Picard HQ reads the verdict and gates the PR if anything comes back CRITICAL.

The same pattern covers scenarios you probably haven't thought about testing yet.

**Customer persona swarms.** Not one confused user — a *crew* of them. The first-time buyer who skips the docs. The enterprise customer whose OAuth flow just changed and who hasn't updated their SDK yet. The developer who reads the error message, ignores it, and retries the same broken request three more times because surely it'll work eventually. Each persona is a separate agent running in parallel, covering surface area no single tester would think to enumerate. When they're done, they're gone.

**Chaos opponents.** You want to stress-test your incident response? Spawn a chaos squad that randomly kills services on a schedule, then observe how your on-call automation — which is also squad-powered, obviously — handles it. The chaos agents are temporary. They do their job and they dissolve. Your incident response muscle either held, or you found out before 2 AM.

**War game opponents.** Your security team runs tabletop exercises. Your infrastructure team does game days. With ephemeral squads, you can give those exercises intelligent opponents instead of scripted scenarios. Agents with a goal, a model of how the target system works, and permission to find every gap before a real adversary does.

This is the thing I keep coming back to: in every war game, someone has to be the Romulans. Moriarty didn't volunteer for the holodeck. The Borg didn't ask politely. Somebody had to be the adversary, or there was no test.

Spawn the agents that exist to find your failures. Give them a mission and a time limit. Let them dissolve when they're done.

The question isn't whether you want adversarial testing. The question is whether you'd rather the adversaries run on your schedule, reporting to your pull request queue — or show up uninvited, in production, at a time that's inconvenient for everyone.

In the next post, I'll take this further — creating *other* squads that fan out work and tests dynamically. Not static agent rosters, but squads that spawn on demand, run their mission, and report back. Think of it as going from a single Holodeck to an entire deck full of them, each running a different scenario simultaneously. 🟩⬛

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [Resistance is Futile — Your First AI Engineering Team](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [The Collective — Organizational Knowledge for AI Teams](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — Many Teams, One Repo with SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)
> - **Part 4**: [When Eight Ralphs Fight Over One Login — Distributed Systems in AI Teams](/blog/2026/03/17/scaling-ai-part4-distributed)
> - **Part 5**: [Knowledge is Power — How an AI Squad Learns to Evolve Itself](/blog/2026/03/18/scaling-ai-part5-evolution)
> - **Part 6**: [9 AI Agents, One API Quota — The Rate Limiting Problem](/blog/2026/03/21/rate-limiting-multi-agent)
> - **Part 7**: [When Git Is Your Database — The Enterprise State Problem](/blog/2026/03/23/scaling-ai-part7-enterprise-state)
> - **Part 7b**: [The Invisible Layer — Git Notes, Orphan Branches, and the Squad State Solution](/blog/2026/03/23/scaling-ai-part7b-git-notes)
> - **Part 8**: [Pathfinder — When AI Squads Learn to Talk to Each Other](/blog/2026/03/26/scaling-ai-part8-pathfinder)
> - **Part 9**: [The Prime Directive, Part I — When Your AI Squad Becomes the Threat Model](/blog/2026/04/03/scaling-ai-part9-prime-directive)
> - **Part 9b**: [The Prime Directive, Part II — The Defense Stack](/blog/2026/04/03/scaling-ai-part9b-prime-directive)
> - **Part 10**: [Message in a Bottle — When Two AI Squads Fixed a Bug Over Teams](/blog/2026/04/05/scaling-ai-part10-message-in-a-bottle)
> - **Part 11**: Safety Protocols Offline — Using AI Squads to Test the Things That Actually Break ← You are here

---


