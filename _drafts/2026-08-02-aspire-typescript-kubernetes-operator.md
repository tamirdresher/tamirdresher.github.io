---
layout: post
title: "The Same Operator Loop, in TypeScript — The AppHost Moves, the Topology Stays"
date: 2026-08-02T07:15:00+03:00
tags: [aspire, dotnet-aspire, typescript, platform-engineering, kubernetes, operator, kind, polyglot, inner-loop]
description: "The Greeter operator loop from the C# AppHost post also runs from a TypeScript AppHost: same Kind cluster, same CRD, same Go operator, and the same Aspire dashboard shape."
---

> This post keeps the same Kubernetes operator loop and swaps only the AppHost language to TypeScript.

The first post in this series used a tiny Go Kubernetes operator to show the pattern: keep real Kubernetes state in Kind, run the editable controller as a host process, and let Aspire model the topology. The second post took that same idea into Argo CD, where the local loop is larger and the first useful breakpoint matters even more.

This one is smaller on purpose. The operator, CRD, Kind cluster, and reconcile behavior stay the same as Part 1. The AppHost moves from C# to TypeScript. That matters because this topic has two audiences that do not always overlap: Node and TypeScript developers who may not spend their day inside Kubernetes, and .NET or Aspire developers who understand the AppHost model but do not write TypeScript for local tooling. The useful question is whether both groups can look at the same resource graph and see something they can own.

Everything in this post is in the sample repository. The TypeScript AppHost lives under `ts-apphost/`, and the default branch is `master`:

```powershell
git clone https://github.com/tamirdresher/aspire-kubernetes-operator-sample.git
cd aspire-kubernetes-operator-sample
code .
```

