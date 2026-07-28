---
layout: post
title: "The First Breakpoint: My argo-cd Story, and Why Aspire Is Quietly Disrupting DevOps"
date: 2026-07-31T07:15:00+03:00
tags: [dotnet-aspire, platform-engineering, devops, argo-cd, kubernetes, kind, cncf, inner-loop]
description: "What happened when the Argo CD Aspire AppHost finally ran end to end: a real F5 Go breakpoint, a Kind cluster holding only state, and the repo fixes that make the next contributor inherit the loop instead of rediscovering it."
---

> This is the real-world version of the pattern I wrote about in [When the Cluster Stops Owning the Inner Loop, and Why Aspire Is Quietly Disrupting Platform Engineering]({% post_url 2026-07-28-aspire-kubernetes-operator-inner-loop %}): a Kind cluster as part of the local topology, not a prerequisite hiding in a README. You can start here without reading that post first; the short version is the same pattern, bigger project, more archaeology. If you want the polyglot angle afterward, I also show the same loop with a [TypeScript AppHost]({% post_url 2026-08-02-aspire-typescript-kubernetes-operator %}) for readers who don't live in .NET; that Greeter sample lives at <https://github.com/tamirdresher/aspire-kubernetes-operator-sample>, while the Argo CD work below lives in the `aspire-dev-loop` branch of <https://github.com/tamirdresher/argo-cd>.

## The breakpoint is the product

A while back I wanted a feature in Argo CD.

