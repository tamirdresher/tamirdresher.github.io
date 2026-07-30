---
layout: post
title: "The Same Operator Loop, in TypeScript — The AppHost Moves, the Topology Stays"
date: 2026-08-02T07:15:00+03:00
tags: [dotnet-aspire, typescript, platform-engineering, kubernetes, operator, kind, polyglot, inner-loop]
description: "The Greeter operator loop from the C# AppHost post also runs from a TypeScript AppHost: same Kind cluster, same CRD, same Go operator, and the same Aspire dashboard shape."
---

> This post keeps the same Kubernetes operator loop and swaps only the AppHost language to TypeScript.

## The loop works from TypeScript

Here is the loop now: from `ts-apphost/`, `aspire run` starts a real Kind cluster, applies the Greeter CRD, launches the unchanged Go operator as a host process, opens the Aspire dashboard, and the operator reconciles a sample Greeter into a ConfigMap, Kubernetes' simple key-value configuration object.

That sentence has a few loaded terms, and this post has two likely audiences.

If you live in Node or TypeScript but not Kubernetes, **Kind** is Kubernetes running inside Docker containers on your machine, a **CRD** is a Custom Resource Definition that teaches the Kubernetes API a new type, an **operator** or **controller** is a program that watches those types and acts on them, and **reconcile** means the controller repeatedly compares the declared state with reality and repairs the difference.

If you live in Kubernetes or .NET but not Aspire and TypeScript, an **Aspire AppHost** is the program that declares the local topology, the **Aspire dashboard** is the web UI that shows the running resources, `kubectl` is Kubernetes' command-line client, and **Delve** is Go's debugger.

The useful claim is not that TypeScript gets a novelty badge. It is that the local topology survives the translation. The cluster is still a typed Aspire resource. The Go operator is still just Go. The AppHost language changes, but the graph does not.

## What Aspire gives the TypeScript AppHost

Aspire 13.4 ships with a TypeScript AppHost template:

```powershell
aspire init --language typescript
```

The generated project has a few important files:

- `apphost.mts` — the AppHost, written as TypeScript ESM (`.mts`), Node's modern module format
- `aspire.config.json` — Aspire runtime configuration, including hosting-integration packages
- `.aspire/modules/` — the generated local SDK that the AppHost imports
- `package.json` and `package-lock.json` — the Node-side dependencies and scripts
- `tsconfig.apphost.json` — compiler settings for the AppHost project

The unusual part is `.aspire/modules/`. There is no stable `@microsoft/aspire-hosting` package on npm in this shape yet. The TypeScript SDK surface is generated into the project from the Aspire CLI and from the integrations the AppHost asks for. You do not hand-edit that folder. You declare packages in `aspire.config.json`, run `aspire restore`, and let Aspire regenerate the local SDK.

In this sample, the important config is:

```json
{
  "packages": {
    "Aspire.Hosting.Go": "13.4.6-preview.1.26319.6",
    "CommunityToolkit.Aspire.Hosting.Kind": "13.4.1-beta.687"
  }
}
```

That is the seam worth noticing. The TypeScript AppHost consumes `CommunityToolkit.Aspire.Hosting.Kind` through the `packages` block, and Aspire generates TypeScript bindings into `.aspire/modules/`. The sample is not blocked from using the C# Kind integration because the AppHost is TypeScript. The same generated binding layer that gives it `addGoApp` from `Aspire.Hosting.Go` also gives it `addKindCluster`, `withClusterLifetime`, `withWorkerNodes`, `withKubernetesVersion`, Kind networking helpers, and `withKindClusterReference` from the Kind package.

Once that part clicks, the rest becomes normal topology code.

## The AppHost core

Here is the heart of `ts-apphost/apphost.mts`:

```typescript
const cluster = builder.addKindCluster('dev-cluster').withClusterLifetime(ClusterLifetime.Persistent);

const greeterCrd = builder
  .addExecutable('greeter-crd', process.execPath, appHostDir, ['./scripts/apply-crd.mjs', '--crd', crdPath])
  .withKindClusterReference(cluster)
  .waitFor(cluster);

await builder
  .addGoApp('greeter-operator', operatorDir, { packagePath: '.' })
  .withKindClusterReference(cluster)
  .withEnvironment('GOFLAGS', '-mod=mod')
  .waitFor(cluster)
  .waitForCompletion(greeterCrd);
```

Read it top to bottom. First, the AppHost creates or reuses a persistent Kind cluster. Then it runs a small CRD helper against that cluster. Then it starts the Go operator from the `operator/` package directory. The `packagePath` value is `'.'` on purpose: the Go hosting integration needs the package directory, not a Go source file.

`withKindClusterReference(cluster)` is the important wiring. It gives the resource a kubeconfig for the Kind cluster, so the operator can talk to Kubernetes without the AppHost manually threading a `KUBECONFIG` string through every process. The operator remains a plain Go process, but the cluster relationship is now part of the resource graph.

There is one genuine Kind-integration gap today. The published package does not yet expose `withManifest` for this TypeScript Kind cluster resource. Manifest support is upstreamed in [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481) as `AddManifest` / `AddManifestFromContent`, but it has not shipped in the package used here. Until it does, `scripts/apply-crd.mjs` is the small bridge: it applies `config/greeter-crd.yaml` and waits until the CRD is Established. It does not create the cluster, own the cluster lifecycle, or replace the Kind integration.

That distinction matters. The TypeScript AppHost can consume the Kind package. The missing piece is only manifest attachment.

