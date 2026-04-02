---
layout: post
title: "From Bicep to C#: Provisioning Azure AI Foundry with Aspire"
date: 2026-04-02
tags: [aspire, azure-ai-foundry, developer-experience, cloud-native, ai, aspire-conf-2026, book-of-news]
series: "Scaling AI-Native Software Engineering"
---

There's a moment every .NET developer who has shipped an AI-powered app knows well. You've got your C# code working perfectly locally. Your service calls GPT-4. Your agent chains are tight. And then someone says: "OK, now write the Bicep."

The keyboard goes quiet.

### How This Post Came to Be: Squad Meets Aspire Conf

Before writing this post, I wanted to deeply understand every announcement from Aspire Conf 2026. So I pointed my Squad — an AI team framework that runs as a GitHub Copilot extension — at the Aspire Conf YouTube playlist and asked it to create a "Book of News."

Here's what made this approach powerful: Aspire's design philosophy is *exactly* what enables AI agents to understand cloud-native applications at scale. The Aspire Dashboard provides real-time observability of every service, resource dependency, and health status. The declarative, graph-based approach in the AppHost file meant Squad could easily parse resource relationships, and the strong typing in C# eliminated ambiguity in configuration. For an AI system, this is gold—structured data it can reason about with confidence.

Within minutes, Squad downloaded all 13 session transcripts from the conference, generated structured summaries with key announcements and demos for each session, and assembled a professionally styled PDF — the *Aspire Conf 2026 Book of News*. No manual note-taking. No rewatching sessions at 2x speed. Just a comprehensive digest organized by topic: AI & Agents, Deployment, Testing, Multi-Language Support, DevEx & Tooling, Customer Stories, and Community.

The book highlighted breakthrough features that immediately became the focus of this post:

- **TypeScript AppHost GA** — full-stack teams can now orchestrate infrastructure without leaving JavaScript
- **AWS Lambda integration** — Aspire extends beyond Azure with first-class Lambda support  
- **Docker Compose GA** — local development gets a standardized, portable foundation
- **Helm chart generation** — one command to go from AppHost to production-ready Kubernetes
- **Standalone Aspire Dashboard** — observe any distributed system, even legacy apps
- **GenAI span tracing** — debug AI chains with the same instrumentation as traditional services
- **MCP integration** — AI models can reason about your infrastructure directly via the Model Context Protocol

That book became my research companion for this post. The Azure AI Foundry hosting integration and the broader Aspire 13.2 story jumped out immediately. What would have taken hours of conference watching was distilled into a clear narrative in under 30 minutes.

If you want the full Book of News PDF—with session-by-session breakdowns, code snippets, demo timecodes, and conference highlights—[reach out](mailto:tamir.dresher@gmail.com). I'm happy to share it with any developer exploring what's new in Aspire this quarter.

---

Not because Bicep is bad—it's actually quite good at what it does. But provisioning Azure AI Foundry through Bicep has always required jumping mental contexts. You leave the comfort of strongly-typed C#, navigate a forest of interdependent ARM resources (AI hub, project, storage account, Key Vault, private endpoints…), wire up RBAC role assignments that race-condition their way to failure, and hope the error messages from a failed `az deployment group create` are specific enough to actually debug.

With Aspire 13.2, released March 23, 2026, that context switch is gone. You provision Azure AI Foundry in the same `AppHost` file where you declare your databases, message buses, and microservices—in C#, with full IntelliSense, and with automatic local provisioning for development.

Let's look at what changed, why it matters, and how to migrate today.

---

## The Old Way: Bicep for Every AI Resource

To stand up a production-grade Azure AI Foundry environment, a typical Bicep approach required at minimum:

- An **AI Foundry Hub** (the top-level resource grouping)
- An **AI Foundry Project** (the workspace scoped to your application)
- An **Azure OpenAI** (or other model) deployment wired to the project
- **Storage Account** and **Key Vault** dependencies
- **Managed Identity** with role assignments across all the above
- `bicepparam` files per environment to manage parameter drift

Even for a simple chat application, the infrastructure repository often balloons to 300–500 lines of Bicep across multiple files. Every new team member asks the same question: "Which Bicep file do I touch to add a new model deployment?"

The deeper problem isn't the line count. It's the **cognitive gap** between your application code and your infrastructure definition. When a developer wants to try GPT-4o instead of GPT-4, they need to update the Bicep, redeploy infrastructure, update connection strings, and remember the incantation to rotate secrets. The AI model swap that should take 30 seconds takes 30 minutes.

---

## The New Way: Aspire 13.2 + `Aspire.Hosting.Foundry`

Aspire 13.2 ships with first-class support for Microsoft Foundry (the name for the Azure AI Foundry hosting integration) via two NuGet packages:

| Package | Purpose |
|---|---|
| `Aspire.Hosting.Foundry` | Declares Foundry hubs, projects, and model deployments in AppHost |
| `Aspire.Hosting.Azure.CognitiveServices` | Declares Azure OpenAI and other Cognitive Services resources |

Installation is one command:

```bash
dotnet add package Aspire.Hosting.Foundry
# or via Aspire CLI:
aspire add foundry
```

Now your entire AI infrastructure declaration lives in `AppHost/Program.cs` alongside every other resource your application needs:

```csharp
var builder = DistributedApplication.CreateBuilder(args);

// Declare a Microsoft Foundry hub + project
var foundry = builder.AddFoundry("foundry");

// Add a model deployment — no portal clicking, no Bicep, no ARM
var chat = foundry.AddDeployment("chat", FoundryModel.OpenAI.Gpt4o);
var embeddings = foundry.AddDeployment("embeddings", FoundryModel.OpenAI.TextEmbeddingAda002);

// Your application service gets the connection details injected automatically
var aiService = builder.AddProject<Projects.MyAiService>("ai-service")
    .WithReference(chat)
    .WithReference(embeddings)
    .WaitFor(chat);

// The rest of your stack declares itself exactly as before
var postgres = builder.AddPostgres("db").AddDatabase("vectors");
var api = builder.AddProject<Projects.Api>("api")
    .WithReference(aiService)
    .WithReference(postgres);

builder.Build().Run();
```

