---
layout: post
title: "I Let AI Produce My Entire Hackathon Demo Video — Here's How"
date: 2026-03-06
tags: [ai-agents, github-copilot, video-production, edge-tts, remotion, ffmpeg, cli-tunnel, hackathon, configgen]
---

I needed a demo video for my Hackathon 2026 project — the ConfigGen CLI. Twelve commands, live terminal recordings, synchronized narration, animated title cards, the whole thing. Instead of spending hours in a video editor, I had my AI agent produce everything end-to-end. The final video was rendered, narrated, and delivered to my OneDrive — all while I watched from my phone via Teams.

Here's the full pipeline and the tools that made it work.

## The Challenge

The ConfigGen CLI is a dotnet tool that helps teams scaffold, configure, deploy, and manage ConfigGen topology projects. I wanted to demo all 12 commands in a single video:

`help` → `new` → `update` → `docs list` → `docs show` → `add` (fuzzy search) → `add` (with `--project`) → `generate` → `deploy` → `pipeline create` → `init` → `support`

Each command needed to run interactively in a real terminal — not a static screenshot. And I wanted AI narration explaining each step as it happened.

## Step 1: CLI Tunnel — AI Typing Into a Real Terminal

The first problem: how does an AI agent execute commands in an interactive terminal it can see? My agent runs in GitHub Copilot CLI, but I needed it to type commands into a **separate** PowerShell window that I was screen-recording.

The answer was [CLI Tunnel](https://github.com/nicholasgasior/cli-tunnel) — a tool that exposes a local terminal via a web UI. My agent connected to it using the Playwright MCP server (browser automation), navigated to the tunnel URL, and literally typed commands character by character into the terminal input field.

![CLI Tunnel connected](/assets/ai-produced-demo-video/cli-tunnel-connected.png)

The workflow:
1. I start CLI Tunnel in a PowerShell window: `cli-tunnel`
2. I start screen recording that window with OBS/Clipchamp
3. My AI agent connects via Playwright to `http://127.0.0.1:{port}?token={token}`
4. Agent types each command, waits for output, then moves to the next

The agent had a 12-step script with precise timing — wait for prompts, handle interactive selections (like choosing a template or confirming a marketplace install), and verify output before proceeding.

## Step 2: Recording — 12 Takes and Counting

Getting a clean recording was harder than expected. Over 12 attempts, we hit:

- **Stale binaries**: The globally installed `configgen.exe` was running an old version, not the one I just fixed. The agent had to replace the DLL inside `~/.dotnet/tools/.store/` directly.
- **Marketplace conflicts**: `configgen init` was failing because a marketplace plugin was "already registered." We fixed InitCommand.cs to treat that as success.
- **Topology discovery bugs**: `configgen add` couldn't find the topology project when multiple candidates existed. We added interactive selection.
- **Hidden files**: Template projects left `.editorconfig` and `.gitignore` files that blocked `configgen new` from creating a fresh project.

Each fix was committed, pushed, and the agent rebuilt the binary — all without me touching the keyboard. The final run (take 12) captured all 12 commands cleanly.

## Step 3: Edge TTS — Free AI Narration

For voiceover, I used Microsoft's [Edge TTS](https://github.com/rany2/edge-tts) — a Python package that gives you access to the same neural voices as Microsoft Edge's Read Aloud feature. Free, no API key, excellent quality.

```python
import edge_tts

communicate = edge_tts.Communicate(
    "Meet the ConfigGen CLI.",
    "en-US-GuyNeural",
    rate="+22%"
)
await communicate.save("segment.mp3")
```

The key insight was **per-segment generation**. Instead of one long narration track, I generated 14 individual audio clips — one per command — each timed to match the video timestamps:

| Seconds | Narration |
|---------|-----------|
| 0-3 | "Meet the ConfigGen CLI." |
| 4-14 | "The new command scaffolds a project interactively..." |
| 55-59 | "Add supports fuzzy search. Type any resource name to find it." |
| 83-89 | "Pipeline create registers your generated YAML pipelines in Azure DevOps." |

Each segment was padded with silence using ffmpeg's `adelay` filter to place it at the exact timestamp, then all segments were mixed into a single narration track.

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

**Outro.tsx** — Closing card with the install command.

The final render: `npx remotion render ConfigGenCLI --output "ConfigGen CLI - Hackathon.mp4"`

![Remotion title card animation](/assets/ai-produced-demo-video/blog-animation.png)

## Step 6: Teams Notifications — Staying in the Loop

Throughout the process, my agent sent me updates via a Teams incoming webhook. Every time a video was rendered or a fix was applied, I got a message:

```
🎬 ConfigGen CLI Videos — v3 (FINAL)
- Volume tuned to 4x
- Fixed "add" narration: finds any resource, not just StorageAccount
- Correct install command in outro
📂 Files in OneDrive > Videos
```

I reviewed each version from my phone, sent feedback ("volume too low", "init should come before support"), and the agent iterated without me touching my laptop.

## The Complete Tool Chain

| Tool | Role | Cost |
|------|------|------|
| [CLI Tunnel](https://github.com/nicholasgasior/cli-tunnel) | Remote terminal for AI to type into | Free |
| [Playwright MCP](https://github.com/anthropics/mcp-playwright) | Browser automation to drive CLI Tunnel | Free |
| [Edge TTS](https://github.com/rany2/edge-tts) | Neural voice narration (en-US-GuyNeural) | Free |
| [FFmpeg](https://ffmpeg.org/) | Audio mixing, video combining, frame extraction | Free |
| [Remotion](https://remotion.dev) | React-based video rendering (title cards, labels) | Free for teams ≤ 3 |
| [OBS / Clipchamp](https://clipchamp.com) | Screen recording | Free |
| Teams Webhooks | Progress notifications to my phone | Free |
| GitHub Copilot CLI | The AI agent orchestrating everything | Included with Copilot |

Total cost for the entire video production pipeline: **$0**.

## What I Learned

1. **Frame-by-frame analysis works.** Extracting 1 frame per second with ffmpeg and analyzing file sizes to detect screen clears gave me precise timestamps for narration sync.

2. **Per-segment TTS is the way.** Generating one long narration and hoping it lines up is a fantasy. Generate individual clips timed to your video segments.

3. **Volume normalization is non-obvious.** TTS engines output at wildly different levels. Always preview and adjust — we went from inaudible to distorted before finding 4x.

4. **The AI agent as video editor is surprisingly effective.** It can't judge aesthetics, but it can execute a precise production pipeline — generate audio, combine tracks, render frames, iterate on feedback — faster than I could in any GUI tool.

5. **CLI Tunnel is magic for demo recordings.** Having the AI type real commands in a real terminal, visible to screen recording, is far more authentic than synthetic terminal screenshots.

## Try It Yourself

Install the ConfigGen CLI:
```bash
dotnet tool install -g ConfigurationGeneration.Cli \
  --add-source https://pkgs.dev.azure.com/microsoft/_packaging/WDATP/nuget/v3/index.json
```

The full video is available on my OneDrive — ask me for a link if you're interested in seeing the final result.

---

*This post was itself written with assistance from an AI agent. The code examples, timestamps, and tool descriptions are from the actual production session.*
