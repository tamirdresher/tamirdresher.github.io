---
layout: post
title: "Pathfinder — When AI Squads Learn to Talk to Each Other"
date: 2026-04-08
tags: [ai-agents, squad, github-copilot, distributed-systems, cross-squad, unix-philosophy, pipes, communication-protocols, kubernetes, star-trek]
series: "Scaling AI-Native Software Engineering"
series_part: 8
hero_image: /assets/img/part8-pathfinder.jpg
hero_image_prompt: "A deep space communications relay — two distant star systems connected by a brilliant data stream, one blue-white, one amber-gold, relay stations bridging the gap, geometric starships at each end, cinematic sci-fi art with warm lighting"
---

> *"I've spent the last year trying to find a way to communicate with Voyager. Everyone said it couldn't be done. They said the distance was too great, the technology didn't exist. But I knew if I could just find the right frequency..."*
> — Lieutenant Barclay, Star Trek: Voyager, "Pathfinder"

In "Pathfinder," Barclay does something everyone told him was impossible: he establishes real-time communication between Starfleet and a ship stranded 30,000 light-years away. Two independent crews. Different contexts. Different problems. Different chain of command. But once they could talk, both became more effective than either was alone.

I've been doing the same thing with AI squads. And it started because I realized I wasn't just running one squad anymore.

---

## The Squad HQ Problem

Somewhere around when I moved Squad to AKS, something shifted in how I work. My personal repo stopped being the place where Squad lives and became the place from which I *control* other squads.

Here's what I mean. At work, I contribute to several repositories. Each one has its own Squad — its own team of AI agents, its own routing table, its own Ralph monitor, its own decisions log. The infrastructure repo has a Squad with agents named after the TNG bridge crew. The provisioning service has a Squad themed around The Matrix. Different crews for different missions, just like Starfleet doesn't send one ship to do everything.

But I needed a home base. A bridge. The place where Captain Me sits and says "hail the other ship."

That's what my personal repo became. My Squad HQ. I use it to query other squads, delegate tasks across repos, and coordinate work that spans multiple codebases. One squad orchestrating others. A fleet command pattern.

And the moment I started doing this — talking to other squads from my home base — a higher-level pattern emerged that I genuinely didn't expect.

---

## The Unix Philosophy, But for AI

Bear with me for a second while I talk about pipes.

