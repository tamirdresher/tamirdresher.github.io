---
layout: post
title: "Seamless Private NPM Feeds in .NET Aspire: No More Authentication Headaches"
date: 2025-11-15
tags: [aspire, npm, azure-devops, authentication, dotnet, react, private-packages]
---

I recently ran into a frustrating problem while working on a project with a React frontend. The app needed packages from an internal Azure DevOps npm feed, but every time I pressed F5 in Visual Studio, Aspire would fail with E401 authentication errors. The typical npm authentication dance—running `vsts-npm-auth`, configuring tokens, dealing with expired credentials—was killing my productivity. I needed Aspire to "just work" like the rest of my development workflow.

## Aspire 13: JavaScript as a First-Class Citizen

Before diving into the authentication challenges, it's worth noting that .NET Aspire 13 has made a huge leap forward in supporting JavaScript applications. As announced in [Aspire 13's release](https://aspire.dev/whats-new/aspire-13/#javascript-as-a-first-class-citizen), JavaScript and TypeScript are now first-class citizens in the Aspire ecosystem.

**What's new in Aspire 13 for JavaScript:**

- **Native npm/yarn/pnpm support** - Aspire can now run your package manager commands directly
- **Vite integration** - Built-in support for Vite dev server with hot module replacement
- **React, Vue, Angular** - First-class support for all major frameworks
- **TypeScript compilation** - Automatic TypeScript building and watching
- **Environment variable injection** - Pass configuration from Aspire to your JS apps seamlessly
- **Proper shutdown handling** - Graceful termination of dev servers

This means you can now use [`AddViteApp()`](https://aspire.dev/api/Aspire.Hosting.ViteAppHostingExtension.AddViteApp.html), [`AddNpmApp()`](https://aspire.dev/api/Aspire.Hosting.NpmAppHostingExtension.AddNpmApp.html), and other JavaScript-specific extension methods that handle the complexity of running JavaScript build tools in the Aspire orchestration environment.

However, this improved JavaScript support also means that authentication challenges with private npm feeds become more visible. When Aspire 13 tries to automatically run `npm install` for your React or Vue app, authentication failures immediately break the F5 experience we've come to expect from Aspire.

## The Problem: Breaking the F5 Experience

When you're working with .NET Aspire and JavaScript/React frontends that pull from private npm feeds, you face several challenges:

- **Authentication tokens expire frequently** - npm tokens typically expire after a few hours
- **Manual credential refresh breaks flow** - Having to run auth commands interrupts development
- **Pipeline builds need different auth** - What works locally doesn't work in CI/CD
- **Team onboarding is painful** - New developers struggle with the initial setup
- **Documentation is scattered** - Pieces are spread across npm, Azure DevOps, and Aspire docs

The core issue is that private npm feeds require authentication, but there's no standard way to handle this seamlessly across local development and automated builds.

## Understanding the Authentication Landscape

Before jumping into the solution, it's important to understand that there are two distinct authentication scenarios:

### Local Development
Developers need:
- **Interactive authentication** - Browser-based login flows
- **Credential caching** - Store tokens in user profile
- **Automatic refresh** - Renew tokens without manual intervention
- **Integration with existing tools** - Leverage `az login` or other auth mechanisms

### Pipeline Builds
Automated builds require:
- **Non-interactive auth** - No browser prompts possible
- **Service principal or managed identity** - System accounts, not user accounts
- **Environment variable injection** - Azure DevOps provides `VSS_NUGET_ACCESSTOKEN`
- **Reproducible builds** - Same auth mechanism every time

The solution needs to handle both scenarios transparently.

## The Solution: Automated Authentication Flow

The key insight is to leverage npm lifecycle hooks to ensure credentials are always fresh before any npm operation. Here's how it works:

### 1. Configure the Private Feed

First, create an [`.npmrc`](.npmrc) file in your React project root that points to your private feed:

```
# Use private feed as the only registry
registry=https://microsoft.pkgs.visualstudio.com/_packaging/YourFeedName/npm/registry/

# Always authenticate with private feed
always-auth=true
```

**Important:** This file should be committed to git. It contains the registry configuration but no credentials.

### 2. Integrate with Aspire

In your AppHost project, configure the React app to use npm with automatic installation. Thanks to [Aspire 13's first-class JavaScript support](https://aspire.dev/whats-new/aspire-13/#javascript-as-a-first-class-citizen), this is now straightforward with the [`AddViteApp()`](https://aspire.dev/api/Aspire.Hosting.ViteAppHostingExtension.AddViteApp.html) extension method:

```csharp
var reactApp = builder.AddViteApp("reactfrontend", "../Dk8sOnboardingWizard.Web.React", "dev")
    .WithNpm(
        install: true,
        installArgs: ["--legacy-peer-deps"])
    .WithReference(apiService)
    .WithExternalHttpEndpoints()
    .PublishAsDockerFile();
```

**What's happening here:**
- [`AddViteApp()`](https://aspire.dev/api/Aspire.Hosting.ViteAppHostingExtension.AddViteApp.html) - New in Aspire 13, specifically designed for Vite-based apps
- [`WithNpm()`](AppHost.cs:189) - Configures npm to run `install` automatically before starting the dev server
- `install: true` - Triggers `npm install` on app start
- `installArgs` - Passes arguments to npm (in this case, `--legacy-peer-deps`)

Aspire 13 handles the complexity of:
- Running npm in the correct working directory
- Managing the npm process lifecycle
- Streaming npm output to the Aspire dashboard
- Gracefully shutting down the Vite dev server

This is where our authentication solution needs to integrate—ensuring credentials are fresh before Aspire runs `npm install`.

### 3. Create the Authentication Script

Create a PowerShell script [`setup-auth.ps1`](setup-auth.ps1) in a `scripts` folder:

```powershell
# setup-auth.ps1
# Authenticates to Azure DevOps npm feed using Azure CLI credentials

$ErrorActionPreference = "Stop"

Write-Host "Setting up npm authentication for private feed..." -ForegroundColor Cyan

# Check if vsts-npm-auth is installed
$vstsNpmAuth = Get-Command vsts-npm-auth -ErrorAction SilentlyContinue

if (-not $vstsNpmAuth) {
    Write-Host "vsts-npm-auth not found. Installing from public npm registry..." -ForegroundColor Yellow
    
    # Temporarily use public registry to install vsts-npm-auth
    $env:NPM_CONFIG_REGISTRY = "https://registry.npmjs.org/"
    npm install -g vsts-npm-auth --registry https://registry.npmjs.org/
    Remove-Item Env:NPM_CONFIG_REGISTRY
    
    Write-Host "✓ vsts-npm-auth installed successfully" -ForegroundColor Green
}

# Verify Azure CLI is logged in
Write-Host "Checking Azure CLI authentication..." -ForegroundColor Gray
$azAccount = az account show 2>$null

if (-not $azAccount) {
    Write-Host "❌ Not logged into Azure CLI!" -ForegroundColor Red
    Write-Host "Please run: az login" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Azure CLI authenticated" -ForegroundColor Green

# Run vsts-npm-auth to refresh credentials
Write-Host "Refreshing npm credentials..." -ForegroundColor Gray
vsts-npm-auth -config .npmrc -F

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ npm authentication configured successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to configure npm authentication" -ForegroundColor Red
    exit 1
}
```

This script:
1. Checks if `vsts-npm-auth` is installed, installs it if needed
2. Verifies you're logged into Azure CLI
3. Runs `vsts-npm-auth` to inject credentials into your user profile's `.npmrc`

### 4. Wire Up npm Lifecycle Hooks

In your [`package.json`](package.json), add the authentication script to run before installation:

```json
{
  "name": "dk8s-onboarding-wizard-react",
  "version": "1.0.0",
  "scripts": {
    "auth": "pwsh -ExecutionPolicy Bypass -File ./scripts/setup-auth.ps1",
    "preinstall": "npm run auth",
    "dev": "vite",
    "build": "vite build"
  }
}
```

The [`preinstall`](package.json:7) hook runs automatically before `npm install`, ensuring credentials are fresh every time.

### 5. Pipeline Authentication (Different Approach)

For pipeline builds, we need a different mechanism since there's no Azure CLI and no interactive browser. Create an [`init.sh`](scripts/init.sh) script for Docker builds:

```bash
#!/bin/bash
set -e

echo "[init.sh] Configuring npm authentication for private feed..."

# Configure npm authentication (matching .npmrc registry URL)
echo "; begin auth token to pull npm packages" > ~/.npmrc
echo "//microsoft.pkgs.visualstudio.com/_packaging/YourFeedName/npm/registry/:_authToken=${VSS_NUGET_ACCESSTOKEN}" >> ~/.npmrc
echo "//microsoft.pkgs.visualstudio.com/_packaging/YourFeedName/npm/registry/:email=npm requires email to be set but doesn't use the value" >> ~/.npmrc
echo "; end auth token to pull npm packages" >> ~/.npmrc

echo "[init.sh] npm authentication configured successfully"
```

Azure DevOps automatically injects the `VSS_NUGET_ACCESSTOKEN` environment variable during pipeline builds, which this script uses to configure authentication.

In your Dockerfile:

```dockerfile
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files
COPY Dk8sOnboardingWizard.Web.React/package*.json ./
COPY Dk8sOnboardingWizard.Web.React/.npmrc ./
COPY Dk8sOnboardingWizard.Web.React/scripts/init.sh ./scripts/

# Setup authentication and install dependencies
ARG VSS_NUGET_ACCESSTOKEN
RUN chmod +x ./scripts/init.sh && \
    ./scripts/init.sh && \
    npm install --legacy-peer-deps

# ... rest of build
```

## How It All Works Together

### Local Development (Press F5)

1. You run `az login` once when setting up your machine
2. Press F5 in Visual Studio to start Aspire
3. Aspire calls `npm install` via [`WithNpm()`](AppHost.cs:189)
4. npm triggers the `preinstall` hook
5. `setup-auth.ps1` runs and:
   - Verifies Azure CLI auth
   - Runs `vsts-npm-auth` to inject credentials
6. npm proceeds with installation using fresh credentials
7. Vite dev server starts
8. You're coding!

**Result:** Seamless authentication, zero manual steps after initial `az login`.

### Pipeline Builds

1. Azure DevOps pipeline starts
2. Sets `VSS_NUGET_ACCESSTOKEN` environment variable
3. Dockerfile runs
4. `init.sh` configures authentication using the token
5. `npm install` succeeds
6. Build completes

**Result:** Reproducible builds with no secrets in git.

## Best Practices

### 1. Never Commit Credentials

The `.npmrc` in your project should only contain the registry URL:
```
registry=https://microsoft.pkgs.visualstudio.com/_packaging/YourFeedName/npm/registry/
always-auth=true
```

Credentials go in your user profile's `~/.npmrc`, managed by `vsts-npm-auth`.

### 2. One-Time Team Setup

New team members need to:
```powershell
# One-time setup
az login
cd Dk8sOnboardingWizard.Web.React
npm run auth
```

After that, F5 just works.

### 3. Handle Credential Expiration

If you see E401 errors after a few days:
```powershell
# Refresh credentials
cd Dk8sOnboardingWizard.Web.React
npm cache clean --force
npm run auth
```

The `preinstall` hook should handle this automatically, but manual refresh is there if needed.

### 4. Separate Local and Pipeline Config

- **Local:** Use `vsts-npm-auth` with Azure CLI
- **Pipeline:** Use `VSS_NUGET_ACCESSTOKEN` with `init.sh`
- **Don't mix them** - They have different token formats and lifetimes

## Troubleshooting

### E401: Unauthorized

**Symptom:** `npm error code E401` during install

**Solutions:**

1. **Verify Azure CLI login:**
   ```powershell
   az account show  # Should show your account details
   az login         # If not logged in
   ```

2. **Clear npm cache:**
   ```powershell
   cd Dk8sOnboardingWizard.Web.React
   npm cache clean --force
   rm -rf node_modules package-lock.json
   npm install --legacy-peer-deps  # preinstall hook runs automatically
   ```

3. **Run auth manually:**
   ```powershell
   npm run auth
   ```

4. **Check feed permissions:**
   - Visit your Azure DevOps feed settings
   - Ensure your account has read permissions

### vsts-npm-auth Installation Fails

**Symptom:** Can't install `vsts-npm-auth`

**Solution:**
```powershell
# Install from public npm explicitly
npm install -g vsts-npm-auth --registry https://registry.npmjs.org/

# Verify
vsts-npm-auth --help
```

### Pipeline Builds Fail with E401

**Symptom:** Pipeline gets E401 despite `VSS_NUGET_ACCESSTOKEN`

**Check:**
1. Verify the pipeline has access to your private feed
2. Ensure `VSS_NUGET_ACCESSTOKEN` is passed as build arg in Dockerfile
3. Check `init.sh` has execute permissions (`chmod +x`)
4. Verify the registry URL in `.npmrc` matches the one in `init.sh`

### Peer Dependency Warnings

**Symptom:** Warnings about peer dependencies during install

**Solution:** This is expected with `--legacy-peer-deps`. The application works correctly despite warnings. Modern package managers are stricter about peer dependencies, but many packages haven't caught up yet.

## Real-World Benefits

After implementing this solution:

**Before:**
- ❌ 5-10 minutes per developer for auth setup
- ❌ E401 errors every few hours
- ❌ Manual `vsts-npm-auth` commands
- ❌ Broken F5 experience
- ❌ Pipeline failures due to auth

**After:**
- ✅ One-time `az login` setup
- ✅ Automatic credential refresh
- ✅ F5 just works
- ✅ Zero auth-related pipeline failures
- ✅ New developers onboard in minutes

## Alternative Approaches

### Option 1: Environment Variables

You could store tokens in environment variables, but:
- ❌ Tokens expire frequently
- ❌ Manual refresh needed
- ❌ Harder to manage across team

### Option 2: Manual .npmrc Management

You could manually edit `~/.npmrc`, but:
- ❌ Error-prone
- ❌ Token format is complex
- ❌ Doesn't integrate with Azure CLI

### Option 3: Public Registry Proxy

You could proxy through a public npm registry, but:
- ❌ Additional infrastructure
- ❌ Security concerns
- ❌ Caching complexity

The `vsts-npm-auth` + lifecycle hooks approach is the sweet spot of automation and simplicity.

## Conclusion

Working with private npm feeds in .NET Aspire doesn't have to be painful. By leveraging npm lifecycle hooks (`preinstall`), Azure CLI integration (`vsts-npm-auth`), and environment variables for pipelines (`VSS_NUGET_ACCESSTOKEN`), you can maintain the seamless "F5 experience" that makes Aspire so productive.

The key is recognizing that local development and pipeline builds are fundamentally different environments, and handling each appropriately. Once configured, your team can focus on building features instead of fighting with authentication.

---

*Working on a similar setup? Run into issues? I'd love to hear about your experience in the comments below!*

## Related Posts

- [Scaling Your AI Development Team with Git Worktrees](/2025/10/20/scaling-your-ai-development-team-with-git-worktrees.html)