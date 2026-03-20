---
layout: post
title: "The Switchboard — Teaching My AI Squad to Email, Chat, and Know When to Shut Up"
date: 2026-07-15
tags: [ai-agents, squad, teams, email, microsoft-graph, communication, routing, whatsapp]
series: "Scaling AI-Native Software Engineering"
series_part: 6
---

> *"Hailing frequencies open."*
> — Lt. Uhura, every single episode

There's a moment in the evolution of any communication system where things go from "this is great" to "I can't hear myself think." For Uhura, it was keeping the Enterprise's subspace communications straight — which signal goes to Starfleet Command, which goes to the Klingon High Council, and definitely which does not accidentally get broadcast on all frequencies simultaneously.

For me, it was the day my AI squad blasted a message containing internal GitHub issue links — links to a private repo that 95% of the recipients had no access to — into a public Teams channel belonging to someone else's team.

Brady Gaster's team.

This is the story of how Squad learned to communicate. And more importantly, how it learned *where* to communicate.

---

## How We Got Here

In [Part 1](/blog/2026/03/11/scaling-ai-part1-first-team), I gave Squad a voice. Agents could open GitHub issues, leave comments, create PRs. Text to text, developer to developer. Clean.

In [Part 3](/blog/2026/03/18/scaling-ai-part3-unimatrix), they got louder. Ralph started sending Teams alerts when things broke. A webhook URL, a `Invoke-RestMethod`, and suddenly I had a squad that could tap me on the shoulder from the machine room.

In [Part 4](/blog/2026/03/20/scaling-ai-part4-patterns), we nearly lost our minds when that shoulder-tapping turned into a constant crowd of people all shouting at once. Every notification went to one channel. Tech news. Build failures. PR reviews. Birthday reminders. "Ralph had 3 consecutive failures." Everything. One channel. A single firehose.

That's when I realized: **my squad could talk, but they had no idea to whom, and through what channel.**

The fix involved three distinct communication systems, a routing layer, and one genuinely embarrassing incident that I am now going to share with the internet.

---

## The Three Channels

Before I get to the incident, let me lay out the communication architecture. Because it's not obvious — and getting it wrong is what caused the problem.

Squad communicates through three systems, each with different audiences, different latencies, and very different privacy models.

### 1. Email (Kes + Outlook COM)

Email is for humans. Real humans, not agents. When I need to send a meeting invite, follow up on a conversation, or reach someone outside of Teams, Kes handles it.

The first version of email automation involved Playwright — launching an Edge browser, loading Outlook Web, waiting for React to hydrate (I will never not mention this), clicking the compose button, typing the address, hoping the autocomplete dropdown appeared before the script timed out. Twenty-five minutes, 70% reliability. I automated email and it was slower than just writing the email myself.

The second version used Outlook COM automation. Two seconds. 99%+ reliability.

```powershell
$outlook = New-Object -ComObject Outlook.Application
$mail = $outlook.CreateItem(0)  # 0 = olMailItem
$mail.Subject = "Squad Update: 3 PRs merged, 1 security finding"
$mail.Body = $body
$mail.Recipients.Add("Brady Gaster")  # Global Address List resolves this automatically
$mail.Recipients.ResolveAll()
$mail.Send()
```

The killer feature here is `ResolveAll()`. You pass a name, and the Global Address List resolves it to the full corporate email. No guessing. No copy-pasting email addresses into prompts. Kes knows to say "Brady Gaster" and the system figures out the rest. It's the same magic that's always been in Outlook's To: field — I just automated the part that used to require a human to type.

Calendar invites work the same way. Five lines of PowerShell. One COM call. Done. Kes has become my defacto meeting scheduler — she books the time, sends the invite, handles reschedules. I review the calendar and occasionally add a note. That's the entire workflow.

**What email is good for:** Formal communications. External people. Structured deliverables that benefit from an email thread. Anything that needs a paper trail the recipient controls.

**What email is bad for:** Real-time notifications. Agent-to-agent coordination. Anything that needs to happen in under 60 seconds.

### 2. Teams (Three Ways, Very Different)

Teams is more complicated. Here I have three entirely different integration points, and using the wrong one has consequences.

**Webhooks — the hammer**

The simplest thing that works. A URL in `~/.squad/teams-webhook.url`, one `Invoke-RestMethod`, a MessageCard payload. Works from any PowerShell script, any context, no auth required beyond knowing the URL.

