---
layout: post
title: "Part 1: A Kubernetes Operator with a Debugger, Not a Deployment"
date: 2026-07-25T07:15:00+03:00
tags: [dotnet-aspire, platform-engineering, kubernetes, operator, controller-runtime, kind, inner-loop, tutorial]
description: "A followable Aspire tutorial for running a real Kubernetes operator against a real Kind cluster, with the reconciler running as a debuggable host process instead of a deployed pod — and a clean path into the cloud-native inner loop."
---

> **Part 1 of 3.** In Parts 2 and 3 I take this same pattern to a real cloud-native project (argo-cd) and then show the AppHost written in TypeScript instead of C#.

There is a very specific smell in platform engineering: the setup guide that has become the system.

You know the one. It starts friendly. Install these tools. Run this script. Start this cluster. Apply this manifest. If you are on Windows, read the note halfway down the next page. If the UI fails, run this other command. If the controller does not start, maybe you missed a generated file from a guide that linked here from a guide that assumed you already ran the first guide.

At some point you are not debugging the code anymore. You are debugging your eligibility to begin.

I wanted to show the opposite loop.

So in this post we are going to build a minimal Kubernetes operator from scratch. Not a fake one. Not a console app pretending to be a controller. A real `controller-runtime` operator watching a real CRD in a real Kind cluster, creating a real ConfigMap, and updating real Kubernetes status.

Then we are going to run the operator as a host process under Aspire, press F5, set a breakpoint in `Reconcile()`, apply a custom resource, and step through the code.

*That is the whole trick.*

---

## Act 1 — So what does it take to build a Kubernetes operator?

A Kubernetes operator is just a controller with opinions.

That is the least scary definition I know. It watches Kubernetes state, usually through a Custom Resource Definition, and reconciles the world toward the desired state. Someone applies a resource that says, "I want this thing." The operator wakes up and says, "Fine, let me make the rest of Kubernetes look like that."

In production, that pattern is incredibly powerful. In local development, it can become a small ritual.

The traditional path looks familiar if you have spent time in this space: run `kubebuilder init`, generate the API types, generate CRDs, write the reconciler, build an image, create a Kind cluster, load the image into Kind, patch a Deployment, apply RBAC, apply the CRD, tail pod logs, and then attempt to attach a debugger through enough indirection that you begin to envy people who debug CSS.

Kubebuilder is still the standard entry point I would recommend. It gives you the project shape, the markers, the generated files, the manager bootstrap, and all the things that keep you from forgetting one boring-but-important piece.

For this post, though, I wanted the smallest possible operator where every moving part is visible. No generated project maze. No image build. No controller Deployment. Just the parts Kubebuilder would have produced anyway: types, CRD, manager, reconciler.

The example is deliberately unimpressive: a `Greeter` custom resource with a single field, `spec.name`. When you apply a `Greeter`, the operator creates a ConfigMap named `greeting-{name}` in the same namespace. The ConfigMap contains one key:

`message: "Hello, {name}!"`

That is it.

Tiny operators are useful because they do not distract us. If this one is easy to run, observe, and debug, then the same loop applies when the reconciler creates Deployments, Services, certificates, cloud resources, finalizers, webhooks, or whatever else your platform team has lovingly turned into Tuesday.

The important thing is the shape:

```powershell
dotnet restore .\GreeterOperator.slnx
dotnet build .\GreeterOperator.slnx
Set-Location .\operator; go build .\...
```

That is from the repo README. Build the AppHost. Build the Go operator. Then start Aspire.

The cluster stays real. Kubernetes stores the CRD and the custom resources. The operator code does not run inside the cluster during the inner loop. It runs on my machine as an Aspire resource, with `KUBECONFIG` pointed at Kind.

So instead of "change code, build image, load image, redeploy pod, tail logs," the loop becomes:

Open solution. Press F5. Apply resource. Breakpoint hits.

I know. Suspiciously humane.

---

## Act 2 — Build

