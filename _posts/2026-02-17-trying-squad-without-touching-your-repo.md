---
layout: post
title: "Trying Squad AI Team Framework Without Touching Your Real Repo"
date: 2026-02-17
tags: [ai-agents, squad, github-copilot, git, symlinks, development-workflow, productivity]
---

I've been running multiple AI agents in parallel using [Git worktrees](/2025/10/20/scaling-your-ai-development-team-with-git-worktrees.html) for a while now, and it's been a productivity multiplier. But recently I stumbled upon [Squad](https://github.com/bradygaster/squad)—a framework by Brady Gaster that lets you define an entire AI team with specialized roles, all orchestrated through GitHub Copilot. Think of it as going from managing individual AI agents to having a full team with a tech lead, developers, testers, and a documentation writer, all coordinated automatically.

The catch? Squad works by adding configuration files directly into your repository—`.ai-team/` for team state, `.ai-team-templates/` for role definitions, and `.github/agents/squad.agent.md` for the main agent. For a personal project, that's fine. But I wanted to try it on a work repo where I can't just commit experimental AI framework files. My teammates didn't sign up for 38 new files appearing in their next pull.

So I found a way to use Squad on any repo without actually changing it. Here's how.

## What is Squad?

[Squad](https://bradygaster.github.io/squad/) is an AI team framework that sits on top of GitHub Copilot. Instead of you giving instructions to a single AI agent, you define a team—each member has a role, skills, and responsibilities. When you give Squad a task, it breaks it down and delegates work to the right team members.

For example, you might have:
- A **tech lead** who plans the architecture and reviews code
- A **developer** who writes the implementation
- A **tester** who creates and runs tests
- A **docs writer** who updates documentation

You initialize it with `npx github:bradygaster/squad`, define your team members, and Squad generates the agent definition that GitHub Copilot discovers automatically. It's clever and well-designed.

But here's the thing—all of Squad's files live inside your repo. And if you're working on a shared codebase, that's a problem.

## The Problem: I Don't Own the Repo's .gitignore

I wanted to try Squad on a project I'm actively working on—a real codebase with real complexity, not a toy example. But I had two constraints:

1. **No committing Squad files** - My team hasn't agreed to adopt Squad, and I don't want to push framework experiments into the shared repo
2. **No modifying .gitignore** - Even adding gitignore entries is a change that shows up in PRs and affects everyone

I needed Squad's files to exist in my working directory (so Copilot can discover them), but be completely invisible to Git—without changing any tracked files.

## The Solution: A Side Repo + Symlinks + Git Exclude

The approach is straightforward: keep Squad's files in a separate repo, symlink them into your working directory, and use Git's local exclude mechanism to hide them.

Here's the setup:

### Step 1: Create the Squad Repo

Create a separate repository next to your working directory. I keep mine in the same parent folder:

```
C:\repos\my-project\              ← your real repo
C:\repos\squad-for-my-project\    ← Squad lives here
```

Initialize Squad in this separate repo:

```powershell
cd C:\repos\squad-for-my-project
npx github:bradygaster/squad
```

Follow the prompts to set up your team. Squad will create the `.ai-team/`, `.ai-team-templates/`, and `.github/agents/squad.agent.md` files in this repo.

Commit everything here—this is your Squad repo, you own it completely.

### Step 2: Create Symlinks into Your Real Repo

Now create symbolic links from your real repo pointing to the Squad repo's files:

```powershell
cd C:\repos\my-project

# Directory symlinks for team state and templates
New-Item -ItemType SymbolicLink -Path ".ai-team" -Target "C:\repos\squad-for-my-project\.ai-team"
New-Item -ItemType SymbolicLink -Path ".ai-team-templates" -Target "C:\repos\squad-for-my-project\.ai-team-templates"

# Create .github\agents if it doesn't exist
New-Item -ItemType Directory -Path ".github\agents" -Force

# File symlink for the agent definition
cmd /c mklink ".github\agents\squad.agent.md" "C:\repos\squad-for-my-project\.github\agents\squad.agent.md"
```

> **Note:** On Windows, you might need to run your terminal as Administrator, or have Developer Mode enabled for symlink creation to work.

After this, your real repo's directory looks like it has Squad installed—Copilot will discover `squad.agent.md` and everything works. But the actual files live in your side repo.

### Step 3: Hide Everything with Git Exclude

Here's the key trick. Instead of adding entries to `.gitignore` (which is a tracked file that everyone sees), use `.git/info/exclude`. This file works exactly like `.gitignore`, but it's local to your machine and never committed.

```powershell
# Add Squad entries to the local-only exclude file
Add-Content -Path ".git\info\exclude" -Value @"

# Squad (symlinked from side repo)
.ai-team
.ai-team/
.ai-team-templates
.ai-team-templates/
.github/agents/squad.agent.md
"@
```

That's it. Git now ignores all the Squad symlinks, but only on your machine. No changes to `.gitignore`, no changes to any tracked files. Your colleagues see nothing.

> **Git Worktrees Note:** If you're using Git worktrees (like I am), the `.git/info/exclude` file lives in the main repo's `.git` directory, not in the worktree. The entries apply to all worktrees of that repo, which is exactly what you want—set it once, it works everywhere.

### Verify It Works

```powershell
# Confirm Git ignores the Squad files
git check-ignore -v .ai-team .ai-team-templates .github/agents/squad.agent.md

# Output should show they're excluded via .git/info/exclude:
# .git/info/exclude:8:.ai-team    .ai-team
# .git/info/exclude:10:.ai-team-templates    .ai-team-templates
```

And in VS Code, open Copilot Chat, type `@` and you should see the Squad agent listed.

## A Windows Gotcha with Symlinks

I ran into a subtle issue on Windows that's worth mentioning. When Git has `core.symlinks=true`, it sees directory symlinks as single file entries, not as directories. This means a gitignore entry like `.ai-team/` (with trailing slash, matching directories) won't match the symlink, because Git sees it as a file.

The fix is to add **both** forms:

```
.ai-team          # matches the symlink-as-file
.ai-team/         # matches if traversed as directory
```

Without both entries, `git check-ignore` silently fails to match, and your Squad files show up in `git status`. I lost 20 minutes figuring that one out.

## Working with Squad

Once everything is set up, you work with Squad through Copilot Chat using the `@squad` agent. Some examples of what you can tell it:

- `@squad add a new team member for security reviews`
- `@squad implement input validation for the API endpoints`
- `@squad review the recent changes and suggest improvements`

Squad delegates work to the right team members based on their defined roles and skills. The team state (who's doing what, what's been decided) persists in the `.ai-team/` directory—which lives in your side repo and can be committed there independently.

## Why Not Just Fork?

You might wonder—why not just fork the repo and add Squad there? A few reasons:

1. **Symlinks keep you on the real branch** - You're working directly on your feature branch, not a fork. PRs go straight to the upstream repo.
2. **No sync overhead** - With a fork, you'd need to keep pulling upstream changes. Symlinks have zero sync cost.
3. **Clean separation** - Squad's configuration is its own thing. It deserves its own repo with its own commit history.
4. **Portable** - You can point the same Squad repo at different worktrees or even different projects.

## Wrapping Up

Squad is an interesting approach to AI-assisted development, and the symlink + git exclude pattern lets you try it on any repo without asking anyone's permission. The whole setup takes about 5 minutes, and if you decide Squad isn't for you, just delete the symlinks—your repo is exactly as it was.

The `git/info/exclude` trick is the real gem here. I've started using it for other local-only tooling too—anything I want on my machine but not in the shared codebase. It's one of those Git features that's been there forever but most people never discover.

---

*Are you experimenting with AI team frameworks? Have you found other ways to try tools without modifying shared repos? I'd love to hear about it in the comments.*

## Related Posts

- [Scaling Your AI Development Team with Git Worktrees](/2025/10/20/scaling-your-ai-development-team-with-git-worktrees.html)
- [Scaling AI Agents with Aspire: The Missing Isolation Layer](/2025/12/16/scaling-ai-agents-with-aspire-isolation.html)