That's it. Aspire handles the provisioning graph: it knows that `chat` depends on a Foundry project, which depends on a hub, which needs a storage account and managed identity. You describe the *what*, Aspire figures out the *how*.

---

## How Automatic Provisioning Works

When you run your Aspire AppHost locally, it reads Azure configuration from user secrets (one-time setup per developer):

```json
{
  "Azure": {
    "SubscriptionId": "<your-subscription-id>",
    "ResourceGroupPrefix": "myapp-dev",
    "Location": "eastus2"
  }
}
```

On first launch, Aspire provisions the Azure resources in the background. On subsequent launches, it reuses the existing resources. The Aspire Dashboard shows provisioning status in real-time, and the connection strings flow into your application via the standard `IConfiguration` abstraction—no manual copy-paste of endpoints or API keys.

For production deployments via `azd up`, the same AppHost drives the deployment manifest. You don't write a separate Bicep file; the Aspire tooling generates the bicep it needs internally and applies it for you. The application code, the infra declaration, and the deployment manifest are all the same artefact.

---

## Swapping Models in Three Characters

Here's the developer experience win that makes this integration genuinely transformative. Want to try GPT-5 Mini instead of GPT-4o for cost optimization? One line changes:

```csharp
// Before
var chat = foundry.AddDeployment("chat", FoundryModel.OpenAI.Gpt4o);

// After
var chat = foundry.AddDeployment("chat", FoundryModel.OpenAI.Gpt5Mini);
```

Aspire detects the infrastructure drift and reprovisioning happens on the next run. No Bicep edits. No parameter files. No `az deployment` commands. The strongly-typed `FoundryModel` enum means you get IntelliSense autocomplete over all available models, and a compile error if you reference a model name that doesn't exist.

The same pattern holds for switching between providers entirely. If you want to use Azure OpenAI directly (via Cognitive Services) instead of the Foundry abstraction:

```csharp
// Direct Azure OpenAI via Cognitive Services package
var openai = builder.AddAzureOpenAI("openai");
var chat = openai.AddDeployment(new AzureOpenAIDeployment("gpt-4o", "gpt-4o", "2024-08-06"));

builder.AddProject<Projects.MyAiService>("ai-service")
    .WithReference(chat);
```

And in the consuming project, the client wiring uses the same injection pattern either way:

```csharp
// In MyAiService's Program.cs
builder.AddAzureOpenAIClient("chat");

// Then in any service class:
public class ChatService(AzureOpenAIClient client) { ... }
```

The `WithReference` on the AppHost side maps to `AddAzureOpenAIClient` on the client side. Switch the model or the provider on the AppHost side, and the client code is untouched.

---

## What About Existing Bicep?

If you already have Bicep templates for your AI resources, you don't have to throw them away immediately. Aspire's `AddBicepTemplate()` API lets you reference existing Bicep files from your AppHost while you migrate incrementally. You can move one resource at a time into the Aspire model.

The typical migration path looks like:

1. Add `Aspire.Hosting.Foundry` to your AppHost project
2. Replace your OpenAI/Foundry Bicep declarations with `AddFoundry()` / `AddAzureOpenAI()`
3. Remove connection string manual management from your CI/CD scripts
4. Delete the Bicep files when you've verified parity

Most teams report completing this migration in a single afternoon.

---

## What Else Shipped in Aspire 13.2

The Foundry integration is the headliner, but Aspire 13.2 packed more:

- **TypeScript AppHost GA** — you can now write your orchestration in TypeScript if your team is more JS-native, opening Aspire to full-stack teams that don't want to maintain a separate C# project
- **AI-agent-native CLI** — `aspire` can now be driven programmatically by AI agents, enabling automated environment setup in CI and agentic dev workflows  
- **GenAI Visualizer** — the Dashboard gains prompt tracing and token-flow visualization, so you can debug your AI calls with the same tooling you use to debug your database queries
- **Resource health probes** — declare health check conditions on AI deployments so your services don't start until the model endpoint is warm

---

## The Bottom Line

The best infrastructure is the infrastructure your developers never have to think about. Azure AI Foundry is a powerful platform, but the friction of manual Bicep provisioning has kept it out of reach for teams that want to move fast.

Aspire 13.2 closes that gap. Your AI infrastructure becomes first-class application code—type-safe, co-located with your services, diffable in pull requests, and automatically provisioned for every developer on your team without a single Bicep line in sight.

If you're building AI-powered .NET applications in 2026 and you're still writing Bicep by hand, it's time to upgrade.

---

### Resources

- [Microsoft Foundry hosting integration for Aspire](https://aspire.dev/integrations/cloud/azure/azure-ai-foundry/azure-ai-foundry-host/)
- [Get started with Foundry + Aspire](https://aspire.dev/integrations/cloud/azure/azure-ai-foundry/azure-ai-foundry-get-started/)
- [NuGet: Aspire.Hosting.Foundry](https://www.nuget.org/packages/Aspire.Hosting.Foundry)
- [NuGet: Aspire.Hosting.Azure.CognitiveServices](https://www.nuget.org/packages/Aspire.Hosting.Azure.CognitiveServices)
- [What's new in Aspire 13.2](https://aspire.dev/whats-new/aspire-13-2/)
- [Aspire AI integrations compatibility matrix](https://learn.microsoft.com/en-ca/dotnet/aspire/azureai/ai-integrations-compatibility-matrix)