```powershell
$webhookUrl = (Get-Content "$env:USERPROFILE\.squad\teams-webhook.url" -Raw).Trim()
$body = @{
    "@type"      = "MessageCard"
    themeColor   = "FF0000"
    title        = "⚠️ Ralph Watch Alert"
    sections     = @(@{
        activityTitle = "3 consecutive failures detected"
        facts = @(
            @{ name = "Round";              value = "42"  }
            @{ name = "Last Exit Code";     value = "1"   }
        )
    })
} | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri $webhookUrl -Method Post -Body $body -ContentType "application/json"
```

Ralph uses this for failure alerts. Neelix uses it for broadcast updates. The scheduler uses it for task failures. It's outbound-only — you can post to Teams, but you can't read from Teams this way. And critically: one webhook URL points to one channel. Which brings us to the problem I'll get to in a minute.

**Teams MCP Server — the scalpel**

When agents run inside a Copilot CLI session with the Teams MCP server configured, they have real bidirectional tools: read channel messages, post to specific channels, manage chat threads. More powerful than webhooks, requires more setup, doesn't work from standalone scripts.

I use this for Neelix's daily briefings — where I want him to check what's already been posted, avoid repeating yesterday's news, and deliver to the right channel with context about what happened in that channel already.

**WorkIQ — the periscope**

Query mode only. WorkIQ lets agents scan M365 data — Teams messages, emails, calendar events — for signals that need a response. Every Ralph round includes a WorkIQ query asking: "Any Teams messages in the last 30 minutes that mention me, my squad, or action items I should know about?" If someone tags me in a Teams message, Ralph turns it into a GitHub issue so it doesn't get lost.

The table that matters:

| Method | Direction | From Scripts? | Auth |
|--------|-----------|---------------|------|
| Webhook | Outbound only | ✅ | URL is auth |
| Teams MCP | Bidirectional | ❌ (needs session) | OAuth |
| WorkIQ | Read-only | ❌ (needs session) | Session token |

**What Teams is good for:** Real-time notifications, team visibility, conversations about work that's happening now.

**What Teams is bad for:** Anything where the audience is unclear.

That last point is where things went sideways.

### 3. WhatsApp (The Family Channel)

This one is a bit different. I'm not using WhatsApp to communicate with my engineering team. I'm using it to monitor the one communication channel my family actually uses.

The wa-monitor-dotnet process runs continuously, watching WhatsApp for signals I need to act on. Priority contacts — my wife Gabi, my kids Yonatan and Shira — get flagged for anything that looks like a printing request. When one of them sends a file for printing, the monitor emails it to my HP ePrint printer at home.

```
Input: WhatsApp message with attached PDF
→ Monitor detects priority contact + file
→ Creates GitHub issue: "print request from Gabi"
→ Kes picks it up, emails file to dresherhome@hpeprint.com
→ Printer starts in the physical world
→ Issue closed
```

It sounds absurdly over-engineered. My family sends me a file on WhatsApp and a GitHub issue gets created. An AI agent emails my printer. But the alternative was: forget to print it, remember after I'm already in the car, send an embarrassing "sorry, forgot to print that" message. This is better. The Squad doesn't forget.

General chats — anything that seems like something I should know about — get forwarded to Teams so I have them in one place. The Squad is my attention filtering layer. The volume of incoming signals is real; the bot decides what surfaces and what doesn't.

---

## The Brady Incident

Now for the part I promised.

When I first started sending Squad notifications to Teams, I had one webhook. One URL. One channel: `tamir-squads-notifications` in the "squads" team. Clean, simple, everything in one place.

Then the volume grew. Thirty notifications a day became fifty. Tech news briefings. PR merge summaries. Build failures. Ralph health checks. They all landed in the same channel. I started ignoring them. Which defeats the entire purpose.

The fix was obvious in retrospect: route by type. Create dedicated channels. Tech news in "Tech News." Failure alerts in "Alerts." PRs in "PR and Code." This is the pub-sub pattern — topics, not a monolithic queue.

So I created the channels. Tested the routing. Everything looked right.

What I missed: there were **two teams** in my Teams environment with nearly identical names.

- "squads" — my personal AI squad team. Seven channels. Just me.
- "Squad" — Brady Gaster's team for the actual Squad product he's building at Microsoft. Real people. Active channel.

When Neelix posted the first routed tech news briefing, the routing code matched "Squad" before "squads." The message — which included GitHub issue links from my private repository — landed in Brady's team's "Tech News" channel.

