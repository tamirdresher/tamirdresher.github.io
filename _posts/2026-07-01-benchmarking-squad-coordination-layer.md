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

This is a post about a benchmark result that got *worse* after we checked it — and why I think that makes it more trustworthy, not less.

For the past few weeks I've been running a benchmark study of Squad together with [Brady Gaster](https://bradygaster.com/), work we did jointly to answer one question as cleanly as we could: when you take a fixed model and organize it into a coordinated team of agents, how much does the coordination *itself* actually buy you?

The honest answer turned out to be smaller than our first draft claimed — because that first draft contained a fabricated figure. We caught it, corrected it, and the corrected result is more modest. I want to walk through both the method and that correction, because the correction is the part I'm most confident about.

---

## Isolating the Coordination Variable

When people publish "our agent scored X%," they're usually measuring the model, not the system wrapped around it. Change the model underneath and the number moves. So the first design decision was to remove the model as a variable.

One clarification up front, because it matters: Squad does **not** force every agent onto a single model. Per-member model selection is a core feature — the coordinator can run one model, a specialist another. But for this ablation we deliberately switched that flexibility off and pinned every agent to **Claude Opus 4.6**. If the model is identical everywhere, then any difference in outcomes has to come from the coordination layer — routing, specialist charters, shared memory, cross-agent review — and not from a newer or larger model quietly doing the real work.

![Squad coordination layer on top of the Copilot CLI harness](/assets/squad-benchmark/architecture.svg)

Squad sits on top of the GitHub Copilot CLI harness. The harness handles tools, context, and the model call; Squad adds task decomposition and routing, parallel specialists with domain charters, persistent memory across tasks, cross-agent review (our Reviewer Rejection Protocol), and a per-agent learning history. If you've read [GitHub's own harness evaluation](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/), this is the layer directly above the one they measured — and their central finding, that orchestration is a first-class performance variable, is exactly the premise we wanted to test one level up.

---

## The Experiment