Here is the complete mental model of the project: `apphost/AppHost.cs` is the Aspire resource graph, `config/greeter-crd.yaml` is the Kubernetes CRD, `examples/greeter-sample.yaml` is the sample custom resource, `operator/api/v1alpha1/greeter_types.go` defines the Go API types, `operator/controllers/greeter_controller.go` is the reconcile loop, `operator/main.go` starts the controller-runtime manager, and `kind-hosting/` holds the reusable Aspire Kind integration.

The actual operator is tiny. The interesting part is not that it took a heroic amount of code. The interesting part is that it did not.

### The API shape

First, the Go types. These are the shape Kubernetes accepts and stores. `Spec` is what the user asks for. `Status` is what the operator reports back after reconciling.

From `operator/api/v1alpha1/greeter_types.go`:

```go
// GreeterSpec describes the greeting to materialize.
type GreeterSpec struct {
	Name string `json:"name"`
}

// GreeterStatus reports the last ConfigMap reconciled for a Greeter.
type GreeterStatus struct {
	ConfigMapName  string      `json:"configMapName,omitempty"`
	Message        string      `json:"message,omitempty"`
	LastReconciled metav1.Time `json:"lastReconciled,omitempty"`
}
```

That is the contract. A Greeter has a name. The controller writes back the ConfigMap name, the generated message, and the last reconcile timestamp.

The group/version is just as small. From `operator/api/v1alpha1/groupversion_info.go`:

```go
var GroupVersion = schema.GroupVersion{Group: "hello.tamirdresher.dev", Version: "v1alpha1"}

var SchemeBuilder = runtime.NewSchemeBuilder(addKnownTypes)

var AddToScheme = SchemeBuilder.AddToScheme

func addKnownTypes(scheme *runtime.Scheme) error {
	scheme.AddKnownTypes(GroupVersion, &Greeter{}, &GreeterList{})
	metav1.AddToGroupVersion(scheme, GroupVersion)
	return nil
}
```

And here is the CRD Kubernetes sees. From `config/greeter-crd.yaml`:

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
            apiVersion:
              type: string
            kind:
              type: string
            metadata:
              type: object
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

Nothing mystical yet. We told Kubernetes there is a new namespaced resource called `Greeter` under `hello.tamirdresher.dev/v1alpha1`, and its spec has one required string.

That is the first operator lesson: the scary part is not the CRD. The CRD is a schema.

The behavior lives in the reconciler.

### The reconcile loop

Here is the whole `Reconcile` method. This is the heart of the post and, honestly, the part I want every platform engineer to stare at for a minute.

From `operator/controllers/greeter_controller.go`:

```go
func (r *GreeterReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx)

	var greeter hellov1alpha1.Greeter
	if err := r.Get(ctx, req.NamespacedName, &greeter); err != nil {
		if apierrors.IsNotFound(err) {
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, err
	}

	configMapName := fmt.Sprintf("greeting-%s", greeter.Spec.Name)
	message := fmt.Sprintf("Hello, %s!", greeter.Spec.Name)

	configMap := &corev1.ConfigMap{
		ObjectMeta: metav1.ObjectMeta{
			Name:      configMapName,
			Namespace: greeter.Namespace,
		},
	}

	operationResult, err := controllerutil.CreateOrUpdate(ctx, r.Client, configMap, func() error {
		if configMap.Data == nil {
			configMap.Data = map[string]string{}
		}
		configMap.Data["message"] = message
		return controllerutil.SetControllerReference(&greeter, configMap, r.Scheme)
	})
	if err != nil {
		return ctrl.Result{}, err
	}

	if operationResult != controllerutil.OperationResultNone || greeter.Status.ConfigMapName != configMapName || greeter.Status.Message != message {
		greeter.Status.ConfigMapName = configMapName
		greeter.Status.Message = message
		greeter.Status.LastReconciled = metav1.Now()
		if err := r.Status().Update(ctx, &greeter); err != nil {
			return ctrl.Result{}, err
		}
		logger.Info("updated greeter status", "configMap", configMapName)
	}

	return ctrl.Result{}, nil
}
```

Read it from top to bottom and the operator becomes much less mysterious.

