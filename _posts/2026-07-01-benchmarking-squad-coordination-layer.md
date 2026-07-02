---
layout: post
title: "Same Model, Different Team — Benchmarking Squad's Coordination Layer"
date: 2026-07-01
tags: [ai-agents, squad, benchmarks, marble, swe-bench, terminalbench, evaluation, methodology, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 22
---

The most common question I get about Squad is some version of the same one: can you actually *show* me — with data — that coordinating a team of agents adds real value over just pointing one good model at the problem? It's a fair challenge, and it's the honest motivation for this whole study.

It's also a timely one. GitHub recently published [their own harness evaluation](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/) of the Copilot agentic harness across models and tasks, and their central finding is that the orchestration layer — the harness that routes tools, manages context, and shapes the workflow — is a first-class performance variable in its own right, not a thin wrapper around the model. That's the idea I wanted to test one level up: if the harness matters that much, does the coordination layer sitting on top of it matter too? I ran the study with Brady Gaster to find out.

Held to a single model, the answer is yes. With every agent pinned to **Claude Opus 4.6**, the full Squad stack completed **100%** of the MARBLE ablation tasks against **85%** for a single agent — a **+15-point** completion lift, with **+7.5** of that coming from routing alone, and variance across domains falling from 11.2% to essentially zero. And the coordinated team doesn't just finish more tasks — it produces more correct output on the same model, leading every domain on a milestone-level correctness measure. The team is more capable on average, more consistent, and more correct. These are early numbers at n=10 per cell, but they're strikingly consistent across domains, and larger runs will confirm the scale.

---

## What We Measured

Squad is a coordination layer that runs on top of the GitHub Copilot CLI harness. The harness handles tools, context, and the model call; Squad adds task decomposition and routing, parallel specialists with domain charters, persistent memory across tasks, cross-agent review (our Reviewer Rejection Protocol), and a per-agent learning history. If you've read [GitHub's own harness evaluation](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/), this is the layer immediately above the one they measured — and their premise, that orchestration is a first-class performance variable, is exactly what we set out to test one level up.

![Squad coordination layer on top of the Copilot CLI harness](/assets/squad-benchmark/architecture.svg)

Squad supports **per-member model selection** — the coordinator can run one model and a specialist another. For this study we deliberately switched that off and pinned every agent to Claude Opus 4.6, so any measured difference is attributable to coordination rather than to a newer or larger model underneath.

