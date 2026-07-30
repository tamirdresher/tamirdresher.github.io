---
layout: post
title: "The First Breakpoint: My Argo CD Story, and Why Aspire Is Quietly Disrupting DevOps"
date: 2026-07-31T07:15:00+03:00
tags: [dotnet-aspire, platform-engineering, devops, argo-cd, kubernetes, kind, cncf, inner-loop]
description: "The working Argo CD Aspire AppHost loop: a real F5 Go breakpoint, a Kind cluster holding only state, and repo-owned topology that the next contributor can inherit."
---

> This is the real-world version of the pattern I wrote about in [When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-28-aspire-kubernetes-operator-inner-loop %}): a Kind cluster (Kubernetes running inside Docker containers on your machine) as part of the local topology, not a prerequisite hiding in a README. You can start here without reading that post first; the short version is the same pattern, larger project, real contributor loop.

## Why the Breakpoint Matters

Here is the loop now: you press **F5** in VS Code, the **Aspire AppHost** starts the Argo CD topology, the dashboard opens, every resource settles into Running and Healthy, the UI answers on `:4000`, and a breakpoint in Go code binds instead of waiting behind a setup guide.

Three terms in that sentence are carrying weight, and depending on which side of the fence you work on, one half will be new. **Argo CD** is a GitOps continuous-delivery controller for Kubernetes: it watches Git repositories and makes the cluster match what is declared there. An **Aspire AppHost** is a small C# program that declares which processes, containers, and clusters make up an application, then starts them together with the wiring between them. The **Aspire dashboard** is the web UI it opens alongside them, showing every resource with its logs, health, and commands.

![The Aspire dashboard listing the Argo CD topology: Redis as a container, dev-mounter as a one-shot setup step, seven Argo CD control-plane processes running as host executables, and the Kind cluster, with every long-running resource showing Running](/assets/aspire-argocd-inner-loop/argocd-aspire-dashboard-resources.png)

It shows ten resources: a persistent Kind cluster, Redis as a container, `dev-mounter` as a one-shot setup step, and seven Argo CD control-plane processes running as host executables. The Kind cluster is not pretending to be production. It holds the Kubernetes state this loop actually needs — the CRDs that teach the Kubernetes API server what an Argo CD `Application` is, the RBAC permissions — Kubernetes role-based access rules — the controllers run under, and `argocd-cm`, Argo CD's own configuration ConfigMap — while the code I want to edit stays on my machine, next to VS Code and Delve, Go's debugger.

That is the whole control plane. `api-server` on 8080, `repo-server` on 8081, `commit-server` on 8086, `applicationset-controller` on 12345, the UI on 4000, and `application-controller` and `notifications-controller` doing their work without an HTTP surface. In practical terms, `api-server` serves Argo CD's API, the UI serves the browser, `repo-server` fetches and renders manifests from Git, and `application-controller` reconciles Applications against the cluster; the others fill out the same local topology. `dev-mounter` shows as Finished because it is a one-shot setup step rather than a service.

That is the product. Not the fluent API. Not the architecture diagram I can draw to feel clever. The product is the moment a contributor can stop setting up the world and start understanding the code.

## The Contributor Problem in Argo CD

