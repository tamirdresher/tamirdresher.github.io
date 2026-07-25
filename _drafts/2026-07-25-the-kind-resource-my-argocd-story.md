---
layout: post
title: "The Kind Resource: My argo-cd Story, and Why Aspire Is Quietly Disrupting DevOps"
date: 2026-07-25T07:15:00+03:00
tags: [dotnet-aspire, platform-engineering, devops, argo-cd, kubernetes, kind, cncf, inner-loop]
description: "The story of how a real feature request in Argo CD (issue #18000) turned into days of local-dev pain — and how the Kind resource in .NET Aspire quietly disrupts the way cloud-native projects onboard contributors."
---

> **Part 2 of 3.** In [Part 1]({% post_url 2026-07-25-a-kubernetes-operator-with-a-debugger-not-a-deployment %}), I built the tiny version: a Greeter operator, a Kind cluster, and a debugger-first Aspire loop. This is the real-world version. Same pattern. Bigger project. More archaeology. In [Part 3]({% post_url 2026-07-25-same-operator-loop-in-typescript %}) I do the same thing with a TypeScript AppHost, for readers who don't live in .NET.

## 1. The hook

A while back I wanted a feature in Argo CD.

Specifically, [issue #18000 — `syncPolicy.DisableHelmChartCache=true`](https://github.com/argoproj/argo-cd/issues/18000). Leland Knight had opened it, we had been discussing it, and I decided to just try building the fix myself.

The request was practical: let a Helm-source Application say, "do not cache the chart." That matters in dev loops. It also matters with OCI Helm registries where charts can be updated in-place without a version bump. If the chart content changes but the version string does not, the cache becomes the enemy. And like most good feature requests, it was small enough to sound easy before I actually touched the code.

So I did what every OSS contributor does.

I cloned the repo.

Then I spent days getting it to run.

Not because Argo CD is badly maintained. Quite the opposite. Argo CD is a mature CNCF project with serious maintainers, real documentation, real developer workflows, and a codebase that has earned every bit of its operational complexity. This is not a dunk on Argo CD. I like Argo CD. That is why I wanted to contribute.

But mature cloud-native projects accumulate local-dev sediment.

A Makefile layer here. A `hack` script there. A Procfile. A Kind cluster. Tilt. Kubernetes patches. UI dependencies. Corepack shims. Generated assets. One guide linking to another guide linking to a note that assumes you already ran the thing from the previous guide. None of those pieces is irrational. Each one exists because someone solved a real problem at a real moment.

The problem is what happens after five years of real moments.

You do not get a clean contributor loop. You get a pilgrimage.

I worked through the READMEs, the developer guides, the shell scripts, the Makefile targets, the Tilt setup, the Kubernetes patching, and the little platform-specific edges that always appear right when you think you are done. Eventually I had the system running. But by that point, I had spent more energy proving that my laptop was acceptable to the project than understanding the feature I wanted to build.

At some point I was not debugging Argo CD anymore.

I was debugging my ability to become acceptable to Argo CD.

That line sounds funny because it is true in the way platform engineers recognize immediately and then stare out a window for a second.

This is the part of open source we under-talk about. We measure time-to-first-issue, time-to-merge, review latency, CI health, and test coverage. Those are all useful. But there is another metric hiding underneath them: how long does it take a motivated contributor to get from "I cloned the repo" to "I am stepping through the code path I care about"?

For a lot of cloud-native projects, the answer is still: longer than it should.

That contributor experience is the problem this post is about.

## 2. The fix

Quick refresher, especially if you did not read Part 1: Aspire is a code-first, polyglot orchestrator for distributed apps. The center is an AppHost — a small program, in C#, TypeScript, JavaScript, and other supported shapes — that describes your app as a resource graph. Containers, processes, cloud resources, dependencies, endpoints, health, and startup ordering live together. When you run it, Aspire starts the graph and gives you a dashboard with logs, state, health, traces, and resource actions. The shortest version lives at [aspire.dev](https://aspire.dev): compose, debug, and deploy distributed applications from code.

For cloud-native inner loops, the missing piece is the cluster.

That is where `CommunityToolkit.Aspire.Hosting.Kind` comes in. It gives the AppHost a real local Kubernetes cluster as a first-class Aspire resource instead of a paragraph in a README that says, "Before you start, create a cluster and apply these things."

The API is intentionally boring, which is my favorite kind of API.

```csharp
var stagingCluster = builder
    .AddKindCluster("staging-cluster")
    .WithWorkerNodes(2)
    .WithKubernetesVersion("v1.31.0")
    .WithClusterLifetime(ClusterLifetime.Persistent)
    .WithPortMapping(hostPort: 80, containerPort: 80)   // ← from our small extensions project
    .WithPortMapping(hostPort: 443, containerPort: 443) // ← same
    .WithHelmChart(
        releaseName: "ingress-nginx",
        chart: "ingress-nginx/ingress-nginx",
        @namespace: "ingress-nginx")
    .WithManifest("k8s/namespace.yaml");                // ← from our small extensions project
```

That whole thing is just a fluent builder.

Cluster creation. Node topology. Kubernetes version pinning. Port mapping. Helm chart installation. Manifest apply. Readiness wait.

Typed C#. Under a debugger. In the same program that describes the rest of the local system.

Not bash. Not Terraform. Not a README ritual with three "important" notes that only become important after you miss one.

The killer method in that snippet is `WithManifest(path)`.

In the earlier version of this experiment, applying Kubernetes state after cluster creation required a bespoke Aspire lifecycle hook. The hook listened for the Kind cluster to become ready, ran `kubectl apply`, updated resource properties, toggled health state, and carried enough ceremony that I had a little state singleton sitting in the middle of the AppHost like a tiny bureaucrat with a clipboard.

It worked.

It was also a smell.

`WithManifest` removes that entire custom bootstrap hook. When the cluster is ready, it kubectl-applies the manifest. Health reflects the result. Downstream resources that call `.WaitFor(cluster)` unblock only after the cluster is ready for them. No custom bootstrap code. No state singleton. No health-check ping-pong. No "remember to run this first" paragraph trying to cosplay as a dependency graph.

Two of the methods in the money-shot above (`WithPortMapping` and `WithManifest`) are not shipped by the CommunityToolkit package itself. They live in a small companion project I wrote — `TamirDresher.Aspire.Hosting.Kind.Extensions` — that adds only the missing pieces on top of the upstream integration. The upstream `CommunityToolkit.Aspire.Hosting.Kind` source is used unmodified; the extensions project is two files that add these two methods and nothing else. When those APIs land upstream, the extensions project gets deleted. That is the healthy version of "fork and PR back": the sample uses the real integration and layers additions where they are genuinely missing, without inventing a parallel implementation.

I contribute to `CommunityToolkit.Aspire.Hosting.Kind`, so upstreaming `WithManifest` and `WithPortMapping` is on my list.

That one method matters because it represents the larger pattern: every "install → configure → verify" step in a platform README wants to become a fluent-builder call with a debugger.

`WithHelmChart` is the same pattern. So is `WithPortMapping`. So is `WithNodeCount`. So is `WithKubernetesVersion`. They are not glamorous. They are better than glamorous: they delete human ceremony.

In the Argo CD experiment, that deletion was very visible. The AppHost went from roughly 180 lines to roughly 100 lines once the Kind resource absorbed the bootstrap work. Less code is nice. Less special local-dev ritual is the real win.

The sample repo for this is `https://github.com/tamirdresher/aspire-argocd-dev-loop`. It is private while I am finishing this post and will be made public when the post drops.

The layout is deliberately plain:

- `src/ArgoCd.Aspire.AppHost/` holds the AppHost.
- `src/CommunityToolkit.Aspire.Hosting.Kind/` holds the **upstream integration used unmodified** (vendored while I wait for it to publish to NuGet).
- `src/TamirDresher.Aspire.Hosting.Kind.Extensions/` holds the two additions on top — `WithManifest` and `WithPortMapping`. Two files, roughly 200 lines of C#.
- `docs/` explains the loop.
- `scripts/clone-argocd.ps1` clones the Argo CD fork in the expected shape.
- `tests/` validates the resource model and startup assumptions.

The topology is the important part.

The Kind cluster is state-only. It holds the Argo CD namespace, CRDs, RBAC, ConfigMaps, Secrets, and Kubernetes API state. The Argo CD components I am editing do not run as Kubernetes workloads in the default inner loop. They run as Aspire host processes on my machine.

Redis is a container resource. The UI is a `pnpm` host process. The Argo CD Go binaries are `AddGoApp` resources. The dependency graph is explicit with `.WaitFor()`.

That last sentence is the whole trick.

A C# AppHost can orchestrate a Go cloud-native project because Aspire does not care whether the thing in the graph is a .NET service. `Aspire.Hosting.Go` gives me `AddGoApp`, so a component can be a real Go app launched from source. The dashboard still sees it. Logs still stream. Health still composes. Dependencies still order startup. Debugger support becomes part of the loop instead of a footnote.

So instead of treating Argo CD's local process model as sacred knowledge hidden in a Procfile, the AppHost turns it into typed extension methods: repo server, API server, application controller, application set controller, notifications controller, commit server, UI. Each wrapper captures the flags and environment that component needs. The graph captures who waits for whom.

That is not magic. It is better than magic. It is boring code you can read.

The polyglot moment still makes me happy. The AppHost is C#, the services are Go, the UI is JavaScript/TypeScript, Redis is a container, Kubernetes is Kind, and the whole thing still shows up as one application. Not one language. Not one framework. One topology. That is the mental model I want contributors to have on day one.

The happy path is now the thing I wanted when I first cloned Argo CD:

```powershell
git clone https://github.com/tamirdresher/aspire-argocd-dev-loop
.\scripts\clone-argocd.ps1
$env:GOMAXPROCS="2"
aspire start
```

That replaces days of contributor onboarding with a few commands and an executable graph.

To be honest, there were still sharp edges, because reality remains undefeated and occasionally enjoys slapstick.

Upstream Argo CD's current main had two regressions that this loop caught and that I fixed today in my fork branch, `tamirdresher/argo-cd`, branch `tamirdresher-microsoft-aspire-kind-dev-review-fix`.

The first was a Cobra boolean flag parsing change. Some bool arguments that used to tolerate `--flag value` now need the explicit `--flag=value` form. For example, `--disable-auth true` needs to become `--disable-auth=true`. That fix shipped as commit `27b8565`.

The second was a UI dependency refresh: the UI needed `@codecov/webpack-plugin`. That fix shipped as commit `6e7f773`.

Those are exactly the kinds of problems I want the local loop to catch. Not after a contributor has spent two days assembling the environment. Immediately. In the graph. With logs in one place.

The other caveat is memory. Argo CD is not a tiny Go program. The full inner loop can compile seven Go binaries in parallel, and on this specific machine the host paging file is too small for that much `Process.Start` pressure. The code is correct; the machine is memory-constrained. That is why the quickstart sets `$env:GOMAXPROCS="2"`. It lowers the pressure enough for laptop-class development.

The validation matched that story. `dotnet build` is clean: 0 warnings, 0 errors. The tests are 87 out of 88 passing. The one failing test fails only because the host paging file is too small for `Process.Start`, the same memory constraint that prevents the full seven-binary parallel compile on this machine.

That is an honest caveat, and it is also useful. If you are trying this on a memory-constrained laptop, set `GOMAXPROCS=2` before you blame yourself, the repo, Go, Kubernetes, Windows, or the moon.

I usually blame the moon third.

## 3. The thesis

Here is the careful version of the disruption claim.

Aspire does not replace Kubernetes.

That is not the interesting sentence. I do not want a local orchestrator pretending production does not exist. I do not want to hide the cluster from platform engineers. The cluster is the thing. Kubernetes is still where the CRDs live, where the API server enforces reality, where controllers observe state, and where production texture matters.

The interesting sentence is this:

Aspire makes Kubernetes' outside modellable in code.

By "outside" I mean all the things around the cluster that every serious cloud-native project needs before a contributor can do useful work: the local cluster, the manifests, the sidecars, the supporting containers, the host processes, the UI, the dependency ordering, the ports, the health checks, the generated state, the commands, the little readiness rituals, and the "please run this before that" knowledge that slowly migrates into documentation because documentation is where pain goes when we have not modeled it yet.

The setup doc is the smell.

A good README is still important. I love a good README. But if the README is carrying topology, lifecycle, dependency ordering, health verification, and environment-specific caveats, then the README is doing work that belongs in a program.

An executable AppHost is better than a paragraph that says "first create a Kind cluster." A fluent builder call is better than a shell snippet that applies a manifest and hopes everyone remembers when it should happen. A `.WaitFor(cluster)` edge is better than "wait until the cluster is ready" as tribal instruction.

That is why `WithManifest` is more than a convenience method. It is the archetype. It says the install-configure-verify sequence belongs in the resource model. `WithHelmChart` says the same thing. So does `WithPortMapping`. So does `WithNodeCount`. Each one moves a piece of local platform ceremony out of prose and into code.

And once it is code, it can be debugged. It can be reviewed. It can be tested. It can be reused.

The Kind integration is not Argo-CD-specific. Any project with Kubernetes state plus host processes can benefit from the same shape. Operators. Controllers. CLIs that talk to the API server. UIs that expect services to exist. Test harnesses that need a real cluster but do not need every edit to become a container image.

The pattern is: keep real state real, run editable code close to the debugger, and let the AppHost model the topology between them.

That is not a .NET-only idea either. Aspire's AppHost can be TypeScript or JavaScript. The C# examples exist because that ecosystem got the first wave of docs and integrations, but the concept is not "platform engineers must become .NET developers." Platform engineers who live in JS or TS should be able to model local topology in the language they already use. Again: [aspire.dev](https://aspire.dev) is the place to track the current language and integration story.

The deeper point is onboarding.

Every minute a contributor spends fighting local setup is a minute they are not spending understanding the code. Maintainers should care about that. Not as a kindness, although kindness is underrated. They should care because setup friction selects against contribution. It punishes the people who are motivated enough to help but not yet steeped in the project's accumulated rituals.

A debugger-first AppHost is not just nicer. It is a maintenance strategy.

It makes the local topology visible. It makes assumptions executable. It makes prerequisites fail fast. It makes "what is running?" answerable from a dashboard instead of five terminals. It turns "follow the guide carefully" into "run the graph and let the graph tell you what is missing."

That is the disruption I mean.

It is not glamorous because the best platform work often is not glamorous. It is the work that removes one more implicit step, one more Slack thread, one more "oh, you also need to run this" from the path between intent and understanding. The win is not that the demo looks impressive. The win is that the contributor gets to the boring part faster — and the boring part is where real engineering starts.

No keynote thunder. No "replace your platform" sticker. No pretending Kubernetes got simple because I wrote a fluent API around Kind. Just a quiet shift where a whole category of pain becomes optional.

A while back I spent days getting Argo CD to run.

Next time:

```powershell
git clone https://github.com/tamirdresher/aspire-argocd-dev-loop
.\scripts\clone-argocd.ps1
$env:GOMAXPROCS="2"
aspire start
```

Days into minutes.

That is the disruption I have been waiting for.