First, `r.Get(ctx, req.NamespacedName, &greeter)` fetches the custom resource that triggered the reconcile. If it was deleted, Kubernetes returns NotFound, and the controller returns an empty `ctrl.Result{}`. There is nothing to do.

Then the reconciler calculates desired state: ConfigMap name, message text, namespace.

Then `controllerutil.CreateOrUpdate` does the idempotent part. If the ConfigMap does not exist, create it. If it already exists, update the data. Either way, make sure `message` equals the desired greeting.

The owner reference is the tiny line that earns its keep later:

`controllerutil.SetControllerReference(&greeter, configMap, r.Scheme)`

That tells Kubernetes, "this ConfigMap belongs to this Greeter." Delete the Greeter, and Kubernetes garbage collection can clean up the ConfigMap. No separate cleanup job. No haunted orphan resources. Just ownership.

Finally, the reconciler updates status. That is how a user can ask Kubernetes, "what did the operator do?" and see `configMapName`, `message`, and `lastReconciled` on the Greeter itself.

The controller registration is also tiny:

```go
func (r *GreeterReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&hellov1alpha1.Greeter{}).
		Owns(&corev1.ConfigMap{}).
		Complete(r)
}
```

This tells controller-runtime: watch Greeters, own ConfigMaps, call this reconciler.

That is the "oh" moment.

Operators are not magic. They are a loop around `Get`, desired state, `CreateOrUpdate`, owner references, and status.

The hard part is usually not the code. The hard part is the local environment we make people drag around the code.

### The manager bootstrap

The manager is the process that talks to Kubernetes, registers schemes, starts health checks, and runs the controller.

From `operator/main.go`:

```go
package main

import (
	"context"
	"flag"
	"os"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"

	hellov1alpha1 "github.com/tamirdresher/part2-greeter-operator/operator/api/v1alpha1"
	"github.com/tamirdresher/part2-greeter-operator/operator/controllers"
)

var scheme = runtime.NewScheme()

func init() {
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(hellov1alpha1.AddToScheme(scheme))
	utilruntime.Must(corev1.AddToScheme(scheme))
}

func main() {
	var metricsAddr string
	var probeAddr string
	flag.StringVar(&metricsAddr, "metrics-bind-address", "0", "metrics bind address; 0 disables metrics")
	flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "health probe bind address")
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseDevMode(true)))

	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{
		Scheme:                 scheme,
		Metrics:                metricsserver.Options{BindAddress: metricsAddr},
		HealthProbeBindAddress: probeAddr,
	})
	if err != nil {
		ctrl.Log.Error(err, "unable to start manager")
		os.Exit(1)
	}

	if err := (&controllers.GreeterReconciler{
		Client: mgr.GetClient(),
		Scheme: mgr.GetScheme(),
	}).SetupWithManager(mgr); err != nil {
		ctrl.Log.Error(err, "unable to create controller", "controller", "Greeter")
		os.Exit(1)
	}

	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		ctrl.Log.Error(err, "unable to set up health check")
		os.Exit(1)
	}
	if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		ctrl.Log.Error(err, "unable to set up ready check")
		os.Exit(1)
	}

	ctx := ctrl.SetupSignalHandler()
	if deadline, ok := ctx.Deadline(); ok {
		ctrl.Log.Info("starting manager", "deadline", deadline)
	} else {
		ctrl.Log.Info("starting manager", "context", context.Background())
	}

	if err := mgr.Start(ctx); err != nil {
		ctrl.Log.Error(err, "problem running manager")
		os.Exit(1)
	}
}
```

Notice what is not here: no container assumptions. No in-cluster config requirement. `ctrl.GetConfigOrDie()` follows the normal Kubernetes client configuration path, and the Aspire AppHost sets `KUBECONFIG` for the process.

So the operator is a normal Go process. It just happens to be talking to a real Kubernetes API server.

This is where Aspire enters.

### The AppHost money shot

Here is the complete `apphost/AppHost.cs`. This is the part I wanted after Part 1: Kind cluster, CRD bootstrap, Go operator, dependency ordering, and dashboard metadata in one file.

From `apphost/AppHost.cs`:

```csharp
using Aspire.Hosting;
using Aspire.Hosting.ApplicationModel;
using Aspire.Hosting.Eventing;
using Aspire.Hosting.Go;
using Aspire.Hosting.Lifecycle;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Logging;
using System.Diagnostics;

GreeterPrerequisites.ValidateOrThrow();

var builder = DistributedApplication.CreateBuilder(args);
var repoRoot = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
var operatorDir = Path.Combine(repoRoot, "operator");
var kubeconfigDir = Path.Combine(repoRoot, ".kube");
Directory.CreateDirectory(kubeconfigDir);
var kubeconfigPath = Path.Combine(kubeconfigDir, "dev-cluster.yaml");

var cluster = builder
    .AddKindCluster("dev-cluster", clusterName: "dev-cluster", kubeconfigPath: kubeconfigPath)
    .WithPersistentCluster()
    .WithWaitForReady(TimeSpan.FromMinutes(5))
    .WithHealthCheck(GreeterCrdBootstrapState.HealthCheckKey)
    .WithDashboardProperty("greeter.cluster", "dev-cluster")
    .WithDashboardProperty("greeter.kubeconfig", kubeconfigPath)
    .WithDashboardProperty("greeter.crd", "greeters.hello.tamirdresher.dev");

var bootstrapState = new GreeterCrdBootstrapState();
builder.Services.AddSingleton(bootstrapState);
builder.Services
    .AddHealthChecks()
    .AddCheck(GreeterCrdBootstrapState.HealthCheckKey, () => bootstrapState.Succeeded
        ? HealthCheckResult.Healthy("Greeter CRD applied.")
        : bootstrapState.Completed
            ? HealthCheckResult.Unhealthy("Greeter CRD bootstrap failed.")
            : HealthCheckResult.Unhealthy("Greeter CRD bootstrap has not completed yet."));

builder.Services.AddSingleton<IDistributedApplicationEventingSubscriber>(sp =>
    new GreeterCrdBootstrapHook(
        sp.GetRequiredService<ILogger<GreeterCrdBootstrapHook>>(),
        sp.GetRequiredService<ResourceNotificationService>(),
        bootstrapState,
        cluster.Resource,
        Path.Combine(repoRoot, "config", "greeter-crd.yaml")));

builder
    .AddGoApp("greeter-operator", operatorDir, "./main.go")
    .WithEnvironment("KUBECONFIG", kubeconfigPath)
    .WithEnvironment("GOFLAGS", "-mod=mod")
    .WaitFor(cluster);

builder.Build().Run();

internal static class GreeterPrerequisites
{
    public static void ValidateOrThrow()
    {
        var missing = new List<string>();
                var checks = new (string Tool, string[] Arguments)[]
        {
            ("docker", ["--version"]),
            ("kind", ["--version"]),
            ("kubectl", ["version", "--client"]),
            ("go", ["version"]),
        };

        foreach (var (tool, arguments) in checks)
        {
            if (!CanRun(tool, arguments))
            {
                missing.Add(tool);
            }
        }

        if (missing.Count > 0)
        {
            throw new InvalidOperationException(
                "Missing prerequisite(s): " + string.Join(", ", missing) +
                ". Install Docker Desktop, kind, kubectl, and Go, then retry `aspire start`.");
        }
    }

    private static bool CanRun(string fileName, IReadOnlyList<string> arguments)
    {
        try
        {
            using var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = fileName,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                },
            };

            foreach (var argument in arguments)
            {
                process.StartInfo.ArgumentList.Add(argument);
            }

            process.Start();
            return process.WaitForExit(10_000) && process.ExitCode == 0;
        }
        catch
        {
            return false;
        }
    }

}

internal sealed class GreeterCrdBootstrapState
{
    public const string HealthCheckKey = "greeter-crd-bootstrap";

    public bool Completed { get; private set; }
    public bool Succeeded { get; private set; }

    public void MarkCompleted(bool succeeded)
    {
        Completed = true;
        Succeeded = succeeded;
    }
}

internal sealed class GreeterCrdBootstrapHook(
    ILogger<GreeterCrdBootstrapHook> logger,
    ResourceNotificationService notifications,
    GreeterCrdBootstrapState state,
    KindClusterResource cluster,
    string crdPath) : IDistributedApplicationEventingSubscriber
{
    public Task SubscribeAsync(
        IDistributedApplicationEventing eventing,
        DistributedApplicationExecutionContext executionContext,
        CancellationToken cancellationToken)
    {
        eventing.Subscribe<KindClusterReadyEvent>(cluster, OnKindClusterReadyAsync);
        return Task.CompletedTask;
    }

    private async Task OnKindClusterReadyAsync(KindClusterReadyEvent applicationEvent, CancellationToken cancellationToken)
    {
        var succeeded = await ApplyCrdAsync(applicationEvent.Cluster, cancellationToken);
        state.MarkCompleted(succeeded);
    }

    private async Task<bool> ApplyCrdAsync(KindClusterResource cluster, CancellationToken cancellationToken)
    {
        if (!File.Exists(crdPath))
        {
            logger.LogError("CRD manifest not found: {CrdPath}", crdPath);
            return false;
        }

        logger.LogInformation("Applying Greeter CRD from {CrdPath}", crdPath);
        var (exitCode, stdout, stderr) = await RunAsync(
            "kubectl",
            ["apply", "-f", crdPath, "--kubeconfig", cluster.KubeconfigPath],
            cancellationToken);

        var succeeded = exitCode == 0;
        await notifications.PublishUpdateAsync(cluster, snapshot => snapshot with
        {
            Properties =
            [
                .. snapshot.Properties,
                new ResourcePropertySnapshot("greeter.crd.status", succeeded ? "Applied" : $"FAILED: {stderr}"),
            ],
        });

        if (succeeded)
        {
            logger.LogInformation("Greeter CRD applied: {Output}", stdout.Trim());
            return true;
        }

        logger.LogError("kubectl apply failed with exit code {ExitCode}: {Error}", exitCode, stderr);
        return false;
    }

    private static async Task<(int ExitCode, string Stdout, string Stderr)> RunAsync(
        string fileName,
        IReadOnlyList<string> arguments,
        CancellationToken cancellationToken)
    {
        using var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = fileName,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            },
        };

        foreach (var argument in arguments)
        {
            process.StartInfo.ArgumentList.Add(argument);
        }

        process.Start();
        var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);
        return (process.ExitCode, await stdoutTask, await stderrTask);
    }
}
```