The reason I cared enough to build this loop was practical. A while back I wanted a feature in Argo CD: [issue #18000 — `syncPolicy.DisableHelmChartCache=true`](https://github.com/argoproj/argo-cd/issues/18000). Leland Knight had opened it, we had been discussing it, and I decided to try building the fix myself.

The request sounded small: let a Helm-source Application say, "do not cache the chart." That matters in dev loops. It also matters with OCI Helm registries where charts can be updated in-place without a version bump. If the chart content changes but the version string does not, the cache becomes the enemy. And like most good feature requests, it sounded easy before I actually touched the code, which is how software lures us into the cave.

The standard OSS move is simple enough: clone the repo, follow the contributor guide, and get to the code path behind the feature request. The hard part is that mature cloud-native projects accumulate local-dev sediment: Makefiles, `hack` scripts, Procfiles, Kind clusters, Tilt, Kubernetes patches, UI dependencies, Corepack shims, generated assets, and one guide linking to another guide that assumes you already ran the thing from the previous guide. None of those pieces is irrational. Each one exists because someone solved a real problem at a real moment.

The problem is what happens after years of real moments: you do not get a clean contributor loop, you get a pilgrimage. Argo CD is a mature CNCF project with serious maintainers, real documentation, real developer workflows, and a codebase that has earned every bit of its operational complexity. This is not a dunk on Argo CD. I like Argo CD. That is why the local loop matters: the sooner a contributor gets from "I cloned the repo" to "I am stepping through the code path I care about," the sooner the project benefits from their attention.

This is the part of open source we under-talk about. We measure time-to-first-issue, time-to-merge, review latency, CI health, and coverage. Those are all useful. But there is another metric hiding underneath them: how long does it take a motivated contributor to reach the first useful breakpoint?

## What the Aspire AppHost Runs

Quick refresher before the topology: Aspire is a code-first, polyglot orchestrator for distributed apps. Containers, processes, cloud resources, dependencies, endpoints, health, and startup ordering live together in the AppHost resource graph. The shortest version lives at [aspire.dev](https://aspire.dev): compose, debug, and deploy distributed applications from code.

For cloud-native inner loops, the missing piece is often the cluster, and that is where `CommunityToolkit.Aspire.Hosting.Kind` comes in. It gives the AppHost a real local Kubernetes cluster as a first-class Aspire resource instead of a paragraph in a README that says, "Before you start, create a cluster and apply these things."

### Kind Holds State; Host Processes Stay Debuggable

The Argo CD topology is deliberately split: **Kind holds state**, Redis runs in a container, and the editable Argo CD processes run as host executables. The cluster does **not** run the Argo CD Deployments in this loop. It provides the Kubernetes API, CRDs, ConfigMaps, Secrets — Kubernetes objects for sensitive values — and state texture the controllers need; the code I want to edit runs on my machine, close to the debugger.

![Diagram of the Argo CD Aspire inner loop split: seven Go control-plane processes and Redis running on the laptop, a Kind cluster holding CRDs, RBAC, and argocd-cm, and KUBECONFIG connecting the host processes to the cluster](/assets/aspire-argocd-inner-loop/what-runs-where.svg)

### The Cluster Bootstrap Lives in the Graph

The actual cluster wiring in this branch is small. The AppHost derives a per-checkout cluster name, renders the Argo CD state manifest, then creates a persistent Kind cluster and applies that generated manifest:

```csharp
// Give each checkout a stable, repo-derived cluster name.
var kindClusterName = ArgoCdClusterName.Resolve(repoRoot);

// Render only the Kubernetes state Argo CD needs locally: CRDs, RBAC, ConfigMaps, Secrets.
var stateManifestPath = ArgoCdManifestSet.RenderStateOnlyManifest(
    Path.Combine(AppContext.BaseDirectory, "generated", "argocd-state.yaml"),
    enableDex);

// Model the Kind cluster as part of the Aspire graph, then apply the generated manifest.
var cluster = builder
    .AddKindCluster(kindClusterName)
    .WithClusterLifetime(ClusterLifetime.Persistent)
    .WithManifest(stateManifestPath);

// Put contributor operations on the resource that owns them.
cluster
    .WithRepoServerOverrideCommand()
    .WithDeleteClusterCommand()
    .WithAdminCredentialCommand();
```

That whole thing is still just a fluent builder: choose the cluster identity, generate the Kubernetes state that Argo CD needs, create the cluster, apply the manifest, and attach contributor commands, all in typed C# under a debugger and in the same program that describes the rest of the local system. Not bash. Not Terraform. Not a README ritual with three "important" notes that only become important after you miss one.

The killer method in that snippet is `WithManifest(stateManifestPath)`.

`WithManifest` turns the cluster bootstrap into part of the resource graph. When the cluster is ready, Aspire applies the generated state manifest, using server-side apply, Kubernetes' field-aware apply mode, for the resources Argo CD needs. Health reflects the manifest resource, and downstream processes that call `.WaitFor(cluster)` unblock only after the cluster and its state are ready for them.

This branch still carries a small local extension because the package version I am using does not yet include the manifest API I need. The upstream work is [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481), which is the piece that makes manifest application, including server-side apply, a first-class part of the Kind integration rather than local AppHost ceremony.

Startup order is part of that same topology. Every component that reads Kubernetes configuration waits for the Kind cluster and its state manifest, while `commit-server` is correctly excluded because it never talks to Kubernetes. Namespace wiring lives there too: the local processes run in `default`, and the generated state lines up with that expectation.

That is the difference I care about. The README can still explain the loop, but the graph carries the loop. A `.WaitFor(cluster)` edge is not glamorous; it is exactly the kind of platform detail that makes a contributor loop feel reliable.

## Dashboard Commands as Contributor Tools

Once that graph is visible, the dashboard is not just a prettier `ps`. The Kind cluster resource also carries three commands: show admin credentials, delete the cluster, and rebuild `repo-server` from the current source. That matters because in the normal Kubernetes loop, these operations usually live as shell incantations in docs. Attached to the resource, they become part of the loop: discoverable, cross-platform, and close to the thing they operate on.

### Rebuild repo-server from source

The most interesting one is **Rebuild repo-server (source override)**. The default loop runs Argo CD's Go processes on the laptop because that is what makes F5 and Delve useful. But sometimes I want the in-cluster path too: build the real `argocd-repo-server` image from the current tree, load it into Kind, patch the Deployment, restart it, and confirm the new binary is the one running. That is a lot of small steps to ask a contributor to assemble by hand.

The command does not invent a parallel build system. Its source follows the same path as `make image DEV_IMAGE=true`: build the `argocd-base` target, run `go build` with the Makefile's ldflags and gcflags, package with `Dockerfile.dev`, load the image into Kind, patch and roll out `argocd-repo-server`, then check the logs for the commit. The reason it does this in C# instead of simply invoking `make` is practical: `make` and bash are not reliably available on Windows. The README can still show the equivalent commands for macOS and Linux contributors, but the button works the same way everywhere.

The image tag is a small detail with an outsized payoff. Every rebuild gets a tag built from the short commit, the tree state, and a UTC timestamp:

```csharp
public static string ComputeTag(string shortGitCommit, bool dirty, DateTimeOffset utcNow)
{
    ArgumentException.ThrowIfNullOrEmpty(shortGitCommit);

    // Keep the tag explainable: commit, tree state, and a timestamp Kind cannot cache away.
    var suffix = dirty ? "dirty" : "clean";
    var timestamp = utcNow.UtcDateTime.ToString("yyyyMMdd'T'HHmmss'Z'", CultureInfo.InvariantCulture);
    return $"{shortGitCommit}-{suffix}-{timestamp}";
}
```

So a local build looks like `7ca0120-dirty-20260722T193201Z`, and the timestamp means Kind sees a new image every time instead of quietly reusing a cached tag. I like that `ComputeTag` is deliberately a tiny pure function too; the test project can prove the tag shape and distinct-timestamp behavior without needing Docker, Kind, or git.

### Credentials and teardown

The smaller commands make the same argument. **Show admin credentials** runs Kubernetes' command-line client, `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath={.data.password}`, and decodes the password in managed code instead of asking everyone to pipe through `base64 -d`, which is fine until the contributor is on Windows without a POSIX shell. It also knows this loop starts `api-server` with `--disable-auth=true`. In that mode the secret is not there because no password is needed, so the command returns a successful explanation instead of dumping a raw Kubernetes error on the person who clicked the button.

**Delete Kind cluster (clean shutdown)** is there for the opposite end of the loop. The dashboard command runs `kind delete cluster --name ...`, waits for it to finish, and then best-effort removes the generated kubeconfig. The important bit is the wait: resource commands are awaited by the Aspire dashboard and CLI, while process shutdown is allowed to move on. Teardown is not just a line in a README; it is an operation the tool can own to completion.

That is why `WithCommand`, Aspire's way to attach dashboard and CLI actions to a resource, feels bigger here than a convenience API. It gives local platform work a home. A multi-step rebuild, a cross-platform credential helper, and a clean teardown button sit on the resource that needs them, next to logs and health, instead of hiding in paragraphs a contributor has to find before they can use the system.

## Health Checks That Mean Something

Green should mean the endpoint a contributor needs is actually answering, not merely that a process launched. That is why the AppHost wires explicit checks with `WithHttpHealthCheck(path, endpointName: ...)`: `api-server` checks `/api/version`, `repo-server` checks `/healthz` on its metrics endpoint at port 8084, `commit-server` checks `/healthz` on its metrics endpoint at port 8087, and the UI checks `/`.

`applicationset-controller` is the honest wrinkle: its `/healthz` and `/readyz` return 404, so the check uses `/metrics` on port 12345. That proves the process is serving HTTP, not that the controller has declared itself ready. `application-controller` and `notifications-controller` do not serve HTTP at all, so they do not get pretend health checks bolted on for symmetry. Symmetry is nice in diagrams; lies are less nice in repos.

The result is exactly the direction I want: Aspire marks the resource healthy only after the endpoint is already answering. That is a conservative signal rather than an early green light, and early is where dashboards stop being trustworthy.

That is the earned claim: seven Go control-plane components as host executables, Redis as a container, a Kind cluster holding state only, the UI answering on `:4000`, `api-server` answering `/api/version`, and F5 hitting a Go breakpoint. The AppHost does not make Argo CD simple. Good. Argo CD is not simple. The AppHost makes the local topology visible enough that the health signal means what it says.

## End-to-End Testing the Real GitOps Loop

Running the full loop is still the only proof that the loop runs. But the useful testing split is not "graph tests versus real runs." It is **cheap checks for the topology** and **one real local run for the behavior nothing cheaper can prove**.

The cheap tests still matter. `ResourcesWithHttpEndpoints_HaveHealthChecks` checks that every resource with an HTTP endpoint has a health check annotation, so health stays part of the topology the next time someone adds an endpoint. That runs without Docker, Kind, Go builds, or network access.

But the interesting test is the expensive one: `WhenCanonicalGuestbookApplicationIsApplied_ThenArgoCdSyncsItAndKindRunsIt`. It is gated behind `ARGOCD_ASPIRE_E2E=1` because it needs Docker, Kind, Go, `kubectl`, Node/pnpm, and outbound access to GitHub. On this branch, it takes about six minutes. That is not "run this every time you save a file" feedback. It is pre-merge or nightly confidence.

The real test file keeps some of the plumbing in helpers because that is the right shape for maintainable test code. For the post, here is the same test with the mechanics inlined so you can see what it is actually proving.

### Step 1: Start the AppHost and Wait for Argo CD

First, the test starts the real AppHost. No mocked API server, no fake cluster, no "trust me, the controller would have started." It builds the same Aspire model a contributor uses and waits for the Argo CD control plane the same way you would: are the servers up?

```csharp
// Build the same AppHost a contributor starts from VS Code or the CLI.
await using var builder = await DistributedApplicationTestingBuilder
    .CreateAsync<Projects.ArgoCd_Aspire_AppHost>();

// The Kind cluster is part of the Aspire model, so the test can use its kubeconfig.
var cluster = builder.Resources.OfType<KindClusterResource>().Single();

await using var app = await builder.BuildAsync(cancellationToken);
await app.StartAsync(cancellationToken);

// Wait for the Argo CD control plane, not just for processes to exist.
await app.ResourceNotifications.WaitForResourceHealthyAsync("repo-server", cancellationToken);
await app.ResourceNotifications.WaitForResourceHealthyAsync("commit-server", cancellationToken);
await app.ResourceNotifications.WaitForResourceHealthyAsync("api-server", cancellationToken);
await app.ResourceNotifications.WaitForResourceAsync(
    "application-controller", KnownResourceStates.Running, cancellationToken);
```

That is already more valuable than a topology assertion. The **real AppHost** has to build, the fixed ports have to be free, the host processes have to launch on the current OS, and Aspire has to resolve the endpoints it modeled.

### Step 2: Apply the Guestbook Application

Then the test writes a real Argo CD `Application` manifest and applies it with `kubectl` against the Kind kubeconfig. The Application points at Argo CD's canonical guestbook sample, enables automated sync, and asks Argo CD to create the target namespace.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: aspire-e2e-guestbook-<unique-suffix>
  namespace: default
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd-aspire-e2e-guestbook
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

```csharp
// Create the Argo CD Application through the Kubernetes API, just like a real user would.
await Kubectl(
    "apply",
    "-f", applicationManifestPath,
    "--kubeconfig", cluster.KubeconfigPath);
```

Now the test has stopped checking whether the graph is plausible and started checking whether the **GitOps loop** works: Argo CD has to fetch from GitHub, render the guestbook manifests, and reconcile them into the local cluster.

### Step 3: Ask Argo CD What It Synced

Next, the test asks Argo CD through its own API. The important detail is that Aspire resolves the `api-server` endpoint from the model, so the test does not hardcode `localhost:8080` and then pretend that is the same thing as the running topology.

```csharp
// Aspire resolves the api-server endpoint from the model — no hardcoded localhost:8080.
var argoCd = app.CreateHttpClient("api-server", "http");

// Poll until the Application reports Synced and Healthy.
var response = await argoCd.GetAsync(
    $"/api/v1/applications/{applicationName}?appNamespace=default&refresh=normal",
    cancellationToken);

using var document = JsonDocument.Parse(
    await response.Content.ReadAsStringAsync(cancellationToken));
var status = document.RootElement.GetProperty("status");

Assert.Equal("Synced", status.GetProperty("sync").GetProperty("status").GetString());
Assert.Equal("Healthy", status.GetProperty("health").GetProperty("status").GetString());

// status.resources[] is what Argo CD believes it manages.
var managed = status.GetProperty("resources");
```

The assertion is intentionally exact. The real test requires **exactly** these managed objects:

- `Deployment/guestbook-ui`
- `Service/guestbook-ui`

Both must be `Synced`, and each must be `Healthy` when Argo CD reports health for it. `requireExactSet: true` matters because it catches a **partial sync** and an accidental extra object, not just a total failure.

One Argo CD API detail was worth learning in the real loop: `/api/v1/applications/{name}/resource-tree` looks obvious, but here it consistently returns a 500 with `error getting cached app resource tree: EOF` because it is backed by Argo CD's Redis-cached tree. `status.resources[]` on the Application object itself is stable, so the test reads that instead. That is the kind of detail you only get from running the actual system.

### Step 4: Ask Kubernetes What Is Actually Running

This is the step that matters most. **Argo CD grading its own homework proves nothing.** A controller saying "Synced" is useful, but the cluster is the system of record for whether a workload is actually running.

So the test asks Kind directly:

```csharp
// Argo CD believing a sync worked is not the same as the workload running.
await Kubectl(
    "wait",
    "--for=condition=available",
    "deployment/guestbook-ui",
    "-n", "argocd-aspire-e2e-guestbook",
    "--timeout=180s",
    "--kubeconfig", cluster.KubeconfigPath);

// Read the actual Kubernetes Deployment from the cluster.
var deployment = await KubectlGetJson(
    "deployment",
    "guestbook-ui",
    "-n", "argocd-aspire-e2e-guestbook",
    "--kubeconfig", cluster.KubeconfigPath);

Assert.Equal(1, deployment.Spec.Replicas);
Assert.Equal(1, deployment.Status.ReadyReplicas);
Assert.True(deployment.Status.AvailableReplicas >= 1);
Assert.Equal("guestbook-ui", deployment.Spec.Selector.MatchLabels["app"]);
```

The real code also checks the `Service/guestbook-ui`: it must select `app=guestbook-ui` and expose port `80` to target port `80`. That extra service check is not decorative. It catches the difference between "the Deployment eventually became available" and "the guestbook shape Argo CD applied is actually usable."

This is the useful boundary: the topology test can prove the graph shape, but it cannot prove that a preferred port became the actual port, that a Windows process can launch the helper executable, or that a real guestbook Application reaches `Healthy`. The graph was correct; the values were wrong.

### Step 5: Open the UI with Playwright

The UI test uses the same scenario and then opens the real Argo CD UI with Playwright. Again, Aspire resolves the endpoint from the model; the test does not guess the browser URL.

```csharp
// Aspire resolves the UI endpoint too.
using var uiClient = app.CreateHttpClient("ui", "http");

using var playwright = await Playwright.CreateAsync();
await using var browser = await playwright.Chromium.LaunchAsync(new() { Headless = true });
var page = await browser.NewPageAsync();

await page.GotoAsync(
    new Uri(uiClient.BaseAddress!, "applications").ToString(),
    new PageGotoOptions { WaitUntil = WaitUntilState.NetworkIdle });

// api-server runs with --disable-auth=true, so there is no login step.
Assert.DoesNotContain("/login", page.Url);

await Expect(page.GetByText(applicationName).First).ToBeVisibleAsync();
await Expect(page.GetByText("Synced").First).ToBeVisibleAsync();
await Expect(page.GetByText("Healthy").First).ToBeVisibleAsync();
```

The real test clicks into the application detail page, also checks for `guestbook-ui`, and saves a screenshot under `contrib/aspire-dev/.e2e/`, which makes UI failures much easier to diagnose after the fact.

### What the Real Run Catches

Two bugs from this branch explain why the expensive test earned its place.

One was resolved ports. The topology can ask Redis to prefer host port `6379`, while a Go component can still hardcode `--redis localhost:6379`, copied from Argo CD's Procfile. In Aspire, a preferred port is not a promise: if the port is taken, Aspire allocates another host port, and the failure surfaces as Redis authentication noise instead of an obvious conflict. The fix was to thread Aspire's resolved endpoint through `REDIS_SERVER` instead of trusting the literal.

Another was OS-specific process launch. `repo-server` shells out to `git-verify-wrapper.sh` during manifest generation, and Go's `exec` cannot run a `.sh` file on Windows. The sync symptom is a bare `EOF`, far away from the actual cause. The fix was a small Windows executable shim in the wrapper's place.

So I want both kinds of tests. Cheap graph checks on every change. One expensive real run when the branch is ready for merge, or on a nightly schedule. Different costs, different questions, both worth answering.

## Why Agents Can Use the Same Loop

There is another consequence hiding in the same shape: anything an agent can execute and observe, it can start to work with. A setup guide is neither. A traditional cloud-native inner loop assumes a human who can read between the lines: install these tools, run this script, remember the Windows note halfway down the next page, and if the controller does not start, try to guess which generated file you missed. That is hard enough for a person on day one. For an agent, it is mostly fog. It cannot reliably know whether step four worked, why a pod is unhealthy, or which of six diagnostic commands answers "is the system up yet?"

An AppHost gives the loop a surface a machine can actually drive. `aspire start` and `aspire stop` are one entry point for the whole topology. `aspire describe` and `aspire ps` expose current state, health, endpoints, and URLs as structured output. `aspire logs <resource>` gets the logs for the thing that failed without first knowing whether that thing is a container, a host process, or a Kubernetes component. Resource commands make the same dashboard buttons invocable, so rebuilding `repo-server` is one operation instead of a recipe. And the topology tests let the agent check the shape of the environment in milliseconds without Docker, Kind, or a prayer to the laptop fan.

That is not theoretical hand-waving. The same surface is useful to a developer and to an agent because the environment exposes the work instead of hiding it in prose. If `api-server` cannot start because `configmap "argocd-cm" not found`, `aspire logs api-server` is a direct path to the clue. If `aspire describe` says something is healthy, a real HTTP request can verify whether anything is actually listening. If health turns green before the endpoint serves, polling both signals makes the gap visible. If the cluster state is in question, `kind get clusters` and a Kubernetes query answer it without someone remembering which page of the guide mentioned the cluster name.

None of this makes the hard parts free. The end-to-end GitOps test works, but five minutes plus Docker, Kind, Go, and network access is a real cost. A machine-readable environment does not mean every workflow belongs in the keystroke loop, or that every workflow is now automatable. It means the observable parts are observable by anyone: the maintainer, the contributor who joined last week, and the agent that has no tribal knowledge at all. In that sense, an agent is just the most extreme newcomer. If the loop is discoverable enough, has one entry point, reports structured state, and keeps its operations with the code, then optimizing for the confused human on day one turns out to produce something a machine can drive too.

## Practical Local Development Notes

One practical note for large Go repos: `dlv debug` compiles with optimizations disabled, which means it uses a different build-cache entry from `go build`, so a cold debug build of Argo CD's `./cmd` can take several minutes. The launch configuration sets `DCP_IDE_REQUEST_TIMEOUT_SECONDS` in `.vscode/launch.json`, so the debug session gets the time budget this repo needs.

The launch config also keeps `"dashboardBrowser": "openExternalBrowser"`, which makes F5 open the Aspire dashboard as part of the loop instead of turning the dashboard URL into another thing to copy from a terminal.

One more local-development thing: every `dlv debug` run leaves a `__debug_bin*.exe` next to the package being debugged. In this repo, they are large debug binaries, so `.gitignore` excludes them. Not a grand architectural point. Just the kind of repo hygiene that keeps the inner loop from leaving souvenirs in the working tree.

## How the Contribution Is Packaged

The sample started life as a standalone companion repo, and that first shape was useful because it let me move fast without pretending I understood the upstream contribution path yet. But it also recreated the exact onboarding smell this post is about: one repo had the AppHost, another repo had Argo CD, and then a helper had to wander around the filesystem trying to find the checkout it was supposed to orchestrate. That worked, but it was a polite way of saying "please solve path discovery before you can solve the real problem."

The better version now lives inside my Argo CD fork itself: `https://github.com/tamirdresher/argo-cd`, on the `aspire-dev-loop` branch, under `contrib/aspire-dev/`. That matters because Argo CD already has a `contrib/` convention, so this is no longer just a side experiment that has to live forever next to the real project. It can be proposed upstream as an actual contribution candidate, and that lands the thesis much harder: the fix to the onboarding problem can live in the project that has the onboarding problem.

The layout is plain on purpose, because the point is to see the contribution path instead of admire the scaffolding:

```text
contrib/aspire-dev/
├── ArgoCd.Aspire.slnx
├── global.json
├── README.md
├── ArgoCd.Aspire.AppHost/
├── ArgoCd.Aspire.Hosting.Kind.Extensions/
└── ArgoCd.Aspire.AppHost.Tests/
```

Moving the AppHost in-tree deleted an entire class of "find the other repo" problems. The repo root is structurally known as `../../..` from the AppHost project, resolved at build time through MSBuild metadata instead of discovered at runtime by filesystem archaeology. That is the same lesson as the AppHost itself: if a path, dependency, startup order, or prerequisite is part of the system, model it where the system can see it instead of asking the reader to remember it.

The same dashboard commands are where this stops being a pretty graph and starts feeling like contributor tooling. The Kind cluster resource wires commands directly in `AppHost.cs`: show admin credentials, delete the Kind cluster cleanly, and rebuild `repo-server` from the current source override. Those are exactly the kinds of buttons serious projects eventually grow: seed data, rotate a secret, force a resync, rebuild the one component you are actually editing.

The happy path is now the thing a contributor should see first:

```powershell
git clone https://github.com/tamirdresher/argo-cd
cd argo-cd
git switch aspire-dev-loop
code .
```

VS Code prompts for the recommended extensions because the repo includes `.vscode/extensions.json`, and the important ones for this loop are `microsoft-aspire.aspire-vscode` and `golang.go`. If the launch entry ever disappears, you do not have to hand-type JSON: press **Ctrl+Shift+P**, run **Aspire: Configure launch.json**, and let the extension write the AppHost entry. In the current checkout, `.vscode/launch.json` already points at `contrib/aspire-dev/ArgoCd.Aspire.AppHost/ArgoCd.Aspire.AppHost.csproj`, sets the longer DCP timeout, opens the dashboard, and gives the contributor the F5 path.

One clone. No path wiring. No script whose main job is to go fetch the real project from somewhere else. The command-line path still exists for automation and constrained machines, but it is no longer the ceremony at the front door.

## Conclusion

Here is the careful version of the disruption claim: Aspire does not replace Kubernetes, and that is not the interesting sentence. I do not want a local orchestrator pretending production does not exist. I do not want to hide the cluster from platform engineers. The cluster is the thing. Kubernetes is still where the CRDs live, where the API server enforces reality, where controllers observe state, and where production texture matters.

The interesting sentence is this: Aspire makes Kubernetes' outside modellable in code. By "outside" I mean all the things around the cluster that every serious cloud-native project needs before a contributor can do useful work: the local cluster, the manifests, the sidecars, the supporting containers, the host processes, the UI, the dependency ordering, the ports, the health checks, the generated state, the commands, the little readiness rituals, and the "please run this before that" knowledge that slowly migrates into documentation because documentation is where pain goes when we have not modeled it yet.

The setup doc is the smell, even though a good README is still important. I love a good README. But if the README is carrying topology, lifecycle, dependency ordering, health verification, and environment-specific caveats, then the README is doing work that belongs in a program.

The same rule applies one layer below the AppHost. VS Code's [workspace recommended extensions](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace#_workspace-recommended-extensions) move "install the Aspire and Go extensions" out of prose and into `.vscode/extensions.json`, so newcomers get prompted by the editor instead of punished by a missed paragraph. A [dev container](https://containers.dev/) can take that further: the SDK, Go toolchain, Kind, `kubectl`, Delve, Node, `pnpm`, and extensions can all be described in [`devcontainer.json`](https://containers.dev/implementors/json_reference/) and built for the contributor, locally or in [Codespaces](https://docs.github.com/en/codespaces/overview). The setup guide stops being a document people follow and becomes a file the machine follows.

An executable AppHost is better than a paragraph that says "first create a Kind cluster." A fluent builder call is better than a shell snippet that applies a manifest and hopes everyone remembers when it should happen. A `.WaitFor(cluster)` edge is better than "wait until the cluster is ready" as tribal instruction. A launch setting checked into the repo is better than a troubleshooting note that only helps after the first F5.

That is why `WithManifest` is more than a convenience method. It is the archetype. It says the install-configure-verify sequence belongs in the resource model. Server-side apply says the resource model must carry the ordinary Kubernetes realities too. `WithPortMapping`, `WithWorkerNodes`, and `WithKubernetesVersion` are the same kind of API when a project needs them. Each one moves a piece of local platform ceremony out of prose and into code.

And once it is code, it can be debugged. It can be reviewed. It can be reused. Most importantly, it can be inherited by the next contributor without them having to rediscover why the guide has a warning box in paragraph eleven.

The Kind integration is not Argo CD-specific. Any project with Kubernetes state plus host processes can benefit from the same shape. Operators. Controllers. CLIs that talk to the API server. UIs that expect services to exist. Test harnesses that need a real cluster but do not need every edit to become a container image.

The pattern is: keep real state real, run editable code close to the debugger, and let the AppHost model the topology between them.

That is not a .NET-only idea either. Aspire's AppHost can be TypeScript or JavaScript. The C# examples exist because that ecosystem got the first wave of docs and integrations, but the concept is not "platform engineers must become .NET developers." Platform engineers who live in JS or TS should be able to model local topology in the language they already use. Again: [aspire.dev](https://aspire.dev) is the place to track the current language and integration story.

The deeper point is onboarding, because every minute a contributor spends fighting local setup is a minute they are not spending understanding the code. Maintainers should care about that. Not as a kindness, although kindness is underrated. They should care because setup friction selects against contribution. It punishes the people who are motivated enough to help but not yet steeped in the project's accumulated rituals.

A debugger-first AppHost is not just nicer; it is a maintenance strategy. It makes the local topology visible. It makes assumptions executable. It makes prerequisites fail fast. It makes "what is running?" answerable from a dashboard instead of five terminals. It turns "follow the guide carefully" into "run the graph and let the graph tell you what is missing."

That is the disruption I mean. No keynote thunder. No "replace your platform" sticker. No pretending Kubernetes got simple because I wrote a fluent API around Kind. Just a quiet shift where a whole category of pain becomes optional.

The healthier loop is the one where the real system runs locally, the topology is explicit, and the repo itself carries the edges, timeouts, apply mode, and health checks the next contributor needs.

Next time, I want the loop to look like this:

```powershell
git clone https://github.com/tamirdresher/argo-cd
cd argo-cd
git switch aspire-dev-loop
code .
```

Then VS Code recommends the extensions, **F5** starts the AppHost, the dashboard opens, and the contributor gets the graph, logs, project-specific commands, and a real Go breakpoint.

That is days into minutes, but more importantly it is the onboarding fix living inside the project that needs it. That is the part I have been waiting for.

## Related Posts

- [Part 1: When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-28-aspire-kubernetes-operator-inner-loop %})
- [Part 3: The Same Operator Loop, in TypeScript — The AppHost Moves, the Topology Stays](/blog/2026/08/02/aspire-typescript-kubernetes-operator.html)