## Running the TypeScript sample today

Start with the sample repository. The TypeScript AppHost lives in `ts-apphost/`:

```powershell
git clone https://github.com/tamirdresher/aspire-kubernetes-operator-sample.git
cd aspire-kubernetes-operator-sample
code .
```

Install the recommended VS Code extensions when prompted. The repo already has `.vscode/extensions.json` for the Aspire and Go extensions, which is exactly the kind of setup detail that should live in the repo instead of in someone's memory.

Here is the honest caveat for the TypeScript sample as it exists today: this post claims terminal-run parity today, not verified one-key F5 parity. The checked-in `.vscode/launch.json` points at the C# AppHost, and there is no TypeScript-specific launch configuration under `ts-apphost/`, so the TypeScript AppHost currently starts from the integrated terminal:

```powershell
cd aspire-kubernetes-operator-sample\ts-apphost
npm install
aspire restore
npm run build
$env:GOMAXPROCS = "2"
aspire run
```

`npm install` pulls the TypeScript-side tools and the runtime dependency the generated Aspire SDK uses to talk to the Aspire runtime. `aspire restore` regenerates the local SDK from `aspire.config.json`. `npm run build` proves the AppHost compiles before the runtime starts it.

When the dashboard opens, the graph is the same shape as the C# version: `dev-cluster` is the Kind cluster, `greeter-crd` applies the CRD, and `greeter-operator` starts after both are ready. The custom dashboard buttons from the C# AppHost are not wired into this TypeScript sample yet. The generated TypeScript SDK exposes `withCommand`, so that is sample parity work, not a platform wall.

For now, apply the sample Greeter from another terminal:

```powershell
kubectl --context kind-dev-cluster apply -f ..\examples\greeter-sample.yaml
kubectl --context kind-dev-cluster get configmap greeting-tamir -o yaml
kubectl --context kind-dev-cluster get greeter tamir -o yaml
```

The operator's `Reconcile()` function creates a ConfigMap named `greeting-{name}`. The operator code has not changed. The CRD has not changed. The Kind cluster is still the real Kubernetes state store. Only the AppHost language moved.

## What is real, and what is still catching up

The generated-SDK model is real, but it is still a preview-shaped developer experience. Today, the SDK surface lives inside `.aspire/modules/` and is regenerated by Aspire. Later, a stable npm package may make that feel more familiar to JavaScript developers. For now, the rule is simple: change `aspire.config.json`, run `aspire restore`, and do not edit generated files.

The Kind story is also real. `CommunityToolkit.Aspire.Hosting.Kind` comes through the packages block and generates usable TypeScript bindings. The gap is specific: `withManifest` has not shipped for this path yet, so the CRD apply step remains a tiny executable resource. That is the kind of helper you delete later, not the foundation of the cluster story.

The dashboard experience is real where the sample models resources: logs, state, dependencies, restart controls, and the same resource graph. The missing custom commands are a sample gap. The generated TypeScript SDK already has the shape needed to add buttons like **Apply Greeter** or **Delete all Greeters**.

The debugger story is the next place for sample polish. The operator process is still a plain Go process, and `packagePath: '.'` gives the Go integration the right package shape. The remaining work is to add the TypeScript VS Code launch entry that connects that process shape to Delve.

## What this means

The core claim from the Greeter post survives translation to TypeScript:

- The AppHost is still the source of truth for local topology.
- The Kind cluster still has a real lifecycle in the graph.
- The CRD apply step is ordered before the operator starts.
- The Go operator still runs from source as a host process.
- The dependency graph still replaces "run these things in this order or it breaks."
- The remaining gaps are visible: editor launch polish, `withManifest` in the Kind package, and dashboard command parity.

That is the proof I wanted. Not perfect parity, and not a claim that every rough edge has disappeared. The proof is that a Node or TypeScript developer can model the same Kubernetes operator loop without rewriting the AppHost in C#.

There is still .NET underneath Aspire's runtime. That is not hidden. The point is narrower and more useful: you do not have to write the AppHost in C# to get an Aspire-shaped local topology. You can author the graph in TypeScript, consume the same Kind integration, run the same Go operator, and keep Kubernetes state real without turning the README into the orchestrator.

This is the same disruption from the earlier posts, just from the other side of the fence. The setup doc is still the smell. The resource graph is still the fix. And the language boundary is thinner than it first looks.

## Try it yourself

Sample repo: <https://github.com/tamirdresher/aspire-kubernetes-operator-sample>.

Layout:

- `operator/` — the Go operator (`controller-runtime`), unchanged across AppHosts
- `apphost/` — the C# AppHost from the earlier Greeter post
- `ts-apphost/` — the TypeScript AppHost from this post
- `config/greeter-crd.yaml` — the CRD
- `examples/greeter-sample.yaml` — a sample Greeter to apply

Read the root `README.md` for both quickstarts side by side, then pick your language.

## Further reading

- Aspire's TypeScript AppHost docs: <https://aspire.dev>
- CommunityToolkit.Aspire.Hosting.Kind on NuGet: <https://www.nuget.org/packages/CommunityToolkit.Aspire.Hosting.Kind>
- Manifest support PR (`AddManifest` / `AddManifestFromContent`): <https://github.com/CommunityToolkit/Aspire/pull/1481>
- [When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-28-aspire-kubernetes-operator-inner-loop %})
- [The First Breakpoint: My Argo CD Story, and Why Aspire Is Quietly Disrupting DevOps]({% post_url 2026-07-31-aspire-argocd-inner-loop %})
