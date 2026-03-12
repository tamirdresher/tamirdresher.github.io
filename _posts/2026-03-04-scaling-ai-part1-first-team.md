---
layout: post
title: "From Personal Repo to Work Team — Bringing Squad to Production"  
date: 2026-03-04
tags: [ai-agents, squad, github-copilot, scaling, team-workflows, productivity]
series: "Scaling AI-Native Software Engineering"
series_part: 1
---

> *"You will be assimilated."*  
> — The Borg, Star Trek: The Next Generation

Remember when I showed you how to [run multiple AI agents in parallel with Git worktrees](/blog/2025/10/20/scaling-your-ai-development-team-with-git-worktrees)? And then how to [give those agents eyes with Playwright MCP](/blog/2025/11/17/give-your-ai-coding-agent-eyes-with-playwright-mcp)? How I learned to [isolate those parallel environments with Aspire](/blog/2025/12/16/scaling-ai-agents-with-aspire-isolation)? And eventually discovered I could [try Squad on any repo without even touching it](/blog/2026/02/17/trying-squad-without-touching-your-repo), even controlling it from [my phone with remote access](/blog/2026/02/26/squad-remote-control)?

That journey taught me something fundamental. AI agents aren't just tools. When you give them roles, when they build institutional knowledge through decisions and history files, when they coordinate with each other through routing rules — they stop being assistants. They become teammates.

And for the past few months, I've been running Squad on my personal repos with that mindset. It's been transformative. Ralph watches the issue queue while I sleep. Scribe captures every decision in markdown files that persist across sessions. Picard breaks down tasks and delegates them. Data writes code with full context of our conventions. Seven documents everything as it ships. The team just works, day and night, whether I'm at my desk or not.

But here's the question that kept me up at night: **What happens when you're not the only human?**

Because I don't just work on personal repos. I have a job. At Microsoft. On an infrastructure platform team. With five other engineers who are brilliant, opinionated, and definitely didn't sign up for AI agents making architecture decisions at 3 AM while they're asleep.

My personal repo is a playground where I can experiment. The work repo? That's production systems that real services depend on. We have code review standards. Security scanning requirements. Compliance gates. Deployment processes. A backlog that spans twelve repositories. Could Squad actually work in that environment without causing a revolt?

![Borg cube](/assets/scaling-ai-part1-first-team/borg-resistance-is-futile.jpg)  
*"Resistance is futile. Your work team will be assimilated. Probably."*

## The Problem: Real Teams Have Real Opinions

In my personal repo, I'm the only human. When Picard makes an architecture decision, nobody pushes back. When Data refactors error handling across the codebase, nobody objects. When Seven updates documentation to reflect a new pattern, there's no debate about phrasing. I'm the benevolent dictator, and the AI squad members serve at my pleasure.

But on a real engineering team? That's six humans with different expertise, different preferences, and very legitimate concerns about AI agents touching production code. You can't just drop an AI team into that environment and say "assimilate the backlog." That's not collaboration — that's chaos.

My first instinct was to keep Squad isolated to my personal work. Use it for prototyping, for documentation drafts, for exploratory analysis — but keep the work repo traditional. Let humans handle all the decisions and implementation. It felt safer.

But that approach bothered me. I'd spent months building a system where AI teammates could operate autonomously, accumulate knowledge, and handle complex workflows. Why should that power be limited to repos where I'm alone? The whole point of Squad is that it scales through coordination. A team of seven AI agents plus background workers should be more valuable on a real team, not less.

Then I realized the problem wasn't Squad. It was how I was thinking about Squad. I was treating it as my AI team that would have to work alongside my human teammates. But what if the humans weren't alongside the AI team? What if they were part of it?

## Human Squad Members: The Feature That Changes Everything

This is where Brady Gaster's design really shines. Squad doesn't just support AI agents. It supports human squad members too. Real people, with GitHub handles, assigned to real roles in the team roster. And when work routes to a human squad member, Squad doesn't hallucinate their response or try to approximate what they might say. It pauses. It waits. It pings the human and blocks until they respond.

I added my teammate Brady to the Squad roster as a human member. Not as "someone who reviews Squad's output" but as an actual squad member with a charter, expertise areas, and routing rules.

Here's what that looks like in practice. When Picard (my AI lead) encounters a task that needs architecture review, Squad routes it to Brady (human squad member). Picard drafts an analysis document, lays out the options with tradeoffs, and tags Brady for decision. Squad doesn't proceed until Brady responds. Once he does, the AI squad members pick up the work and implement his guidance.

The AI squad members handle the grunt work: implementing the changes, writing tests, updating documentation, running validation. The human squad member handles the judgment call: which architectural direction to take, which tradeoffs are acceptable, what the long-term implications might be for other teams.