This is the part that makes me grin.

`builder.AddKindCluster("dev-cluster")` creates or reuses the local Kind cluster. The AppHost writes a kubeconfig to `.kube/dev-cluster.yaml`, then exposes that path as dashboard metadata so I do not have to go spelunking through folders.

The CRD bootstrap is an Aspire lifecycle hook. Once the Kind resource emits `KindClusterReadyEvent`, the hook runs `kubectl apply -f config/greeter-crd.yaml --kubeconfig ...`. The CRD state becomes a health check, so the cluster resource is not just "running" in the vague sense. It is ready for this operator.

Then this line turns the Go controller into a first-class Aspire resource:

`builder.AddGoApp("greeter-operator", operatorDir, "./main.go")`

That comes from `Aspire.Hosting.Go`. Aspire runs the operator from source, wires environment variables, captures logs, and makes it visible in the dashboard like any other resource.

And then `.WaitFor(cluster)` is doing real work. The operator should not start before the cluster exists and the CRD bootstrap has completed. Instead of encoding that in a README paragraph called "Important: run this first," the dependency lives in the graph.

README paragraphs are fine. Dependency graphs are better at not forgetting.

### The Kind integration is reusable

The `kind-hosting` project is the same generic shape that also powers the larger Argo CD experiment, dropped into this repo as a project reference. The AppHost consumes it through `Aspire.Hosting.Kind.csproj`:

```xml
<ProjectReference Include="..\kind-hosting\Aspire.Hosting.Kind.csproj" IsAspireProjectResource="false" />
```

The extension method is intentionally general. From `kind-hosting/KindClusterBuilderExtensions.cs`:

