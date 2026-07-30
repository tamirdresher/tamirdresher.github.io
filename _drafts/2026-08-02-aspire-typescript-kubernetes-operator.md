---
layout: post
title: "You Do Not Need C# to Use Aspire: The Same Kubernetes Operator Loop in TypeScript"
date: 2026-08-02T07:15:00+03:00
tags: [aspire, dotnet-aspire, typescript, platform-engineering, kubernetes, operator, kind, polyglot, inner-loop]
description: "Aspire is not a .NET-only local orchestration story: the same Greeter operator loop from Part 1 runs with a TypeScript AppHost, including the Kind cluster, CRD, Go operator, and dashboard commands."
---

Parts 1 and 2 both used a C# AppHost, and that is a reasonable place for some readers to stop. Plenty of excellent engineers do not write C#, do not want to write C#, and would naturally assume Aspire is a .NET tool wearing a cloud-native jacket. Fair assumption. Wrong conclusion.

Aspire's AppHost is a model of your local topology. C# is one way to author that model, and it is still a great one, especially for the .NET audience I usually write for. But it is not the only door into the room. TypeScript is a first-class way to write an AppHost too.

So this post rebuilds the Greeter operator example from Part 1 with nothing but a TypeScript AppHost. Same Go operator. Same CRD. Same Kind cluster. Same Aspire dashboard shape, including the custom Apply and Delete commands. The only thing that changes is the language used to describe the graph.

Everything in this post is in the sample repository. The TypeScript AppHost lives under `ts-apphost/`, and the default branch is `master`:

```powershell
git clone https://github.com/tamirdresher/aspire-kubernetes-operator-sample.git
cd aspire-kubernetes-operator-sample
code .
```

