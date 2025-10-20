---
layout: post
title: "Scaling Your AI Development Team with Git Worktrees"
date: 2025-01-20
tags: [git, ai-agents, development-workflow, hackathon, vscode, productivity]
---

During the Microsoft Global Hackathon 2025, my team faced a familiar challenge: too many features, too little time. We needed to build multiple features simultaneously, and the traditional approach of switching between branches was killing our productivity. That's when I discovered a game-changing technique: using Git worktrees to create a virtual AI development team, with each agent working on a different feature in parallel.

The result? We had multiple AI code agents working simultaneously on different features, each in their own workspace, while I supervised the entire team like a tech lead reviewing pull requests. It was like having a team of developers working on your machine at the same time, without the overhead of managing multiple repository clones.

## The Problem: Context Switching is Killing Productivity

When you're working on multiple features, the traditional Git workflow forces you to constantly switch branches. This means:

- Stopping your current work
- Committing or stashing changes
- Switching branches
- Waiting for your IDE to reload
- Getting your AI agent back in context
- Repeating this dance every time you need to work on something else

With AI code agents like Roo, GitHub Copilot, or Cursor, this problem gets worse. Each time you switch branches, you lose the context your AI agent has built up. You're essentially resetting your assistant's understanding of what you're working on.

## Enter Git Worktrees: Your AI Team's Secret Weapon

Git worktrees solve this problem elegantly. Instead of one working directory, you can have multiple directories, each checked out to a different branch. Git handles all the complexity of keeping everything in sync - you just work in separate folders.

Why is this better than cloning the repository multiple times?

- **Shared Git history**: All worktrees share the same `.git` directory, so commits and branches are instantly available everywhere
- **Smaller disk footprint**: You're not duplicating the entire repository
- **Seamless integration**: Git handles the coordination between worktrees automatically
- **VS Code native support**: Visual Studio Code has built-in worktree management

## The Power of Parallel AI Agents

Here's where it gets interesting. Once you have multiple worktrees:

1. **Open each worktree in its own VS Code window**
2. **Launch a separate AI code agent in each window**
3. **Give each agent a specific task to work on**
4. **Switch between windows to supervise progress**

You can even mix and match AI tools! During the hackathon, I used Roo in VS Code for feature development and GitHub Copilot in Visual Studio 2022 for debugging, because Copilot's integration with the Visual Studio debugger is exceptional.

It's like having a distributed team working on your local machine, where you're the tech lead reviewing and guiding the work.

## Step-by-Step: Setting Up Your AI Agent Team

Let me show you exactly how to set this up in VS Code.

### Step 1: Show the Repositories View

First, you need to add the Repositories view to your Source Control area in VS Code.

![Show Repositories in VS Code](/assets/worktree-and-ai-superpowers/show-repositories-in-vscode.png)

1. Open the Source Control panel (Ctrl+Shift+G)
2. Click the three dots (•••) at the top
3. Look for "Repositories" in the Views submenu and enable it

### Step 2: Access the Worktrees Menu

Once you have the Repositories view visible, you can access worktree management.

![Worktrees View in Repository Pane](/assets/worktree-and-ai-superpowers/worktrees-view-in-repo-pane.png)

1. In the Repositories view, find your repository
2. Click the three dots next to your repository name
3. Navigate to "Worktrees" in the context menu

### Step 3: Create a New Worktree

Now you're ready to create your first worktree!

![Create New Worktree](/assets/worktree-and-ai-superpowers/create-new-worktree.png)

Click on "Create New Worktree" from the worktrees menu. This will start the worktree creation wizard.

### Step 4: Select or Create a Branch

You'll be prompted to choose a branch for your worktree.

![New Worktree Branch Selection](/assets/worktree-and-ai-superpowers/new-worktree-branch.png)

You can either:
- Select an existing branch that you want to work on
- Create a new branch for a new feature or bug fix

Choose the branch that corresponds to the feature you want your AI agent to work on.

### Step 5: Choose the Worktree Location

Next, specify where the worktree will be created on your filesystem.

![New Worktree Folder Selection](/assets/worktree-and-ai-superpowers/new-worktree-folder.png)

I recommend creating a dedicated folder structure like:
```
project-name/
├── main/           (your main worktree)
├── feature-auth/   (worktree for authentication)
├── feature-api/    (worktree for API changes)
└── bugfix-123/     (worktree for bug fix)
```

This keeps everything organized and makes it easy to see what's being worked on.

### Step 6: Open in a New Window

Once created, you can open the worktree in its own VS Code window.

![Open Worktree in New Window](/assets/worktree-and-ai-superpowers/open-worktree-in-new-window.png)

Right-click on the newly created worktree and select "Open in New Window". This gives you a completely separate VS Code instance for this branch.

### Step 7: Repeat for Each Feature

Create a worktree for each feature or bug fix you need to work on:
- Feature branch → Worktree → VS Code window
- Bug fix branch → Worktree → VS Code window
- Experiment branch → Worktree → VS Code window

### Step 8: Deploy Your AI Agent Team

Now comes the magic:

1. **In each VS Code window**, start your AI code agent (Roo, Copilot, Cursor, etc.)
2. **Give each agent a clear task**: "Implement authentication", "Add API endpoints", "Fix bug #123"
3. **Switch between windows** to monitor progress
4. **Review and guide** each agent like you would review a team member's work
5. **Commit and push** when satisfied with the implementation

## Real-World Benefits

During the hackathon, this approach gave us several concrete advantages:

**No Context Switching**: Each AI agent maintained full context of its specific task. When I needed to check on the authentication feature, I just switched windows - no branch switching, no reloading.

**Parallel Development**: While one agent was working on the API layer, another was implementing the UI components. Features that would have taken sequential work happened in parallel.

**Different Tools for Different Jobs**: I used Roo for rapid feature development because of its excellent code generation, and Visual Studio with Copilot when I needed to debug complex issues, leveraging the deep IDE integration.

**Easy Progress Review**: I could quickly Alt+Tab through windows to see the state of each feature, like doing standup with multiple team members.

**Clean Branch Management**: Each worktree was isolated. If one feature needed to be abandoned or drastically changed, it didn't affect the others.

## My Hackathon Success Story

Our hackathon project required building a full-stack application with authentication, real-time features, and a complex data pipeline - all in 48 hours. Using worktrees, I had:

- One agent building the authentication system
- Another implementing the real-time WebSocket communication
- A third working on the data processing pipeline
- Myself coordinating and handling the integration

What would have taken a week of sequential development happened in two days. The worktrees approach let us maintain velocity without the chaos of constant branch switching or the overhead of multiple repository clones.

## Getting Started Today

If you want to try this technique, start small:

1. Pick a project with at least two features or bugs to work on
2. Create a worktree for each branch
3. Open each in its own window
4. Start your AI agent in each window with a specific task
5. Experience the productivity boost firsthand

The first time you switch between windows and see multiple features progressing simultaneously, you'll understand why this is a superpower.

## Conclusion

Git worktrees transform how you work with AI code agents. Instead of one assistant that constantly loses context as you switch branches, you have a team of focused agents, each working on their assigned task. Combined with VS Code's excellent worktree support, it's the closest thing to having a distributed development team running on your local machine.

The Microsoft Global Hackathon taught me that the future of development isn't just about having AI assistants - it's about orchestrating them effectively. Worktrees are the tool that makes that orchestration possible.

Give it a try on your next project. Your productivity (and your AI agents) will thank you.

---

*Have you tried using Git worktrees with AI code agents? I'd love to hear about your experience in the comments below!*