This completely changes the dynamic. Squad isn't replacing my team. It's augmenting it. My teammates don't have to learn how to prompt AI agents or review generated code for hallucinations. They just participate in decisions like they always have — through GitHub comments, through issue discussions, through pull request reviews. Squad integrates into their existing workflow. The only difference is that when they approve a direction, the implementation happens faster because AI squad members are handling the mechanical work.

## Making the Roster: Who Does What

Adding humans to the Squad roster required thinking carefully about roles and responsibilities. I couldn't just mirror our org chart. Squad works best when roles are defined by capability and scope, not by title or seniority.

I added each of my teammates as human squad members with clear charters. One teammate became the human squad member for security reviews — when Worf (AI security agent) finds issues, they route to the human security lead for final assessment. Another became the human squad member for infrastructure — when B'Elanna (AI infrastructure agent) needs to make deployment decisions, she escalates to the human who actually owns those production systems.

I also added myself as a human squad member, not as "the person who runs Squad" but as someone with specific expertise in AI workflows and integration patterns. When the AI squad members encounter something in that domain, they can route to me. But for backend code or infrastructure decisions, they route to the teammates who actually own those areas.

The key insight here is that human squad members have the same structure as AI squad members. They have charters that define their expertise. They have scopes that define what they own. They have routing rules that define when work escalates to them. The only difference is that when a task lands on a human squad member, Squad waits for them instead of executing autonomously.

This symmetry makes Squad legible to the rest of the team. They're not debugging AI behavior or trying to understand why an agent made a weird decision. They're seeing work items assigned to team members — some of whom happen to be AI agents running on Copilot infrastructure — and responding to those assignments like they always have.

## Routing Rules: When AI Pauses for Humans

The routing rules file is where the magic happens. This is where you define when AI squad members work autonomously and when they pause for human squad members. For my work team, the rules break down like this:

Architecture decisions always route to Brady, our engineering lead and a human squad member. When Picard (AI lead) encounters changes to core contracts, API designs, or cross-repository dependencies, he drafts an analysis and tags Brady for approval. The AI squad members don't proceed with implementation until Brady signs off. This ensures that critical structural decisions involve human judgment, while the AI squad members still do the analytical work of surfacing options and tradeoffs.

Security reviews route to our security lead, who's also a human squad member. When Worf (AI security agent) scans code and finds authentication issues, credential handling, or supply chain risks, he generates a report and routes to the human security lead. The human decides whether the risk is acceptable and what mitigations are needed. The AI squad members then implement those mitigations. This gives us continuous security scanning without requiring a human to manually run tools, but keeps human judgment in the loop for actual security decisions.

Code implementation follows a two-tier pattern. For routine changes — bug fixes, test additions, documentation updates — the AI squad members work autonomously and open pull requests for human review like any other contributor. For complex changes — reconciler logic, API layer refactoring, performance-critical code — the AI squad members draft the implementation but route to a human squad member for review before the PR goes live. The human can edit the draft, request changes, or approve as-is.

Documentation has a similar pattern. Seven (AI documentation expert) handles routine doc updates automatically when code changes require them. But for user-facing documentation, architecture decision records, or anything that will be published externally, she drafts the content and routes to me as a human squad member for review before merging. This keeps docs in sync with code without requiring human oversight on every comma, while ensuring high-visibility content still gets human judgment.

The routing rules also handle escalation. If an AI squad member is stuck on a task for more than a defined threshold — say, three attempts at fixing a failing test — the task automatically escalates to a human squad member. This prevents AI squad members from spinning their wheels and ensures humans step in when the problem is genuinely hard.

## What It Feels Like in Practice

Here's what a typical day looks like now. I arrive at my desk in the morning and check the issue tracker. Ralph (our background worker) has already triaged new issues overnight, labeled them according to our taxonomy, and assigned them to squad members — both AI and human. I see several issues assigned to Data (AI code expert) that are already in progress. I see a couple assigned to me as a human squad member that need my judgment.

One of the issues assigned to me is an architecture question. Picard did the analysis overnight, documented three options with tradeoffs, and tagged me for decision. I read through Picard's analysis, leave a comment picking option two with some context on why, and move on. Within minutes, Data picks up the work and starts implementing option two. I don't have to write code. I just made the decision.

Another issue assigned to me is a security finding. Worf scanned a new dependency and flagged a moderate-severity vulnerability with a proof-of-concept exploit. He's already drafted a mitigation plan: upgrade the dependency to a patched version and add input validation at two specific call sites. I review the plan, approve it, and tag back to Worf. He implements the fix, runs the test suite, and opens a PR. I review the PR like any other code change, but the heavy lifting — research, drafting, testing — already happened.