Specifically, [issue #18000 — `syncPolicy.DisableHelmChartCache=true`](https://github.com/argoproj/argo-cd/issues/18000). Leland Knight had opened it, we had been discussing it, and I decided to try building the fix myself.

The request was practical: let a Helm-source Application say, "do not cache the chart." That matters in dev loops. It also matters with OCI Helm registries where charts can be updated in-place without a version bump. If the chart content changes but the version string does not, the cache becomes the enemy. And like most good feature requests, it sounded easy before I actually touched the code, which is how software lures us into the cave.

The standard OSS move is simple enough: clone the repo, follow the contributor guide, and get to the code path behind the feature request. The hard part is that mature cloud-native projects accumulate local-dev sediment: a Makefile layer here, a `hack` script there, a Procfile, a Kind cluster, Tilt, Kubernetes patches, UI dependencies, Corepack shims, generated assets, and one guide linking to another guide linking to a note that assumes you already ran the thing from the previous guide. None of those pieces is irrational. Each one exists because someone solved a real problem at a real moment.

The problem is what happens after years of real moments: you do not get a clean contributor loop, you get a pilgrimage. Argo CD is a mature CNCF project with serious maintainers, real documentation, real developer workflows, and a codebase that has earned every bit of its operational complexity. This is not a dunk on Argo CD. I like Argo CD. That is why the local loop matters: the sooner a contributor gets from "I cloned the repo" to "I am stepping through the code path I care about," the sooner the project benefits from their attention.

This is the part of open source we under-talk about. We measure time-to-first-issue, time-to-merge, review latency, CI health, and coverage. Those are all useful. But there is another metric hiding underneath them: how long does it take a motivated contributor to reach the first useful breakpoint?

Today, the answer for this branch changed from a theory to an observed loop: I pressed **F5** in VS Code, the Aspire AppHost started the Argo CD topology, and a breakpoint in Go code was hit.

That is the product. Not the dashboard screenshot. Not the fluent API. Not the architecture diagram I can draw to feel clever. The product is the moment a contributor can stop setting up the world and start understanding the code.

## The first F5 failed for exactly the right reason

The most interesting discovery was not that the graph had a missing edge or that Kubernetes had an opinion. The most interesting discovery was a timeout.

On the first F5 attempt, most of the Go components showed `Finished` in the Aspire dashboard. The logs had this sequence:

```text
[sys] Timeout of 120 seconds exceeded waiting for the IDE to start a run session;
      you can set the DCP_IDE_REQUEST_TIMEOUT_SECONDS environment variable to override this
      Put "https://localhost:62985/run_session?api-version=2025-10-01": context deadline exceeded
[sys] Starting process...: Cmd = go.exe, Args = ["--loglevel", "debug", "--port", "8081", ...]
flag provided but not defined: -loglevel
```

Then Go printed its usage banner and exited, which is Go's way of saying, "I have no idea what ceremony you thought was happening, but this is not it."

The cause was subtle and very real. `dlv debug` does not use the same build-cache entry as a normal `go build`. It compiles with:

```text
-gcflags="all=-N -l"
```

That disables optimizations and inlining so the debugger can do its job. It also means that a repo with a warm normal build can still face a cold debug build.

Measured on this machine:

- `go build ./cmd`, warm: **114 seconds**
- `go build -gcflags="all=-N -l" ./cmd`, cold: **463 seconds**
- DCP's default IDE request timeout: **120 seconds**

Aspire was waiting for the IDE to start the run session. The Go debug build was still compiling. DCP gave up after two minutes and fell back to launching the executable directly. But without the IDE debug run session, it did not get the Delve `run ./cmd` shape. The process received only the application's flags, saw `--loglevel`, and died because the `go` command itself does not have that flag.

That is a perfect example of the kind of problem you only learn by running the loop. The build was clean. The tests were green. The graph looked plausible. The actual contributor experience still had a two-minute assumption hidden inside it.

The fix is now one line in the repo, inside `.vscode/launch.json`:

```jsonc
{
  "name": "Debug Aspire AppHost",
  "type": "aspire",
  "request": "launch",
  "program": "${workspaceFolder}/contrib/aspire-dev/ArgoCd.Aspire.AppHost/ArgoCd.Aspire.AppHost.csproj",
  "dashboardBrowser": "openExternalBrowser",
  "env": {
    "DCP_IDE_REQUEST_TIMEOUT_SECONDS": "900"
  }
}
```

That is the series argument arriving without asking permission. The fix is not a paragraph that says, "If debugging times out, set this environment variable." It is not a tribal note in a setup guide. It is a checked-in launch configuration. The next contributor clones, installs the recommended extensions, presses F5, and inherits the extra time budget.

It is also an honest limitation. Aspire's default assumes debug builds start quickly. That is a reasonable default for many applications. A Go monorepo the size of Argo CD breaks that assumption, especially on the first debug build. The right answer is not to pretend the default was silly; the right answer is to make this repo's reality executable.

The other small but lovely setting is:

```jsonc
"dashboardBrowser": "openExternalBrowser"
```

That makes F5 open the Aspire dashboard automatically. If you prefer a different shape, the setting also supports `none`, `notification`, `integratedBrowser`, and `debugChrome` / `debugEdge` / `debugFirefox`. The debug-browser options are nice for web apps because they auto-close when debugging ends. For this loop, I want the dashboard to feel like part of pressing F5, not like a URL I copied from a terminal while pretending that counts as polish.

## What the loop actually runs

Quick refresher, especially if this is where you are starting: Aspire is a code-first, polyglot orchestrator for distributed apps. The center is an AppHost — a small program, in C#, TypeScript, JavaScript, and other supported shapes — that describes your app as a resource graph. Containers, processes, cloud resources, dependencies, endpoints, health, and startup ordering live together. When you run it, Aspire starts the graph and gives you a dashboard with logs, state, health, traces, and resource actions. The shortest version lives at [aspire.dev](https://aspire.dev): compose, debug, and deploy distributed applications from code.

For cloud-native inner loops, the missing piece is often the cluster, and that is where `CommunityToolkit.Aspire.Hosting.Kind` comes in. It gives the AppHost a real local Kubernetes cluster as a first-class Aspire resource instead of a paragraph in a README that says, "Before you start, create a cluster and apply these things."

The Argo CD topology I wanted is deliberately split:

- Kind holds Kubernetes state: CRDs and `argocd-cm`.
- Redis runs as a container resource.
- The UI runs as a host process and serves HTTP 200 on port 4000.
- The Go control-plane components run as host processes.
- `api-server` answers HTTP 200 on `/api/version`.
- The cluster does **not** run the Argo CD Deployments in this loop.

That last point matters. The cluster is real, but it is state-only for the inner loop. It provides the Kubernetes API, CRDs, ConfigMaps, Secrets, and state texture the controllers need. The code I want to edit runs on my machine, close to the debugger.

The actual cluster wiring in this branch is intentionally small. The AppHost derives a per-checkout cluster name, renders the Argo CD state manifest, then creates a persistent Kind cluster and applies that generated manifest:

```csharp
var kindClusterName = ArgoCdClusterName.Resolve(repoRoot);
var stateManifestPath = ArgoCdManifestSet.RenderStateOnlyManifest(
    Path.Combine(AppContext.BaseDirectory, "generated", "argocd-state.yaml"),
    enableDex);

var cluster = builder
    .AddKindCluster(kindClusterName)
    .WithClusterLifetime(ClusterLifetime.Persistent)
    .WithManifest(stateManifestPath);

cluster
    .WithRepoServerOverrideCommand()
    .WithDeleteClusterCommand()
    .WithAdminCredentialCommand();
```

That whole thing is still just a fluent builder: choose the cluster identity, generate the Kubernetes state that Argo CD needs, create the cluster, apply the manifest, and attach contributor commands, all in typed C# under a debugger and in the same program that describes the rest of the local system. Not bash. Not Terraform. Not a README ritual with three "important" notes that only become important after you miss one.

The killer method in that snippet is `WithManifest(stateManifestPath)`.

In the earlier version of this experiment, applying Kubernetes state after cluster creation required a bespoke Aspire lifecycle hook. The hook listened for the Kind cluster to become ready, ran `kubectl apply`, updated resource properties, toggled health state, and carried enough ceremony that I had a little state singleton sitting in the middle of the AppHost like a tiny bureaucrat with a clipboard.

It worked, but it was also a smell, and `WithManifest` removes that entire custom bootstrap hook. When the cluster is ready, it applies the manifest. Health reflects the result. Downstream resources that call `.WaitFor(cluster)` unblock only after the cluster is ready for them. No custom bootstrap code. No state singleton. No health-check ping-pong. No "remember to run this first" paragraph trying to cosplay as a dependency graph.

This branch still carries a small local extension because the package version I am using does not yet include the manifest API I need. The upstream work is [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481). The important bit for this post is modest: `WithServerSideApply` exists in that PR precisely because real CRDs make ordinary `kubectl apply` run into limits.

## The CRD was too big for client-side apply

The manifest apply failed outright with this:

```text
kubectl apply failed (exit 1): The CustomResourceDefinition "applicationsets.argoproj.io" is invalid:
metadata.annotations: Too long: may not be more than 262144 bytes
```

Client-side `kubectl apply` writes the whole resource into the `kubectl.kubernetes.io/last-applied-configuration` annotation. That is convenient until the resource is a very large CRD. Argo CD's ApplicationSet CRD crosses the 256 KB annotation ceiling, so the state manifest could not be applied that way.

The fix is server-side apply:

```csharp
[
    "apply",
    "--server-side",
    "--force-conflicts",
    "-f",
    manifestPath,
    "--kubeconfig",
    kubeconfigPath
]
```

This is where a toolkit API stops being aesthetic and starts being practical. `WithServerSideApply` in [CommunityToolkit/Aspire#1481](https://github.com/CommunityToolkit/Aspire/pull/1481) exists for exactly this class of problem. Not because every sample needs it. Because the minute you point a local topology at a serious Kubernetes project, you meet the same limits maintainers already know from production-grade manifests.

Again, the interesting part is where the fix lives. The next person should not need to read a blog post that says, "Oh, by the way, Argo CD's ApplicationSet CRD is too large for client-side apply." The AppHost should know. The graph should carry the right apply mode.

## Startup order is part of the topology

The next failure was more ordinary, which does not make it less useful.

`api-server` waited on Redis and `repo-server`, but it did not wait on the cluster. That meant it could start while the Kind cluster was still provisioning and while the state manifest had not finished applying. The error was exactly what you would expect once you see the missing edge:

```text
configmap "argocd-cm" not found
```

Then `api-server` exited with status 20.

The fix was to add `.WaitFor(cluster)` in `WithKindEnvironment(...)`, covering every component that reads Kubernetes configuration. `commit-server` is correctly excluded because it never talks to Kubernetes.

There was one more small wiring issue in the same neighborhood: namespace. The local processes run in `default`, while part of the state was being applied elsewhere. That mismatch is the sort of thing a README can warn about forever and a graph can simply model correctly.

I do not want to overdramatize this. Startup ordering bugs happen. Namespace mismatches happen. The point is that the remedy belongs in the resource graph, not in a note that says, "If this fails, wait a bit and try again." A `.WaitFor(cluster)` edge is not glamorous, but it is exactly the kind of unglamorous platform work that makes a contributor loop feel reliable.

## Green is not the same as running

This was the most sobering observation from the day: the build was clean, 87 tests passed, and the dashboard could show `api-server` as `Running / Healthy` on a port with nothing actually bound to it.

That is not an indictment of tests or dashboards. It is a reminder that a model is not the same thing as the loop. You can have the right graph shape and still miss the timeout that only appears when Delve builds a cold debug binary. You can have green checks and still discover that the CRD is too large for client-side apply. You can have a resource look healthy until the first real HTTP probe tells you whether anything is listening.

After the fixes, the observed state is the one I care about:

- All seven Go control-plane components run as host processes and show `Running` / `Healthy`.
- The UI serves HTTP 200 on `:4000`.
- `api-server` answers HTTP 200 on `/api/version`.
- The Kind cluster holds state only: CRDs and `argocd-cm`, not Argo CD Deployments.
- The build is clean, with 87 tests passing.
- F5 in VS Code hits a Go breakpoint.

That is the earned claim. Nothing more mystical than that, and nothing less important.

The AppHost does not make Argo CD simple. Good. Argo CD is not simple. The AppHost makes the local topology visible enough that the next failure has a place to go. A timeout becomes `DCP_IDE_REQUEST_TIMEOUT_SECONDS` in launch config. A CRD apply limit becomes server-side apply in the manifest resource. A startup race becomes `.WaitFor(cluster)`. A namespace mismatch becomes environment wiring.

That is the difference between documenting a workaround and giving the workaround a home.

## The practical friction drawer

One tiny practical note, because local development is still local development: every `dlv debug` run leaves a `__debug_bin*.exe` next to the package being debugged. In this repo, each one is roughly 190 MB. A few F5 sessions accumulated about 1.87 GB in the working tree.

That is now covered by `.gitignore`. Not a grand architectural point. Just the kind of thing worth fixing once so everyone else does not wonder why their checkout gained the mass of a small moon.

## The contribution shape

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

The dashboard commands are where this stops being a pretty graph and starts feeling like contributor tooling. The Kind cluster resource wires commands directly in `AppHost.cs`: show admin credentials, delete the Kind cluster cleanly, and rebuild `repo-server` from the current source override. Those are exactly the kinds of buttons serious projects eventually grow: seed data, rotate a secret, force a resync, rebuild the one component you are actually editing.

The happy path is now the thing a contributor should see first:

```powershell
git clone https://github.com/tamirdresher/argo-cd
cd argo-cd
git switch aspire-dev-loop
code .
```

VS Code prompts for the recommended extensions because the repo includes `.vscode/extensions.json`, and the important ones for this loop are `microsoft-aspire.aspire-vscode` and `golang.go`. If the launch entry ever disappears, you do not have to hand-type JSON: press **Ctrl+Shift+P**, run **Aspire: Configure launch.json**, and let the extension write the AppHost entry. In the current checkout, `.vscode/launch.json` already points at `contrib/aspire-dev/ArgoCd.Aspire.AppHost/ArgoCd.Aspire.AppHost.csproj`, sets the longer DCP timeout, opens the dashboard, and gives the contributor the F5 path.

One clone. No path wiring. No script whose main job is to go fetch the real project from somewhere else. The command-line path still exists for automation and constrained machines, but it is no longer the ceremony at the front door.

## The thesis, now with a breakpoint

Here is the careful version of the disruption claim: Aspire does not replace Kubernetes, and that is not the interesting sentence. I do not want a local orchestrator pretending production does not exist. I do not want to hide the cluster from platform engineers. The cluster is the thing. Kubernetes is still where the CRDs live, where the API server enforces reality, where controllers observe state, and where production texture matters.

The interesting sentence is this: Aspire makes Kubernetes' outside modellable in code. By "outside" I mean all the things around the cluster that every serious cloud-native project needs before a contributor can do useful work: the local cluster, the manifests, the sidecars, the supporting containers, the host processes, the UI, the dependency ordering, the ports, the health checks, the generated state, the commands, the little readiness rituals, and the "please run this before that" knowledge that slowly migrates into documentation because documentation is where pain goes when we have not modeled it yet.

The setup doc is the smell, even though a good README is still important. I love a good README. But if the README is carrying topology, lifecycle, dependency ordering, health verification, and environment-specific caveats, then the README is doing work that belongs in a program.

The same rule applies one layer below the AppHost. VS Code's [workspace recommended extensions](https://code.visualstudio.com/docs/configure/extensions/extension-marketplace#_workspace-recommended-extensions) move "install the Aspire and Go extensions" out of prose and into `.vscode/extensions.json`, so newcomers get prompted by the editor instead of punished by a missed paragraph. A [dev container](https://containers.dev/) can take that further: the SDK, Go toolchain, Kind, `kubectl`, Delve, Node, `pnpm`, and extensions can all be described in [`devcontainer.json`](https://containers.dev/implementors/json_reference/) and built for the contributor, locally or in [Codespaces](https://docs.github.com/en/codespaces/overview). The setup guide stops being a document people follow and becomes a file the machine follows.

An executable AppHost is better than a paragraph that says "first create a Kind cluster." A fluent builder call is better than a shell snippet that applies a manifest and hopes everyone remembers when it should happen. A `.WaitFor(cluster)` edge is better than "wait until the cluster is ready" as tribal instruction. A launch setting checked into the repo is better than a troubleshooting note that only helps after the first failed F5.

That is why `WithManifest` is more than a convenience method. It is the archetype. It says the install-configure-verify sequence belongs in the resource model. Server-side apply says the resource model must carry the boring Kubernetes realities too. `WithPortMapping`, `WithWorkerNodes`, and `WithKubernetesVersion` are the same kind of API when a project needs them. Each one moves a piece of local platform ceremony out of prose and into code.

And once it is code, it can be debugged. It can be reviewed. It can be reused. Most importantly, it can be inherited by the next contributor without them having to rediscover why the guide has a warning box in paragraph eleven.

The Kind integration is not Argo-CD-specific. Any project with Kubernetes state plus host processes can benefit from the same shape. Operators. Controllers. CLIs that talk to the API server. UIs that expect services to exist. Test harnesses that need a real cluster but do not need every edit to become a container image.

The pattern is: keep real state real, run editable code close to the debugger, and let the AppHost model the topology between them.

That is not a .NET-only idea either. Aspire's AppHost can be TypeScript or JavaScript. The C# examples exist because that ecosystem got the first wave of docs and integrations, but the concept is not "platform engineers must become .NET developers." Platform engineers who live in JS or TS should be able to model local topology in the language they already use. Again: [aspire.dev](https://aspire.dev) is the place to track the current language and integration story.

The deeper point is onboarding, because every minute a contributor spends fighting local setup is a minute they are not spending understanding the code. Maintainers should care about that. Not as a kindness, although kindness is underrated. They should care because setup friction selects against contribution. It punishes the people who are motivated enough to help but not yet steeped in the project's accumulated rituals.

A debugger-first AppHost is not just nicer; it is a maintenance strategy. It makes the local topology visible. It makes assumptions executable. It makes prerequisites fail fast. It makes "what is running?" answerable from a dashboard instead of five terminals. It turns "follow the guide carefully" into "run the graph and let the graph tell you what is missing."

That is the disruption I mean. No keynote thunder. No "replace your platform" sticker. No pretending Kubernetes got simple because I wrote a fluent API around Kind. Just a quiet shift where a whole category of pain becomes optional.

The healthier loop is the one where a contributor hits a gap, runs the real system, discovers the missing edge or timeout or apply mode, fixes it in the repo, and leaves a better path behind.

Next time, I want the loop to look like this:

```powershell
git clone https://github.com/tamirdresher/argo-cd
cd argo-cd
git switch aspire-dev-loop
code .
```

Then VS Code recommends the extensions, **F5** starts the AppHost, the dashboard opens, and the contributor gets the graph, logs, project-specific commands, and a real Go breakpoint.

That is days into minutes, but more importantly it is the onboarding fix living inside the project that needs it. That is the part I have been waiting for.