Brady's team saw a "Tech News" briefing from my AI squad. With links they couldn't open. About issues they didn't know existed. In a product context where "squad" is a real noun with real meaning.

I got a very polite Teams message from one of Brady's teammates: *"Hey, is this for us? I can't open these links."*

I can't open these links.

The links went to private GitHub issues in a private repository. Zero context for anyone outside my personal workflow. They were reading my squad's internal engineering feed because a string-match on "Squad" resolved to the wrong team.

This is the **service discovery problem** in the flesh. DNS has been solving this for decades: when you type `google.com`, you want *Google's* servers, not some other host that happens to have "google" in its hostname. The lesson every distributed systems engineer learns at some point: names that look similar will route traffic to the wrong destination, and the wrong destination might be a public-facing endpoint.

I fixed it the same way DNS fixes ambiguity: with explicit identifiers.

```json
{
  "teamId": "5f93abfe-b968-44ea-bd0a-6f155046ccc7",
  "teamName": "squads",
  "channels": {
    "general":    { "channelId": "19:6gjjSHAUPHJlqyxeJemN9giR8HYZkWGpvsznRDSyagE1@thread.tacv2" },
    "tech-news":  { "channelId": "19:bfe3224e8e764c2785e81e7cb3cc944d@thread.tacv2" },
    "alerts":     { "channelId": "19:fdd6d4b44a434ffe80a9029e14b7c2c2@thread.tacv2" },
    "wins":       { "channelId": "19:11bc8c3520284596b1ea2f6701b777fa@thread.tacv2" },
    "pr-code":    { "channelId": "19:4d7b7376bace4d42868f20a422fecc6f@thread.tacv2" }
  }
}
```

No more string matching. Every channel is referenced by its immutable ID, resolved once when you set up the config, never re-resolved at runtime. If the team renames itself tomorrow, the routing still works. Channel IDs don't change.

The webhook fallback — the legacy one-URL-does-everything approach — is still there for when agents don't have MCP access. But when they do, they post by channel ID. Explicit. Unambiguous. Brady's team's channel is nowhere in my routing config.

---

## The Routing Layer

The actual solution has two parts: a routing map that classifies messages by type, and a resolution layer that turns classification into a specific channel.

Here's the routing map from `notification-routes.json`:

```json
{
  "routing": {
    "wins":       ["merged", "closed", "milestone", "celebration", "shipped"],
    "alerts":     ["error", "failure", "blocked", "urgent", "stall", "health"],
    "pr-code":    ["PR", "review", "CI", "build", "deploy", "pipeline"],
    "research":   ["research", "analysis", "report", "findings"],
    "tech-news":  ["tech news", "hacker news", "industry", "trending"]
  }
}
```

Agents tag their notifications with `CHANNEL:` metadata. "Ralph had 3 consecutive failures" gets tagged `CHANNEL: alerts`. "PR #423 merged" gets tagged `CHANNEL: wins`. Neelix's morning briefing gets tagged `CHANNEL: tech-news`.

The channel key maps to the explicit channel ID in `teams-channels.json`. Nothing routes by name. Everything routes by ID.

The result: I actually read my Teams notifications again. "Wins and Celebrations" is a feed I look at with genuine interest — it's where I see what the squad accomplished today. "Alerts" I check when something feels wrong. "Tech News" I browse over coffee. "PR and Code" I check during review windows. Separate signals, separate contexts, separate mental modes.

That's the pub-sub insight, restated for communication: **the value of a message is partly determined by where it lands.** A great announcement that lands in the wrong channel is noise. The same announcement in the right channel is signal.

---

## Privacy and the Public/Private Boundary

The Brady incident surfaced a second problem I hadn't thought through: **my squad's internal communications have no concept of audience scope**.

When Neelix writes a tech news briefing, it includes context about what my squad is working on. Issue numbers. PR links. Internal decisions. Things that are fine for me, my machine, my private repos — but not fine for a shared channel with external visibility.

The fix I haven't fully implemented but am working toward: Neelix gets a `AUDIENCE` tag alongside the `CHANNEL` tag. Internal-only content goes only to channels I own. Content safe for broader audiences can route to shared channels.

In practice this means:
- "PR #423 merged in tamirdresher/squad-tools" → `CHANNEL: wins, AUDIENCE: private` → stays in my squads team
- "New Helm chart pattern from Brady's repo we should adopt" → `CHANNEL: tech-news, AUDIENCE: shared` → can go to Brady's tech news channel too

