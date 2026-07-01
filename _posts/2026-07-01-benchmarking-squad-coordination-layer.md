---
layout: post
title: "Same Model, Different Team — Benchmarking Squad's Coordination Layer"
date: 2026-07-01
tags: [ai-agents, squad, benchmarks, marble, swe-bench, terminalbench, evaluation, methodology, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 22
image: /assets/squad-benchmark/hero.png
---

<!-- TODO(assets): /assets/squad-benchmark/hero.png does not exist yet — needs to be created before publishing. The other SVGs referenced below (architecture, marble-ablation, cross-benchmark, completion-vs-cost, cost-per-task) are exported from the squad-marble-benchmark repo. -->

Holding a model constant and organizing it into a coordinated team of agents produces a modest, repeatable improvement over running the same model as a single agent — and, on the hardest correctness metric we measured, no improvement at all. That is the short version of a benchmark study of Squad I ran with [Brady Gaster](https://bradygaster.com/), and the numbers come first.

With every agent pinned to **Claude Opus 4.6**, the full Squad stack completed **100%** of the MARBLE ablation tasks against **85%** for a single agent — a **+15-point** completion lift. Routing alone, with no shared memory, accounts for **+7.5** of that. Variance across domains collapses from 11.2% to essentially zero: the coordinated team isn't only a little better on average, it's far more consistent. One caveat stated up front, because it governs everything below: at n=10 per cell, that lift sits within statistical noise. It's directional, not significant. The rest of this post is the detail behind those sentences.

---

## What We Measured

Squad is a coordination layer that runs on top of the GitHub Copilot CLI harness. The harness handles tools, context, and the model call; Squad adds task decomposition and routing, parallel specialists with domain charters, persistent memory across tasks, cross-agent review (our Reviewer Rejection Protocol), and a per-agent learning history. If you've read [GitHub's own harness evaluation](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/), this is the layer immediately above the one they measured, and their premise — that orchestration is a first-class performance variable — is the one we set out to test one level up.

![Squad coordination layer on top of the Copilot CLI harness](/assets/squad-benchmark/architecture.svg)

Squad supports **per-member model selection** — the coordinator can run one model and a specialist another. For this study we deliberately switched that off and pinned every agent to Claude Opus 4.6, so that any measured difference is attributable to coordination rather than to a newer or larger model underneath.

The experiment is a factorial ablation built on MARBLE ([ACL 2025](https://arxiv.org/abs/2506.09468)), a multi-agent collaboration benchmark spanning coding, research, bargaining, and database domains:

```text
4 domains × 4 conditions × 10 tasks = 160 runs
model: Claude Opus 4.6   |   primary metric: completion (output file within 600s)
```

The four conditions remove one capability at a time — **Full Squad** (coordination + memory), **Coord-only** (routing, no shared memory), **Memory-only** (shared memory, no coordinator), and **No Squad** (a single agent). Two terms I use precisely throughout: **completion** means an output file appeared within the limit; **resolution / pass** means the output was verified *correct*. The ablation's primary metric is completion; correctness is measured separately below. Every cell in the tables that follow is backed by a re-validated run in the public dataset — no placeholders, and no estimates except where explicitly labeled.

---

## Coordination: The Completion Lift

Completion rate by domain and condition:

| Domain      | Full Squad | Coord-only | Memory-only | No Squad |
|-------------|-----------:|-----------:|------------:|---------:|
| Coding      |       100% |       100% |         40% |      90% |
| Research    |       100% |        90% |         70% |      80% |
| Bargaining  |       100% |        90% |         60% |      70% |
| Database    |       100% |        90% |          0% |     100% |
| **Average** |   **100%** |  **92.5%** |   **42.5%** |  **85%** |

![MARBLE factorial ablation — completion rate by domain and condition](/assets/squad-benchmark/marble-ablation.svg)

The full stack reaches 100% completion against 85% for a single agent — **+15 points**. Routing alone (Coord-only) gets to 92.5%, so coordination on its own is worth about **+7.5 points**; shared memory adds the rest.

Memory-only is the outlier at 42.5%, *below* the bare single agent. The condition injects a Squad-generated `decisions.md` into an otherwise uncoordinated agent, so it measures what happens when memory arrives without any machinery to govern it — the context reads as noise rather than signal. Read it as a result about ungoverned memory, not about memory in general.

Coordination's clearest effect is consistency. Completion standard deviation across the four domains (n=10 each):

```text
Full Squad   σ = 0.0%
Coord-only   σ = 4.3%
No Squad     σ = 11.2%
Memory-only  σ = 26.8%
```

The coordinated configurations are tightly clustered; the single agent swings much more from domain to domain. That said, consistency is not significance. At n=10 per cell, a two-proportion z-test only detects effects of roughly **25 points** at p < 0.05, so the +15-point lift is below the threshold to call it statistically proven. It's a real, repeatable observation across these runs — and one that needs larger samples to confirm.

---

## Completion Is Not Correctness

An output that finishes is not necessarily an output that's right. We re-graded the database domain with MARBLE's official recall metric — the share of known root causes the agent actually identified (|gold ∩ predicted| / |gold|), n=10:

| Condition                | Completion (produced output) | MARBLE recall (correctness) |
|--------------------------|-----------------------------:|----------------------------:|
| Full Squad               |                         100% |                         40% |
| Coord-only               |                          90% |                         50% |
| Memory-only              |                           0% |                          0% |
| No Squad (single agent)  |                         100% |                         60% |

On database root-cause correctness, coordination gave no advantage in this run — if anything, a slight penalty. The single agent had the highest recall (60%), ahead of Coord-only (50%) and Full Squad (40%). In the transcripts, the multi-agent configurations tended to converge on the obvious, high-signal causes — large bulk inserts, full-table scans — and reinforce each other's confidence, while missing subtler culprits such as redundant indexes.

The finding to take away is narrow: **coordination did not improve database correctness here.** It is *not* "single agents are better at database work" — with n=10 these gaps are within noise. But the direction is worth watching as configurations scale, because convergence among agents can amplify shared blind spots.

---

## Cost

The other axis is dollars per completed task, where the objective is up and to the left — higher completion, lower cost.

![MARBLE ablation — completion rate vs. cost per task](/assets/squad-benchmark/completion-vs-cost.svg)

![MARBLE — cost per task by condition](/assets/squad-benchmark/cost-per-task.svg)

- **Coord-only** — 92.5% at **~$0.41/task**. The efficiency frontier: nearly all of the completion benefit at the lowest cost.
- **Full Squad** — 100% at **~$0.97/task**. Roughly 2.4× the cost for the final 7.5 points.
- **Memory-only** — ~42.5% at **~$1.50/task** (estimated). The most expensive and least effective condition.

If the objective is cost per completed task, routing without heavyweight memory is the sweet spot.

---

## Beyond the Controlled Run

The MARBLE ablation is the only fully controlled comparison in the study — same model, same tasks, same metric. We ran three further benchmarks for breadth; each carries a confound, so I read them as directional signals rather than clean measurements of coordination.

| Benchmark          | Tasks     | Model           | Squad                | Baseline                             | Read as |
|--------------------|-----------|-----------------|----------------------|--------------------------------------|---------|
| MARBLE (ablation)  | 160       | Claude Opus 4.6 | 100% completion      | 85% (same model, no Squad)           | **Controlled** ✅ (+15pp) |
| MARBLE (full run)  | 400       | Claude Opus 4.6 | 99.25% (397/400)     | ~45% gpt-4o-mini (diff model/metric) | Directional, no clean Δ |
| DevBench           | 1,800     | GPT-5.4         | 53.1%                | 43.5% (GPT-5.5, newer model)         | Directional (+9.6pp), preliminary |
| SWE-bench Lite     | 300       | GPT-4o          | 66% (198/300 pass@1) | ~48% (estimated)                     | Directional (+18pp), estimated baseline |
| TerminalBench 2.0  | 20 of 89  | Claude Opus 4.6 | 80% (16/20)          | 75% (15/20, same model)              | Directional, 1-task margin, diff harness |

![Per-benchmark scores — Squad vs baselines (metrics differ)](/assets/squad-benchmark/cross-benchmark.svg)

- **MARBLE full run (400 tasks).** 99.25% completion (397/400; three timeouts). The paper's baseline used a different model and metric, so there's no clean same-model delta to quote — the figure stands on its own but isn't a coordination measurement.
- **DevBench (1,800 tasks).** 53.1% on GPT-5.4 against a 43.5% baseline that ran on GPT-5.5, a *newer* model. Squad on an older model edging out a single agent on a newer one is suggestive; raw per-task data isn't public yet, so I treat +9.6 points as preliminary. A same-model ablation is planned.
- **SWE-bench Lite (300 tasks).** 66% pass@1 (198/300) against an *estimated* ~48% baseline. With no verified same-model run behind the baseline, +18 points is directional.
- **TerminalBench 2.0 (20 of 89 tasks).** 80% (16/20) vs 75% (15/20) on the same model, but through different harness paths — Squad's host-side orchestrator versus the native terminal-bench harness — with a one-task margin. Suggestive at best; the full 89 through a matched harness is future work.

---

## What I Can and Can't Claim

Stated narrowly: **with the model held constant, coordination provides a modest completion lift — +15 points for the full stack, +7.5 from routing alone — and makes behavior markedly more consistent.** At n=10 that lift is directional rather than significant, and coordination did not improve database correctness. Memory handed to an uncoordinated agent hurts.

What the data does not support: that Squad "beats" GPT-5.5, that it is the current SWE-bench champion, or that any cross-benchmark delta is a clean measurement of coordination. Those comparisons mix models and metrics, and reading them as coordination results would defeat the purpose of pinning the model in the first place.

---

## The Point

- **Hold the model constant, or you're measuring the model.** The only comparison here I fully trust is the one where every agent ran the same model.
- **Coordination helps, modestly — and its clearest benefit is consistency.** Routing bought roughly +7.5 points of completion and near-zero variance across domains.
- **Completion is not correctness.** On database root-cause recall, coordination gave no advantage in this run. Worth watching as agent counts grow.
- **At n=10, treat everything as directional.** The numbers point somewhere; larger runs are needed to prove it. The full raw dataset is public, down to individual transcripts.

Given a fixed model, a well-organized team of agents is a little better and considerably more consistent than a single agent. It's a narrow claim — and one the data supports.

---

## Sources

- Raw MARBLE data, all ablation runs, and charts — [tamirdresher/squad-marble-benchmark][1] (581 files)
- SWE-bench data and reproduction harness, including `evaluate.py` for independent verification — [tamirdresher/squad-swe-bench][2] (1,500+ files)
- MARBLE integration — [PR #245][3]
- MARBLE benchmark paper (ACL 2025) — [Zhu et al.][4]
- GitHub's harness methodology, which this study mirrors — [Evaluating performance and efficiency of the GitHub Copilot agentic harness][5]
- Framework version under test — Squad v0.9.6 (June 2026)
- Co-author on this work — [Brady Gaster][6]

[1]: https://github.com/tamirdresher/squad-marble-benchmark
[2]: https://github.com/tamirdresher/squad-swe-bench
[3]: https://github.com/tamirdresher/squad-marble-benchmark/pull/245
[4]: https://arxiv.org/abs/2506.09468
[5]: https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/
[6]: https://bradygaster.com/

---

*This is Part 22 of [Scaling AI-Native Software Engineering](/tags/#scaling-ai-native-software-engineering). If you're new here, [Part 1](/blog/2026/03/11/scaling-ai-part1-first-team) is where the team first shows up.*