Browse it here: [github.com/tamirdresher/aspire-kubernetes-operator-sample/tree/master/ts-apphost](https://github.com/tamirdresher/aspire-kubernetes-operator-sample/tree/master/ts-apphost)

## What the TypeScript AppHost Runs

Here is the loop now: from `ts-apphost/`, `aspire run` starts a real Kind cluster, applies the Greeter CRD, launches the unchanged Go operator as a host process, opens the Aspire dashboard, and the operator reconciles a sample Greeter into a ConfigMap, Kubernetes' simple key-value configuration object.

That sentence has a few loaded terms. If you live in Node or TypeScript but not Kubernetes, **Kind** is Kubernetes running inside Docker containers on your machine, a **CRD** is a Custom Resource Definition that teaches the Kubernetes API a new type, an **operator** or **controller** is a program that watches those types and acts on them, and **reconcile** means the controller repeatedly compares declared state with reality and repairs the difference.

If you live in Kubernetes or .NET but not Aspire and TypeScript, an **Aspire AppHost** is the program that declares the local topology, the **Aspire dashboard** is the web UI that shows the running resources, `kubectl` is Kubernetes' command-line client, and **Delve** is Go's debugger.

The useful claim is not that TypeScript gets a novelty badge. It is that the local topology survives the translation. The cluster is still an Aspire resource. The Go operator is still just Go. The AppHost language changes, but the graph does not.

### The Same Topology, Different AppHost Language

The TypeScript AppHost is short enough that the core loop fits in one screen:

```typescript
// The generated SDK comes from .aspire/modules/aspire.mjs.
// It is restored from aspire.config.json, not installed from npm.
import { ClusterLifetime, createBuilder } from './.aspire/modules/aspire.mjs';

const builder = await createBuilder();

// Create or reuse the real local Kubernetes cluster.
const cluster = builder
  .addKindCluster('dev-cluster')
  .withClusterLifetime(ClusterLifetime.Persistent);

// Apply the CRD before the operator starts. This is a narrow bridge until
// Kind manifest support is projected into the TypeScript SDK.
const greeterCrd = builder
  .addExecutable('greeter-crd', process.execPath, appHostDir, ['./scripts/apply-crd.mjs', '--crd', crdPath])
  .withKindClusterReference(cluster)
  .waitFor(cluster);

// Run the unchanged Go operator from source against that Kind cluster.
await builder
  .addGoApp('greeter-operator', operatorDir, { packagePath: '.' })
  .withKindClusterReference(cluster)
  .withEnvironment('GOFLAGS', '-mod=mod')
  .waitFor(cluster)
  .waitForCompletion(greeterCrd);
```

Read it top to bottom. First, the AppHost creates or reuses a persistent Kind cluster. Then it runs a small CRD helper against that cluster. Then it starts the Go operator from the `operator/` package directory. The `packagePath` value is `'.'` on purpose: the Go hosting integration needs the package directory, not a Go source file.

`withKindClusterReference(cluster)` is the important wiring. It gives the executable and the Go operator a kubeconfig for the Kind cluster, so the operator can talk to Kubernetes without the AppHost manually threading a `KUBECONFIG` string through every process. The operator remains a plain Go process, but the cluster relationship is now part of the resource graph.

### The CRD and Greeter Contract Stay the Same

The CRD is the Kubernetes contract. This is the trimmed shape from `config/greeter-crd.yaml`:

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: greeters.hello.tamirdresher.dev
spec:
  group: hello.tamirdresher.dev
  scope: Namespaced
  names:
    plural: greeters
    singular: greeter
    kind: Greeter
    listKind: GreeterList
    shortNames:
      - greet
  versions:
    - name: v1alpha1
      served: true
      storage: true
      subresources:
        status: {}
      schema:
        openAPIV3Schema:
          type: object
          required: [spec]
          properties:
            spec:
              type: object
              required: [name]
              properties:
                name:
                  type: string
                  minLength: 1
                  maxLength: 240
                  pattern: '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
            status:
              type: object
              properties:
                configMapName:
                  type: string
                message:
                  type: string
                lastReconciled:
                  type: string
                  format: date-time
```

That says Kubernetes can store a namespaced `Greeter` with one required field, `spec.name`, and a status section the operator can update after it creates the ConfigMap.

A Greeter resource is just as small:

```yaml
apiVersion: hello.tamirdresher.dev/v1alpha1
kind: Greeter
metadata:
  name: reader
  namespace: default
spec:
  name: reader
```

When that object lands in Kubernetes, the Go reconciler creates `ConfigMap/greeting-reader` with `message: Hello, reader!`, then writes the ConfigMap name and message back into Greeter status. None of that behavior moved into TypeScript. The AppHost only models the local environment that lets the same operator run.

## How Aspire Projects C# Integrations into TypeScript

Aspire 13.4 ships with a TypeScript AppHost template:

```powershell
aspire init --language typescript
```

The generated project has a few important files:

- `apphost.mts` — the AppHost, written as TypeScript ESM (`.mts`), Node's modern module format.
- `aspire.config.json` — Aspire runtime configuration, including hosting-integration packages.
- `.aspire/modules/` — the generated local SDK that the AppHost imports.
- `package.json` and `package-lock.json` — the Node-side dependencies and scripts.
- `tsconfig.apphost.json` — compiler settings for the AppHost project.

The unusual part is `.aspire/modules/`. There is no stable `@microsoft/aspire-hosting` package on npm in this shape yet. The TypeScript SDK surface is generated into the project from the Aspire CLI and from the integrations the AppHost asks for. You do not hand-edit that folder. You declare packages in `aspire.config.json`, run `aspire restore`, and let Aspire regenerate the local SDK.

### The Package Block Is the Bridge

In this sample, the important config is the `packages` block in `ts-apphost/aspire.config.json`:

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

### The Generated Bindings Look Like TypeScript

The generated SDK is large because it projects the hosting API surface, but the important part is ordinary TypeScript declarations and wrappers. Trimmed down, `.aspire/modules/aspire.mts` contains shapes like these:

```typescript
export enum ClusterLifetime {
  Session = 'Session',
  Persistent = 'Persistent',
}

export interface IDistributedApplicationBuilder {
  addGoApp(name: string, appDirectory: string, options?: AddGoAppOptions): GoAppResourcePromise;
  addKindCluster(name: string): KindClusterResourcePromise;
}

export interface GoAppResourcePromise {
  withKindClusterReference(kind: Awaitable<KindClusterResource>): GoAppResourcePromise;
}

export interface KindClusterResourcePromise {
  withClusterLifetime(lifetime: ClusterLifetime): KindClusterResourcePromise;
  withKubernetesVersion(version: string): KindClusterResourcePromise;
  withWorkerNodes(count: number): KindClusterResourcePromise;
}
```

That folder is generated, so the important habit is restraint: read it when you need to understand what Aspire projected, but make changes in `aspire.config.json` and `apphost.mts`, then regenerate.

## AppHost Mechanics That Matter

The TypeScript sample does not have every C# sample convenience yet. That is fine. The useful line is between gaps in the sample and gaps in the model.

### Why `scripts/apply-crd.mjs` Exists

There is one genuine Kind-integration gap today. The published package does not yet expose `withManifest` for this TypeScript Kind cluster resource. Manifest support is upstreamed in [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481) as `AddManifest` / `AddManifestFromContent`, but it has not shipped in the package used here. Until it does, `scripts/apply-crd.mjs` is the small bridge: it applies `config/greeter-crd.yaml` and waits until the CRD is Established. It does not create the cluster, own the cluster lifecycle, or replace the Kind integration.

The script is deliberately narrow:

```javascript
if (!process.env.KUBECONFIG) {
  throw new Error('KUBECONFIG was not set. This script must be wired with withKindClusterReference(cluster).');
}

// Apply the CRD to the Kind cluster Aspire attached to this resource.
await runChecked('kubectl', ['apply', '-f', crdPath]);

// Do not let the operator start while the API server is still learning the new type.
await runChecked('kubectl', [
  'wait',
  '--for',
  'condition=Established',
  'crd/greeters.hello.tamirdresher.dev',
  '--timeout=60s',
]);

console.log(`Greeter CRD applied and Established: ${crdPath}`);
```

That distinction matters. The TypeScript AppHost can consume the Kind package. The missing piece is only manifest attachment. The helper is something to delete later, not the foundation of the cluster story.

### The Operator Process Is Still Plain Go

The operator is not aware of Aspire. It uses the normal controller-runtime configuration path:

```go
mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
    Scheme:                 scheme,
    Metrics:                metricsserver.Options{BindAddress: metricsAddr},
    HealthProbeBindAddress: probeAddr,
})
```

`ctrl.GetConfigOrDie()` finds `KUBECONFIG`, and Aspire supplies that environment variable through `withKindClusterReference(cluster)`. That is the same trick as the C# AppHost version, just projected through the TypeScript SDK.

### The Current F5 Boundary

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

## Try It Yourself

Start with Docker Desktop running and the prerequisites from the sample README installed: Node.js, the Aspire CLI, Go, Kind, and `kubectl`.

### Start the TypeScript AppHost

From the TypeScript AppHost folder:

```powershell
cd aspire-kubernetes-operator-sample\ts-apphost
npm install
aspire restore
npm run build
$env:GOMAXPROCS = "2"
aspire run
```

In a separate terminal, confirm the graph is running:

```powershell
aspire describe
```

The healthy shape is three resources:

```text
Name              Type          State     Health
----              ----          -----     ------
dev-cluster       Kind Cluster  Running   Healthy
greeter-crd       Executable    Finished  -
greeter-operator  Executable    Running   Healthy
```

The dashboard also shows the same resource graph. The terminal is enough for this post because the TypeScript sample is proving terminal-run parity.

### Point `kubectl` at the Aspire-Managed Cluster

The TypeScript Kind resource exposes its kubeconfig path through `aspire describe dev-cluster --format Json`. Copy the `KubeConfigPath` value, then set it in the second terminal:

```powershell
$env:KUBECONFIG = "<KubeConfigPath from aspire describe>"
kubectl get crd greeters.hello.tamirdresher.dev
```

A ready CRD looks like this:

```text
NAME                              CREATED AT
greeters.hello.tamirdresher.dev   2026-07-30T18:42:21Z
```

That CRD exists because `greeter-crd` ran after the Kind cluster became ready and before the operator started.

### Apply a Greeter and Watch the ConfigMap Appear

Create `greeter-reader.yaml`:

```yaml
apiVersion: hello.tamirdresher.dev/v1alpha1
kind: Greeter
metadata:
  name: reader
  namespace: default