MARBLE ([ACL 2025](https://arxiv.org/abs/2506.09468)) is a multi-agent collaboration benchmark spanning four domains — coding, research, bargaining, and database. We built a factorial ablation on top of it:

```text
4 domains × 4 conditions × 10 tasks = 160 runs
model: Claude Opus 4.6   |   primary metric: completion (output file within 600s)
```

The four conditions strip capabilities away one at a time:

- **Full Squad** — coordination and memory
- **Coord-only** — the coordinator routes, no shared memory
- **Memory-only** — shared memory, no coordinator
- **No Squad** — a single agent, same model, same task

One piece of terminology I'll hold to for the rest of the post, because conflating these two is precisely how the trouble started:

- **Completion** — an output file appeared within the time limit. The run finished.
- **Resolution / pass** — the output was verified *correct*.

The ablation's primary metric is completion. Correctness is a separate, harder question I'll return to.

---

## The Correction

Here's the part I actually want to lead with.

Our first pass at the database domain showed something dramatic: a single agent scored **0%** completion, while every Squad configuration scored 90–100%. It was the best chart in the deck. "Database work is impossible without coordination" makes a great headline.

It was also wrong.

When we went back to audit the raw runs, the no-Squad database cell wasn't backed by real transcripts — it was placeholder files that had never been populated with actual runs. The 0% wasn't a measurement; it was missing data recorded as a zero. So we re-ran all ten no-Squad database tasks from scratch. Every one produced a substantive root-cause diagnosis. The real number was **100% completion**, not 0%.

The dramatic finding evaporated. "Database requires coordination" was an artifact of bad data, not a real effect. I'm putting this front and center because it changed our headline conclusion — and because a study you can't correct isn't a study, it's a brochure.

---

## The Corrected Ablation

Here is the ablation with real data in every cell. Numbers are **completion rate**:

| Domain      | Full Squad | Coord-only | Memory-only | No Squad |
|-------------|-----------:|-----------:|------------:|---------:|
| Coding      |       100% |       100% |         40% |      90% |
| Research    |       100% |        90% |         70% |      80% |
| Bargaining  |       100% |        90% |         60% |      70% |
| Database    |       100% |        90% |          0% |     100% |
| **Average** |   **100%** |  **92.5%** |   **42.5%** |  **85%** |

![MARBLE factorial ablation — completion rate by domain and condition](/assets/squad-benchmark/marble-ablation.svg)

With the database cell fixed, the coordination effect is real but modest:

- Full Squad averages **100%** completion; a single agent averages **85%**. That's a **+15-point** lift from the full stack.
- Routing alone — Coord-only, no memory — reaches **92.5%**, so coordination by itself is worth about **+7.5 points** over the bare agent.
- Memory-only *hurts*: **42.5%**, well below the 85% you get from doing nothing.

That last point needs an honest caveat. The Memory-only condition injects a Squad-generated `decisions.md` into an otherwise raw agent. So it isn't testing "does persistent memory help" in general — it's testing what happens when you hand an uncoordinated agent a pile of *another system's* memory. Unsurprisingly, context the agent has no machinery to govern reads as noise. I'd call this a finding about ungoverned memory, not about memory as such.

---

## Completion Is Not Correctness

Producing an output isn't the same as producing the *right* output, and the database domain is where that gap gets interesting. We re-graded those runs with MARBLE's official recall metric — the fraction of the known root causes the agent actually identified (|gold ∩ predicted| / |gold|), n=10:

| Condition                | Completion (produced output) | MARBLE recall (correctness) |
|--------------------------|-----------------------------:|----------------------------:|
| Full Squad               |                         100% |                         40% |
| Coord-only               |                          90% |                         50% |
| Memory-only              |                           0% |                          0% |
| No Squad (single agent)  |                         100% |                         60% |

Read that carefully. On database root-cause *correctness*, coordination did not help — it slightly hurt. The raw single agent had the highest recall at 60%, ahead of Coord-only (50%) and Full Squad (40%).

When I read the transcripts, the pattern was consistent: the multi-agent configurations kept converging on the obvious, high-signal causes — large bulk inserts, full-table scans — and then reinforcing each other's confidence, while missing subtler culprits like redundant indexes. In this small sample, coordination amplified a kind of confirmation bias.

I want to be careful in both directions. The honest takeaway is **not** "single agents are better at database work." At n=10 these gaps are well within noise. The takeaway is narrower and more useful: **coordination gave no correctness advantage in this domain** — the exact opposite of what the fabricated 0% had implied.

---

## Consistency, and How Much to Trust Any of This

Coordination did do one thing clearly: it made behavior more consistent. Completion standard deviation across the four domains (n=10 each):

```text
Full Squad   σ = 0.0%
Coord-only   σ = 4.3%
No Squad     σ = 11.2%
Memory-only  σ = 26.8%
```

(The σ = 35.4% we'd reported earlier for No-Squad was itself inflated by the fabricated 0%. Fixing the data tightened the spread.)

But consistency is not significance, and this is the caveat I most want to land. At n=10 per cell, a two-proportion z-test only detects effects of roughly **25 points** at p < 0.05. Our headline +15-point completion lift falls *below* that threshold. So do the database correctness gaps, which top out around 20 points. In plain terms: everything here is directional, not statistically significant. These are real observations from real runs, but the sample is too small to call any of them proven. Larger runs are the obvious next step, and I'd rather say that than dress up n=10 as a verdict.

---

## Cost

If completion is one axis, dollars per task is the other, and on that plane the goal is simple: up and to the left — higher completion, lower cost.

![MARBLE ablation — completion rate vs. cost per task](/assets/squad-benchmark/completion-vs-cost.svg)

![MARBLE — cost per task by condition](/assets/squad-benchmark/cost-per-task.svg)

- **Coord-only** — 92.5% at **~$0.41/task**. This is the efficiency frontier: nearly all of the completion benefit at the lowest cost.
- **Full Squad** — 100% at **~$0.97/task**. You pay roughly 2.4× for the final 7.5 points.
- **Memory-only** — ~42.5% at **~$1.50/task** (estimated). The most expensive condition and the least effective — the corner nobody wants.

If you care about cost per completed task, routing without heavyweight memory is the sweet spot.

---

## The Other Benchmarks

The MARBLE ablation is the only *controlled* comparison in the study — same model, same tasks, same metric. We ran three more benchmarks for breadth, but each one carries a confound, so I read them as directional signals, not clean measurements of coordination.

| Benchmark          | Tasks     | Model           | Squad             | Baseline                        | Read as |
|--------------------|-----------|-----------------|-------------------|---------------------------------|---------|
| MARBLE (ablation)  | 160       | Claude Opus 4.6 | 100% completion   | 85% (same model, no Squad)      | **Controlled** ✅ (+15pp) |
| MARBLE (full run)  | 400       | Claude Opus 4.6 | 99.25% (397/400)  | ~45% gpt-4o-mini (diff model/metric) | Directional, no clean Δ |
| DevBench           | 1,800     | GPT-5.4         | 53.1%             | 43.5% (GPT-5.5, newer model)    | Directional (+9.6pp), preliminary |
| SWE-bench Lite     | 300       | GPT-4o          | 66% (198/300 pass@1) | ~48% (estimated)             | Directional (+18pp), estimated baseline |
| TerminalBench 2.0  | 20 of 89  | Claude Opus 4.6 | 80% (16/20)       | 75% (15/20, same model)         | Directional, 1-task margin, diff harness |

![Per-benchmark scores — Squad vs baselines (metrics differ)](/assets/squad-benchmark/cross-benchmark.svg)

- **MARBLE full run (400 tasks).** Squad completed 99.25% (397 of 400; three timeouts). The paper's baseline used gpt-4o-mini and a different metric, so there's no clean same-model delta to quote. The 99.25% stands on its own, but it isn't a coordination measurement.
- **DevBench (1,800 tasks).** Squad on GPT-5.4 scored 53.1% against a 43.5% baseline — but that baseline ran on GPT-5.5, a *newer* model. Squad on an older model edging out a single agent on a newer one is suggestive, not conclusive, and the raw per-task data isn't public yet, so I'd treat +9.6 points as preliminary. A same-model ablation is planned.
- **SWE-bench Lite (300 tasks).** 66% pass@1 (198/300) against an estimated ~48% baseline. The baseline is *estimated* — there's no verified same-model run behind it — so +18 points is directional only.
- **TerminalBench 2.0 (20 of 89 tasks).** 80% (16/20) vs 75% (15/20) on the same model. But Squad and the baseline ran through *different harness paths* — Squad's host-side orchestrator versus the native terminal-bench harness — and the margin is a single task. Suggestive at best. Running the full 89 through a matched harness is future work.

---

## What I Can and Can't Claim

The claim I'll defend, stated narrowly: **with the model held constant, coordination provides a modest completion lift — +15 points for the full stack, +7.5 from routing alone — and makes behavior markedly more consistent. But at n=10 that lift sits within statistical noise, and coordination did not improve database correctness.** Ungoverned memory, handed to an uncoordinated agent, actively hurts.

The claims I won't make: that Squad "beats" GPT-5.5, that it's the current SWE-bench champion, or that any cross-benchmark delta is a clean measurement of coordination. They aren't — and pretending otherwise would undo the entire reason we held the model constant in the first place.

---

## The Point

- **Hold the model constant, or you're benchmarking the model.** The only comparison in this study I fully trust is the one where every agent ran the same model.
- **Coordination helps, modestly.** Routing bought about +7.5 points of completion and near-zero variance. That's worth something — the consistency especially — but it's not the step-change our fabricated data implied.
- **More output is not more correctness.** On database root-cause recall, coordination gave no advantage and possibly a small penalty, because multiple agents converged and reinforced one another. Worth watching as configurations scale.
- **The correction is the credibility.** We shipped a fabricated 0%, caught it, re-ran it, and it erased our best headline. I'd rather publish the modest true number than the dramatic false one — and the raw data is public, so you can check every cell yourself.

Given a fixed model, a well-organized team of agents is a little better and a lot more consistent than a single agent. That is a smaller claim than the one I started with. It's also one I can actually stand behind.

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

*This is Part 22 of [Scaling AI-Native Software Engineering](/tags/#scaling-ai-native-software-engineering). If you're new here, [Part 1](/blog/2026/03/11/scaling-ai-part1-first-team) is where the team first shows up. This is the part where I tried to measure whether it actually helps — and reported what I found, including the parts that didn't flatter it.*

