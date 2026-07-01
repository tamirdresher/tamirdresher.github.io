---
layout: post
title: "Same Model, Different Team — Benchmarking Squad's Coordination Layer"
date: 2026-07-01
tags: [ai-agents, squad, benchmarks, marble, swe-bench, terminalbench, evaluation, methodology, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 22
image: /assets/squad-benchmark/hero.png
---

<!-- TODO(assets): hero.png and marble-ablation.png under /assets/squad-benchmark/ do not exist yet — export the charts from the squad-marble-benchmark repo before publishing. -->

I have a reflex when someone shows me an agent benchmark: I go looking for the part they're *not* measuring. Most "our agent scored X%" posts are really "our *model* scored X%" wearing a trench coat. Swap the model underneath, the number moves, and you've learned nothing about the thing the team actually built.

So when [Brady Gaster](https://bradygaster.com/) and I sat down to evaluate Squad, we agreed on one rule before we ran a single task: **hold the model constant.** Whatever we measured had to be attributable to the coordination layer — the routing, the specialist charters, the shared memory — and not to a newer, smarter model quietly doing the heavy lifting.

This post is about what that discipline let us claim, and — just as important — what it did not.

---

## The Variable Everyone Forgets to Isolate

Squad isn't a model. It's a team that runs *on top of* the GitHub Copilot CLI harness. Every agent in that team — coordinator, coder, researcher, reviewer — is powered by the **same** underlying model.

```text
            ┌──────────────────────────────┐
            │   Squad coordination layer    │  ← the thing under test
            │  routing · charters · memory  │
            │  cross-agent review · history │
            └───────────────┬──────────────┘
                            │
            ┌───────────────▼──────────────┐
            │  GitHub Copilot CLI harness   │
            └───────────────┬──────────────┘
                            │
            ┌───────────────▼──────────────┐
            │   One model (held constant)   │
            └──────────────────────────────┘
```

So the honest question is not "is Squad's model any good?" It's: *given a fixed model, does organizing it into a coordinated team beat pointing a single agent at the same problem?*

What Squad actually adds on top of one agent is a specific list: task decomposition and routing, parallel agent execution, persistent memory across tasks, domain charters, cross-agent review (we call it the Reviewer Rejection Protocol), and a per-agent self-learning history. If you've read GitHub's own harness work, think of their "Rubber Duck" cross-model critique — then extend it from one critic to a whole team with roles and memory.

That's a testable claim. You just have to be ruthless about isolating the variable.

---

## The Hero: A Factorial Ablation

Across four benchmarks we ran **2,520 tasks**. But I want to start with the 160 that matter most, because they're the only place where every confound is pinned down at once: same model, same tasks, same metric, same timeout.

MARBLE ([ACL 2025](https://arxiv.org/abs/2506.09468)) is a multi-agent collaboration benchmark spanning four domains — coding, research, bargaining, and database. We took it and ran a proper factorial ablation:

```text
4 domains  ×  4 conditions  ×  10 tasks  =  160 runs
model: Claude Opus 4.6   |   metric: output file within 600s (binary)
```

Four conditions, each stripping something away:

- **Full Squad** — coordination *and* persistent memory
- **Coord-only** — the coordinator routes, but no shared memory
- **Memory-only** — shared memory, but no coordinator to direct it
- **No Squad** — a single agent, same model, same task

Here's the whole thing. Numbers are **resolution rate** (produced a valid output file inside the 600-second window):

| Domain      | Full Squad | Coord-only | Memory-only | No Squad |
|-------------|-----------:|-----------:|------------:|---------:|
| Coding      |       100% |       100% |         40% |      90% |
| Research    |       100% |        90% |         70% |      80% |
| Bargaining  |       100% |        90% |         60% |      70% |
| Database    |       100% |        90% |         25% |       0% |
| **Average** |   **100%** |  **92.5%** |  **48.75%** |  **60%** |

![MARBLE factorial ablation — resolution rate by domain and condition](/assets/squad-benchmark/marble-ablation.png)
*Full charts and every raw run live in the public repo; this table is the short version.*

---

## Coordination Is the Whole Game

Two numbers do most of the talking here.

**First:** routing *alone* — Coord-only, no shared memory — takes you from 60% to 92.5%. That's **+32.5 points from coordination by itself.** No memory, no magic. Just a coordinator deciding who does what, and specialists staying in their lane.

**Second — the one that made me trust the entire dataset:** memory without coordination is *worse than doing nothing.* Memory-only lands at 48.75%, below the 60% a bare single agent gets. That is deeply counterintuitive, and I want to be clear that we didn't sand it off. A result that makes your own product look bad in one cell is a result you didn't cook. The mechanism, once you sit with it, is obvious: memory without a coordinator to decide what's relevant is just noise shoved into the prompt. Context you can't govern isn't an asset. It's a distraction.

The database domain is where this gets dramatic. A single agent scores **0%** — it simply cannot hold the task together end to end. Add coordination and it jumps to 90–100%. That's not an incremental win; that's the difference between "impossible" and "routine."

And it's not only the average that moves — it's the *variance*. Standard deviation across the ten tasks in each cell (n=10):

```text
Full Squad   σ = 0%       ← dead-on repeatable
Coord-only   σ = 4.3%
Memory-only  σ = 17.5%
No Squad     σ = 35.4%    ← the database zeros living here
```

Coordination doesn't just raise the score. It makes the system *predictable*, which — if you're going to put agents anywhere near production — matters at least as much as the headline number.

---

## Cost: Up and to the Left

Resolution rate isn't free, so the second axis is dollars per task. The rule I keep in my head for the cost/resolution chart is simple: **up and to the left is better** — higher resolution, lower cost.

- **Coord-only** — 92.5% at **~$0.41/task** ← the efficiency frontier
- **Full Squad** — 100% at **~$0.97/task**
- **Memory-only** — ~48.75% at **~$1.50/task** (estimated) — paying the most to do the worst

If you want every last point of resolution, Full Squad buys it. But if you care about cost per *solved* task, Coord-only is the frontier: you keep almost all of the win for well under half the spend. Memory-only, meanwhile, sits in the corner nobody wants — expensive *and* ineffective — which is exactly what you'd predict once you accept that ungoverned memory is a tax, not a feature.

---

## The Other Three Benchmarks (Read These as Directional)

The MARBLE ablation is the controlled core. The rest of the 2,520 tasks are supporting evidence — some strong, some I'll caveat hard. In the charts I colored the controlled results **blue** for a reason; everything else is directional.

| Benchmark          | Tasks    | Model           | Squad   | Baseline            | Read as        |
|--------------------|---------:|-----------------|--------:|---------------------|----------------|
| MARBLE (main)      |      400 | Claude Opus 4.6 |  99.25% | 60% (same model)    | Same-model     |
| MARBLE (ablation)  |      160 | Claude Opus 4.6 |    100% | 60% (same model)    | **Controlled** |
| TerminalBench 2.0  |  20 / 89 | Claude Opus 4.6 |     80% | 75% (same model)    | **Controlled** (subset) |
| DevBench           |    1,800 | GPT-5.4         |   53.1% | 43.5% (GPT-5.5)     | Directional    |
| SWE-bench Lite     |      300 | GPT-4o          |     66% | ~48% (estimated)    | Directional    |

A word on each, because the caveats *are* the story:

**MARBLE main (400 tasks).** 99.25% — that's 397 of 400, with three timeouts I'm counting as misses rather than pretending they didn't happen — against 60% for the same model with no Squad. A +39-point, same-model gap on the full suite. This one I'll stand on.

**TerminalBench 2.0.** Same model, 80% vs 75%: +5 points. But read the fine print — it's a **20-of-89 subset**. Squad can't run the full suite yet because these tasks execute host-side and the Harbor container integration isn't wired up on our end. We took the first 20 by sequential order, *not* the 20 that flatter us. Small n, honest selection — encouraging, not conclusive.

**DevBench (1,800 tasks).** +9.6 points looks great until you see the baseline: 43.5% on **GPT-5.5** — a *newer* model than the GPT-5.4 we ran Squad on. So an older model wearing Squad edged out a single agent on a newer model. Suggestive, not clean. A same-model DevBench ablation is on the to-do list.

**SWE-bench Lite (300 tasks).** 66% vs an *estimated* ~48% baseline — estimated, meaning I can't hand you a matching same-model run to verify it, only the code to reproduce ours. It was #1 on the leaderboard *at the time of submission in June 2026*. Past tense, and I won't claim it still is.

---

## What I Can and Can't Claim

Here's the methodology, stated as plainly as I can.

**Controlled** means same model **and** same tasks **and** same metric. That holds strictly in exactly two places: the MARBLE ablation and TerminalBench. Everything cross-benchmark mixes models or metrics (or both), so it's directional by construction — useful as a trend, not as proof.

The metrics themselves aren't even the same currency, which is why I use one word, *resolution rate*, and never pretend a MARBLE 100% and a SWE-bench 66% mean the same thing:

```text
MARBLE        → produced an output file within 600s (binary)
DevBench      → pass@1, test execution
SWE-bench     → pass@1, patch applies + tests pass
TerminalBench → verifier script passes
```

On statistical power: at n=10 per cell, a two-proportion z-test detects roughly a **25-point** effect at p<0.05. Coordination's +32.5 clears that bar comfortably. A +5 on 20 terminal tasks does **not** — so treat TerminalBench as a lead to chase, not a law of nature.

The claim I'll defend: **given a fixed model, coordination is the dominant lever, and shared memory only helps once there's a coordinator to make it mean something.** The claims I won't make: that Squad "beats" GPT-5.5, that it's the current SWE-bench champion, or that a 5-point win on 20 tasks is settled science.

---

## The Point

- **A benchmark that doesn't hold the model constant is measuring the model, not your system.** If you take one thing from this, take that.
- **Coordination beats memory, and it isn't close.** Routing alone bought +32.5 points. Memory without routing *lost* ground — expensive noise.
- **Trust the controlled results first.** The blue ones — MARBLE ablation and TerminalBench — are where the confounds are pinned down. The rest is direction of travel.
- **The counterintuitive finding is the credibility check.** "Memory hurts when it's ungoverned" is not a line you write to sell a product. It's the tell that the rest of the numbers weren't massaged.

GitHub's own harness evaluation made the same underlying argument from the other side: as the tooling matures, *how you harness the model* becomes a first-class performance variable, not an afterthought. Squad is a bet on the next layer up — that once the harness is solid, the biggest remaining lever isn't a bigger model. It's a better-organized team running on the one you already have.

Same model. Different team. Measurably different results.

---

## Sources

Everything below is public. The raw runs are there so you can check my math instead of taking my word for it.

- Raw MARBLE data, ablation runs, and charts — [tamirdresher/squad-marble-benchmark][1] (581 files)
- SWE-bench data and reproduction harness, including `evaluate.py` for independent verification — [tamirdresher/squad-swe-bench][2] (1,500+ files)
- MARBLE integration — [PR #245][3]
- MARBLE benchmark paper — [Zhu et al., ACL 2025][4]
- GitHub's harness methodology, which this evaluation deliberately mirrors — [Evaluating performance and efficiency of the GitHub Copilot agentic harness][5]
- Framework version under test — Squad v0.9.6 (June 2026)
- Co-conspirator on all of the above — [Brady Gaster][6]

[1]: https://github.com/tamirdresher/squad-marble-benchmark
[2]: https://github.com/tamirdresher/squad-swe-bench
[3]: https://github.com/tamirdresher/squad-marble-benchmark/pull/245
[4]: https://arxiv.org/abs/2506.09468
[5]: https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/
[6]: https://bradygaster.com/

---

*This is Part 22 of [Scaling AI-Native Software Engineering](/tags/#scaling-ai-native-software-engineering). If you're new here, [Part 1](/blog/2026/03/11/scaling-ai-part1-first-team) is where the team first shows up. This is the part where I finally tried to prove it does anything.*
