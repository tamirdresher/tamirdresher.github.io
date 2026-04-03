---
layout: post
title: "Kubernetes IN Docker, IN Aspire — Why KinD Changes Everything for Platform Engineers"
date: 2026-04-15
tags: [aspire, kubernetes, kind, platform-engineering, community-toolkit, aspire-community-toolkit, crd, operators, controllers, squad, ai-agents]
published: false
---

## The Part of Aspire Nobody Was Talking About

Aspire 13.2 shipped recently, and everyone's talking about the TypeScript AppHost. And honestly? Fair. Being able to write your entire distributed application manifest in TypeScript — service discovery, resource dependencies, environment wiring — is genuinely useful, especially for teams where the AppHost owner is more comfortable in TypeScript than C#.

But that's not the 13.2 thing I keep thinking about.

The thing I keep thinking about is what Aspire can now do for the people who don't build apps *on* Kubernetes — they build the platform *for* Kubernetes.

---

## A Problem I Have at Work

Here's something I don't write about much on this blog: a significant part of my day job involves Kubernetes platform work. Not just deploying apps to K8s — building the K8s extensions themselves. Controllers, operators, CRDs, admission webhooks. The kind of thing where you write code that *watches* Kubernetes resources and reacts to them. Where you define `kind: TenantConfig` and build the reconciler that makes "TenantConfig exists" mean "tenant infrastructure exists."

Testing this stuff has historically been... a process.

