---
layout: post
title: "Your Copilot CLI on Your Phone — Building Squad Remote Control"
date: 2026-02-26
tags: [ai-agents, squad, github-copilot, remote-control, devtunnel, xterm, pty, mobile, development-workflow]
---

I've been using GitHub Copilot CLI as my daily driver for coding — it edits files, runs commands, searches my codebase, all from the terminal. But I kept running into the same frustration: I'd kick off a task, walk away from my desk, and have no way to check on it or send follow-up instructions from my phone.

Claude Code has [Remote Control](https://code.claude.com/docs/en/remote-control). Matt Kotsenas built [Uplink](https://github.com/MattKotsenas/uplink) for Copilot. I wanted something similar but integrated into [Squad](https://github.com/bradygaster/squad) — my AI team framework — with multi-session support across repos and machines.

So I built it. Here's how it works and the technical journey to get there.

## The End Result

You run `squad start --tunnel --yolo` in your terminal. Copilot CLI launches normally — full TUI with diffs, colors, tool calls, everything. A devtunnel URL and QR code appear. Open that URL on your phone:

![Copilot CLI running in the browser via xterm.js](/assets/squad-remote-control/mobile-terminal.png)

That's the **real Copilot CLI** running in your browser. Not a simplified chat UI — the actual terminal output with all the ANSI colors, box drawing characters, and interactive prompts. You can type from your phone and it goes straight into the copilot session. Arrow keys, Tab, Escape, Ctrl+C — all available via a key bar at the bottom.

And it's **private** — devtunnels are scoped to your Microsoft/GitHub identity. Nobody else can access your session even if they have the URL.

## The Architecture: Three Failed Approaches and One That Worked

### Attempt 1: ACP JSON-RPC (The "Right" Way)

The [Agent Client Protocol](https://agentclientprotocol.com) (ACP) is the standardized way for editors to talk to coding agents. Copilot CLI supports `--acp` mode which speaks JSON-RPC over stdio. My first attempt was to build a bridge that:

1. Spawns `copilot --acp` 
2. Sends `initialize` → `session/new` → `session/prompt` over stdin
3. Reads streaming `session/update` notifications from stdout
4. Relays everything over WebSocket to a browser PWA

This is how Matt's Uplink works. The problem? **Copilot --acp on v0.0.419 takes 15-20 seconds to load MCP servers before it responds to anything.** My bridge was sending `initialize` too early and timing out. Once I figured out the timing (by reading the copilot log files at `~/.copilot/logs/`), it worked — but the output was machine-readable JSON, not the beautiful terminal TUI.

### Attempt 2: ACP with Custom Rendering

I built a chat-style PWA that parsed ACP events and rendered them as formatted cards — tool calls with icons (📖 read, ✏️ edit, ▶️ shell), streaming text with a blinking cursor, collapsible diff blocks. It looked like WhatsApp, not like a terminal.

It worked. Real Copilot responses, streaming, tool calls, permissions. But it wasn't what I wanted — I wanted the **exact** CLI output.

### Attempt 3: The PTY Breakthrough

The insight: **don't use `--acp` at all.** Instead, spawn `copilot` (without any flags) inside a pseudo-terminal using [node-pty](https://github.com/nicely/node-pty). The copilot process thinks it's running in a real terminal and renders its full TUI. We capture the raw terminal output (ANSI escape codes and all) and stream it to the browser, where [xterm.js](https://xtermjs.org/) — a real terminal emulator — renders it pixel-perfectly.

```
Your keyboard → PTY stdin ← Phone keyboard (via WebSocket)
                    ↓
              copilot process
              (full TUI mode)
                    ↓
              PTY stdout
                    ↓
         ┌─────────┴──────────┐
         ↓                    ↓
   Local terminal        WebSocket → devtunnel → Phone (xterm.js)
   (exact output)        (same bytes, same rendering)
```

This is like [CliWrap](https://github.com/Tyrrrz/CliWrap) in .NET — wrapping a process with piped I/O — but with a PTY for full terminal emulation, and a network tap for remote access.

### The Key Technical Details

**PTY spawning with node-pty:**
```typescript
const pty = nodePty.spawn(copilotCmd, copilotArgs, {
  name: 'xterm-256color',
  cols: process.stdout.columns || 120,
  rows: process.stdout.rows || 30,
  cwd,
  env: process.env,
});
```

**Terminal size sync:** When the phone connects, xterm.js reports its dimensions. The bridge resizes the PTY to match, so copilot renders for the phone's screen size:
```typescript
bridge.setPassthrough((msg) => {
  const parsed = JSON.parse(msg);
  if (parsed.type === 'pty_resize') {
    pty.resize(parsed.cols, parsed.rows);
  }
  if (parsed.type === 'pty_input') {
    pty.write(parsed.data);
  }
});
```

**Devtunnel as the relay:** No server to deploy. Microsoft's [Dev Tunnels](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/) provide the HTTPS relay, TLS termination, and authentication — all free, already deployed, zero infrastructure for us to maintain:
```typescript
// Create tunnel with labels for discovery
execSync(`devtunnel create --labels squad --labels ${repo} --labels ${branch} --labels ${machine} --labels port-${port} --expiration 1d --json`);
execSync(`devtunnel port create ${tunnelId} -p ${port} --protocol http`);
```

**Session discovery:** Each `squad start --tunnel` tags its devtunnel with labels (repo name, branch, machine hostname, port). The PWA's "Sessions" view queries `devtunnel list --labels squad` to show all your active sessions across repos and machines. Tap one to connect.

## Security: Your Sessions Are Private

This was a non-negotiable requirement. Here's how it works:

- **Devtunnels are private by default.** Only the Microsoft/GitHub account that created the tunnel can connect. The auth is enforced at Microsoft's relay layer — before any traffic reaches your machine.
- **No inbound ports.** Your machine only makes outbound HTTPS connections. No firewall changes needed.
- **No anonymous access.** We never set `--allow-anonymous`. Even if someone guesses the tunnel URL, they can't connect.
- **No central server.** There's no backend we deploy or maintain. The bridge runs on your machine, devtunnel handles the relay, xterm.js runs in the browser. Everything is peer-to-peer through Microsoft's infrastructure.

To explicitly share with your team, you'd need to add `--tenant` (Entra org) or `--org` (GitHub org) — neither of which happens by default.

## Multi-Session Dashboard

Running multiple sessions across repos and worktrees? The "Sessions" button shows all your active Squad sessions:

![Sessions dashboard showing two active sessions](/assets/squad-remote-control/sessions-dashboard.png)

Each session card shows the repo, branch, and machine. Tap one to connect. The dashboard also lets you clean up stale tunnels — sessions where the bridge process died but the tunnel wasn't cleaned up.

Under the hood, each `squad start --tunnel` tags its devtunnel with labels: repo name, branch, machine hostname, and port. The dashboard queries `devtunnel list --labels squad` to discover all your sessions. Since devtunnel scopes the list to your identity, you only see your own sessions — even across multiple machines.

## How to Use It

```bash
# Start copilot with remote access
squad start --tunnel

# With all permissions auto-approved
squad start --tunnel --yolo

# With a specific model
squad start --tunnel --model claude-sonnet-4

# With a custom CLI (e.g., agency copilot)
squad start --tunnel --command "agency copilot"

# On a specific port (useful for multiple sessions)
squad start --tunnel --port 3457
```

The tunnel URL and QR code appear before copilot launches. Open the URL on your phone, sign in with your Microsoft account (one-time), and you're in.

On your phone, you'll see:
- The full Copilot CLI rendered by xterm.js
- A key bar with ↑ ↓ → ← Tab Enter Esc Ctrl+C for navigation
- A "Sessions" button to see all your running sessions

## What I Learned

1. **Copilot's `--acp` mode works** but needs 15-20 seconds for MCP servers to load. Send `initialize` too early and it silently ignores you.

2. **PTY > ACP for mirroring.** If you want the exact CLI experience remotely, you need a pseudo-terminal. ACP gives you structured data — great for building custom UIs, terrible for replicating the terminal.

3. **xterm.js is incredible.** It handles every ANSI escape code copilot throws at it — cursor movement, alternate screen buffer, 256 colors, box drawing. Load it from CDN, write terminal data into it, done.

4. **Devtunnels are underrated.** Free, authenticated, zero-config relay with built-in discovery (labels). The `devtunnel list --labels` API is basically a session registry without needing a database.

5. **Terminal size matters.** If the PTY and xterm.js disagree on dimensions, spinner animations render as new lines instead of overwriting. Always sync the size on connect.

## What's Next

- **Session history replay** — when you connect from your phone, you should see everything that happened before you joined
- **Push notifications** — get notified when an agent needs your input or a task completes
- **Multi-machine dashboard** — the Sessions view works but needs OAuth for cross-machine tunnel discovery

The code is on the `squad/remote-control` branch of the Squad repo. 19 commits from zero to working — including all the failed ACP attempts that led to the PTY breakthrough.

Sometimes the "wrong" approach teaches you why the right one works. 🖖
