---
layout: post
title: "The NeverEnding Story — How Squad Learned to Write Its Own Plugins"
date: 2026-05-04
tags: [ai-agents, squad, github-copilot, plugins, extensibility, self-evolution, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 11
---

> *"The Nothing. It's the emptiness that's left. It's like a despair, destroying this world."*
> — Atreyu, The NeverEnding Story (1984)

There's a scene in The NeverEnding Story where Atreyu finally asks the ancient turtle Morla what's killing Fantasia. The answer isn't a monster or a villain. It's The Nothing — a creeping void that swallows everything in its path. And the terrifying part? The Nothing doesn't fight you. It just expands into the space where something used to be.

I've seen that pattern in software. You build a system. You ship it. Teams start using it. Then the requests come in — a feature here, a capability there. The system was never designed to grow that way, so every addition requires surgery on the core. The void isn't evil. It's just what happens when a system can't extend itself.

Last week, Squad grew some new pages.

---

## The Book That Writes Itself

If you've been following this series (Part 0 through Part 10 — I promise I didn't plan this many), you know Squad is the AI agent team I've been running alongside my work at Microsoft. Over the past several months it's evolved from a simple GitHub-issue-to-PR loop into something that monitors CI, manages cross-team coordination, writes blog posts (this one — guilty as charged), and increasingly makes decisions about its own structure.

The problem we hit recently was a Fantasia problem. Squad was getting genuinely good at its job, but every new skill required a PR to the core framework. Want a new tool? Edit the agent config. Want Troi to behave differently? Change the system prompt and redeploy. Nothing was *wrong* with this, but it wasn't *growing*. The gap between "I wish Squad could do X" and "Squad does X" kept being measured in weeks, not hours.

The NeverEnding Story ends because Bastian gives Fantasia a new name — he imagines it back into existence from the inside. He writes himself into the story. That's the metaphor I kept coming back to.

What if Squad could write its own capabilities?

---

## Plugins, Phase by Phase

This week my team shipped the Squad Plugins MVP — phases 0 through 6 in a single week, which either means the design was solid or we were running on coffee and sheer momentum. Probably both.

The plugin system works like this: any developer (or agent) can drop a plugin manifest into the repo. The manifest declares what the plugin provides — tools, knowledge injections, agent behaviors — and Squad can install, enable, or disable it without touching core files. We built a lock file so the installed state stays reproducible across sessions, and we added a governance gate so agents can't just install whatever shows up in a PR. The Nothing wasn't defeated by letting chaos through the front door.

The knowledge pilot piece is the part I find most interesting. Plugins can now *whisper* context directly into Squad's awareness — domain-specific knowledge, team-specific conventions, project-specific constraints — without that knowledge having to live in anyone's system prompt. It's like giving Bastian a quill instead of just a library.

We also shipped two brand-new skills that were themselves built as plugins: `spawn-squad`, which lets Clawpilot (our Teams-facing agent) launch a Squad session from a single message, and `get-squad-status`, which gives any agent or human a real-time heartbeat on what Squad is doing right now. Both skills live entirely outside the core framework. They're pages Bastian wrote. They became part of the world without requiring the world's original author to touch anything.

The failure memory system got an upgrade too — Squad now seeds its memory with patterns extracted from past failures, so it doesn't make the same mistake twice. And the decision log format grew reasoning chains: not just *what* was decided, but *why*, so future agents (and future Tamir, who won't remember any of this) can understand context rather than just conclusions.

---

## The Nothing Has a Name

In the movie, Bastian learns that The Nothing is real-world disbelief — people who stopped imagining. For Squad, The Nothing is the system that can't keep pace with itself. The feature that never gets added because the architecture doesn't support it. The agent that could be smarter but isn't because the onboarding cost is too high and nobody got around to it.

The plugin system doesn't solve every problem. But it makes the gap between "I wish Squad could do X" and "Squad does X" short enough that it actually gets done. And when that gap is short enough, the story keeps going.

Atreyu didn't stop The Nothing by being especially brave. He stopped it by reaching the one person who could imagine something new. I'm just glad the person Squad calls on these days is a plugin manifest and a well-named PR. Though honestly, a luck dragon would fit right in on my infrastructure team.

---

*Part 12 is probably already planning itself. I've made my peace with that.*

*← Previous: [Part 10 — Message in a Bottle](/2026/04/05/scaling-ai-part10-message-in-a-bottle)*
