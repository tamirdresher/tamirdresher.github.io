---
layout: post
title: "Give Your AI Coding Agent Eyes: Integrating Playwright MCP for Visual Testing"
date: 2025-11-15
tags: [ai-agents, playwright, mcp, testing, visual-testing, automation, roo]
---

AI coding agents like Roo and GitHub Copilot are incredible at writing code, but they're completely blind to what your application actually looks like. While working on a recent project, I needed my AI agent to help debug UI issues and verify that components rendered correctly. The agent could read my React code and suggest fixes, but it couldn't see that the submit button was hidden behind a modal, or that my CSS changes broke the mobile layout. That's when I discovered the Playwright MCP server—a way to give your AI agent actual eyes to see and interact with your web application.

## The Problem: AI Agents Live in a Text-Only World

Traditional AI coding agents work exclusively with text:
- They read your source code files
- They write code changes
- They run terminal commands and see text output
- They analyze error messages and stack traces

But they can't answer questions like:
- "Does this button actually appear on the page?"
- "Is the modal positioned correctly?"
- "Did my CSS changes work as expected?"
- "Can a user actually click this element, or is something covering it?"

This creates a significant blind spot. You end up in conversations like this:

**You:** "The login button isn't working"  
**Agent:** "Let me check the code... the onClick handler looks correct"  
**You:** "But it's not clickable on the page"  
**Agent:** "Try adding `cursor: pointer` in the CSS?"  
**You:** *sigh*

The agent is guessing based on code, when the real issue might be a z-index problem, an overlapping element, or a CSS specificity conflict that's only visible in the rendered page.

## Enter Model Context Protocol (MCP)

Before diving into the solution, let's understand what MCP is.

**Model Context Protocol** is an open protocol that allows AI assistants to connect to external tools and data sources. Think of it as a plugin system for AI agents. Instead of being limited to reading files and running commands, an AI agent with MCP support can:

- Query databases
- Access APIs
- Control browsers
- Read sensor data
- Interact with any service that exposes MCP tools

The Playwright MCP server specifically gives AI agents the ability to:
- Navigate to web pages
- Take screenshots
- Click elements
- Fill forms
- Inspect the DOM
- Run JavaScript in the browser context

It's like giving your AI agent a pair of eyes and hands to interact with your web application.

## Setting Up Playwright MCP

The setup is surprisingly straightforward. The Playwright MCP server runs as a separate process that your AI agent communicates with.

### Installation

```bash
# Install and run the Playwright MCP server
npx @playwright/mcp@latest --browser=msedge --extension
```

This command:
- Downloads the Playwright MCP server
- Installs Microsoft Edge (or uses your existing installation)
- Starts the MCP server with browser automation capabilities
- **The `--extension` flag is crucial** - it gives the agent access to your authenticated browser session

### Why `--extension` Matters

The `--extension` flag is a game-changer for real-world development. Without it, Playwright starts a fresh browser session with no cookies, no authentication, no nothing. But with `--extension`, your AI agent can:

- **Access authenticated pages** - If you're logged into Azure DevOps, the agent can navigate authenticated routes
- **Use existing browser state** - Cookies, local storage, service workers all persist
- **Test real user scenarios** - Not just public pages, but actual authenticated workflows
- **Skip login flows** - No need to automate authentication in every test

This is especially valuable when working with private feeds, internal tools, or any application behind authentication.

### Configuration in Roo (VS Code)

If you're using Roo in VS Code, you configure MCP servers in your settings file. Here's my actual configuration:

**Location:** `%APPDATA%\Code - Insiders\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json`

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--browser=msedge",
        "--extension"
      ],
      "alwaysAllow": [
        "browser_click",
        "browser_navigate",
        "browser_snapshot",
        "browser_screenshot"
      ]
    }
  }
}
```

**Key points:**
- The `command` is `npx` to auto-download latest version
- `--browser=msedge` uses Microsoft Edge (you can use `chromium`, `firefox`, or `webkit`)
- `--extension` enables authenticated session access
- `alwaysAllow` lists tools the agent can use without asking permission each time

For more details on the extension mode, see the [Playwright MCP extension documentation](https://github.com/microsoft/playwright-mcp/blob/main/extension/README.md).

### Available Tools

Once connected, your AI agent gains access to powerful browser automation tools:

| Tool | Purpose |
|------|---------|
| [`browser_navigate`](browser_navigate) | Navigate to URLs |
| [`browser_snapshot`](browser_snapshot) | Capture accessibility tree (better than screenshots for AI) |
| [`browser_screenshot`](browser_screenshot) | Take visual screenshots |
| [`browser_click`](browser_click) | Click elements on the page |
| [`browser_type`](browser_type) | Type text into inputs |
| [`browser_evaluate`](browser_evaluate) | Run JavaScript in browser |
| [`browser_console_messages`](browser_console_messages) | Read console output |
| [`browser_fill_form`](browser_fill_form) | Fill multiple form fields |
| [`browser_hover`](browser_hover) | Hover over elements |

The full list includes many more—check the [Playwright MCP documentation](https://github.com/microsoft/playwright-mcp) for details.

## Integration with Your Aspire Development Workflow

The beauty of Playwright MCP is how seamlessly it integrates with your existing development setup.

### Running with Aspire

When your Aspire app host starts your React frontend, it's typically accessible at a local URL:

```csharp
var reactApp = builder.AddViteApp("reactfrontend", "../Dk8sOnboardingWizard.Web.React", "dev")
    .WithExternalHttpEndpoints(); // Makes it accessible to MCP
