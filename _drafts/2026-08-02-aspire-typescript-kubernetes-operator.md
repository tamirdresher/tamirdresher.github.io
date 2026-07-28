---
layout: post
title: "The Same Operator Loop, in TypeScript — No .NET Required"
date: 2026-08-02T07:15:00+03:00
tags: [dotnet-aspire, typescript, platform-engineering, kubernetes, operator, kind, polyglot, inner-loop]
description: "Aspire's polyglot claim is real. The same Greeter operator from the C# AppHost post runs under a TypeScript AppHost — no C#, no .NET SDK in the AppHost itself. Same Kind cluster, same dashboard shape, different language."
---

> This post stands on its own, but it is also connected to two earlier experiments: [When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-29-aspire-kubernetes-operator-inner-loop %}) built the Greeter operator with a C# AppHost, and [The Kind Resource: My argo-cd Story, and Why Aspire Is Quietly Disrupting DevOps]({% post_url 2026-07-31-aspire-argocd-inner-loop %}) took the same pattern into a real cloud-native project. Here I keep the operator and the cluster the same, then swap only the AppHost to TypeScript, because the interesting question is whether the loop survives outside .NET.

There is a very specific reason I care about this post existing.

Every time I have talked about Aspire in the last year, someone from the JavaScript, TypeScript, or Python side of the world has raised the same eyebrow. Sometimes politely. Sometimes not. The eyebrow means: *"This looks nice, but it is a .NET thing, right?"*

And I get it, because every Aspire example in the ecosystem, including the two related posts I wrote earlier, shows a C# AppHost. The API surface I have been quoting reads like a C# fluent builder. The tool that ships it is called `dotnet`. If your day job lives in `node_modules`, the polyglot pitch feels a little like the wine list at a steakhouse — thoughtfully worded but not really for you.

So this post is the wine: we are going to take the exact Greeter operator from the C# AppHost post — same Go code, same CRD, same Kind cluster — and swap the AppHost. From C# to TypeScript. Nothing else changes. The dashboard should still show the same graph, the operator should still be a plain Go process, and the debugger mechanism should still be the same Go mechanism. The useful test is not whether TypeScript gets a novelty badge; it is whether the local topology survives the translation.

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

That sounds weird. It is a little weird. But it also solves a real problem: the TypeScript surface is generated from the exact Aspire integrations your AppHost asks for. You do not hand-edit `.aspire/modules/`; you declare packages in `aspire.config.json`, run `aspire restore`, and let Aspire regenerate the local SDK.

The other important thing in that config file is this snippet:

```json
{
  "packages": {
    "Aspire.Hosting.Go": "13.4.6-preview.1.26319.6",
    "CommunityToolkit.Aspire.Hosting.Kind": "13.4.1-beta.687"
  }
}
```

That is not a typo. These are C# hosting integrations being projected into a TypeScript AppHost. `Aspire.Hosting.Go` gives the sample `addGoApp`; `CommunityToolkit.Aspire.Hosting.Kind` gives it `addKindCluster`, `withClusterLifetime`, `withWorkerNodes`, `withKubernetesVersion`, Helm-chart builders, `withKind()` on Kubernetes environments, Kind networking/container-reference helpers, and `withKindClusterReference`. The generated module is where those TypeScript bindings appear, and `aspire restore` is the thing that keeps them aligned.

That is the seam, and once you see it, the rest becomes ordinary plumbing you can reason about. The same `AddKindCluster` integration works from both AppHosts because Aspire is projecting integration capabilities, not asking every language ecosystem to hand-port every resource by Friday.

## Act 2 — The AppHost, in full

Here is the heart of the TypeScript AppHost from `ts-apphost/apphost.mts`:

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

Read it top to bottom and the important part is not that this is TypeScript. The important part is that the first line is the same Kind resource the C# AppHost uses, projected into TypeScript through the package declaration in `aspire.config.json` and the generated `.aspire/modules/aspire.mjs` file.

That also explains the little bit of irony in this sample. The file was already doing this for Go. `addGoApp` comes from `Aspire.Hosting.Go`, which is also a C# hosting integration. The TypeScript AppHost was already consuming one C# integration through generated bindings; Kind uses the same mechanism.

`withKindClusterReference(cluster)` is the other payoff. It injects `KUBECONFIG` pointing at the host kubeconfig path, so the AppHost no longer has to thread an explicit `withEnvironment('KUBECONFIG', ...)` through the operator resource. The operator remains a plain Go process, but the cluster relationship is now typed instead of implied by an environment-variable string.

