---
layout: post
title: "I Let AI Produce My Entire Hackathon Demo Video — Here's How"
date: 2026-03-06
tags: [ai-agents, github-copilot, video-production, edge-tts, remotion, ffmpeg, cli-tunnel, hackathon]
---

I needed a demo video for my Hackathon 2026 project — an internal CLI tool at Microsoft. Twelve commands, live terminal recordings, synchronized narration, animated title cards, the whole thing. Instead of spending hours in a video editor, I had my AI agent produce everything end-to-end. The final video was rendered, narrated, and delivered to my OneDrive — all while I watched from my phone via Teams.

The technique works for **any** CLI tool or terminal-based demo. Here's the full pipeline.

## The Challenge

I had a dotnet CLI tool with 12 commands to demo. Each command needed to run interactively in a real terminal — not a static screenshot. And I wanted AI narration explaining each step as it happened. Manual video editing? No thanks.

## Step 1: CLI Tunnel — AI Typing Into a Real Terminal

The first problem: how does an AI agent execute commands in an interactive terminal it can see? My agent runs in GitHub Copilot CLI, but I needed it to type commands into a **separate** PowerShell window that I was screen-recording.

The answer was [CLI Tunnel](https://github.com/tamirdresher/cli-tunnel) — a tool I built that exposes a local terminal via a web UI. My agent connected to it using the Playwright MCP server (browser automation), navigated to the tunnel URL, and literally typed commands character by character into the terminal input field.

![CLI Tunnel connected](/assets/ai-produced-demo-video/cli-tunnel-connected.png)

The workflow:
1. I start CLI Tunnel in a PowerShell window: `cli-tunnel`
2. I start screen recording that window with OBS/Clipchamp
3. My AI agent connects via Playwright to `http://127.0.0.1:{port}?token={token}`
4. Agent types each command, waits for output, then moves to the next

The agent had a 12-step script with precise timing — wait for prompts, handle interactive selections (like choosing options from a list or confirming installs), and verify output before proceeding.

**This works for any CLI tool** — npm, dotnet, pip, kubectl, terraform — anything you'd type in a terminal. The AI sees the web UI, types the command, reads the output, and decides what to do next.

## Step 2: Recording — 12 Takes and Counting

Getting a clean recording was harder than expected. Over 12 attempts, we hit:

- **Stale binaries**: The globally installed tool was running an old version, not the one I just fixed. The agent had to replace the DLL inside the global tool store directly.
- **Plugin conflicts**: A marketplace plugin was "already registered," causing errors. We fixed the source code to treat that as success.
- **Discovery bugs**: One command couldn't find the project when multiple candidates existed. We added interactive selection.
- **Hidden files**: Previous project files blocked creating a fresh project from template.

Each fix was committed, pushed, and the agent rebuilt the binary — all without me touching the keyboard. The final run (take 12) captured all 12 commands cleanly.

## Step 3: Edge TTS — Free AI Narration

For voiceover, I used Microsoft's [Edge TTS](https://github.com/rany2/edge-tts) — a Python package that gives you access to the same neural voices as Microsoft Edge's Read Aloud feature. Free, no API key, excellent quality.

```python
import edge_tts

communicate = edge_tts.Communicate(
    "Meet the CLI tool.",
    "en-US-GuyNeural",
    rate="+22%"
)
await communicate.save("segment.mp3")
```

The key insight was **per-segment generation**. Instead of one long narration track, I generated 14 individual audio clips — one per command — each timed to match the video timestamps.

To figure out the timestamps, I extracted one frame per second with ffmpeg, then analyzed frame file sizes — large files mean content on screen, small files mean a cleared terminal. This gave me precise boundaries for each command segment without manual timecoding.

## Step 4: FFmpeg — The Audio Swiss Army Knife

[FFmpeg](https://ffmpeg.org/) handled all the audio processing:

**Silence-padded mixing** — each TTS segment was delayed to its start time and mixed together:

```
ffmpeg -i seg_00.mp3 -i seg_01.mp3 ... -filter_complex
  "[0]adelay=0|0[s0];[1]adelay=4000|4000[s1];...
   [s0][s1]...amix=inputs=14:duration=longest[narration]"
  narration_synced.mp3
```

**Video + audio combining** — the narration was laid over the video (original audio stripped):

```
ffmpeg -i demo.mp4 -i narration_synced.mp3
  -filter_complex "[1:a]volume=4.0[narr]"
  -map 0:v -map "[narr]" -c:v copy -c:a aac
  output.mp4
```

The `volume=4.0` was critical — TTS output is quiet by default. We went through several iterations (1x → 3x → 5x → 4x) before finding the sweet spot.

## Step 5: Remotion — React-Powered Video Production

For the hackathon presentation version, I wanted animated title cards and lower-third labels showing each command name. [Remotion](https://remotion.dev) is a React framework for creating videos programmatically — perfect for an AI agent.

The agent scaffolded a Remotion project and created three components:

**TitleCard.tsx** — Spring-animated intro with the project name, tagline, and hackathon badge:

```tsx
const titleY = interpolate(
  spring({ frame, fps, config: { damping: 200 } }),
  [0, 1], [60, 0]
);
```

**DemoSection.tsx** — Embeds the demo video with synchronized narration and animated lower-third labels:

```tsx
{LABELS.map((label, i) => (
  <Sequence from={label.from * fps} durationInFrames={label.duration * fps}>
    <LowerThird text={label.text} />
  </Sequence>
))}
```

**Outro.tsx** — Closing card with the install command and credits.

The Remotion skills package (`remotion-dev/skills`) was installed globally, giving the AI agent best-practice patterns for compositions, sequencing, and animations.

The final render: `npx remotion render MyVideo --output hackathon-video.mp4`

## Step 6: Teams Notifications — Staying in the Loop

Throughout the process, my agent sent me updates via a Teams incoming webhook. Every time a video was rendered or a fix was applied, I got a message on my phone:

```
🎬 Demo Videos — v3 (FINAL)
- Volume tuned to 4x
- Fixed narration text for the add command
- Correct install command in outro
📂 Files in OneDrive > Videos
```

I reviewed each version from my phone, sent feedback ("volume too low", "swap the order of two commands"), and the agent iterated without me touching my laptop.

## The Complete Tool Chain

| Tool | Role | Cost |
|------|------|------|
| [CLI Tunnel](https://github.com/tamirdresher/cli-tunnel) | Remote terminal for AI to type into | Free (my project) |
| [Playwright MCP](https://github.com/anthropics/mcp-playwright) | Browser automation to drive CLI Tunnel | Free |
| [Edge TTS](https://github.com/rany2/edge-tts) | Neural voice narration (en-US-GuyNeural) | Free |
| [FFmpeg](https://ffmpeg.org/) | Audio mixing, video combining, frame extraction | Free |
| [Remotion](https://remotion.dev) | React-based video rendering (title cards, labels) | Free for teams ≤ 3 |
| [OBS / Clipchamp](https://clipchamp.com) | Screen recording | Free |
| Teams Webhooks | Progress notifications to my phone | Free |
| GitHub Copilot CLI | The AI agent orchestrating everything | Included with Copilot |

Total cost for the entire video production pipeline: **$0**.

## What I Learned

1. **Frame-by-frame analysis works.** Extracting 1 frame per second with ffmpeg and analyzing file sizes to detect screen clears gave me precise timestamps for narration sync — no manual timecoding needed.

2. **Per-segment TTS is the way.** Generating one long narration and hoping it lines up is a fantasy. Generate individual clips timed to your video segments.

3. **Volume normalization is non-obvious.** TTS engines output at wildly different levels. Always preview and adjust — we went from inaudible to distorted before finding 4x.

4. **The AI agent as video editor is surprisingly effective.** It can't judge aesthetics, but it can execute a precise production pipeline — generate audio, combine tracks, render frames, iterate on feedback — faster than I could in any GUI tool.

5. **CLI Tunnel is magic for demo recordings.** Having the AI type real commands in a real terminal, visible to screen recording, is far more authentic than synthetic terminal screenshots or asciinema recordings.

## Try It Yourself

This pipeline works for any terminal-based demo:

1. Install CLI Tunnel and start recording your terminal
2. Have your AI agent connect via Playwright and execute your demo script
3. Generate per-segment narration with Edge TTS
4. Mix audio with ffmpeg using adelay + amix
5. (Optional) Wrap in Remotion for title cards and labels

The hardest part isn't the tools — it's getting a clean recording. Budget for multiple takes, and let the AI agent handle the retries.

---

*This post was itself written with assistance from an AI agent. The code examples, timestamps, and tool descriptions are from the actual production session.*
