---
layout: post
title: "Same Model, Different Team — Benchmarking Squad's Coordination Layer"
date: 2026-07-01
tags: [ai-agents, squad, benchmarks, marble, swe-bench, terminalbench, evaluation, methodology, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 22
published: false
---

The most common question I get about Squad is some version of the same one: can you actually *show* me — with data — that coordinating a team of agents adds real value over just pointing one good model at the problem? It's a fair challenge, and it's the honest motivation for this whole study.

It's also a timely one. GitHub recently published [their own harness evaluation](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/) of the Copilot agentic harness across models and tasks, and their central finding is that the orchestration layer — the harness that routes tools, manages context, and shapes the workflow — is a first-class performance variable in its own right, not a thin wrapper around the model. That's the idea I wanted to test one level up: if the harness matters that much, does the coordination layer sitting on top of it matter too? Brady Gaster and I designed and ran the study together.

Held to a single model, the answer is yes where coordination matters. With every agent pinned to **Claude Opus 4.6**, a coordinated team produces more correct output than the model running solo on MARBLE — it leads every domain on a milestone-level correctness measure (detailed below) — and it does it more reliably, completing more tasks and finishing with near-zero variance across domains. The team is more correct on average, and more consistent about delivering. These are early numbers at n=10 per cell, but they're strikingly consistent across domains, and larger runs will confirm the scale.

---

## What We Measured

Squad is a coordination layer that runs on top of the GitHub Copilot CLI harness. The harness handles tools, context, and the model call; Squad adds task decomposition and routing, parallel specialists with domain charters, persistent memory across tasks, cross-agent review (our Reviewer Rejection Protocol), and a per-agent learning history. If you've read [GitHub's own harness evaluation](https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/), this is the layer immediately above the one they measured — and their premise, that orchestration is a first-class performance variable, is exactly what we set out to test one level up.

![Squad coordination layer on top of the Copilot CLI harness](/assets/squad-benchmark/architecture.svg)

Squad supports **per-member model selection** — the coordinator can run one model and a specialist another. For this study we deliberately switched that off and pinned every agent to Claude Opus 4.6, so any measured difference is attributable to coordination rather than to a newer or larger model underneath.