Browse it here: [github.com/tamirdresher/aspire-kubernetes-operator-sample/tree/master/ts-apphost](https://github.com/tamirdresher/aspire-kubernetes-operator-sample/tree/master/ts-apphost)

## The Same Greeter Loop, in TypeScript

Here is the loop from Part 1, now started from `ts-apphost/`: `aspire run` creates or reuses a real Kind cluster, applies the Greeter CRD, launches the unchanged Go operator as a host process, opens the Aspire dashboard, and the operator reconciles a sample Greeter into a ConfigMap, Kubernetes' simple key-value configuration object.

That sentence has a few loaded terms. If you live in Node or TypeScript but not Kubernetes, **Kind** is Kubernetes running inside Docker containers on your machine, a **CRD** is a Custom Resource Definition that teaches the Kubernetes API a new type, an **operator** or **controller** is a program that watches those types and acts on them, and **reconcile** means the controller repeatedly compares declared state with reality and repairs the difference.

If you live in Kubernetes or .NET but not Aspire and TypeScript, an **Aspire AppHost** is the program that declares the local topology, the **Aspire dashboard** is the web UI that shows the running resources, `kubectl` is Kubernetes' command-line client, and **Delve** is Go's debugger.

The useful claim is not that TypeScript gets a novelty badge. It is that the local topology survives the translation. The cluster is still an Aspire resource. The Go operator is still just Go. The AppHost language changes, but the graph does not.

### C# and TypeScript Side by Side

Part 1's C# AppHost creates the Kind cluster like this:

```csharp
var cluster = builder
    .AddKindCluster("dev-cluster")
    .WithClusterLifetime(ClusterLifetime.Persistent)
    .WithManifest(Path.Combine(repoRoot, "config", "greeter-crd.yaml"))
    .WithApplyGreeterCommand()
    .WithDeleteGreetersCommand();
```

The TypeScript AppHost creates the same persistent Kind cluster like this:

```typescript
let cluster = builder.addKindCluster('dev-cluster').withClusterLifetime(ClusterLifetime.Persistent);
```

That is the point of the post in one small comparison. C# says `AddKindCluster("dev-cluster").WithClusterLifetime(ClusterLifetime.Persistent)`. TypeScript says `addKindCluster('dev-cluster').withClusterLifetime(ClusterLifetime.Persistent)`. Different syntax, same resource in the graph.

The Go operator mapping is the same kind of translation. Part 1 uses the Go hosting integration from C#:

```csharp
builder
    .AddGoApp("greeter-operator", operatorDir)
    .WithEnvironment("KUBECONFIG", cluster.Resource.KubeconfigPath)
    .WithEnvironment("GOFLAGS", "-mod=mod")
    .WaitFor(cluster);
```

The TypeScript AppHost uses the projected Go integration:

```typescript
await builder
  .addGoApp('greeter-operator', operatorDir, { packagePath: '.' })
  .withKindClusterReference(cluster)
  .withEnvironment('GOFLAGS', '-mod=mod')
  .waitFor(cluster)
  .waitForCompletion(greeterCrd);
```

The TypeScript version also waits for the CRD helper, because the CRD needs to exist before the operator starts watching Greeters. But the operator is still the same Go package from Part 1. It did not become a Node service, it did not move into the cluster, and it did not learn anything about Aspire.

The topology portion of the TypeScript AppHost fits in one screen:

```typescript
import { ClusterLifetime, createBuilder } from './.aspire/modules/aspire.mjs';

const builder = await createBuilder();

let cluster = builder.addKindCluster('dev-cluster').withClusterLifetime(ClusterLifetime.Persistent);

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

`withKindClusterReference(cluster)` is the important wiring. It gives the executable and the Go operator a kubeconfig for the Kind cluster, so the operator can talk to Kubernetes without the AppHost manually threading a `KUBECONFIG` string through every process. The operator remains a plain Go process, but the cluster relationship is now part of the resource graph.

### The CRD and Greeter Contract Do Not Move

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

## How the TypeScript AppHost Gets the Same Aspire Integrations

This is the mechanism that makes the "you do not need C#" claim credible. The TypeScript AppHost is not a separate, watered-down orchestration system. It is using Aspire hosting integrations through generated TypeScript bindings.

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

### Dashboard Commands Are TypeScript Too

The last visible gap in the TypeScript sample was the dashboard command story. That gap is gone. The TypeScript AppHost now attaches the same useful action to the Kind resource with `withCommand`:

```typescript
let cluster = builder.addKindCluster('dev-cluster').withClusterLifetime(ClusterLifetime.Persistent);

cluster = cluster.withCommand(
  'apply-greeter',
  'Apply Greeter (timestamped)',
  async (context) => {
    const stamp = formatStamp();
    const crName = `greeter-${stamp}`;
    const specName = `tamir-${stamp}`;
    const kubeconfigPath = await getKubeconfigPath(await context.resourceName());
    const yaml = `apiVersion: hello.tamirdresher.dev/v1alpha1
kind: Greeter
metadata:
  name: ${crName}
  namespace: default
spec:
  name: ${specName}
`;

    const result = await runKubectl(['--kubeconfig', kubeconfigPath, 'apply', '-f', '-'], yaml);

    if (result.exitCode !== 0) {
      return commandFailure(`kubectl apply failed for ${crName}.`, result.stderr || result.stdout);
    }

    return commandSuccess(`Applied ${crName} (spec.name=${specName})`, result.stdout.trim());
  },
  {
    commandOptions: {
      description: 'Applies a timestamped Greeter custom resource to trigger the operator reconcile loop.',
      iconName: 'Add',
      updateState: async () => ResourceCommandState.Enabled,
    },
  },
);
```

There is a companion `delete-greeters` command that runs `kubectl delete greeters --all -n default --ignore-not-found`, so the dashboard now has both sides of the loop: create a fresh Greeter and clean up all Greeters afterward.

The timestamp is what makes **Apply Greeter** useful rather than just convenient. Every click creates a new Greeter name and a new `spec.name`, which means every click is a fresh trip through `Reconcile()` with a value you can watch change in the debugger. It is the same point as Part 1, now coming from a TypeScript AppHost.

The helper functions are ordinary plumbing. `formatStamp()` creates the `yyyyMMdd-HHmmss` suffix. `runKubectl()` delegates to `runProcess()`, sending YAML on stdin when needed and collecting stdout, stderr, and exit code. `commandSuccess()` and `commandFailure()` return dashboard-friendly command results with `CommandResultFormat.Text` and `displayImmediately: true`. The interesting helper is `getKubeconfigPath()`, because it exposes a real maturity seam: `withCommand` is projected into TypeScript, but `KubeconfigPath` is not.

## Try It Yourself

Start with Docker Desktop running and the prerequisites from the sample README installed: Node.js, the Aspire CLI, Go, Kind, and `kubectl`.

### Start the TypeScript AppHost

From VS Code, choose **Debug Aspire TypeScript AppHost** to launch the `.mts` AppHost through the Aspire extension. For the reproducible terminal path, use the TypeScript AppHost folder directly:

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

When the dashboard opens, the graph is the same shape as the C# version: `dev-cluster` is the Kind cluster, `greeter-crd` applies the CRD, and `greeter-operator` starts after both are ready. The `dev-cluster` resource also has **Apply Greeter (timestamped)** and **Delete all Greeters** commands, so you can drive the same loop from the dashboard instead of keeping the command sequence in your head.

The terminal path is still useful because it is reproducible, but the dashboard parity is no longer theoretical. The commands were also verified directly:

```powershell
aspire resource dev-cluster apply-greeter --non-interactive
# configmap/greeting-tamir-20260731-001029

aspire resource dev-cluster delete-greeters --non-interactive
# Greeters and their ConfigMaps removed
```

### Point `kubectl` at the Aspire-Managed Cluster

The TypeScript Kind binding does not expose `KubeconfigPath` as a property yet, but Aspire does include it in the resource description. Run `aspire describe --non-interactive --format Json`, copy `dev-cluster.properties.KubeConfigPath`, then set it in the second terminal:

```powershell
$env:KUBECONFIG = "<dev-cluster.properties.KubeConfigPath>"
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

You can also use the dashboard command or the equivalent CLI path once you are done:

```powershell
aspire resource dev-cluster delete-greeters --non-interactive
```

## What Is Real, and What Is Still Catching Up

The generated-SDK model is real, but it is still a preview-shaped developer experience. Today, the SDK surface lives inside `.aspire/modules/` and is regenerated by Aspire. Later, a stable npm package may make that feel more familiar to JavaScript developers. For now, the rule is simple: change `aspire.config.json`, run `aspire restore`, and do not edit generated files.

The Kind story is also real. `CommunityToolkit.Aspire.Hosting.Kind` comes through the packages block and generates usable TypeScript bindings. The gap is specific: `withManifest` has not shipped for this path yet, so the CRD apply step remains a tiny executable resource. That is the kind of helper you delete later, not the foundation of the cluster story.

The dashboard experience is real where the sample models resources: logs, state, dependencies, restart controls, the same resource graph, and now the same custom commands. `withCommand` came across into the generated TypeScript SDK just fine. The remaining gap is more specific: the TypeScript Kind binding does not project `KubeconfigPath`, while the C# command can read `cluster.Resource.KubeconfigPath` directly.

The workaround is concrete and pragmatic: `getKubeconfigPath()` shells out to `aspire describe --non-interactive --format Json`, finds the `dev-cluster` resource by name or display name, and reads `resource.properties.KubeConfigPath`. That is not as nice as a strongly typed property, but it is a narrow binding gap, not a missing dashboard-command model.

The F5 story is also catching up rather than missing. The sample repo has a TypeScript launch configuration checked into the root `.vscode/launch.json` alongside the C# one:

```jsonc
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Aspire AppHost",
      "type": "aspire",
      "request": "launch",
      "program": "${workspaceFolder}/apphost/GreeterOperator.AppHost.csproj"
    },
    {
      "name": "Debug Aspire TypeScript AppHost",
      "type": "aspire",
      "request": "launch",
      "program": "${workspaceFolder}/ts-apphost/apphost.mts",
      "env": {
        "DCP_IDE_REQUEST_TIMEOUT_SECONDS": "900"
      }
    }
  ]
}
```

That is a nice little design point: **one VS Code debug type, two AppHost languages**. The Aspire extension treats `program` as a file path. When it points at a `.csproj`, the C# AppHost path runs. When it points at `apphost.mts`, the extension runs `aspire run --apphost <program>` from that file's directory, classifies the file as a TypeScript AppHost, and routes it through the Node AppHost path.

The `DCP_IDE_REQUEST_TIMEOUT_SECONDS` value is the same kind of guard as in the Argo CD post: it raises DCP's default request timeout so a cold Go debug build has time to finish instead of losing the race to startup plumbing.

What I can say now is stronger than the earlier caveat: the launch configuration exists, the TypeScript AppHost runs through the same Aspire debug type, and DCP maps Go resources to the `golang.go` extension and `dlv-dap`, which is the same underlying Go debugging mechanism the C# AppHost path uses.

The remaining caveat is narrow and important: I have not yet confirmed a bound Go breakpoint from the TypeScript launch path in an interactive VS Code session, so I am not claiming verified F5 parity with the C# post. The terminal path above is still the reproducible path this post walks through.

## Conclusion

The core claim from the Greeter post survives translation to TypeScript: the AppHost is still the source of truth for local topology, the Kind cluster still has a real lifecycle in the graph, the CRD apply step is ordered before the operator starts, and the Go operator still runs from source as a host process.

That is the proof I wanted. Not perfect parity, and not a claim that every rough edge has disappeared. The proof is that a Node or TypeScript developer can model the same Kubernetes operator loop without rewriting the AppHost in C#.

There is still .NET underneath Aspire's runtime. That is not hidden, and it is not a problem. The point is narrower and more useful: you do not have to write the AppHost in C# to get an Aspire-shaped local topology. You can author the graph in TypeScript, consume the same Kind integration, run the same Go operator, and keep Kubernetes state real without turning the README into the orchestrator.

The setup doc is still the smell. The resource graph is still the fix. And the language boundary is thinner than it first looks.

## Related Posts

- [Part 1: When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-28-aspire-kubernetes-operator-inner-loop %})
- [Part 2: The First Breakpoint: My Argo CD Story, and Why Aspire Is Quietly Disrupting DevOps]({% post_url 2026-07-30-aspire-argocd-inner-loop %})