```

The [`WithExternalHttpEndpoints()`](AppHost.cs:194) call ensures the Vite dev server is accessible not just to your browser, but also to tools like Playwright MCP.

### The Workflow

1. **Start Aspire** (F5 in Visual Studio)
2. **Aspire starts all services** including your React frontend
3. **Open Roo/AI agent** in VS Code
4. **Ask agent to inspect the app**
5. **Agent uses Playwright MCP** to navigate and interact
6. **Get visual feedback** in real-time

### Working with Multiple Agents

In my [previous post about Git worktrees](/2025/10/20/scaling-your-ai-development-team-with-git-worktrees.html), I showed how to run multiple AI agents in parallel. With Playwright MCP, you can have:

- **Agent A** (Code Mode): Writing React components
- **Agent B** (Test Mode with MCP): Verifying the UI renders correctly
- **You** (Supervisor): Coordinating between them

Each agent in its own VS Code window, each with access to Playwright MCP, testing their own isolated worktree's version of the app.

## Best Practices

### 1. Use Snapshots Over Screenshots When Possible

[`browser_snapshot`](browser_snapshot) captures the accessibility tree, which is:
- **Faster** to process for AI
- **More semantic** (shows role, state, properties)
- **Better for accessibility testing**

Use [`browser_screenshot`](browser_screenshot) when you need to:
- Check visual styling (colors, spacing, alignment)
- Debug CSS issues
- Share visual proof with humans

### 2. Combine with Code Analysis

Don't rely on MCP alone. The best approach combines:
- **Code analysis** - Understanding logic and structure
- **Visual inspection** - Verifying rendering and behavior
- **Console monitoring** - Catching JavaScript errors

```
You: "The form submission is failing"
Agent: 
  1. *Reads FormComponent.tsx* - "Logic looks correct"
  2. *Navigates to page with MCP* - "Form renders properly"
  3. *Checks console* - "Found error: 'API endpoint returned 500'"
  4. *Reads API code* - "Found null reference in validation"
```

### 3. Start Local, Verify Remote

Use MCP for local development and debugging, then run proper automated tests for CI/CD:

- **Local**: MCP-enabled AI agent for rapid iteration
- **CI/CD**: Playwright tests in your pipeline

MCP is for developer productivity, not replacing your test suite.

### 4. Be Specific in Your Requests

Vague requests lead to generic actions. Be specific about what you want the agent to check:

❌ "Check the page"
✅ "Navigate to localhost:5000/login and verify the submit button is visible and clickable"

## Limitations and Considerations

### Not a Replacement for Proper Testing

Playwright MCP is a development tool, not a testing framework. For production:
- ✅ Use MCP for rapid debugging and verification
- ✅ Write proper Playwright tests for CI/CD
- ✅ Use established testing patterns (Page Objects, etc.)

### Performance Overhead

Browser automation is slower than code-only interactions:
- **MCP call**: 1-5 seconds
- **File read**: <0.1 seconds

Use MCP judiciously:
- ✅ When you need visual verification
- ✅ When debugging UI issues
- ❌ For every single question to the AI

### Requires Running Application

MCP can only test what's running:
- ✅ Works great with Aspire (always running locally)
- ✅ Works with any web server (localhost, staging, prod)
- ❌ Can't test before you build/run

### Context Switching

Each MCP call is a context switch for the AI:
- Reading code is fast
- Navigating browsers is slow
- Balance both modes effectively

## Troubleshooting

### MCP Server Won't Start

```bash
# Check if port is in use
netstat -an | findstr :9222

# Try different browser
npx @playwright/mcp@latest --browser=chromium

# Check logs
npx @playwright/mcp@latest --browser=msedge --verbose
```

### Agent Can't See the Page

**Issue:** Agent says "page not loaded" or times out

**Solutions:**
1. Verify your app is actually running (check Aspire dashboard)
2. Check the URL is accessible in your browser
3. Ensure no CORS issues blocking headless browser
4. Try adding `--headless=false` to see what the browser sees

### Screenshots are Blank

**Issue:** Screenshots are captured but show blank pages

**Solutions:**
1. Add waits for page load: `--wait-until=networkidle`
2. Check if content is dynamically loaded (React/SPA)
3. Verify authentication isn't blocking access
4. Try full page screenshot vs viewport only

## Conclusion

Giving your AI coding agent eyes through Playwright MCP bridges the gap between code and reality. It's like having a pair programmer who can actually see your application, not just imagine it from the code.

The combination of code analysis and visual inspection creates a powerful debugging workflow:
1. **AI reads code** - Understands logic
2. **AI inspects visuals** - Verifies behavior
3. **AI suggests fixes** - Based on both code and visual context

If you're already using AI coding agents, adding Playwright MCP is a no-brainer. The setup takes 5 minutes, and the productivity boost is immediate.

---

*Have you tried Playwright MCP or other visual testing tools with AI agents? What's your experience? Share in the comments below!*

## Related Posts

- [Scaling Your AI Development Team with Git Worktrees](/2025/10/20/scaling-your-ai-development-team-with-git-worktrees.html)
- [Seamless Private NPM Feeds in .NET Aspire](/2025/11/15/seamless-private-npm-feeds-in-dotnet-aspire.html)