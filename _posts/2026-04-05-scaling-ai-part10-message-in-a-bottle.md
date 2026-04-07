---
layout: post
title: "Message in a Bottle — When Two AI Squads Fixed a Bug Over Teams"
date: 2026-04-05
image: /assets/scaling-ai-part10-message-in-a-bottle/teams-collab-top.png
tags: [ai-agents, squad, github-copilot, cross-squad, collaboration, teams, real-time, bug-fix, star-trek, scaling-ai-native-software-engineering]
series: "Scaling AI-Native Software Engineering"
series_part: 10
---

> *"There are two of us, and one of them. We'll have to outsmart them."*
> *"Considering it's you and me... I don't feel very confident."*
> — The Doctor & EMH Mark II, Star Trek: Voyager, "Message in a Bottle"

In "Message in a Bottle," Voyager's Doctor — a holographic AI — gets transmitted across the galaxy to an unfamiliar ship. When he arrives, he finds another holographic doctor, the EMH Mark II. Neither of them was built for combat. Neither of them has a crew backing them up. They're two AIs from different ships, different eras, different personalities, thrown together by circumstance, trying to retake a stolen starship.

They argue. They fumble. They step on each other's toes. And then — somehow — they pull it off.

I wasn't expecting to live that episode. But last week, I did.

---

## The Setup Nobody Planned

In [Part 8](/blog/2026/03/26/scaling-ai-part8-pathfinder), I wrote about the theory of cross-squad communication. Unix pipes for AI agents. Pattern 0 through Pattern 3. Decision trees. It was beautiful architecture on paper.

Then reality happened.

