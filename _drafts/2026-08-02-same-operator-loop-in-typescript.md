---
layout: post
title: "The Same Operator Loop, in TypeScript — No .NET Required"
date: 2026-08-02T07:15:00+03:00
tags: [dotnet-aspire, typescript, platform-engineering, kubernetes, operator, kind, polyglot, inner-loop]
description: "Aspire's polyglot claim is real. The same Greeter operator from the C# AppHost post runs under a TypeScript AppHost — no C#, no .NET SDK in the AppHost itself. Same Kind cluster, same F5 loop, different language."
---

> This post stands on its own, but it is also connected to two earlier experiments: [When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-29-a-kubernetes-operator-with-a-debugger-not-a-deployment %}) built the Greeter operator with a C# AppHost, and [The Kind Resource: My argo-cd Story, and Why Aspire Is Quietly Disrupting DevOps]({% post_url 2026-07-31-the-kind-resource-my-argocd-story %}) took the same pattern into a real cloud-native project. Here I keep the operator and the cluster the same, then swap only the AppHost to TypeScript, because the interesting question is whether the loop survives outside .NET.

There is a very specific reason I care about this post existing.

Every time I have talked about Aspire in the last year, someone from the JavaScript, TypeScript, or Python side of the world has raised the same eyebrow. Sometimes politely. Sometimes not. The eyebrow means: *"This looks nice, but it is a .NET thing, right?"*

And I get it, because every Aspire example in the ecosystem, including the two related posts I wrote earlier, shows a C# AppHost. The API surface I have been quoting reads like a C# fluent builder. The tool that ships it is called `dotnet`. If your day job lives in `node_modules`, the polyglot pitch feels a little like the wine list at a steakhouse — thoughtfully worded but not really for you.

So this post is the wine: we are going to take the exact Greeter operator from the C# AppHost post — same Go code, same CRD, same Kind cluster — and swap the AppHost. From C# to TypeScript. Nothing else changes. If the pattern holds, the debugger still hits, the dashboard still shows the same graph, and every claim from the Greeter post and the argo-cd post survives the translation. That is the whole test.

---

## Act 1 — What Aspire actually gives a TypeScript developer

Aspire 13.4 ships with a TypeScript AppHost template. You bootstrap it with:

```powershell
aspire init --language typescript
```

That command drops a few files into the current directory. The important ones are:

- `apphost.mts` — the AppHost, written in TypeScript ESM (`.mts`, so Node runs it as an ES module even in a mixed project)
- `aspire.config.json` — Aspire runtime configuration, including which hosting-integration packages the AppHost pulls in
- `.aspire/modules/` — the generated **local SDK** that the AppHost imports
- `package.json` with a lean dependency list and Aspire scripts
- `tsconfig.apphost.json` — TypeScript compiler options for the AppHost project

The generated `.aspire/modules/` folder is the part I want to explain up front, because it is unusual. There is no `@microsoft/aspire-hosting` package on npm. The Aspire SDK that your TypeScript AppHost imports lives, right now, as a **generated file inside your project**. When Aspire ships a stable npm package, the story will shift; for now, the SDK ships with the CLI and gets written into your project at `aspire init` time.

That sounds weird. It is a little weird. But it also solves a real problem: the Aspire SDK version stays perfectly aligned with the Aspire CLI version you initialized with. You get to see the SDK code you are calling. You do not fight `package-lock.json` drift with the runtime.

The other important thing in that config file is this snippet:

```json
"packages": {
  "Aspire.Hosting.Go": "13.4.6-preview.1.26319.6"
}
```

That is not a typo. Aspire's Go hosting integration — the same integration the C# AppHost used to model the Greeter operator as a first-class `AddGoApp` resource — is available to the TypeScript AppHost through the same mechanism. Aspire's polyglot claim goes both ways: a TypeScript AppHost can consume a .NET-ecosystem hosting integration, because Aspire's runtime is what actually enforces the graph, not the language of the AppHost.

That is the seam, and once you see it, the rest becomes ordinary plumbing you can reason about.

## Act 2 — The AppHost, in full

Here is the entire TypeScript AppHost. Sixty lines. From `ts-apphost/apphost.mts`:

