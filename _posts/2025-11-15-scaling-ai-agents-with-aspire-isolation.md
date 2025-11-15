---
layout: post
title: "Scaling AI Coding Agents with .NET Aspire: True Isolation for Parallel Development"
date: 2025-11-15
tags: [aspire, git-worktrees, ai-agents, cosmos-db, isolation, parallel-development, dotnet]
---

In my [previous post about Git worktrees](/2025/10/20/scaling-your-ai-development-team-with-git-worktrees.html), I showed how to run multiple AI agents in parallel, each working on different features. But there was a problem I didn't fully solve: if two agents were working on branches that touched the database, they'd interfere with each other. Cosmos DB emulators, vector databases, message queues—they all shared the same ports and storage. I recently solved this by building clone-aware infrastructure into our Aspire app host. Now each agent gets its own completely isolated environment.

## The Problem: Shared State Kills Parallelism

When you run multiple Git worktrees with AI agents working in parallel, everything seems great until you realize they're all fighting over the same resources:

**All worktrees connect to:**
- The same Cosmos DB emulator (port 8081)
- The same Qdrant vector database (port 6333)
- The same message queues
- The same storage accounts
- The same Aspire dashboard

This creates real problems:

### Data Pollution
**Agent A** creates test data for a feature:
```sql
INSERT INTO Customers (Id, Name) VALUES ('test-123', 'Test Customer')
```

**Agent B** runs a query:
```sql
SELECT * FROM Customers WHERE Name LIKE 'Test%'
```
Agent B sees Agent A's test data and gets confused.

### Schema Conflicts
**Agent A** adds a new required field to the database schema:
```csharp
public class Customer {
    public string Id { get; set; }
    public string Name { get; set; }
    public string Email { get; set; } // Agent A adds this
}
```

**Agent B**'s code breaks because it doesn't know about the Email field yet.

### Port Conflicts
You try to start a third worktree:
```
Error: Port 8081 is already in use by Cosmos DB emulator
Error: Port 6333 is already in use by Qdrant
Error: Port 17000 is already in use by Aspire dashboard
```

### Race Conditions
Both agents try to process the same queue message, leading to duplicate processing or deadlocks.

The fundamental issue: **your worktrees have isolated code, but shared infrastructure**.

## The Solution: Clone-Aware Infrastructure

The key insight came from realizing that Git worktree folder names are perfect identifiers for creating isolated resources. If my worktree is at `../repo.worktrees/feature-auth`, I can use `feature-auth` as a unique identifier to allocate separate ports, volumes, and containers.

### Architecture Overview

Instead of all worktrees sharing resources:

```
❌ BEFORE (Shared Resources)
├── feature-auth worktree     ┐
├── feature-payments worktree ├──► All use Cosmos on port 8081
└── feature-ui worktree       ┘    All use same data volume
```

We create isolated resources per clone:

```
✅ AFTER (Clone-Aware Resources)

repo.worktrees/feature-auth/
├── Cosmos DB: port 8091, volume: cosmos-feature-auth
├── Qdrant: port 6341
├── Aspire Dashboard: port 17001
└── Queue: queue-feature-auth

repo.worktrees/feature-payments/
├── Cosmos DB: port 8092, volume: cosmos-feature-payments
├── Qdrant: port 6342
├── Aspire Dashboard: port 17011
└── Queue: queue-feature-payments

repo.worktrees/feature-ui/
├── Cosmos DB: port 8093, volume: cosmos-feature-ui
├── Qdrant: port 6343
├── Aspire Dashboard: port 17021
└── Queue: queue-feature-ui
```

Each clone is completely isolated. No shared state, no conflicts, true parallel development.

## Implementation Deep Dive

Let me show you exactly how to build this.

### Step 1: Detect the Clone Name from Git Folder

First, we need to detect which Git worktree we're running in. Git worktrees have a predictable structure:

```
my-repo/              # Main repository
my-repo.worktrees/    # Worktrees folder
├── feature-auth/     # Worktree for feature-auth branch
├── feature-payments/ # Worktree for feature-payments branch
└── bugfix-logging/   # Worktree for bugfix-logging branch
```

Here's the utility that extracts the clone name:

```csharp
public static class GitFolderResolver
{
    public static string? GetGitFolderName()
    {
        var currentDir = Directory.GetCurrentDirectory();
        
        // Check if we're in a worktree
        // Worktrees follow pattern: repo-name.worktrees/branch-name/
        if (currentDir.Contains(".worktrees"))
        {
            var parts = currentDir.Split(Path.DirectorySeparatorChar);
            var worktreeIndex = Array.FindIndex(parts, p => p.EndsWith(".worktrees"));
            
            if (worktreeIndex >= 0 && worktreeIndex < parts.Length - 1)
            {
                // Return the folder name after .worktrees
                return parts[worktreeIndex + 1];
            }
        }
        
        // Not in a worktree, return null (will use "default")
        return null;
    }
}
```

This extracts `feature-auth` from a path like:
```
C:\Projects\my-repo.worktrees\feature-auth\YourProject.AppHost
```

### Step 2: Extension Method to Resolve Clone Name

Add an extension method to make it easy to get the clone name in your AppHost:

```csharp
public static class CosmosCloneExtensions
{
    public static string ResolveCloneName(this IDistributedApplicationBuilder builder)
    {
        var options = new CosmosCloneOptions();
        
        // Priority for clone name resolution:
        // 1. Explicit option
        // 2. Environment variable (CLONE_NAME)
        // 3. Configuration value (CloneName)
        // 4. Git folder name (supports worktrees)
        // 5. "default" as fallback
        
        return options.CloneName
            ?? builder.Configuration["CLONE_NAME"]
            ?? builder.Configuration["CloneName"]
            ?? GitFolderResolver.GetGitFolderName()
            ?? "default";
    }
}
```

This gives you flexibility—you can override the clone name via environment variables if needed, but it defaults to auto-detecting from the worktree folder.

### Step 3: Clone-Aware Cosmos DB

Now create an extension method that configures Cosmos DB with isolation:

```csharp
public static IResourceBuilder<AzureCosmosDBResource> AddCloneAwareCosmosDB(
    this IDistributedApplicationBuilder builder,
    string name,
    Action<CosmosCloneOptions>? configureOptions = null)
{
    var options = new CosmosCloneOptions();
    configureOptions?.Invoke(options);
    
    // Resolve clone name and shared flag
    var cloneName = builder.ResolveCloneName();
    var useShared = options.UseSharedInstance 
        || builder.Configuration["USE_SHARED_COSMOS"] == "true";
    
    // Get or create clone configuration with persistent state
    var manager = new CosmosCloneManager(options.StateFolder);
    var config = manager.GetOrCreateCloneConfig(cloneName, useShared, 
                                                 options.FixedPort, 
                                                 options.FixedVolume);
    
    // Create Cosmos DB resource with clone-specific settings
    return builder.AddAzureCosmosDB(name)
        .RunAsPreviewEmulator(emulator =>
        {
            emulator
                .WithContainerName($"{name}-{cloneName}")
                .WithGatewayPort(config.Port)
                .WithDataVolume(config.VolumeFolder)
                .WithLifetime(ContainerLifetime.Persistent)
                .WithDataExplorer()
                .WithEnvironment("AZURE_COSMOS_EMULATOR_PARTITION_COUNT", "2")
                .WithEnvironment("AZURE_COSMOS_EMULATOR_IP_ADDRESS_OVERRIDE", "127.0.0.1");
        });
}
```

Key points:
- **Container name** includes clone name for uniqueness
- **Port** is dynamically allocated per clone
- **Volume** is isolated per clone
- **Persistent lifetime** ensures data survives restarts

### Step 4: Port Management

We need a way to allocate free ports dynamically:

```csharp
public static class PortManager
{
    private static readonly object _lock = new object();
    
    public static int GetAvailablePort()
    {
        lock (_lock)
        {
            var listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start();
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            listener.Stop();
            return port;
        }
    }
}
```

This asks the OS for a free port, ensuring no conflicts.

### Step 5: Persistent State Management

The [`CosmosCloneManager`](CosmosCloneManager.cs) tracks port allocations in a JSON file:

```csharp
public class CosmosCloneManager
{
    private readonly string _stateFolder;
    private const string StateFileName = "cosmos-clones.json";
    
    public CosmosCloneManager(string stateFolder = ".aspire")
    {
        _stateFolder = stateFolder;
    }
    
    public CosmosCloneConfiguration GetOrCreateCloneConfig(
        string cloneName,
        bool useShared,
        int? fixedPort = null,
        string? fixedVolume = null)
    {
        var stateFile = Path.Combine(_stateFolder, StateFileName);
        var configs = LoadConfigurations(stateFile);
        
        // Check if configuration already exists
        var existing = configs.FirstOrDefault(c => c.CloneName == cloneName);
        if (existing != null)
        {
            return existing; // Reuse existing port/volume
        }
        
        // Create new configuration
        var port = fixedPort ?? (useShared ? 8081 : PortManager.GetAvailablePort());
        var volume = fixedVolume ?? (useShared 
            ? "cosmos-shared" 
            : $"cosmos-{cloneName}");
        
        var config = new CosmosCloneConfiguration
        {
            CloneName = cloneName,
            Port = port,
            VolumeFolder = volume,
            IsShared = useShared,
            CreatedAt = DateTime.UtcNow
        };
        
        configs.Add(config);
        SaveConfigurations(stateFile, configs);
        
        return config;
    }
}
```

The state file looks like:

```json
{
  "Clones": [
    {
      "CloneName": "feature-auth",
      "Port": 8091,
      "VolumeFolder": "cosmos-feature-auth",
      "IsShared": false,
      "CreatedAt": "2025-11-15T10:30:00Z"
    },
    {
      "CloneName": "feature-payments",
      "Port": 8092,
      "VolumeFolder": "cosmos-feature-payments",
      "IsShared": false,
      "CreatedAt": "2025-11-15T10:35:00Z"
    }
  ]
}
```

This ensures:
- **Consistency**: Same clone always gets the same port
- **Persistence**: Survives app restarts
- **Cleanup**: Can identify unused clones

### Step 6: Dynamic Aspire Dashboard Ports

Each clone should also have its own Aspire dashboard:

```csharp
var builder = DistributedApplication.CreateBuilder(args);

// Allocate dynamic ports for Aspire dashboard
int GetFreePort()
{
    var listener = new TcpListener(IPAddress.Loopback, 0);
    listener.Start();
    int port = ((IPEndPoint)listener.LocalEndpoint).Port;
    listener.Stop();
    return port;
}

// Configure dashboard on unique ports
builder.Configuration["ASPIRE_DASHBOARD_OTLP_ENDPOINT_URL"] =
    $"http://localhost:{GetFreePort()}";
builder.Configuration["ASPIRE_RESOURCE_SERVICE_ENDPOINT_URL"] =
    $"http://localhost:{GetFreePort()}";
```

### Step 7: Application Naming

Give each clone a unique application name in the dashboard:

```csharp
builder.Environment.ApplicationName =
    $"{builder.Environment.ApplicationName}-{builder.ResolveCloneName()}";
```

This shows:
- `YourProject-feature-auth` in one dashboard
- `YourProject-feature-payments` in another
- `YourProject-feature-ui` in a third

### Step 8: Using Clone-Aware Resources

In your [`AppHost.cs`](AppHost.cs), replace standard resource creation:

```csharp
// ❌ OLD: Shared Cosmos DB
var cosmos = builder.AddAzureCosmosDB("Onboarding")
    .RunAsEmulator();

// ✅ NEW: Clone-aware Cosmos DB
var cosmos = builder.AddCloneAwareCosmosDB("Onboarding");
```

That's it! The extension handles all the complexity.

For other resources, apply the same pattern:

```csharp
// Clone-aware Qdrant
var qdrant = builder.AddQdrant($"qdrant-{builder.ResolveCloneName()}")
    .WithGatewayPort(GetDynamicPort(6333))
    .WithLifetime(ContainerLifetime.Persistent);

// Clone-aware storage queues
var storage = builder.AddAzureStorage("storage")
    .RunAsEmulator(emulator =>
    {
        emulator
            .WithDataVolume($"storage-{builder.ResolveCloneName()}")
            .WithLifetime(ContainerLifetime.Persistent);
    });
```

## The Complete Workflow

Let me show you the end-to-end experience.

### Initial Setup (One Time)