The [Unix philosophy](https://cscie2x.dce.harvard.edu/hw/ch01s06.html), as articulated by Doug McIlroy in 1978, goes like this: *Write programs that do one thing and do it well. Write programs to work together. Write programs to handle text streams, because that is a universal interface.*

Small composable tools. Connected by `stdin` and `stdout`. Each tool is ignorant of the others — it just reads input, does its thing, and writes output. The magic is in the composition.

```bash
cat server.log | grep ERROR | sort | uniq -c | sort -rn | head -20
```

Six tools. None of them know about the others. The pipe is the protocol. The text stream is the interface. You've written a log analysis pipeline by composing primitives.

Now look at this:

```
dir *.cs | ANALYZE_CODE_QUALITY | lint --fix | REWRITE_TESTS | CREATE_TASKS | EXECUTE | SUMMARIZE
```

Uppercase commands are Squad-backed AI tools. Lowercase commands are regular deterministic programs. `ANALYZE_CODE_QUALITY` is a prompt sent to a Squad agent. `lint --fix` is ESLint. `REWRITE_TESTS` is another AI agent. `CREATE_TASKS` opens GitHub issues. `EXECUTE` triggers Ralph. `SUMMARIZE` writes the daily report.

**The deterministic tools and the AI-powered tools use the same interface: text in, text out.** The pipe doesn't care whether the transformation is algorithmic or neural. It doesn't care whether the tool took 2 milliseconds or 45 seconds. It doesn't care whether the tool is a 30-line shell script or a language model with 200 billion parameters.

This is the Unix philosophy applied to AI agents. And it's not metaphorical — it's literally how cross-squad invocation works.

When I invoke another squad, the command looks like this:

```powershell
$targetRepo = "C:\temp\Infra.PlatformService"
$promptFile = New-TemporaryFile
@"
You are working in a Squad-enabled repository.
Read .squad/team.md and .squad/decisions.md first.

[CROSS-SQUAD REQUEST]
From: squad-hq
Request Type: knowledge_query
Query: What is the current architecture of the ARM RP?
Response Format: Brief structured summary
"@ | Out-File $promptFile -Encoding utf8

copilot --yolo --agent squad -p $promptFile -- --working-directory $targetRepo
```

Text in (the prompt file), text out (the response).The Squad on the other side reads its own `.squad/team.md`, loads its own context, and answers the question using its own codebase. I never touch their code. I never configure their agents. I just... ask.

This is `cat | grep` for organizational knowledge. The prompt is stdin. The response is stdout. The Squad is the tool.

And just like Unix tools can be written by different people, in different languages, for different purposes — squads can be configured by different teams, with different agents, for different codebases. The interface is the same: a text prompt asking a question, and a text response answering it.

Here's the thing that really clicked for me: **some of those "lowercase" deterministic tools in the pipeline? They were written by squads.** Data wrote the linter config. Seven wrote the documentation templates. B'Elanna wrote the Helm validation scripts. The squads are both the tools *and* the tool-makers. The pipeline is self-improving.

---

## Five Patterns for Cross-Squad Communication

The Unix pipe analogy is the philosophy. Now here's the engineering. We ended up with five distinct patterns for how squads talk to each other, and a decision tree for choosing between them.

### Pattern 0: The Synchronous Call (The Phone Call)

This is the one I showed above. Spawn a Copilot CLI session with the working directory set to the target squad's repo. The session gets full context — the target's codebase, their `.squad/` metadata, their MCP tools. It's like calling someone and having them look up the answer while you wait.

```powershell
# Quick knowledge query — synchronous, immediate response
copilot -p $promptFile -- --working-directory $targetRepo
```

We write the prompt to a temp file instead of passing it inline. This was a lesson from `ralph-watch.ps1` — when you pass multi-line prompts as command arguments, PowerShell's argument splitting turns your carefully crafted question into word salad. The temp file approach came from debugging Ralph rounds where prompts containing flags like `-R` were being interpreted as CLI arguments. Two hours of "why is Ralph ignoring my prompt?" answered by "because Start-Process thought your prompt was a parameter."

This pattern is fast — answer in 30-90 seconds — but it requires the target repo to be cloned locally and the CLI to be installed. Fine for my laptop. Not great for Kubernetes. We'll come back to that.

### Pattern 1: The Metadata Read (The Filing Cabinet)

Sometimes you don't need a conversation. You just need to read the other squad's decisions.

```powershell
$target = "C:\temp\Infra.PlatformService"
$team = Get-Content "$target\.squad\team.md" -Raw
$decisions = Get-Content "$target\.squad\decisions.md" -Raw
$routing = Get-Content "$target\.squad\routing.md" -Raw
```

This is the simplest pattern — just read their files. No CLI invocation, no session overhead. It answers questions like "what stack does this team use?" and "who handles security in this repo?" directly from the source.

I tested this against two real squads. PlatformService's `team.md` told me they use C#, .NET, and several Azure services. Their decisions file revealed their primary resource type and several architecture decisions under review. All without asking a single question — just reading their published metadata.

Think of it as reading the other ship's registry before hailing them. You wouldn't open a channel to the *Enterprise-D* to ask "what class of starship are you?" You'd look it up.

### Pattern 2: The Async Handoff (The Memo)

For work that takes longer than a quick question — PR reviews, multi-step analysis, code-level investigations — you drop a request file into a shared directory and let the target squad's Ralph pick it up:

```yaml
# .squad/cross-squad/requests/2026-07-11-baseplatformrp-arch-review.yaml
id: req-2026-07-11-001
source_squad: squad-hq
target_squad: baseplatformrp
request_type: knowledge_query
priority: normal
query: "Review the Workspace resource lifecycle. Are there any gaps in the delete flow?"
routing_hint: "picard"
status: pending
```

The target squad's Ralph picks this up on its next cycle, routes it to the appropriate agent, and writes a response file. Your Ralph picks up the response on *its* next cycle. Eventually consistent. Fully asynchronous. No one waits for anyone.

This is the git-based async pattern — your version control system is the message bus. Durable, auditable, and it works even when the target squad isn't currently running. The message waits until someone processes it.

### Pattern 3: The Issue Delegation (The Work Order)

For GitHub-hosted repos, issues are the natural message bus:

```bash
gh issue create \
  --repo contoso/Infra.PlatformService \
  --title "[Cross-Squad] Workspace delete flow review" \
  --body "Source: squad-hq\nRouting: picard" \
  --label "squad:cross-squad"
```

The `squad:cross-squad` label triggers the target squad's routing system. Picard picks it up, does the analysis, posts the findings as a comment, and closes the issue. It's the same workflow as a human creating a bug report — the Squad just happens to be the one reading the inbox.

### Pattern 4: The Dependency Scan (The Radar Sweep)

Before you talk to another squad, you should know *how* you relate to them. Pattern 4 is about discovery — scanning for shared dependencies, mutual references, common packages:

```powershell
# What do these two repos share?
Select-String -Path (Get-ChildItem $repoA -Recurse -Include "*.csproj") `
  -Pattern $repoB_name
Select-String -Path (Get-ChildItem $repoB -Recurse -Include "*.csproj") `
  -Pattern $repoA_name
```

This found things I didn't know about. Shared NuGet packages. Mutual ADO project references. Infrastructure modules that both repos depend on. You can't have a meaningful cross-squad conversation if you don't know what you have in common.

### The Decision Tree

When should you use which pattern? We landed on this:

```
Is the target repo cloned locally?
├─ NO → Issue-Based (Pattern 3) or Git-Async (Pattern 2)
└─ YES
    ├─ Quick query?     → Sync CLI (Pattern 0)
    ├─ Need artifacts?  → Git-Async (Pattern 2)
    ├─ Long analysis?   → Git-Async (Pattern 2)
    └─ Ralph running?
        ├─ YES → Async patterns (2 or 3)
        └─ NO  → Sync CLI (Pattern 0) or Metadata Read (Pattern 1)
```

The pattern I use most often? Pattern 1, followed by Pattern 0. Most cross-squad interactions are "tell me about yourself" queries, not complex delegations. The filing cabinet is surprisingly powerful.

---

## The Test That Worked (And the Bug It Found)

Theory is nice. But does this actually work when you point one squad at another?

We tested against two real squads. PlatformService, which lives on GitHub and has a Star Trek TNG cast — Picard, Data, Worf, Geordi, Deanna, Beverly, Riker, Wesley, Guinan, and Q. (Yes, they went all in on the roster.) And ServiceOrchestrator, which lives on Azure DevOps and has a Matrix cast — Neo, Trinity, Morpheus, and Oracle.

The metadata reads worked immediately. I could tell you everything about both squads without either of them knowing I'd looked. PlatformService uses several Azure-native services and patterns. ServiceOrchestrator uses Go and gRPC. Their routing tables told me who handles what. Their decisions files told me what they'd already decided. Pattern 1 is free intel.

The sync CLI test was more interesting. I launched a full Copilot CLI session targeting the ServiceOrchestrator repo:

```powershell
copilot -p $promptFile -- --working-directory "C:\temp\ServiceOrchestrator"
```

The session spun up. It loaded the Squad agent. It found `team.md` (25 lines, Matrix-themed, 4 agents). The MCP servers started initializing — all seven of them. And then... my 120-second hard timeout killed the session.

It wasn't hung. It was working. The MCP servers for that repo take 40-60 seconds to initialize — each one connects to different backend services, and some of those connections are slow. The session was actively making progress, writing to its log directory, loading tools. But my timeout didn't know that. It saw "120 seconds elapsed, no response" and pulled the plug on a valid session.

This is a distributed systems problem, and I recognized it immediately: **you can't use wall-clock timeouts as health checks for processes with variable startup costs.** Kubernetes solved this years ago with the distinction between liveness probes and readiness probes. A pod that's still starting up isn't dead — it's just not ready yet.

So we built a liveness protocol. Instead of "kill after N seconds," we monitor the session's log directory for activity:

```powershell
$logDir = Get-ChildItem "$env:USERPROFILE\.agency\logs" -Directory |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$lastSize = 0
$stallCount = 0

while ($proc -and -not $proc.HasExited) {
    Start-Sleep -Seconds 15
    $currentSize = (Get-ChildItem $logDir -Recurse -File |
        Measure-Object -Property Length -Sum).Sum

    if ($currentSize -eq $lastSize) {
        $stallCount++
        if ($stallCount -ge 4) {  # 60s of no progress
            Write-Warning "Session stalled — no log activity for 60s"
            break
        }
    } else {
        $stallCount = 0  # Reset — session is alive
        $lastSize = $currentSize
    }
}
```

If the log files are growing, the session is alive. If they've been the same size for four consecutive 15-second checks (60 seconds), something is actually stuck. This is the difference between a readiness probe ("are you ready to serve traffic?") and a liveness probe ("are you still alive?"). The session that my hard timeout killed was alive and making progress — the liveness protocol would have let it finish.

Here's the thing that made me laugh about this: I spent Parts [5](/blog/2026/03/24/scaling-ai-part5-vinculum) and [7](/blog/2026/04/02/scaling-ai-part7-cooperative) writing about distributed systems patterns I rediscovered while running AI agents. And then, while building the *communication layer between AI squads*, I rediscovered another one. Liveness vs. readiness. The lesson keeps giving.

---

## The Vision: Squads as Distributed Services

Let me zoom out.

Right now, cross-squad communication works because all the repos are cloned on my laptop. The Sync CLI pattern requires `--working-directory` to point to a local path. The metadata read requires filesystem access. Even the git-based async pattern assumes you can push to a shared remote.

That works for one person managing a few squads. It doesn't work for an organization where fifty teams each have their own squad, running on their own infrastructure, potentially in different clouds.

When I moved Squad to AKS — Kubernetes CronJobs, KEDA autoscaling, workload identity, zero credentials in the pod — the squad went from "a PowerShell loop on my laptop" to "a cloud-native service that scales and self-heals." That was the foundation.

This post is what you build on that foundation.

If squads run on AKS (or any agentic host runtime), they could discover each other over the network. Pattern 1's metadata read becomes an API call. Pattern 0's synchronous CLI becomes an RPC. Pattern 2's git-based async becomes a message queue. The patterns don't change — the transport does.

Imagine this: a squad running in one cluster needs a security review of a package. It doesn't file a GitHub issue. It sends a request to the security squad's API endpoint. The security squad's Worf picks it up, does the analysis, and sends the response back. All automated. All over the network. No human filing tickets. No human checking inboxes.

The protocol could be A2A (Google's Agent-to-Agent protocol), or MCP over HTTP, or something we haven't named yet. I've been thinking of it as **S2S — Squad to Squad.** Same patterns as above, but over the network instead of the filesystem. Discovery becomes DNS or a service registry. Health checks become actual HTTP liveness probes. The gossip protocol from [Part 7](/blog/2026/03/22/scaling-ai-part7-enterprise-state) (and [Part 7b](/blog/2026/03/23/scaling-ai-part7b-git-notes)) becomes a real pub/sub system.

The progression looks like this:

| Stage | Where Squads Live | How They Talk |
|-------|-------------------|---------------|
| Part 1 | One laptop | They don't — it's one squad |
| Part 3 | Two machines | Git push as consensus |
| AKS | AKS cluster | CronJobs + KEDA |
| **Part 8** | **Multiple repos, one machine** | **CLI + metadata + git-async** |
| Next | **Multiple clusters** | **Network protocols (S2S)** |

The Star Trek parallel writes itself. In "Pathfinder," Barclay doesn't just make contact with Voyager — he establishes a *repeatable communication protocol*. A monthly data stream. Regular check-ins. What starts as a desperate one-time hack becomes institutional infrastructure. That's exactly the path from "I manually ran `copilot` targeting another repo" to "squads discover and communicate with each other as cloud-native services."

We're somewhere between rows 4 and 5 in that table. The patterns are proven. The protocol is documented. The foundation (AKS deployment) is running. What's missing is the network transport — and that's an engineering problem, not a research problem.

---

## What I Actually Learned

If I'm being honest — and this is the part of these posts where I always try to be — the most surprising thing about cross-squad communication wasn't the technical patterns. Those fell out naturally once I started trying. Five patterns, a decision tree, a liveness protocol. Standard distributed systems engineering.

The surprising thing was realizing that **the Unix philosophy scales to AI agents without modification.** Small tools. Composable. Text in, text out. Squads *are* tools. The pipe is the prompt. The composition is the workflow. McIlroy's 1978 design philosophy works for 2026 AI teams because the abstraction was always right: don't build monoliths, build composable units that communicate through simple interfaces.

The second surprise was that **the hard problems aren't the communication patterns — they're the discovery and liveness problems.** Knowing *how* to talk to another squad is easy. Knowing *whether* they're there, *whether* they're healthy, and *whether* they can handle your request right now — that's the distributed systems challenge. It's the same challenge every service mesh solves, every Kubernetes health probe addresses, every load balancer navigates. We're not inventing new problems. We're recognizing old ones in new clothes.

And the third surprise, which probably shouldn't have been a surprise at all: **the Star Trek metaphor keeps earning itself.** Pathfinder is about establishing communication between two crews that were never designed to work together, separated by enormous distance, using a protocol that nobody thought would work. Every time I think the analogy has been stretched too far, the engineering proves it's still on track.

Squads talking to squads. Fleets coordinating across repos. The Collective, but cooperative.

Barclay would approve.

🖖

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 1**: [From Personal Repo to Work Team](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [The Collective — Organizational Knowledge](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)
> - **Part 4**: [When Eight Ralphs Fight Over One Login](/blog/2026/03/17/scaling-ai-part4-distributed)
> - **Part 5**: [Knowledge is Power — Squad Learns to Evolve](/blog/2026/03/18/scaling-ai-part5-evolution)
> - **Standalone**: [9 AI Agents, One API Quota — Rate Limiting](/blog/2026/03/21/rate-limiting-multi-agent)
> - **Standalone**: [Aspire + Squad = ❤️](/blog/2026/03/22/aspire-squad-love)
> - **Part 7**: [When Git Is Your Database](/blog/2026/03/22/scaling-ai-part7-enterprise-state)
> - **Part 7b**: [The Invisible Layer — Git Notes](/blog/2026/03/23/scaling-ai-part7b-git-notes)
> - **Standalone**: [My Precious — Securing AI Squad](/blog/2026/03/25/securing-hardening-ai-agent-squad)
> - **Part 8**: Pathfinder — When AI Squads Learn to Talk to Each Other ← You are here

*The cross-squad communication patterns described here were designed and tested in a live session on July 11-12, 2026, against two real squad-enabled repositories. The session died of context overflow before this post could be written — which is itself a distributed systems failure mode I should probably cover in Part 9. Code examples from production Squad scripts. Doug McIlroy's Unix philosophy is from 1978. Barclay's Pathfinder protocol is from 2376. Both still work.*
