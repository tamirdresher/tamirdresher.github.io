---
layout: post
title: "cli-tunnel v1.3: Hub Dashboard, Tmux Grid, Terminal Recording — and 70 Security Fixes"
date: 2026-03-01
categories: [tools, cli, security]
tags: [cli-tunnel, copilot, devtunnel, xterm, pty, security]
---

A week ago I released [cli-tunnel](https://github.com/tamirdresher/cli-tunnel) — a tool that tunnels any CLI app to your phone. You run `npx cli-tunnel copilot --yolo`, scan a QR code, and your phone becomes a live terminal mirror. [The original blog post]({{ site.baseurl }}{% post_url 2026-02-26-squad-remote-control %}) covers how it was built and the three approaches I tried before the PTY breakthrough.

Since then, cli-tunnel has gone from a simple PTY mirror to a full multi-session terminal dashboard with recording, security hardening from four red team audits, and a bunch of quality-of-life improvements. Here's what changed.

## Hub Mode — Your Sessions Dashboard

The first thing people asked was: "I have multiple sessions running. How do I see them all?"

Run `cli-tunnel` with no command and you get **hub mode** — a dashboard showing all your active cli-tunnel sessions across machines.

![Hub dashboard showing sessions across machines](/assets/cli-tunnel-v1.3/hub-dashboard.png)

Each session card shows the name, repo, branch, and machine. Sessions on your local machine are directly connectable (tap to open). Sessions on other machines show a 🔒 icon — they're visible via devtunnel labels but the hub doesn't have their tokens.

The token discovery works through the filesystem: each session writes its token to `~/.cli-tunnel/sessions/<tunnelId>.json` with owner-only permissions (0o600). The hub reads these files to match tokens to sessions. No network IPC, no HTTP endpoints — just file permissions.

## Grid View — tmux in Your Browser

The real showstopper is the **Grid view**. When the hub sees 2+ connectable sessions, a ⊞ Grid button appears. Click it and you get all your terminals side by side — live, interactive, with four layout modes:

### Tiles — Windows Task View

Scaled-down terminal previews in a card grid. Click any tile to go fullscreen.

![Tiles view showing terminal previews](/assets/cli-tunnel-v1.3/grid-tiles.png)

### Tmux — Split Panels

Equal split panels with layout presets: **Equal**, **Main+Side**, and **Stacked**. The closest thing to tmux in a browser.

![Tmux view with equal split panels](/assets/cli-tunnel-v1.3/grid-tmux.png)

### Focus — Presentation Mode

One terminal takes 75% of the screen. Others shown as clickable strips at the bottom. Perfect for demos — your main session is front and center, but you can quick-switch to any other.

![Focus view with one main terminal](/assets/cli-tunnel-v1.3/grid-focus.png)

### Fullscreen

Single terminal with the key bar for mobile input. A "← Grid" button gets you back.

![Fullscreen view](/assets/cli-tunnel-v1.3/grid-fullscreen.png)

All four modes share the same WebSocket connections. Switching is instant — no reconnection, no re-authentication.

The tricky part was the **ticket proxy**. Each session has its own auth token, but the hub dashboard runs on a different port. Cross-port fetches get blocked by CORS. So the hub acts as a proxy: `POST /api/proxy/ticket/<port>` — the hub fetches a one-time ticket from the session's local port using the token from the session file, then returns the ticket to the browser. The browser connects WebSocket with the ticket. Clean, no CORS, no raw tokens exposed to the client.

## Terminal Recording

Tap ⏺ in the key bar to start recording. The button turns red and shows elapsed time (⏹ 2:35). Tap again to stop — a `.webm` video file downloads automatically.

It uses the browser's `MediaRecorder` API to capture the xterm.js canvas at 30fps. VP9 codec, 2.5 Mbps bitrate. Records exactly what you see on screen — perfect for demos, presentations, or just showing someone what happened in your session.

A few details that matter:
- **Auto-stops after 10 minutes** to prevent memory issues on mobile
- **Auto-stops on view change** — if you switch to the dashboard or disconnect, recording stops cleanly
- **Canvas selection** — in grid fullscreen mode, it records the focused panel's canvas, not the hidden main terminal

## Security: Seven Layers Deep

Remote terminal access is inherently scary — someone types commands on your machine from the internet. The security had to be right. Over several iterations, I hardened cli-tunnel with a layered security model:

1. **Devtunnel** — private by default, only your MS/GitHub identity can connect
2. **Session token** — random UUID, 4-hour TTL
3. **Ticket-based WebSocket** — single-use, 60-second expiry tickets for WS auth
4. **Rate limiting** — 30 req/min per IP for HTTP, 10/min for tickets, 429 on burst
5. **Environment isolation** — dangerous vars (NODE_OPTIONS, BASH_ENV, LD_PRELOAD) stripped from PTY
6. **Secret redaction** — JWT, OpenAI, GitHub, AWS, and other credential patterns scrubbed from audit logs
7. **Connection limits** — 5 global, 2 per IP, 30s ping/pong heartbeat

Every release runs 32 integration tests before publish. The CI pipeline tests HTTP endpoints, WebSocket auth, hub mode, rate limiting, and secret redaction patterns. GitHub Actions are pinned to commit SHAs.

## Quality of Life

A few smaller things that made the experience much better:

**Interactive devtunnel install** — If devtunnel isn't installed, cli-tunnel asks "Would you like to install it now?" and runs the install command. Then prompts for login if not authenticated. First-run to working in under a minute.

**Press-any-key** — After showing the QR code and tunnel URL, cli-tunnel waits for you to press a key before starting the CLI tool. No more scrambling to scan the QR before copilot scrolls it away.

**Node 23 compatibility** — Our env var allowlist was too aggressive — it stripped system vars that Windows crypto (`BCryptGenRandom`) needed, causing CSPRNG crashes on Node 23. Switched to a blocklist approach and the crash went away.

## What's Next

- **asciinema recording** — server-side `.cast` files alongside the browser video recording
- **Cross-machine grid** — connect to sessions on other machines through their hubs
- **Session sharing** — share a read-only view of your terminal with teammates

Try it: `npx cli-tunnel copilot --yolo`

Source: [github.com/tamirdresher/cli-tunnel](https://github.com/tamirdresher/cli-tunnel)

Previous post: [Your Copilot CLI on Your Phone — Building Squad Remote Control]({{ site.baseurl }}{% post_url 2026-02-26-squad-remote-control %})