There is still one real gap, and it is worth being precise about it. The published Kind package does not yet have `withManifest` on `KindClusterResource`. The generic `addManifest(...)` API exists for Kubernetes resources generated from Helm-chart manifests, but not for this Kind cluster resource. Manifest support is upstreamed in [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481) as `AddManifest` / `AddManifestFromContent`; it just has not shipped yet.

So the sample keeps one small executable resource: `scripts/apply-crd.mjs`. It does not create the cluster. It does not own Kind lifecycle. It applies `config/greeter-crd.yaml` and waits until the CRD is Established. When the manifest API lands in the package, that helper can disappear. That is a package-maturity gap, not a platform limitation.

`builder.build().run()` is still the terminal call. Same shape as C#.

The file says: create or reuse the Kind cluster as a typed Aspire resource, apply the one CRD through a tiny helper until the Kind package grows manifest support, then run the Go operator against the cluster. The rest is Aspire runtime.

## Act 3 — Trying it

Start in VS Code, because that is the loop this series is really about:

```powershell
git clone https://github.com/tamirdresher/aspire-kubernetes-operator-sample.git
cd aspire-kubernetes-operator-sample
code .
```

Install the recommended extensions when VS Code prompts you. The repo already has `.vscode/extensions.json` with `microsoft-aspire.aspire-vscode` and `golang.go`, which is the right shape: the setup guide stops being a paragraph people miss and becomes a file the editor follows. If you are authoring a fresh AppHost and the launch entry is missing, press **Ctrl+Shift+P**, run **Aspire: Configure launch.json**, and let the Aspire extension write the entry instead of hand-typing JSON.

Here is the honest caveat for the TypeScript sample as it exists today: the checked-in `.vscode/launch.json` points at the C# AppHost, and there is no TypeScript-specific launch configuration under `ts-apphost/`. So I am not going to pretend this sample has a verified one-key F5 path yet. The TypeScript AppHost currently starts from the integrated terminal:

```powershell
cd aspire-kubernetes-operator-sample\ts-apphost
npm install
aspire restore --non-interactive
npm run build
$env:GOMAXPROCS = "2"
aspire run
```

`npm install` is the one unavoidable Node step here. It pulls TypeScript, ESLint, `tsx`, `nodemon`, and the `vscode-jsonrpc` runtime dependency that the generated local Aspire SDK uses to talk to the Aspire runtime. That is still setup as code — `package.json` and `package-lock.json`, not a blog post asking you to remember package names — but it is not as clean as pressing F5 on the C# AppHost.

Once the dashboard is up, the graph is the same shape: `dev-cluster` is the Kind cluster, `greeter-crd` applies the CRD, and then `greeter-operator` starts after both are ready. The custom dashboard buttons from the C# AppHost are not wired into the TypeScript sample yet. The generated TypeScript SDK does expose `withCommand`, so this is a sample gap rather than a platform limitation. For now, apply the sample Greeter from another terminal:

```powershell
kubectl --kubeconfig ..\.kube\dev-cluster.yaml apply -f ..\examples\greeter-sample.yaml
kubectl --kubeconfig ..\.kube\dev-cluster.yaml get configmap greeting-tamir -o yaml
kubectl --kubeconfig ..\.kube\dev-cluster.yaml get greeter tamir -o yaml
```

The reconcile loop is still the same one from the C# AppHost post: apply a Greeter, and the operator's `Reconcile()` function creates a ConfigMap named `greeting-{name}`. The operator has not changed a single line. The Kind cluster is the same real Kubernetes state store. Only the AppHost is different.

## What surprised me about the TypeScript side

A few honest notes, because posts that pretend the demo gods always smile make me suspicious.

The `.aspire/modules/` generated-SDK model surprised me at first. My reflex was: "wait, where is my `npm install @microsoft/aspire-hosting`?" And the answer, for now, is: nowhere. The SDK ships with the CLI. Once the npm package is out, this whole shape will normalize. Until then, the AppHost is calling generated code that lives inside your own project. Do not edit it. Change `aspire.config.json`, run `aspire restore`, and let the generator do its job.

The better surprise is that the mechanism is broader than I first assumed. The same file consumes `Aspire.Hosting.Go` and `CommunityToolkit.Aspire.Hosting.Kind` through the same generated TypeScript surface. One gives me `addGoApp`; the other gives me `addKindCluster` and `withKindClusterReference`. That is the polyglot story in one file: the AppHost language changes, but the resource model still comes from Aspire integrations.