The standard flow: spin up a local `kind` cluster (I'll explain what that is in a second), apply your CRDs, run your controller locally against the cluster, poke at it, wait for logs, debug why the reconciler isn't triggering, repeat. It works. But it's friction. Manual steps, no dashboard, logs strewn across multiple terminal windows, and every time you restart the cluster you start from scratch with zero visibility into what just happened.

I've been thinking for a while that there should be a better way. And then, a few weeks ago, I found myself down a rabbit hole with Andrey Noskov, working through what "better" might actually look like.

---

## What KinD Is (For Everyone Who Just Googled It)

Quick clarification because the naming here is genuinely confusing: when I say "KinD," I mean the **tool** — **Kubernetes IN Docker** — not the Kubernetes API concept of `kind: Deployment`. Same letters, completely different thing. (I'll agree with you that this is unfortunate naming.)

[KinD](https://kind.sigs.k8s.io/) is a tool that runs a complete Kubernetes cluster inside Docker containers. You install it, run `kind create cluster`, and in about 30 seconds you have a real, fully functional Kubernetes cluster running on your laptop without needing any cloud resources, any VM, or any prior cluster setup. The control plane runs in Docker. The worker nodes run in Docker. It's genuinely remarkable.

For local development and CI, KinD has become *the* standard. If you write Kubernetes controllers or operators, you use KinD for local testing. If you write CI pipelines that need a k8s cluster, they use KinD. It's fast, it's reproducible, and it tears down cleanly when you're done.

The question I had: what if KinD clusters were just another Aspire resource?

---

## Building the Aspire.Hosting.Kind Resource

A few weeks ago, I started sketching this out with Andrey. The idea is simple on paper: `AddKindCluster()` in your Aspire AppHost, and Aspire manages the cluster lifecycle — creates it when you run the app, exposes it in the dashboard, and tears it down when you stop. Your operator or controller, running as another Aspire resource, connects to the cluster through Aspire's resource reference model.

I ended up building a working implementation: `KindClusterResource` (implementing `IResourceWithConnectionString`), a `KindClusterLifecycleHook` that wraps the `kind` CLI via `CliWrap`, extension methods for the fluent API, and enough integration tests to feel confident it actually worked. The repo is at [tamirdresher/aspire-kind](https://github.com/tamirdresher/aspire-kind).

Then Andrey took a proper look. Andrey knows the Aspire Community Toolkit ecosystem well, and having someone who could tell me "this doesn't match the conventions" was exactly what I needed. We went back and forth on the API surface, the lifecycle semantics (should `AddDeployment` be a child resource? yes, it should), and the testing approach.

Matt and Mitch joined the conversation from the Aspire community side. The thing I always appreciate about this ecosystem is how fast maintainers engage with a well-specified proposal. Within a day of filing the [CommunityToolkit/Aspire issue](https://github.com/CommunityToolkit/Aspire/issues/1232), Aaron Powell had tagged David Fowler for broader thoughts on the design. That's the signal that it's being taken seriously.

Here's what the API looks like:

```csharp
var builder = DistributedApplication.CreateBuilder(args);

var cluster = builder.AddKindCluster("dev-cluster")
    .WithKubernetesVersion("v1.30.0");

cluster.AddDeployment("my-controller", "manifests/controller-deployment.yaml");
cluster.AddService("my-controller-service", "manifests/controller-service.yaml");

// Your operator runs as a regular Aspire project, targeting the KinD cluster
var controller = builder.AddProject<Projects.MyController>("my-controller")
    .WithReference(cluster);

builder.Build().Run();
```

One `dotnet run`. KinD cluster spins up, manifests apply, your controller starts with the right kubeconfig wired through Aspire's environment model, and everything appears in the Aspire Dashboard — cluster health, controller logs, distributed traces across your reconcile loops.

---

## Why This Matters for Platform Engineers

Let me describe the workflow this enables, because I think it's genuinely different from what exists today.

Normally, if you're building a Kubernetes operator, your local dev loop looks like this: make change → build binary → copy to cluster or restart local process → apply test manifests → check logs in one terminal → check events in another terminal → check controller output in a third terminal → somehow correlate all of this mentally. Your cluster might have state from the last run that's interfering. You're not sure if the behavior you're seeing is from your new code or from some stale CRD instance sitting around from yesterday.

With Aspire running your KinD cluster:

Every run starts fresh (or seeded from state, your choice). Your controller's logs, the K8s events, and anything else your operator emits all flow into the Aspire Dashboard via OpenTelemetry — structured, searchable, correlated by trace. You can see the reconcile call as a span, the API server calls it makes as child spans, and the eventual state change as the outcome. All in one place, instead of mentally stitching together three terminal windows.

The feedback loop from "made a change" to "understood the impact" collapses from minutes to seconds.

And here's the part that connects back to why I care about this: my team does a lot of this kind of platform work. Writing controllers, building CRDs, extending Kubernetes for internal use. The dev experience for that has always been second-class compared to, say, a microservice developer who has Aspire, hot-reload, and a beautiful dashboard. The KinD resource is how platform engineers get the same experience.

That gap has always bothered me. Now we can close it.

---

## Aspire 13.2 Context

While all of this was happening, Aspire 13.2 shipped. Two things worth noting:

**TypeScript AppHost** is now available in preview. For teams where the platform configuration is TypeScript-first — or where the person owning the AppHost is more comfortable in TypeScript — this is real. The polyglot story isn't just "my services can run in Python"; it's now "my platform definition can run in TypeScript." That includes `AddKindCluster`, once the CommunityToolkit package matures.

**The direction is clear**: Aspire is moving toward being the local development standard not just for app developers but for platform engineers and infrastructure teams. The CommunityToolkit is part of how that happens — it's the place where ecosystem-driven integrations live before (and sometimes instead of) getting pulled into the main Aspire project. KinD is exactly the kind of thing that fits there. Specialized enough that it shouldn't be in the core, general enough that a lot of people need it.

---

## How Squad Helped

I can't write about a project I've been building without mentioning that I didn't build it alone — and I don't just mean Andrey and Matt and Mitch.

When I was trying to understand the CommunityToolkit's contribution conventions, the lifecycle hook patterns, and how other hosting integrations like `Hosting.Docker` handle similar problems, I asked Seven (my research agent) to dig through the CommunityToolkit source. She read the CONTRIBUTING guide, mapped out the patterns across similar integrations, and gave me a structured summary that saved me hours of reading unfamiliar code.

When I was validating that `IDistributedApplicationLifecycleHook` was the right abstraction for the cluster lifecycle, Data reviewed the implementation and flagged something I'd missed: the teardown on SIGINT needed to be resilient to race conditions with other resources shutting down at the same time. Easy to miss. Easy to fix once you see it.

That's how I actually work now. Research, code review, writing — it happens in parallel, across agents, with me directing rather than doing everything myself. The squad knows the project, knows the conventions. The work is collaborative in a way that feels different from "I used an AI to clean up my sentences."

It's more like: I had an idea, and I had a team that helped me figure out whether it was a good one and then build it.

---

## Status and What's Next

The proposal is live: [CommunityToolkit/Aspire#1232](https://github.com/CommunityToolkit/Aspire/issues/1232). The implementation is at [tamirdresher/aspire-kind](https://github.com/tamirdresher/aspire-kind). Aaron Powell has tagged David Fowler for design input. We're in the feedback cycle.

If the maintainers are happy with the approach, the next step is adapting the implementation to fully match CommunityToolkit conventions, writing the samples, and submitting the PR. That's the part I'm most looking forward to — going from "this works on my machine" to "anyone building K8s tooling can `dotnet add package CommunityToolkit.Aspire.Hosting.Kind` and go."

If you're building Kubernetes operators or controllers and this sounds useful — or if you have opinions about the API surface — go comment on [the issue](https://github.com/CommunityToolkit/Aspire/issues/1232). The design is still open and feedback from people who actually do KinD-based workflows is exactly what makes these proposals land well.

This is the kind of thing (sorry) that makes me genuinely excited about the Aspire ecosystem. The framework is well-designed and well-maintained. The CommunityToolkit pattern for community integrations actually works. And there's a window right now where Aspire is expanding from "developer tool" to "platform engineering tool," and it's possible to help shape what that looks like.

Worth building.

---

## Links

- [CommunityToolkit/Aspire Issue #1232](https://github.com/CommunityToolkit/Aspire/issues/1232) — the proposal
- [tamirdresher/aspire-kind](https://github.com/tamirdresher/aspire-kind) — working implementation
- [KinD: Kubernetes IN Docker](https://kind.sigs.k8s.io/) — the upstream tool
- [Aspire Community Toolkit](https://github.com/CommunityToolkit/Aspire) — where this would live
- [Aspire 13.2 What''s New](https://aspire.dev/whats-new/aspire-13-2/) — TypeScript AppHost and more
- [Squad Framework](https://github.com/microsoft/squad) — the AI team that helps me build things