```csharp
public static IResourceBuilder<KindClusterResource> AddKindCluster(
    this IDistributedApplicationBuilder builder,
    [ResourceName] string name,
    string? clusterName = null,
    string? kubeconfigPath = null)
{
    ArgumentNullException.ThrowIfNull(builder);
    ArgumentException.ThrowIfNullOrEmpty(name);

    var resolvedClusterName = clusterName ?? name;
    var resolvedKubeconfigPath = kubeconfigPath
        ?? Path.Combine(Path.GetTempPath(), $"kind-{resolvedClusterName}-kubeconfig.yaml");

    var resource = new KindClusterResource(name, resolvedClusterName, resolvedKubeconfigPath);
```

So the demo is not "a one-off C# file that shells out to Kind." It is an Aspire hosting integration you can reuse in any AppHost: create a cluster, write kubeconfig, expose commands, wait for readiness, and then let the rest of the graph depend on it.

That is the pattern I care about.

A Kubernetes operator project does not need to choose between fake local tests and full in-cluster deployment for every edit. The cluster can hold state. The host can run code. Aspire can own the topology.

---

## Act 3 — Run it

Start the AppHost from the repo root:

```powershell
aspire start .\apphost\GreeterOperator.AppHost.csproj
kubectl --context kind-dev-cluster apply -f .\examples\greeter-sample.yaml
kubectl --context kind-dev-cluster get configmap greeting-tamir -o yaml
kubectl --context kind-dev-cluster get greeter tamir -o yaml
```

Or open `GreeterOperator.slnx` and press F5.

Here is what happens in the version I tested: prerequisites are validated first, Kind starts or gets reused, the CRD is applied by the lifecycle hook, the Go operator starts as a host process, and the Aspire dashboard shows both the cluster and the operator.

The slow part was not Go. The slow part was Kind doing real cluster work, which is exactly where I want the time to go. The complete validated end-to-end run was 87 seconds from `aspire start` to the first successful reconcile, with all reconciliation checks green.

The sample resource is real Kubernetes YAML. From `examples/greeter-sample.yaml`:

```yaml
apiVersion: hello.tamirdresher.dev/v1alpha1
kind: Greeter
metadata:
  name: tamir
  namespace: default
spec:
  name: tamir
---
apiVersion: hello.tamirdresher.dev/v1alpha1
kind: Greeter
metadata:
  name: torres
  namespace: default
spec:
  name: torres
```

Apply it, and the operator log stream in the Aspire dashboard shows the controller running and updating Greeter status. Then Kubernetes has the ConfigMap:

`kubectl --context kind-dev-cluster get configmap greeting-tamir -o yaml`

That ConfigMap exists in Kind. Not in memory. Not in a mock client. In Kubernetes.

Delete the Greeter, and the ConfigMap disappears because the reconciler set the controller owner reference. That is Kubernetes garbage collection doing the thing Kubernetes is supposed to do.

Now set a breakpoint on `Reconcile()`.

Apply the sample again.

The debugger hits.

This is the moment I wanted. Not "you could theoretically debug this if you had the right launch profile and a sympathetic moon." You are stepping through Go code while it reconciles against a real API server.

The ritual collapsed into a solution file.

That matters more than this toy Greeter. The Greeter is deliberately boring. The workflow is not.

Once this loop exists, you can add the parts real operators need: finalizers, status conditions, multiple CRDs, watches over owned resources, webhooks, metrics, leader election, or integration tests that bring the whole topology up and prove reconciliation end to end.

You can also take an existing operator project and do the same thing over a weekend: keep the CRDs and Kubernetes state in Kind, run the controller as a host process, wire it through Aspire, and make the dashboard the place where contributors see what is happening.

That is the platform-engineering disruption I actually care about. Not a new abstraction for production. A better inner loop for the people maintaining the abstractions everyone else depends on.

The Greeter is deliberately small. That is the point. Small examples make the loop visible.

In Part 2 I take the same pattern to a real cloud-native project — Argo CD — and tell the story of why I ended up building this in the first place.

For now, I am happy with the tiny thing.

A CRD. A reconciler. A Kind cluster. A debugger.

And no image build in the loop.

That is a very good start.