```bash
# Main repo
cd my-repo
git checkout main
```

### Creating Isolated Agents

**Agent 1: Authentication Feature**
```bash
# Create worktree
git worktree add ../my-repo.worktrees/feature-auth feature-auth

# Open in VS Code
code ../my-repo.worktrees/feature-auth

# Press F5
# Aspire detects clone name: "feature-auth"
# Allocates: Cosmos port 8091, Qdrant port 6341, Dashboard port 17001
# Creates volumes: cosmos-feature-auth, storage-feature-auth
# Application name: "YourProject-feature-auth"
```

**Agent 2: Payment Processing**
```bash
# Create another worktree
git worktree add ../my-repo.worktrees/feature-payments feature-payments

# Open in different VS Code window
code ../my-repo.worktrees/feature-payments

# Press F5
# Aspire detects clone name: "feature-payments"
# Allocates: Cosmos port 8092, Qdrant port 6342, Dashboard port 17011
# Creates volumes: cosmos-feature-payments, storage-feature-payments
# Application name: "YourProject-feature-payments"
```

**Agent 3: UI Updates**
```bash
git worktree add ../my-repo.worktrees/feature-ui feature-ui
code ../my-repo.worktrees/feature-ui
# Press F5 - gets its own isolated resources
```

### What Each Agent Sees

**Agent 1 (feature-auth):**
- Dashboard at `https://localhost:17001`
- Cosmos DB on port 8091
- Only sees data it created
- Can make breaking schema changes without affecting others

**Agent 2 (feature-payments):**
- Dashboard at `https://localhost:17011`
- Cosmos DB on port 8092
- Completely isolated data
- Can test payment flows independently

**Agent 3 (feature-ui):**
- Dashboard at `https://localhost:17021`
- Cosmos DB on port 8093
- Can work on UI without backend interference
- Tests with clean state

### Monitoring All Agents

Alt+Tab between dashboard URLs:
- `https://localhost:17001` - feature-auth progress
- `https://localhost:17011` - feature-payments progress
- `https://localhost:17021` - feature-ui progress

Each dashboard shows its clone's isolated resources.

## Real-World Experience

In practice, I've successfully run **four agents simultaneously**:

1. **feature-auth** - Implementing Azure AD authentication
2. **feature-api** - Building REST API endpoints
3. **feature-ui** - Creating React components
4. **bugfix-logging** - Fixing logging configuration issues

Each had:
- ✅ Own Cosmos DB instance (no data pollution)
- ✅ Own message queues (no duplicate processing)
- ✅ Own Aspire dashboard (independent monitoring)
- ✅ Own VS Code window with dedicated AI agent

**Result:**
- 4x productivity (truly parallel work)
- Zero merge conflicts from database issues
- No "wait for Agent A to finish" bottlenecks
- Independent testing of each feature

**Concrete Example:**

**Agent 1** (feature-auth) was testing:
```csharp
// Creates test users in its Cosmos DB
await cosmosDb.CreateItemAsync(new User { 
    Id = "test-user",
    Email = "test@example.com" 
});
```

**Agent 2** (feature-api) was simultaneously:
```csharp
// Queries its own Cosmos DB - doesn't see Agent 1's data
var users = await cosmosDb.GetItemsAsync<User>();
// Returns empty - as expected!
```

No interference, no confusion.

## Benefits

### 1. True Parallelism

Multiple agents work simultaneously without blocking each other:
- No "wait for database to be free"
- No "stop your agent so I can test"
- No resource contention

### 2. Data Isolation

Each clone has its own data:
- Test data doesn't pollute other clones
- Can use realistic production-like data volumes
- Reset state without affecting others

### 3. Independent Schema Evolution

Make breaking changes fearlessly:
```csharp
// feature-auth: Add required Email field
public class User {
    public required string Email { get; set; } // Breaking change!
}

// feature-payments: Still works with old schema
public class User {
    // No Email field yet
}
```

### 4. Easy Cleanup

Delete a worktree, volumes are clearly labeled:
```bash
# Remove worktree
git worktree remove feature-auth

# Clean up volumes
docker volume rm cosmos-feature-auth storage-feature-auth

# Remove from state
# (Can add cleanup command)
```

### 5. Persistent State