spec:
  name: reader
```

Then apply it:

```powershell
kubectl apply -f .\greeter-reader.yaml
```

The API server accepts the custom resource:

```text
greeter.hello.tamirdresher.dev/reader created
```

Give the operator a few seconds, then ask for the ConfigMap:

```powershell
kubectl get configmap greeting-reader
```

```text
NAME              DATA   AGE
greeting-reader   1      5s
```

Now inspect what the operator created:

```powershell
kubectl get configmap greeting-reader -o yaml
```

```yaml
apiVersion: v1
data:
  message: Hello, reader!
kind: ConfigMap
metadata:
  name: greeting-reader
  namespace: default
  ownerReferences:
  - apiVersion: hello.tamirdresher.dev/v1alpha1
    blockOwnerDeletion: true
    controller: true
    kind: Greeter
    name: reader
```

The owner reference is doing real Kubernetes work. Delete the Greeter, and Kubernetes garbage collection can remove the ConfigMap because the operator declared ownership.

The Greeter status also shows the reconcile result:

```powershell
kubectl get greeter reader -o yaml
```

```yaml
apiVersion: hello.tamirdresher.dev/v1alpha1
kind: Greeter
metadata:
  name: reader
  namespace: default
spec:
  name: reader
status:
  configMapName: greeting-reader
  lastReconciled: "2026-07-30T18:47:14Z"
  message: Hello, reader!