Meanwhile, my teammates are going through similar workflows. Brady approved an architecture decision this morning that Picard had prepared. Our infrastructure lead reviewed a deployment config change that B'Elanna drafted. Our security lead signed off on a threat model that Worf had generated. Everyone's working in their normal GitHub workflow — commenting on issues, reviewing PRs, approving changes. The only difference is that a lot of the implementation work is happening without us writing code ourselves.

The AI squad members also handle cross-repository coordination. When a change in one repository affects downstream repositories, Picard automatically opens tracking issues in those repos, tags the relevant squad members (both AI and human), and creates a rollout plan. Humans approve the plan. AI squad members execute it. What used to take days of coordination across teams now happens in hours, because the mechanical work of opening issues and tracking dependencies is automated.

## The First Real Test: When Humans Catch AI Mistakes

About two weeks into running Squad on the work repo, Data (AI code expert) opened a PR that looked perfect. Clean code, good test coverage, clear commit message. The tests passed. The linter was happy. But when Brady reviewed it as a human squad member, he immediately caught a subtle logic bug. The code assumed a certain order of operations that wasn't guaranteed in our platform's execution model. In production, that would have caused intermittent failures that would be nightmare to debug.

Brady left a comment explaining the issue and suggested a fix. Data re-implemented using a different approach, updated the tests to cover the edge case, and pushed a new commit. The second version was correct. Brady approved and merged.

This was a validating moment. The system worked exactly as designed. The AI squad member did the bulk of the implementation work, freeing Brady to focus on the high-level correctness and architectural implications. When Brady caught the issue, the AI squad member corrected it quickly without getting defensive or needing extensive explanation. The division of labor was clear: AI handles mechanical implementation, humans handle deep correctness.

We've had several more instances like this. Sometimes humans catch issues that AI squad members miss. Sometimes AI squad members catch issues in human-written code. The key is that both are working together as a team, with clear roles and clear escalation paths. Nobody's trying to prove that AI is better than humans or vice versa. We're just using each for what they're good at.

## What Doesn't Work Yet

Squad on a work team isn't perfect. There are clear boundaries we've hit. AI squad members struggle with ambiguous requirements. When an issue says "improve the user experience," a human squad member knows to ask clarifying questions about what specific pain points matter. An AI squad member will pick an interpretation and run with it, which might not be what the stakeholder actually wanted.

AI squad members also don't understand organizational politics. When a feature request comes from a senior leader, a human squad member knows that's different from a nice-to-have suggestion from a junior engineer. The AI squad members treat them identically, which is technically fair but politically naive. We've learned to have human squad members triage issues that involve stakeholders before assigning them to AI squad members.

Production incidents are another area where AI squad members provide value but can't replace humans. When a system goes down at 2 AM, Ralph can gather logs, correlate recent changes, and surface likely root causes. But the final diagnosis and the mitigation decision require human judgment. The on-call engineer makes the call. The AI squad members execute the fix once the decision is made.

Despite these limitations, the value is undeniable. Our team ships faster. Code review latency is down because AI squad members pre-screen PRs. Test coverage is up because AI squad members generate scaffolding. Documentation stays in sync because AI squad members catch drift automatically. And most importantly, human squad members spend more time on the work that actually requires human judgment — architecture, design, stakeholder management, mentoring — and less time on the mechanical work that AI squad members can handle.

## What's Next: From One Team to Many

This post covered a single team with a single Squad: human squad members and AI squad members working together in one repository. But my organization has dozens of teams, hundreds of repositories. What happens when multiple teams adopt Squad? Do they each build isolated AI teams, or do they share knowledge?

And what about organizational standards — coding conventions, security policies, architectural patterns — that should apply across all teams? Can Squad in one team learn from Squad in another team? Can institutional knowledge propagate across squad boundaries?

In Part 2, I'll cover Squad upstreams: how we're building a hierarchy of shared knowledge across teams, so that organizational context propagates down to every Squad without manual copy-paste. From personal repo to work team (this post) to organizational scale (coming next).

The assimilation continues. 🖖

---

> 📚 **Series: Scaling AI-Native Software Engineering**  
> - **Part 1**: From Personal Repo to Work Team — Bringing Squad to Production ← You are here  
> - **Part 2**: Coming soon — Organizational Knowledge for AI Teams

## Related Posts

- [Trying Squad Without Touching Your Real Repo](/blog/2026/02/17/trying-squad-without-touching-your-repo)
- [Squad Remote Control — Your Copilot CLI on Your Phone](/blog/2026/02/26/squad-remote-control)
- [Scaling AI Agents with Aspire](/blog/2025/12/16/scaling-ai-agents-with-aspire-isolation)
- [Give Your AI Coding Agent Eyes with Playwright MCP](/blog/2025/11/17/give-your-ai-coding-agent-eyes-with-playwright-mcp)
- [Scaling Your AI Development Team with Git Worktrees](/blog/2025/10/20/scaling-your-ai-development-team-with-git-worktrees)