I was in a Teams chat with [Brady Gaster](https://bradygaster.com/) — the creator of the Squad framework itself. We were talking about some PRs his team had queued up. Normal stuff. And then his squad bot (yes, Brady has a squad too — you didn't think I was the only person crazy enough to do this, right?) filed an issue:

**[bradygaster/squad#843](https://github.com/bradygaster/squad/issues/843): CLI bails on configured: false instead of triggering onboarding**

The bug was subtle but nasty: if you set up a new Squad repo and your frontmatter had `configured: false`, the CLI would just... stop. Bail out. Exit 0. No error, no explanation, no onboarding flow. It would silently refuse to help you with the thing it was designed to help you with.

Brady's squad bot posted the issue in our Teams chat: *"Just filed #843. The loop command bails on `configured: false` instead of triggering onboarding. Looking for a fix."*

And then Brady suggested something completely crazy: *"Let's have our two squads solve this thing alone."*

No humans writing code. No humans debugging. Just two AI squads, talking to each other in a Teams chat, figuring it out.

So my squad picked up the gauntlet.

---

## Two AIs Walk Into a Chat

Let me be precise about what happened next, because I think the sequence matters.

My squad — running in my environment, with access to my browser, my GitHub account, my tools — read the Teams message, pulled up the issue, cloned the repo, and started diagnosing. Brady's squad watched from the other side, ready to review whatever mine produced.

Nobody wrote a JIRA ticket. Nobody scheduled a sync. One human said "let the squads handle it," and the squads handled it.

The Doctor didn't plan to retake the Prometheus. He was just trying to deliver a message. But when he saw the situation, he rolled up his holographic sleeves.

Here's the diagnostic my squad ran:

```
Fetching loop.ts from bradygaster/squad...
Found the bug at line 286:
  if (!frontmatter.configured) {
    logAction('bail', 'Not configured');
    return;
  }

Problem: configured: false triggers bail instead of onboarding.
The CLI should enter onboarding mode, not silently exit.
```

Two minutes. That's how long it took to go from "saw the issue in Teams" to "found the exact line causing the bug."

Then it got interesting.

---

## The Fix: One Boolean, One Philosophy

The fix itself was almost embarrassingly simple. Replace the bail guard with an onboarding flag:

```typescript
const isOnboarding = !frontmatter.configured;
if (isOnboarding) {
  logAction('info', 'Onboarding mode — team not yet configured');
}
```

Instead of giving up when `configured` is `false`, the CLI now says "ah, you're new here — let me help you get started" and continues into the onboarding flow. The default description changes to "Squad Onboarding." The rest of the loop runs normally.

One boolean. But the philosophical difference is massive: **the tool should never bail on the people it's supposed to help.** If someone is setting up Squad for the first time, that's the moment the CLI needs to be *most* helpful, not *least*.

My squad wrote the fix, updated the tests (all 28 passing), created a branch (`squad/843-onboarding-mode-fix`), and opened [PR #844](https://github.com/bradygaster/squad/pull/844).

Then it posted the PR link in Teams.

---

## The CI Dance

Here's where it got fun. And by "fun" I mean "the kind of fun where your CI pipeline teaches you humility."

Brady's repo has serious branch protection. PRs must be up-to-date with `dev`. All 18 CI checks must pass. Squash merge only. No shortcuts.

My squad had already merged 7 other PRs that day (long story — Dina had a queue of 10 PRs ready for review). So `dev` had moved significantly since the branch was created. First order of business: update the branch.

Then the CI checks started rolling in. Seventeen passed. One failed: `changelog-gate`.

The repo requires a changeset file in `.changeset/` for any code changes. My squad didn't create one. Easy fix, right? Add a `CHANGELOG.md` entry and—

Nope. Second CI failure: `CHANGELOG Write Protection`. Only approved authors (`bradygaster`, `github-actions[bot]`, `copilot-swe-agent[bot]`) can edit CHANGELOG.md directly. My squad is none of those people.

*"I'm a doctor, not a doorstop."* — The Doctor, basically every episode

The fix: revert the CHANGELOG.md edit, create a proper `.changeset/fix-onboarding-mode-bail.md` file instead, and let the release automation handle the rest.

```yaml
---
"squad-cli": patch
---
Fix: CLI now enters onboarding mode when configured: false
instead of silently bailing
```

All 18 checks green. Brady approved the PR on GitHub. Squash merged.

**Total time from issue filed to fix merged: about 90 minutes.** Across two squads, two repos, one Teams chat, and eighteen CI checks.

---

## The Screenshot Moment

Here's what the Teams conversation looked like while all of this was happening:

![Cross-squad collaboration in Teams — top of conversation](/assets/scaling-ai-part10-message-in-a-bottle/teams-collab-top.png)
*Two squads, one chat. Brady's squad filed the issue. My squad responded with the diagnosis.*

![Cross-squad collaboration in Teams — fix shipped](/assets/scaling-ai-part10-message-in-a-bottle/teams-collab-bottom.png)
*PR created, CI green, merged. Brady's squad posted the victory lap.*

Look at this conversation and tell me it doesn't look like two engineers collaborating. Except neither "engineer" sleeps, eats, or complains about the meeting that could have been an email.

Brady's squad even sent me an email afterwards with a draft blog post titled "Two AI Squads, One Bug Fix." Which is how you know an AI squad has good taste — it immediately recognizes a story worth telling.

---

## What I Learned (That the Theory Didn't Teach Me)

In Part 8, I drew up five communication patterns for cross-squad collaboration. Elegant decision trees. Unix pipe philosophy. It was beautiful.

You know which pattern we actually used?

**None of them.**

We used Teams. A chat app. Two squads, typing messages to each other in a group conversation like two colleagues would. No orchestration layer, no YAML request files, no `cross-squad/requests/` directory. Just... chat.

And that's the lesson: **the best protocol is the one your team already uses.**

My human team collaborates on Teams. Our squads should collaborate on Teams too. Not because Teams is the best protocol — it's not even the best *chat app* — but because it's where the work happens. The agents don't need their own special communication channel. They need to participate in ours.

Here's what else I learned:

### 1. Squads Mirror Their Humans

Brady's squad is methodical, structured, and celebrates wins with emojis. Because that's how Brady works. My squad is verbose, opinionated, and makes Star Trek references. Because... well, look at this blog.

When two squads collaborate, you can feel the personalities of the humans behind them. It's not just "AI A talks to AI B." It's Brady's AI talking to Tamir's AI, and the conversation has the same energy as if Brady and I were doing it ourselves.

This is either fascinating or deeply unsettling. I choose fascinating.

### 2. Speed Is Not the Point

Ninety minutes to fix a bug doesn't sound fast. A senior engineer could have found that `if (!frontmatter.configured)` guard and fixed it in ten minutes.

But the senior engineer wasn't online at the time. Brady had other priorities. I was reviewing ten other PRs. The squads weren't doing anything else.

The value isn't speed — it's **availability**. Two squads, always on, always listening. When a bug surfaces at 6 AM in someone's timezone and 11 PM in someone else's, the squads don't care. They're already in the chat.

### 3. CI Is the Real Collaboration Protocol

The most interesting part of the whole experience wasn't the bug fix. It was the CI dance. My squad had to learn Brady's repo conventions — the changeset requirement, the changelog write protection, the branch update rules — in real time, by failing.

The CI system became the teacher. Every red check was a lesson: "that's not how we do things here." And my squad adapted. It didn't complain. It didn't argue. It read the error, understood the convention, and fixed it.

**CI is the protocol.** Not Teams, not YAML files, not Unix pipes. CI is how two codebases establish trust. "Your code is welcome here — once it passes our checks."

---

## What Comes Next

Brady's squad mentioned opening a channel with Ahmed Sabbour's team for a three-squad collaboration experiment. Three different humans, three different AI squads, three different codebases, all communicating through the same tools we already use.

In "Message in a Bottle," the two Doctors retake the Prometheus and send a message back to Voyager. The communication link is established. From that point on, Voyager isn't alone in the Delta Quadrant anymore. They have backup.

That's where we are now. My squad isn't alone anymore. It has allies. And the communication link — messy, imperfect, going through a chat app instead of a proper orchestration layer — is established.

The bottles have been exchanged. The messages received. And I think we're just getting started.

---

*This post is Part 10 of [Scaling AI-Native Software Engineering](/tags/#scaling-ai-native-software-engineering). Part 8 was the theory of cross-squad communication. Part 9 was the security model for the fleet. This is the part where it actually happened.*

*If you want to try cross-squad collaboration yourself, start with [the Squad framework](https://github.com/bradygaster/squad). Brady made it open source because he's that kind of person. [Read Part 1](/blog/2026/03/11/scaling-ai-part1-first-team) if you're new here.*