```typescript
import { execFileSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createBuilder } from './.aspire/modules/aspire.mjs';

const appHostDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(appHostDir, '..');
const operatorDir = resolve(repoRoot, 'operator');
const kubeconfigPath = resolve(repoRoot, '.kube', 'dev-cluster.yaml');
const crdPath = resolve(repoRoot, 'config', 'greeter-crd.yaml');
const clusterName = 'dev-cluster';

validatePrerequisites(['docker', 'kind', 'kubectl', 'go']);
mkdirSync(dirname(kubeconfigPath), { recursive: true });

const builder = await createBuilder();

const cluster = builder.addExecutable('dev-cluster', process.execPath, appHostDir, [
  './scripts/kind-cluster.mjs',
  '--cluster-name', clusterName,
  '--kubeconfig', kubeconfigPath,
  '--crd', crdPath,
  '--timeout-seconds', '300',
]);

await builder
  .addGoApp('greeter-operator', operatorDir, { packagePath: './main.go' })
  .withEnvironment('KUBECONFIG', kubeconfigPath)
  .withEnvironment('GOFLAGS', '-mod=mod')
  .waitForCompletion(cluster);

await builder.build().run();
```

Read it top to bottom and `createBuilder()` returns the AppHost builder. That is the exact same primitive the C# side calls `DistributedApplication.CreateBuilder(args)`. Same job, different casing.

Then the cluster: `builder.addExecutable('dev-cluster', process.execPath, appHostDir, [...])`. This is where the TypeScript story diverges from the C# story in one honest way. The C# side now has a published NuGet package, `CommunityToolkit.Aspire.Hosting.Kind` `13.4.1-beta.687`, with a first-class `AddKindCluster` resource, `WithWorkerNodes`, `WithKubernetesVersion`, `WithClusterLifetime`, Helm chart support, Kind config customization, and references. Manifest support is still pending upstream in [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481), where the C# API becomes `AddManifest` / `AddManifestFromContent`. That is great news for C# AppHosts. It does not automatically create a TypeScript SDK surface. As of this writing, there is no TypeScript counterpart.

So we drop one level down. Aspire's TypeScript SDK exposes `addExecutable`, which runs any process as an Aspire resource with logs, restart, and dashboard visibility. We hand it Node itself — `process.execPath` — and tell it to run our small helper script `scripts/kind-cluster.mjs`. That script is 185 lines of plain JavaScript that creates or reuses the cluster, applies the CRD, and blocks until the CRD is Established.

That is not a workaround. That is the exact composition pattern Aspire is built around: a resource is a process, a container, or something the runtime knows how to lifecycle. When the ecosystem does not yet have a specialized resource type for your infrastructure, you compose it out of an executable. Later, when the Kind integration has a TypeScript-facing shape — probably through the same `aspire add` / generated-SDK mechanism used by other integrations — this block can collapse to something like `builder.addKindCluster('dev-cluster').withManifest(crdPath)`. The rest of the file does not change.

Then the operator, unchanged in shape:

```typescript
await builder
  .addGoApp('greeter-operator', operatorDir, { packagePath: './main.go' })
  .withEnvironment('KUBECONFIG', kubeconfigPath)
  .withEnvironment('GOFLAGS', '-mod=mod')
  .waitForCompletion(cluster);
```

`addGoApp` comes from the `Aspire.Hosting.Go` integration referenced in `aspire.config.json`. Same Aspire runtime knowledge of Go apps that the C# AppHost had. Same behavior: `go run ./main.go` under the hood, with Delve/debugger integration, but exposed as a first-class Aspire resource with proper logs and lifecycle.

`waitForCompletion(cluster)` is the ordering primitive. The operator does not start until the cluster resource finishes bootstrapping (create + wait + `kubectl apply` + wait for the CRD to be Established). That is a graph edge, not a README paragraph.

`builder.build().run()` is the terminal call. Same shape as C#.

Sixty lines to say: run this Node script that owns the cluster, then run this Go operator against it, and make sure the second one waits for the first. The rest is Aspire runtime.

## Act 3 — Trying it

The quickstart from `ts-apphost/README.md`:

```powershell
cd part2-greeter-operator\ts-apphost
npm install
$env:GOMAXPROCS = "2"
aspire run
```

Then in another shell:

```powershell
kubectl --context kind-dev-cluster apply -f ..\examples\greeter-sample.yaml
kubectl --context kind-dev-cluster get configmap greeting-tamir -o yaml
kubectl --context kind-dev-cluster get greeter tamir -o yaml
```

`npm install` pulls a small number of dev dependencies (TypeScript, ESLint, `tsx`, `nodemon`) and one runtime dependency (`vscode-jsonrpc`, which the local Aspire SDK uses to talk to the runtime). `aspire run` is the same command shape as `aspire start` in the C# world — the TypeScript scaffold defines it as an npm script alias.