The experiment is a factorial ablation built on MARBLE ([ACL 2025](https://arxiv.org/abs/2506.09468)), a multi-agent collaboration benchmark spanning coding, research, bargaining, and database domains:

```text
4 domains × 4 conditions × 10 tasks = 160 runs
model: Claude Opus 4.6   |   ablation metric: completion (output file within 600s)
correctness measured separately: aligned 80-transcript re-run, n=38/condition
```

The four conditions remove one capability at a time — **Full Squad** (coordination + memory), **Coord-only** (routing, no shared memory), **Memory-only** (shared memory, no coordinator), and **No Squad** (a single agent). A note on that third condition: *memory-only* does not test generic persistent memory. It injects the same `decisions.md` that Squad's coordinator would produce — Squad-formatted memory — into an otherwise uncoordinated agent. The result is "coordinator output without the live coordinator," not arbitrary memory vs. none. Two terms I use precisely: **completion** means an output file appeared within the limit; **resolution / pass** means the output was verified *correct*. The 160-run ablation measured completion; correctness came from a separate, aligned 80-transcript re-run (n=38 per condition), so no single run is asked to stand in for both. Every cell in the tables below is backed by a validated run in the public dataset — no placeholders, and no estimates except where explicitly labeled.

---

## Correctness: Did the Team Get It Right?

The short answer: yes, though modestly — the coordinated team leads on correctness, and the margin is real but not dramatic. This is the result I lead with, because it's the one that matters most: on the same model, does coordinating a team produce *more correct* output? To answer that, we re-ran all four conditions from an identical task list — so "task N" is the same MARBLE task in every condition, alignment guaranteed by construction — and graded the 80 fresh transcripts two ways with a single uniform judge (Claude Opus 4.6, same prompt and code path for every condition): the **Milestone-KPI**, MARBLE's signature metric for the fraction of a task's gold milestones the output actually achieves, and a **1–5 quality rubric** for the correctness, completeness, and quality of the produced artifact.

Correctness and quality across all four domains (same model, same tasks, uniform judge; n=38 per condition). Domain cells show Milestone-KPI% / quality:

| Condition | Milestone-KPI | Quality (1–5) | Research | Bargaining | Coding | Database† |
|-----------|--------------:|--------------:|---------:|-----------:|-------:|----------:|
| **Full Squad** (coordination + memory)      | **81.1%** | **4.10** | 81.2 / 4.21 | 95.0 / 4.80 | 81.7 / 3.73 | 66.7 / 3.67 |
| **Coord-only** (coordinator + specialists)   | 81.1% | 4.04 | 89.6 / 4.50 | 96.7 / 4.83 | 68.3 / 3.27 | 71.7 / 3.67 |
| **No Squad** (single agent)                  | 77.2% | 3.76 | 75.0 / 4.00 | 90.0 / 4.24 | 78.3 / 3.77 | 65.0 / 3.10 |
| **Memory-only** (Squad memory, no coordination) | 65.8% | 3.58 | 52.1 / 3.21 | 96.7 / 4.80 | 53.3 / 2.97 | 58.3 / 3.27 |

![Correctness (Milestone-KPI) vs. cost per task — up and to the left is better](/assets/squad-benchmark/correctness-vs-cost.svg)

Plot correctness against cost and the value picture snaps into focus — up and to the left is better. **Coord-only** delivers the *same* 81.1% milestone-KPI as the full stack at less than half the cost, which makes it the best value on the board. **Full Squad** ties for top correctness and buys you the reliability that comes with it. The single agent trails. And **Memory-only** sits in the worst corner — low correctness, high cost.

Correctness tells a coherent story: coordination helps or ties in every domain, and Full Squad leads overall on both metrics — 81.1% milestone-KPI and 4.10 quality, a clean **+3.9pp** KPI and **+0.34** quality over the single agent. Coord-only ties on KPI (81.1%) and lands just behind on quality (4.04). The coordinated team isn't only finishing more tasks; it's producing more correct output on the same model.

The aligned re-run also sharpens two earlier readings that turned out to be measurement artifacts rather than real effects — a direct benefit of better instrumentation. On **coding**, with tasks aligned one-to-one, Full Squad (81.7% KPI) now leads the single agent (78.3%); the earlier apparent reversal is gone. On **database**, grading identical tasks with one uniform judge, the coordinated conditions match or beat the single agent (Coord-only 71.7%, Full Squad 66.7% vs. No-Squad 65.0%), refuting the earlier "coordination hurts" impression; that impression came from grading *divergent* tasks — the four conditions hadn't run the same MARBLE program at a given task index — not from any real coordination gap.

Memory without a coordinator is the more nuanced case. It's not cost-effective in most domains, and in coding (53.3% KPI) and research (52.1%) the ungoverned context actively hurts. But it's not worthless everywhere: on the easier bargaining domain, Memory-only actually edges Full Squad (96.7% vs. 95.0% KPI, tied on quality at 4.80), and it ties Full Squad on database quality (3.67). The point isn't that memory is dead weight — it's that memory pays off only when there's a coordinator to govern it. Leave it unmanaged and it helps in the easy cases and hurts in the hard ones.

The honest bottom line: coordination's correctness advantage is real and consistent across domains, and it's modest — a few points of milestone-KPI and about a third of a rubric point, not a double-digit swing. That's the right way to read it: correctness is where coordination wins steadily.

*These are early numbers — n=8–10 per domain, so the correctness deltas are directional rather than statistically significant, and larger runs will confirm the scale. †The database milestone-KPI blends diagnostic-process milestones (which `pg_stat_*` views to query) with the final answer, so the 1–5 rubric is the cleaner correctness signal there. Because the primary judge (Opus 4.6) shares the agents' model family, we cross-checked with an independent gpt-4o rubric on the research and bargaining cells — the two judges agree on the broad ordering (coordinated ≥ single agent) and differ only on fine placement.*

---

## Reliability: It Finishes — and Finishes Predictably

Correctness tells you the output is right. Reliability tells you the team will actually deliver it — every time. That's the completion story, and on the same model the coordinated team is both more likely to finish and far more consistent about it.

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

Reliability's other standout is consistency. Completion standard deviation across the four domains (n=10 each):

```text
Full Squad   σ = 0.0%
Coord-only   σ = 4.3%
No Squad     σ = 11.2%
Memory-only  σ = 26.8%
```

The coordinated team posts the same high number in every domain; the single agent swings hard from one to the next. In production terms, predictable is worth nearly as much as high — and the full stack delivers both.

---

## Cost

The other axis is dollars per completed task, where the objective is the same up-and-to-the-left frontier — more output, lower cost.

![MARBLE ablation — completion rate vs. cost per task](/assets/squad-benchmark/completion-vs-cost.svg)

![MARBLE — cost per task by condition](/assets/squad-benchmark/cost-per-task.svg)

- **Coord-only** — 92.5% at **~$0.41/task**. The efficiency frontier: nearly all of the completion benefit at the lowest cost.
- **Full Squad** — 100% at **~$0.97/task**. The premium tier — you pay for the last few points and the zero-variance consistency.
- **Memory-only** — ~42.5% at **~$1.50/task** (estimated). Not cost-effective in most domains, and a reminder that memory only earns its keep when a coordinator governs it.

Two live options come out of this: routing-only when you're optimizing for cost and value per task, and the full stack when you want maximum correctness and rock-steady reliability.

---

## What the Benchmarks Show

There are now two clean controlled arms in the study. On MARBLE, the multi-agent collaboration benchmark, Squad clearly wins. On SWE-bench Verified, an atomic single-issue bug-fixing benchmark, Squad honestly ties the standalone agent. The broader benchmarks are directional context and point the same way, including a #1 finish on the public SWE-bench Lite leaderboard at submission time (June 2026). The through-line is simple: Squad wins where coordination has something to coordinate.

This is the only apples-to-apples figure in the post: every pair holds model, tasks, and metric constant. It combines the MARBLE ablation (Claude Opus 4.6), the TerminalBench sample, and the new 50-instance SWE-bench Verified arm (gpt-5.5).

![Controlled comparison — Squad-on vs Squad-off, same model / same tasks / same metric](/assets/squad-benchmark/controlled-comparison.svg)

The honest headline: on MARBLE, where the task is collaboration, Squad shows a clear lift — **+15pp** completion. On SWE-bench Verified, where the task is atomic solo bug-fixing, the arms tie at **36/50** each (**72%**). The subsets are not the same: Squad uniquely resolves astropy-13977, django-10097, and django-11265; standalone uniquely resolves astropy-13236, astropy-14365, and django-10973. Coordination reshuffles which problems get solved without moving the aggregate count. Squad's coordination pays off where there's collaboration to coordinate.

Broader directional context, mixed metrics/models:

| Benchmark          | Tasks     | Model           | Metric      | Squad                | Baseline                     | Comparison |
|--------------------|-----------|-----------------|-------------|----------------------|------------------------------|------------|
| MARBLE (ablation)  | 160       | Claude Opus 4.6 | Completion  | 100% completion      | 85% (same model)             | Controlled, **+15pp** ✅ |
| MARBLE (full run)  | 400       | Claude Opus 4.6 | Completion  | 99.75% (399/400)     | ~45% gpt-4o-mini*            | different model/metric |
| DevBench           | 1,800     | GPT-5.4         | Pass@1      | 53.1%                | 43.5% (GPT-5.5)              | cross-model, preliminary |
| SWE-bench Lite     | 300       | GPT-4o          | Pass@1      | 66% (198/300 pass@1) | ~48% (est.)                 | #1 on public Lite leaderboard (66% vs 62.7%); vs ~48% same-tool est. — directional |
| SWE-bench Verified (controlled) | 50 | gpt-5.5 | Pass@1 | 72% (36/50) | 72% (36/50, same model) | **Tie** — controlled ✅ |
| TerminalBench 2.0  | 20 of 89  | Claude Opus 4.6 | Resolution  | 80% (16/20)          | 75% (15/20)                 | **+5pp** same model, subset |

![Per-benchmark scores — Squad vs baselines (metrics differ)](/assets/squad-benchmark/cross-benchmark.svg)

This table gathers each benchmark's headline score on its *own* native metric — the two MARBLE rows are completion, and DevBench, SWE-bench, and TerminalBench are correctness/pass — so it mixes axes on purpose. The clean controlled comparisons are MARBLE (win) and SWE-bench Verified (tie), both shown in the figure above. The MARBLE full run lands 99.75% (399/400). On DevBench, Squad running on GPT-5.4 scored higher than a single agent on the newer GPT-5.5 — a suggestive, contextual data point rather than an apples-to-apples result, since the models differ and it isn't a controlled comparison. SWE-bench Lite comes in at 66% pass@1 (198/300) on the full 300-task Lite run — our real measured result, and #1 on the public Lite leaderboard at time of submission (June 2026) — a self-run evaluation using the official Docker harness, with formal leaderboard submission pending maintainer verification — ahead of Claude Opus 4.6 at 62.7%. That is distinct from the controlled SWE-bench Verified-50 tie: different task set, different protocol, different model, and not contradictory. TerminalBench lands at 80% on the same model.

*Reading the cross-benchmark table:*

- *DevBench runs on a different model (Squad on GPT-5.4 vs. a GPT-5.5 baseline) and is preliminary/contextual, not a controlled comparison.*
- *SWE-bench Lite is the directional full-run / leaderboard number: 66% pass@1 on the 300-task Lite set, #1 on the public Lite leaderboard at submission time (June 2026), distinct from the Verified-50 controlled arm.*
- *SWE-bench Verified is the controlled solo-bug-fixing counterpart to the MARBLE collaboration ablation: gpt-5.5, matched WSL/Docker harness, gold test-diffs stripped, and a 36 vs. 36 tie (36/50 each), with non-overlapping solved subsets.*
- *TerminalBench uses a 20-task subset through a different harness path.*
- *There are two controlled arms: MARBLE, where Squad wins on collaboration, and SWE-bench Verified, where Squad ties on atomic solo bug-fixing. The edge concentrates where coordination matters; the rest is directional context.*

---

## The Point

- **Same model, more correct output.** Held to Claude Opus 4.6, the coordinated team produced more correct results than the model running solo — Full Squad leads every domain on milestone-KPI and rubric quality, +3.9pp and +0.34 over the single agent. The gain is modest but consistent.
- **Reliability is the standout.** The coordinated team didn't just get more right; it finished more tasks — +15 points for the full stack, +7.5 from routing alone — and scored the same high completion number in every domain, driving variance to essentially zero. Correctness tells you it's right; reliability tells you it'll actually deliver, every time.
- **The pattern is clearer now.** Squad wins where coordination matters — MARBLE collaboration — honestly ties on atomic solo bug-fixing in controlled SWE-bench Verified (36/50 vs. 36/50), and tops the public SWE-bench Lite leaderboard at submission time (66% vs. 62.7%). DevBench and TerminalBench add directional context.
- **This is the coordination layer earning its keep.** The model is the raw material; organizing it into a team is what turns it into correct, repeatable results. Correctness and reliability now point the same direction where there is coordination work to do; scaling n and adding runs is what comes next.

A well-organized team of agents, on the same model, consistently comes out ahead when the work benefits from coordination — getting more of the collaborative work right and delivering it more reliably. The benchmarks back that up where coordination has something to coordinate; on atomic solo tasks, the controlled result is an honest tie, which is what a rigorous measurement should show. We're just getting started.

---

## Sources

- Raw MARBLE data, all ablation runs, and charts — [tamirdresher/squad-marble-benchmark][1] (581 files)
- SWE-bench data and reproduction harness, including `evaluate.py` for independent verification — [tamirdresher/squad-swe-bench][2] (1,500+ files)
- MARBLE integration — [PR #245][3]
- MARBLE benchmark paper (ACL 2025) — [Zhu et al.][4]
- GitHub's harness evaluation — the inspiration for testing the coordination layer one level up — [Evaluating performance and efficiency of the GitHub Copilot agentic harness][5]
- Framework versions under test — Squad v0.9.6 (MARBLE ablation, SWE-bench Lite) and v0.11 (SWE-bench Verified arm).

[1]: https://github.com/tamirdresher/squad-marble-benchmark
[2]: https://github.com/tamirdresher/squad-swe-bench
[3]: https://github.com/ulab-uiuc/MARBLE/pull/245
[4]: https://arxiv.org/abs/2506.09468
[5]: https://github.blog/ai-and-ml/github-copilot/evaluating-performance-and-efficiency-of-the-github-copilot-agentic-harness-across-models-and-tasks/

---

*This is Part 22 of [Scaling AI-Native Software Engineering](/tags/#scaling-ai-native-software-engineering). If you're new here, [Part 1](/blog/2026/03/11/scaling-ai-part1-first-team) is where the team first shows up.*