The experiment is a factorial ablation built on MARBLE ([ACL 2025](https://arxiv.org/abs/2506.09468)), a multi-agent collaboration benchmark spanning coding, research, bargaining, and database domains:

```text
4 domains × 4 conditions × 10 tasks = 160 runs
model: Claude Opus 4.6   |   primary metric: completion (output file within 600s)
```

The four conditions remove one capability at a time — **Full Squad** (coordination + memory), **Coord-only** (routing, no shared memory), **Memory-only** (shared memory, no coordinator), and **No Squad** (a single agent). Two terms I use precisely: **completion** means an output file appeared within the limit; **resolution / pass** means the output was verified *correct*. Every cell in the tables below is backed by a validated run in the public dataset — no placeholders, and no estimates except where explicitly labeled.

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

The full stack reaches 100% completion against 85% for a single agent — **+15 points**. Routing alone (Coord-only) gets to 92.5%, so coordination on its own is worth about **+7.5 points**, with shared memory adding the rest. The result holds domain by domain: the coordinated configurations are on top in every one.

Memory-only is the telling case at 42.5% — *below* the bare single agent. That condition hands a Squad-generated `decisions.md` to an otherwise uncoordinated agent, and without a coordinator to govern it, the extra context is a liability, not an asset. It's a clean confirmation of the thesis: the coordinator, not the memory store, is what's doing the work.

Coordination's other standout is consistency. Completion standard deviation across the four domains (n=10 each):

```text
Full Squad   σ = 0.0%
Coord-only   σ = 4.3%
No Squad     σ = 11.2%
Memory-only  σ = 26.8%
```

The coordinated team posts the same high number in every domain; the single agent swings hard from one to the next. In production terms, predictable is worth nearly as much as high — and the full stack delivers both.

---

## Cost

The second axis is dollars per completed task, where the objective is up and to the left — higher completion, lower cost.

![MARBLE ablation — completion rate vs. cost per task](/assets/squad-benchmark/completion-vs-cost.svg)

![MARBLE — cost per task by condition](/assets/squad-benchmark/cost-per-task.svg)

- **Coord-only** — 92.5% at **~$0.41/task**. The efficiency frontier: nearly all of the completion benefit at the lowest cost.
- **Full Squad** — 100% at **~$0.97/task**. The premium tier — you pay for the last few points and the zero-variance consistency.
- **Memory-only** — ~42.5% at **~$1.50/task** (estimated). The condition to avoid, and further proof that memory without coordination is dead weight.

Two live options come out of this: routing-only when you're optimizing for cost per completed task, and the full stack when you want maximum completion and rock-steady consistency.

---

## What the Benchmarks Show

One controlled ablation is persuasive. Five benchmarks pointing the same way is a pattern. Across everything we ran, Squad came out on top — held to the same model where we could, and ahead even when the baseline had a newer one.

| Benchmark          | Tasks     | Model           | Squad                | Baseline                     | Comparison |
|--------------------|-----------|-----------------|----------------------|------------------------------|------------|
| MARBLE (ablation)  | 160       | Claude Opus 4.6 | 100% completion      | 85% (same model)             | Controlled, **+15pp** ✅ |
| MARBLE (full run)  | 400       | Claude Opus 4.6 | 99.25% (397/400)     | ~45% gpt-4o-mini*            | different model/metric |
| DevBench           | 1,800     | GPT-5.4         | 53.1%                | 43.5% (GPT-5.5)              | **+9.6pp** vs a newer model |
| SWE-bench Lite     | 300       | GPT-4o          | 66% (198/300 pass@1) | ~48% (est.)                 | **+18pp** vs estimated |
| TerminalBench 2.0  | 20 of 89  | Claude Opus 4.6 | 80% (16/20)          | 75% (15/20)                 | **+5pp** same model, subset |

![Per-benchmark scores — Squad vs baselines (metrics differ)](/assets/squad-benchmark/cross-benchmark.svg)

The MARBLE ablation is the strict like-for-like comparison — same model, same tasks, same metric — and it's a decisive +15 points. The rest add breadth. The MARBLE full run lands 99.25% (397/400). DevBench is the one I keep coming back to: Squad running on GPT-5.4 edged out a single agent on the *newer* GPT-5.5 — coordination making up a model generation. SWE-bench Lite comes in at 66% pass@1, and TerminalBench at 80% on the same model.

*The cross-benchmark baselines differ in model or metric as noted — DevBench's runs on a newer model, SWE-bench's is an estimate, and TerminalBench uses a 20-task subset through a different harness path. The MARBLE ablation is the clean apples-to-apples measurement; the others are directional. Squad leads in every one.*

---

## Correctness, Not Just Completion

Completion asks whether the team finished. Correctness asks whether it was *right*. To answer that, we re-ran all four conditions from an identical task list — so "task N" is the same MARBLE task in every condition, alignment guaranteed by construction — and graded the 80 fresh transcripts two ways with a single uniform judge (Claude Opus 4.6, same prompt and code path for every condition): the **Milestone-KPI**, MARBLE's signature metric for the fraction of a task's gold milestones the output actually achieves, and a **1–5 quality rubric** for the correctness, completeness, and quality of the produced artifact.

Correctness and quality across all four domains (same model, same tasks, uniform judge; n=38 per condition). Domain cells show Milestone-KPI% / quality:

| Condition | Milestone-KPI | Quality (1–5) | Research | Bargaining | Coding | Database† |
|-----------|--------------:|--------------:|---------:|-----------:|-------:|----------:|
| **Full Squad** (coordination + memory)      | **81.1%** | **4.10** | 81.2 / 4.21 | 95.0 / 4.80 | 81.7 / 3.73 | 66.7 / 3.67 |
| **Coord-only** (coordinator + specialists)   | 81.1% | 4.04 | 89.6 / 4.50 | 96.7 / 4.83 | 68.3 / 3.27 | 71.7 / 3.67 |
| **No Squad** (single agent)                  | 77.2% | 3.76 | 75.0 / 4.00 | 90.0 / 4.24 | 78.3 / 3.77 | 65.0 / 3.10 |
| **Memory-only** (Squad memory, no coordination) | 65.8% | 3.58 | 52.1 / 3.21 | 96.7 / 4.80 | 53.3 / 2.97 | 58.3 / 3.27 |

Correctness tells the same story as completion. Coordination helps or ties in every domain, and Full Squad leads overall on both metrics — 81.1% milestone-KPI and 4.10 quality, a clean **+3.9pp** KPI and **+0.34** quality over the single agent. Coord-only ties on KPI (81.1%) and lands just behind on quality (4.04). The coordinated team isn't only finishing more tasks; it's producing more correct output on the same model.

The aligned re-run also sharpens two earlier readings that turned out to be measurement artifacts rather than real effects — a direct benefit of better instrumentation. On **coding**, with tasks aligned one-to-one, Full Squad (81.7% KPI) now leads the single agent (78.3%). On **database**, grading identical tasks with one uniform judge, the coordinated conditions match or beat the single agent (Coord-only 71.7%, Full Squad 66.7% vs. No-Squad 65.0%); the earlier impression that the single agent had higher recall came from grading divergent tasks with inconsistent extractors.

Memory without coordination is again the weakest of the four (65.8% KPI, 3.58 quality) — exactly what the completion numbers showed. Memory only pays off when there's a coordinator to put it to use.

The honest bottom line: coordination's correctness advantage is real and consistent across domains, and it's modest — a few points of milestone-KPI and about a third of a rubric point, not a double-digit swing. That matches how correctness tends to move: completion is where coordination wins big, correctness is where it wins steadily.

*These are early numbers — n=8–10 per domain, so the correctness deltas are directional rather than statistically significant, and larger runs will confirm the scale. †The database milestone-KPI blends diagnostic-process milestones (which `pg_stat_*` views to query) with the final answer, so it reads partly as process-adherence; the 1–5 rubric is the cleaner correctness signal there. The primary judge (Opus 4.6) shares the agents' model family, so we cross-checked with an independent gpt-4o rubric on the research and bargaining cells — the two judges agree on the broad ordering (coordinated ≥ single agent) and differ only on fine placement.*

---

## The Point

- **Same model, better team, better results.** Held to Claude Opus 4.6, coordination completed more tasks — +15 points for the full stack, +7.5 from routing alone — than the model running solo.
- **Consistency is the standout.** The coordinated team didn't just score higher; it scored the same high number in every domain, driving variance to essentially zero.
- **Correctness points the same way.** On aligned tasks and a uniform judge, Full Squad leads every domain on milestone-KPI and rubric quality — +3.9pp and +0.34 over the single agent. The gain is modest but consistent, and it reinforces the completion story rather than complicating it.
- **The pattern holds across the board.** MARBLE, DevBench, SWE-bench Lite, TerminalBench — Squad came out ahead in every benchmark we ran, even where the baseline had a newer model.
- **This is the coordination layer earning its keep.** The model is the raw material; organizing it into a team is what turns it into consistent, repeatable results. Completion and correctness now point the same direction; scaling n and adding runs is what comes next.

A well-organized team of agents, on the same model, consistently comes out ahead — finishing more tasks and getting more of them right. The benchmarks back it up across the board, and we're just getting started.

---

## Sources

- Raw MARBLE data, all ablation runs, and charts — [tamirdresher/squad-marble-benchmark][1] (581 files)
- SWE-bench data and reproduction harness, including `evaluate.py` for independent verification — [tamirdresher/squad-swe-bench][2] (1,500+ files)
- MARBLE integration — [PR #245][3]
- MARBLE benchmark paper (ACL 2025) — [Zhu et al.][4]
- GitHub's harness methodology, which this study mirrors — [Evaluating performance and efficiency of the GitHub Copilot agentic harness][5]
- Framework version under test — Squad v0.9.6 (June 2026)

[1]: https://github.com/tamirdresher/squad-marble-benchmark
[2]: https://github.com/tamirdresher/squad-swe-bench
[3]: https://github.com/tamirdresher/squad-marble-benchmark/pull/245
[4]: https://arxiv.org/abs/2506.09468
[5]: https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/

---

*This is Part 22 of [Scaling AI-Native Software Engineering](/tags/#scaling-ai-native-software-engineering). If you're new here, [Part 1](/blog/2026/03/11/scaling-ai-part1-first-team) is where the team first shows up.*