The reconcile loop is the same one from the C# AppHost post: apply a Greeter, the operator's `Reconcile()` function creates a ConfigMap named `greeting-{name}`, the debugger attaches to the Go process, breakpoints hit. That last part is the whole reason to do any of this.

The operator has not changed a single line. The Go code is the Go code. The debugger flow is the debugger flow. The Kind cluster is the same real Kubernetes state store. Only the AppHost is different.

## What surprised me about the TypeScript side

A few honest notes, because posts that pretend the demo gods always smile make me suspicious.

The `.aspire/modules/` generated-SDK model surprised me at first. My reflex was: "wait, where is my `npm install @microsoft/aspire-hosting`?" And the answer, for now, is: nowhere. The SDK ships with the CLI. Once the npm package is out, this whole shape will normalize. Until then, the AppHost is calling code that lives inside your own project, which is either terrifying or refreshing depending on your relationship with node_modules.

The lack of a `CommunityToolkit.Aspire.Hosting.Kind` TypeScript port meant I had to drop from `AddKindCluster` down to `addExecutable`. The NuGet package being published fixes the C# story, not this one. That is fine, but it is also a real gap. The moment someone (I have ideas) exposes a TypeScript-facing Kind integration, this AppHost drops from ~60 lines to ~35, and the story tightens further.

The dashboard experience was identical. Logs, resource state, dependencies, restart controls — same UI, same feel. Aspire's runtime is genuinely language-agnostic. When you `aspire run` a TypeScript AppHost, you get the exact same operator dashboard experience as when you `aspire start` a C# one.

The debugger side was where I expected trouble and found none. Setting a breakpoint in Go and watching it hit from a TypeScript-orchestrated run felt slightly unreal the first time. It should not — the operator process is still a plain Go process, and the debugger attaches to it through Aspire's Go integration regardless of what launched the graph. But there is a moment where you notice.

## What this means

Every claim I made in the Greeter post and the argo-cd post survives translation to TypeScript.

- The setup doc is still the smell.
- The AppHost is still the executable source of truth for local topology.
- The Kind cluster still lives as a modeled resource with a real lifecycle, not a bash-blob in a README.
- The Go operator still runs as a host process with a real debugger attached.
- The typed dependency graph still replaces "run these things in this order or it breaks."

The only thing that changed is the language you write the AppHost in, which means if you write Node.js services all day, you can now model a Kubernetes operator loop, a real Kind cluster, and any Aspire-shaped topology without leaving your ecosystem. You do not need to learn C#. You do not need to install the .NET SDK to author the AppHost itself. (You do still need it available for Aspire's runtime, but you are not writing `using` statements at 11pm.)

For platform engineers on the JS/TS side of the world, that is not a small thing. That is the difference between "there is an interesting .NET tool for local topology as code" and "there is a tool for local topology as code, and it happens to have a .NET reference implementation."

Aspire is the second thing, and this post is the proof. The Greeter operator on my machine runs from a TypeScript AppHost, with the same reconcile loop, the same debugger, the same Kind cluster, and the same F5 story.

The disruption I have been talking about is not about .NET. It is about **local topology as code**, in the language you already use.

And that is finally something I can say with a straight face to the eyebrow.

---

## Try it yourself

Sample repo: <https://github.com/tamirdresher/aspire-greeter-operator> (currently private; made public when this post drops).

Layout:

- `operator/` — the Go operator (`controller-runtime`), unchanged across AppHosts
- `apphost/` — the **C# AppHost** from the earlier Greeter post
- `ts-apphost/` — the **TypeScript AppHost** from this post
- `config/greeter-crd.yaml` — the CRD
- `examples/greeter-sample.yaml` — a sample Greeter to apply

Read the root `README.md` for both quickstarts side by side, then pick your language.

## Further reading

- Aspire's TypeScript AppHost docs: <https://aspire.dev>
- CommunityToolkit.Aspire.Hosting.Kind on NuGet (C# only, for now): <https://www.nuget.org/packages/CommunityToolkit.Aspire.Hosting.Kind/13.4.1-beta.687>
- Manifest support PR (`AddManifest` / `AddManifestFromContent`, 174 tests as of HEAD `5c80dc4b`): <https://github.com/CommunityToolkit/Aspire/pull/1481>
- [When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-29-a-kubernetes-operator-with-a-debugger-not-a-deployment %})
- [The Kind Resource: My argo-cd Story, and Why Aspire Is Quietly Disrupting DevOps]({% post_url 2026-07-31-the-kind-resource-my-argocd-story %})