The Brady team's channel ID is actually in `teams-channels.json` — there's a note that his "Squad Tech News" channel should receive the same tech news as my tech news channel. That's an intentional sharing of *public* tech news content. It was the accidental sharing of *private* issue URLs that caused the problem. Audience scope is the missing discriminator.

---

## What Good Communication Actually Looks Like

When all three systems are working together — and properly routed — here's what a productive morning looks like from the Squad's communication side:

**7:00 AM** — Neelix's morning briefing arrives in "Tech News." Five items from the overnight Hacker News scan, two from engineering blogs I follow. Zero internal links. Completely safe for any audience. I read it with coffee.

**8:23 AM** — WhatsApp monitor detects a message from Gabi: file for printing. GitHub issue created. Kes emails the file to the printer. Issue closed. Gabi assumes I'm on top of things (I am; I just outsourced the mechanism).

**9:47 AM** — Ralph's round produces a security finding. Routes to "Alerts." I see it immediately because "Alerts" is high-signal. I triage it in 2 minutes — it's a false positive, Worf already flagged it as such.

**11:15 AM** — Three PRs merged. "Wins and Celebrations" shows a 🎉 emoji storm. Data, B'Elanna, and Seven all shipped. I add a 👍 and move on.

**2:30 PM** — A colleague tags me in a Teams message: "question about the squad setup." WorkIQ surfaces it in Ralph's next round. Ralph creates a GitHub issue: "Teams message from [colleague], action item: respond to squad setup question." It doesn't get lost.

Everything reached me. Nothing reached the wrong person. No internal links ended up in Brady's channel. That's the goal — not silence, not noise, but *signal*.

---

## The Abstraction We're Building Toward

There's a pattern underneath all of this that I want to name: **squad agents need a communications layer with the same properties we demand from distributed systems**.

When you design a microservices architecture, you don't let services call each other directly. You introduce message brokers, service meshes, routing rules. Why? Because direct coupling is brittle. Because routing rules let you change destinations without changing senders. Because you need to know, at any point in time, what traffic is going where.

My squad's communication layer is converging on the same architecture. Agents don't decide where to send messages. They tag messages with type and audience. The routing layer resolves type + audience to a specific channel ID. The channel ID is the stable endpoint, not the name.

```
Agent → Tag(type=alert, audience=private) → Router → teams://channelId/19:fdd6...
Agent → Tag(type=tech-news, audience=public) → Router → teams://channelId/19:bfe3...
Agent → Tag(type=email, recipient=name) → Kes → Outlook COM → GAL → send
Agent → Tag(type=family, trigger=print) → WA Monitor → HP ePrint
```

Each output channel has a receiver. Each receiver has an audience. The routing layer makes the mapping explicit, testable, and auditable.

I still don't have this fully automated. The audience tagging is manual right now — I add it to Neelix's charter when I need to. The privacy boundary enforcement is aspirational. But the bones are there.

And more importantly: nobody from Brady's team is seeing my private issue links anymore.

---

## The Lesson Uhura Would Recognize

Uhura didn't just open hailing frequencies. She routed them. Captain's log to Starfleet Command. Distress signals to the nearest vessel. Diplomatic communiqués to the right ambassador, on the right channel, in the right codec.

The mistake I made wasn't sending a message. It was not thinking about where it was going.

Every time I've given Squad a new communication capability, the first version was undifferentiated. One webhook URL. One channel. Everything goes here. And every time, that evolved into routing, specialization, and audience awareness.

Email got COM automation and GAL resolution. Teams got per-type channels and per-channel IDs. WhatsApp got priority contacts and audience filtering. The pattern keeps repeating: **communication primitives are easy; routing is the hard part.**

The next time you're building a system that sends notifications, skip straight to the routing layer. Don't start with "how do I send a message." Start with "who should receive this, under what conditions, and what should they *not* receive."

The answer to that question is half your architecture.

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [First Contact — Building a Crew That Codes](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [Assimilation — Scaling to a Real Engineering Team](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — When Your AI Squad Becomes a Distributed System](/blog/2026/03/18/scaling-ai-part3-unimatrix)
> - **Part 4**: [The Patterns Emerged — Distributed Systems, Rediscovered](/blog/2026/03/20/scaling-ai-part4-patterns)
> - **Part 5**: [Knowledge is Power — How Squads Remember](/blog/2026/04/01/scaling-ai-part5-knowledge)
> - **Part 6**: The Switchboard — Teaching My AI Squad to Email, Chat, and Know When to Shut Up *(this post)*