```

That is the proof line. A TypeScript AppHost started the Kind cluster, ordered the CRD apply step, started the Go operator from source, and the real Kubernetes API server stored the resource, the ConfigMap, and the status update.

### Clean Up

Remove the Greeter first:

```powershell
kubectl delete greeter reader
```

Then stop `aspire run` with **Ctrl+C**. If you want to remove the persistent Kind cluster too:

```powershell
kind delete cluster --name dev-cluster
```

The C# AppHost sample has dashboard commands for cleanup. The TypeScript sample does not wire those buttons yet, so the explicit terminal cleanup is the honest path today.

## What Is Real, and What Is Still Catching Up

The generated-SDK model is real, but it is still a preview-shaped developer experience. Today, the SDK surface lives inside `.aspire/modules/` and is regenerated by Aspire. Later, a stable npm package may make that feel more familiar to JavaScript developers. For now, the rule is simple: change `aspire.config.json`, run `aspire restore`, and do not edit generated files.

The Kind story is also real. `CommunityToolkit.Aspire.Hosting.Kind` comes through the packages block and generates usable TypeScript bindings. The gap is specific: `withManifest` has not shipped for this path yet, so the CRD apply step remains a tiny executable resource. That is the kind of helper you delete later, not the foundation of the cluster story.

The dashboard experience is real where the sample models resources: logs, state, dependencies, restart controls, and the same resource graph. The missing custom commands are a sample gap. The generated TypeScript SDK already has the shape needed to add buttons like **Apply Greeter** or **Delete all Greeters**.

The debugger story is the next place for sample polish. The operator process is still a plain Go process, and `packagePath: '.'` gives the Go integration the right package shape. The remaining work is to add the TypeScript VS Code launch entry that connects that process shape to Delve.

## Conclusion

The core claim from the Greeter post survives translation to TypeScript: the AppHost is still the source of truth for local topology, the Kind cluster still has a real lifecycle in the graph, the CRD apply step is ordered before the operator starts, and the Go operator still runs from source as a host process.

That is the proof I wanted. Not perfect parity, and not a claim that every rough edge has disappeared. The proof is that a Node or TypeScript developer can model the same Kubernetes operator loop without rewriting the AppHost in C#.

There is still .NET underneath Aspire's runtime. That is not hidden. The point is narrower and more useful: you do not have to write the AppHost in C# to get an Aspire-shaped local topology. You can author the graph in TypeScript, consume the same Kind integration, run the same Go operator, and keep Kubernetes state real without turning the README into the orchestrator.

This is the same disruption from the earlier posts, just from the other side of the fence. The setup doc is still the smell. The resource graph is still the fix. And the language boundary is thinner than it first looks.

## Related Posts

- [Part 1: When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-28-aspire-kubernetes-operator-inner-loop %})
- [Part 2: The First Breakpoint: My Argo CD Story, and Why Aspire Is Quietly Disrupting DevOps]({% post_url 2026-07-30-aspire-argocd-inner-loop %})