Stop and restart without losing data:
```bash
# Stop agent (Ctrl+C)
# Do something else
# Restart (F5)
# All data still there - same ports, same volumes
```

## Advanced: Shared Resources When Needed

Sometimes you WANT sharing, like read-only reference data:

```csharp
// Reference data shared across all clones
var sharedCosmos = builder.AddCloneAwareCosmosDB("ReferenceData", options =>
{
    options.UseSharedInstance = true; // Force sharing
});

// Clone-specific operational data
var isolatedCosmos = builder.AddCloneAwareCosmosDB("Onboarding");
// Automatically isolated
```

Or use environment variables:

```bash
# Force shared Cosmos for this clone
export USE_SHARED_COSMOS=true
dotnet run
```

## Environment Variables for Control

Full control via environment:

```bash
# Explicit clone name (overrides folder detection)
export CLONE_NAME="my-special-test"

# Use shared Cosmos instead of isolated
export USE_SHARED_COSMOS=true

# Custom state folder
export COSMOS_STATE_FOLDER="/path/to/state"
```

## Management and Cleanup

### List All Clones

```csharp
var manager = new CosmosCloneManager();
var clones = await manager.GetAllConfigurationsAsync();

foreach (var clone in clones)
{
    Console.WriteLine($"{clone.CloneName}: Port {clone.Port}, Volume {clone.VolumeFolder}");
}
```

Output:
```
feature-auth: Port 8091, Volume cosmos-feature-auth
feature-payments: Port 8092, Volume cosmos-feature-payments
feature-ui: Port 8093, Volume cosmos-feature-ui
```

### Remove Old Clone

```csharp
await manager.DeleteCloneConfigAsync("feature-auth");
```

### Docker Volume Cleanup

```bash
# List volumes
docker volume ls | grep cosmos-

# Remove specific clone
docker volume rm cosmos-feature-auth

# Remove all clone volumes (careful!)
docker volume ls | grep "cosmos-feature" | awk '{print $2}' | xargs docker volume rm
```

## Best Practices

### 1. Configure Dynamic Ports in launchSettings.json

To avoid port conflicts between different clones running the same services, ensure your `launchSettings.json` doesn't hardcode specific ports. Instead, let the OS assign available ports dynamically:

```json
{
  "profiles": {
    "YourProject.ApiService": {
      "commandName": "Project",
      "launchBrowser": true,
      "environmentVariables": {
        "ASPNETCORE_ENVIRONMENT": "Development"
      },
      "applicationUrl": "https://localhost;http://localhost"
    }
  }
}
```

**Key points:**
- ❌ **Don't use:** `"applicationUrl": "https://localhost:5001;http://localhost:5000"` (fixed ports)
- ✅ **Do use:** `"applicationUrl": "https://localhost;http://localhost"` (dynamic ports)

Without port numbers, .NET automatically allocates free ports. This is crucial because:

**With Fixed Ports (❌):**
```
Clone 1: API tries to use port 5001 ✅
Clone 2: API tries to use port 5001 ❌ (conflict!)
Clone 3: API tries to use port 5001 ❌ (conflict!)
```

**With Dynamic Ports (✅):**
```
Clone 1: API gets port 5001 ✅
Clone 2: API gets port 5137 ✅
Clone 3: API gets port 5294 ✅
```

Aspire handles service discovery through its orchestration layer, so your services will still find each other even with dynamic ports.

**Apply this to all your service projects:**
- API services
- Web frontends (when running outside Aspire)
- Worker services
- MCP servers

This ensures each clone's services can run simultaneously without port collisions.

### 2. Use Descriptive Clone Names

Match your branch names:
```bash
git worktree add ../repo.worktrees/feature-auth feature-auth
# Clone name: "feature-auth" ✅

# Not:
git worktree add ../repo.worktrees/temp feature-auth
# Clone name: "temp" ❌ (not descriptive)
```

### 2. Clean Up Old Worktrees

```bash
# List worktrees
git worktree list

# Remove finished ones
git worktree remove feature-auth

# Prune stale references
git worktree prune
```

### 3. Monitor Disk Space

Each clone needs storage:
```bash
# Check Docker disk usage
docker system df

# Clean up unused volumes periodically
docker volume prune
```