The remaining Kind gap is much smaller and more specific than package projection. What has not shipped yet is manifest attachment on `KindClusterResource`. Until [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481) lands, `scripts/apply-crd.mjs` is the narrow bridge for `config/greeter-crd.yaml`. It is the kind of helper you delete later, not the foundation of the cluster story.

The dashboard experience was mostly identical where the TypeScript sample actually models resources: logs, resource state, dependencies, restart controls — same UI, same feel. Aspire's runtime is genuinely language-agnostic. Dashboard commands are part of that story too: the generated TypeScript SDK exposes `withCommand`, so a TypeScript AppHost can grow the same kind of buttons as the C# AppHost. This checkout simply has not wired **Apply Greeter (timestamped)** and **Delete all Greeters** into `apphost.mts` yet, so the sample still uses `kubectl apply` for the Greeter resource.

The debugger story is the place to be careful. The earlier `packagePath` bug existed in `apphost.mts` too, and the fix is now the same fix as the C# side: pass the package directory, `packagePath: '.'`, not `./main.go`. That makes the Go process shape compatible with the Go hosting integration again. I have not verified a TypeScript-launched F5 session with a bound Go breakpoint, so the honest claim is narrower: the operator process is still a plain Go process, and the mechanism should be the same once the VS Code launch path is wired. Useful guidance beats a confident sentence I have not earned yet.

## What this means

The core claims from the Greeter post and the argo-cd post survive translation to TypeScript, with the remaining gaps called out instead of hidden.

- The setup doc is still the smell.
- The AppHost is still the source of truth for local topology.
- The Kind cluster still lives as a typed Aspire resource with a real lifecycle, not a bash-blob in a README.
- The Go operator still runs as a host process launched from source.
- The typed dependency graph still replaces "run these things in this order or it breaks."
- The TypeScript sample still needs a real F5 launch entry, manifest support in the Kind package, and dashboard command parity before it matches the C# sample's full ergonomics.

The only thing that changed is the language you write the AppHost in, which means if you write Node.js services all day, you can now model a Kubernetes operator loop, a real Kind cluster, and any Aspire-shaped topology without leaving your ecosystem. You do not need to learn C#. You do not need to install the .NET SDK to author the AppHost itself. (You do still need it available for Aspire's runtime, but you are not writing `using` statements at 11pm.)

For platform engineers on the JS/TS side of the world, that is not a small thing. That is the difference between "there is an interesting .NET tool for local topology as code" and "there is a tool for local topology as code, and it happens to have a .NET reference implementation."

Aspire is the second thing, and this post is the proof with the rough edges left visible. The Greeter operator runs from a TypeScript AppHost, with the same reconcile loop, the same Kind resource, and the same resource graph. The debugger and F5 story should converge because the Go process is still just Go, but this sample has not earned that sentence yet.

The disruption I have been talking about is not about .NET. It is about **local topology as code**, in the language you already use.

And that is finally something I can say with a straight face to the eyebrow.

---

## Try it yourself

Sample repo: <https://github.com/tamirdresher/aspire-kubernetes-operator-sample>.

Layout:

- `operator/` — the Go operator (`controller-runtime`), unchanged across AppHosts
- `apphost/` — the **C# AppHost** from the earlier Greeter post
- `ts-apphost/` — the **TypeScript AppHost** from this post
- `config/greeter-crd.yaml` — the CRD
- `examples/greeter-sample.yaml` — a sample Greeter to apply

Read the root `README.md` for both quickstarts side by side, then pick your language.

## Further reading

- Aspire's TypeScript AppHost docs: <https://aspire.dev>
- CommunityToolkit.Aspire.Hosting.Kind on NuGet: <https://www.nuget.org/packages/CommunityToolkit.Aspire.Hosting.Kind/13.4.1-beta.687>
- Manifest support PR (`AddManifest` / `AddManifestFromContent`, 174 tests as of HEAD `5c80dc4b`): <https://github.com/CommunityToolkit/Aspire/pull/1481>
- [When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-29-aspire-kubernetes-operator-inner-loop %})
- [The Kind Resource: My argo-cd Story, and Why Aspire Is Quietly Disrupting DevOps]({% post_url 2026-07-31-aspire-argocd-inner-loop %})