### 4. Document Environment Variables

In your README:
```markdown
## Environment Variables

- `CLONE_NAME`: Override auto-detected clone name
- `USE_SHARED_COSMOS`: Use shared Cosmos instead of isolated (true/false)
- `COSMOS_STATE_FOLDER`: Custom folder for state files (default: .aspire)
```

### 5. Add .worktrees to .gitignore

```gitignore
# Git worktrees
../*.worktrees/

# Aspire state
.aspire/
cosmos-clones.json
```

## Limitations and Considerations

### Resource Usage

Each clone consumes:
- **CPU**: Cosmos DB emulator, Qdrant, etc.
- **Memory**: ~2-4GB per clone
- **Disk**: ~500MB-2GB per clone volume

**Practical limit:** 3-5 active clones on a typical dev machine.

### Complexity

More moving parts:
- Multiple dashboards to monitor
- Multiple containers to manage
- State files to track

**Mitigation:** Good tooling and documentation.

### Learning Curve

Team needs to understand:
- Git worktrees concept
- Clone-aware infrastructure
- When to use isolation vs sharing

**Mitigation:** Pair programming during onboarding.

### Port Exhaustion

With many clones:
- Each needs 3-5 ports
- Can exhaust ephemeral port range

**Mitigation:** Clean up old clones regularly.

## Comparison: Before vs After

### Before (Shared Resources)

```
├── feature-auth worktree
│   └── Code: Isolated ✅
│   └── Data: SHARED ❌
│   └── Ports: SHARED ❌
│
├── feature-payments worktree
│   └── Code: Isolated ✅
│   └── Data: SHARED ❌  ← Conflicts!
│   └── Ports: SHARED ❌  ← Conflicts!
```

**Problems:**
- ❌ Port conflicts when scaling
- ❌ Data pollution between features
- ❌ Schema migration conflicts
- ❌ One agent blocks others
- ❌ Manual coordination required

### After (Clone-Aware Infrastructure)

```
├── feature-auth worktree
│   └── Code: Isolated ✅
│   └── Data: Isolated ✅
│   └── Ports: Unique ✅
│   └── Dashboard: 17001 ✅
│
├── feature-payments worktree
│   └── Code: Isolated ✅
│   └── Data: Isolated ✅
│   └── Ports: Unique ✅
│   └── Dashboard: 17011 ✅
```

**Benefits:**
- ✅ No port conflicts
- ✅ Isolated data per feature
- ✅ Independent schema evolution
- ✅ True parallel development
- ✅ Zero coordination overhead

## Conclusion

By combining Git worktrees with clone-aware Aspire infrastructure, you unlock true parallel development with AI agents. Each agent works in complete isolation—separate code, separate data, separate resources—eliminating the conflicts and coordination overhead that plague shared development environments.

The implementation is surprisingly straightforward:
1. Detect clone name from Git folder structure
2. Use clone name to allocate unique ports and volumes
3. Store port assignments in persistent state
4. Apply pattern to all stateful resources

The result is a development workflow where you can:
- Run multiple AI agents in parallel
- Each agent has its own isolated environment
- Zero interference between agents
- Easy monitoring via multiple Aspire dashboards
- Clean separation that mirrors your branch structure

This approach transformed my AI agent team from a theoretical concept into a practical reality. I went from sequential development (one agent at a time) to truly parallel development (four agents simultaneously), with zero coordination overhead.

If you're already using Git worktrees with AI agents, adding clone-aware infrastructure is the missing piece that turns parallelism from wishful thinking into daily reality.

---

*Have you tried parallel development with multiple AI agents? What challenges did you face with shared resources? I'd love to hear about your experience in the comments!*

## Related Posts

- [Scaling Your AI Development Team with Git Worktrees](/2025/10/20/scaling-your-ai-development-team-with-git-worktrees.html) - The foundation for parallel AI development
- [Seamless Private NPM Feeds in .NET Aspire](/2025/11/15/seamless-private-npm-feeds-in-dotnet-aspire.html) - Handling private packages in Aspire
- [Give Your AI Coding Agent Eyes with Playwright MCP](/2025/11/15/give-your-ai-coding-agent-eyes-with-playwright-mcp.html) - Visual testing for AI agents