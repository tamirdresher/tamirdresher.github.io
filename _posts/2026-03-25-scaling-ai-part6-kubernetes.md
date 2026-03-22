---
layout: post
title: "Assimilating the Cloud — Running Your AI Squad on Kubernetes"
date: 2026-03-25
tags: [ai-agents, squad, github-copilot, kubernetes, aks, keda, helm, docker, devops, star-trek, borg]
series: "Scaling AI-Native Software Engineering"
series_part: 6
---

![Assimilating the Cloud — Running Your AI Squad on Kubernetes](/assets/scaling-ai-part6-kubernetes/hero.png)

> *"You will be assimilated. Your biological and technological distinctiveness will be added to our own."*
> — The Borg Collective, Star Trek: The Next Generation

In [Part 3](/blog/2026/03/15/scaling-ai-part3-streams), I showed you how my Squad became a distributed system spanning a laptop, a DevBox, and an Azure VM — all coordinated through git-based task queues and heartbeat files. In [Part 4](/blog/2026/03/17/scaling-ai-part4-distributed), I showed you what happened when that system broke spectacularly. Thirty-seven consecutive Ralph failures. Auth races. Lock files that lied. Three hours of an AI team spinning in the void.

Both of those posts ended the same way: duct tape. A clever fix, a new edge case handled, and a vague sense that we were building the wrong thing.

This post is about admitting that.

---

## The 3am Realization

It was 3am on a Tuesday. Not because I was working — I was asleep. Ralph was supposed to be working. Ralph was not working.

I picked up my phone to check Teams and saw the notification stack:

```
⚠️ Ralph Watch Alert — 8 consecutive failures
⚠️ Ralph Watch Alert — 16 consecutive failures
⚠️ Ralph Watch Alert — 24 consecutive failures
```

Somewhere around failure twelve, my laptop had gone to sleep. `ralph-watch.ps1` runs in a terminal window. Terminal windows do not run when laptops sleep. This is not a bug. This is physics.

I had a fix for this, of course. A script called `keep-devbox-alive.ps1`. It moved the mouse cursor by one pixel every four minutes to prevent the screensaver from kicking in. I'm not proud of it. The file header says:

```powershell
# Keep-DevBox-Alive v2
# Moves mouse 1px to prevent sleep/screensaver
# Yes, this is exactly as dumb as it sounds.
# TODO: replace with something that isn't a crime against engineering
```

The TODO was six weeks old. Ralph had missed eight hours of work because I forgot to run the mouse-wiggler. Somewhere in the queue, issues had piled up unprocessed. PRs waited for review. Ralph, the tireless member of my team, had been out cold since midnight.

I lay there in the dark thinking: *I have built an AI team and given them a habitat that goes to sleep.*

---

## What We Actually Built (Before Admitting It)

In Parts 3 and 4, I called it a "distributed system." That was generous.

What we actually built was this: Ralph runs as a terminal process. When the laptop stays awake, Ralph works. When the laptop sleeps, Ralph dies. When I'm on a DevBox in the cloud, Ralph runs there instead — which means we have two potential Ralphs, and they need a mutex file in git to not stomp on each other. The mutex lives in `.squad/ralph.lock`. We update it every five minutes. When a machine dies hard (power cut, Azure maintenance), the lock file goes stale, and the other Ralph has to decide whether to steal the lock or wait.

I had also written a heartbeat file (`ralph-heartbeat.json`), a circuit breaker (after five consecutive failures, back off exponentially), and a watchdog script that emails me if Ralph misses three heartbeats.

Sound familiar? We independently re-implemented:

- **Leader election** (the mutex fight)
- **Health checks** (the heartbeat file)
- **Failure detection** (the watchdog)
- **Exponential backoff** (the circuit breaker)
- **Persistent state** (`.ralph-state.json` written to disk)

We built half of Kubernetes. Badly. Without the fourteen years of lessons that went into Kubernetes.

The realization wasn't painful. It was actually kind of funny. I had reinvented distributed systems coordination using PowerShell and git commits, and the result was a system that died when a laptop went to sleep. The Borg would be embarrassed.

---

## The Migration Mental Model

Before writing a single YAML file, I sat down and mapped every Squad concept to a Kubernetes primitive. This mapping is the whole migration:

| Local Squad | Kubernetes Equivalent |
|---|---|
| `ralph-watch.ps1` (running in terminal) | **CronJob** — scheduled, managed, auto-restarted |
| `ralph.lock` mutex file in git | **Lease** — K8s built-in leader election |
| Heartbeat JSON file | **Liveness probe** — K8s checks it for us |
| `keep-devbox-alive.ps1` | **Gone.** K8s nodes don't sleep. |
| `.ralph-state.json` on disk | **PersistentVolume** — survives pod restarts |
| Config in `.squad/*.md` | **ConfigMap** — mounted as files |
| GitHub tokens, PATs | **Secret** — encrypted at rest |
| "Run on DevBox or laptop" | **Deployment** — run wherever K8s schedules it |
| Circuit breaker logic | **restartPolicy: OnFailure** — K8s does this |

The `keep-devbox-alive.ps1` row is my favorite. The entire reason that file exists — the reason I was staring at failure notifications at 3am — disappears entirely. Kubernetes nodes do not go to sleep. Pods do not have screensavers. The mouse-wiggling script becomes dead code the moment the container starts.

That's worth the migration price by itself.

---

## The Architecture Decision: One Pod Per Agent

Before writing the Dockerfile, we had a genuine design argument. Two options:

**Option A: Sidecar model.** Ralph runs as the main container. When Ralph decides to dispatch Seven or B'Elanna, it spawns them as sidecar containers in the same pod. Single pod, shared filesystem, easy communication.

**Option B: Pod-per-agent.** Each agent gets its own pod. Ralph runs as a CronJob. When Ralph dispatches Seven, it creates a new pod (or KEDA scales one up). Separate lifecycle, separate resources, separate failure domains.

We chose Option B. The reasoning is documented in [ADR-002](https://github.com/tamirdresher/tamresearch1/issues/994) and it boils down to this: the sidecar model is the "distributed monolith" trap. When Seven OOMs on a large document, she takes Ralph down with her. When B'Elanna's Terraform apply hangs for 20 minutes, Ralph can't process anything else. The whole point of moving to K8s was to get independent failure domains. Sharing a pod defeats that.

Pod-per-agent also means each agent gets its own resource limits, its own scheduling constraints, and its own node affinity. Ralph needs 256Mi and a burstable CPU. Seven processing a 200-page research corpus needs 4Gi and real compute. Putting them in the same pod means one of them is over-provisioned and the other is under-provisioned. There's no good middle ground.

The tradeoff: inter-agent communication is now network calls instead of filesystem reads. We accepted that. MCP over localhost is fast enough for agent coordination that happens at human timescales.

---

## The Dockerfile

The Squad container needs four things: Node.js (to run the GitHub Copilot CLI), PowerShell 7+ (to run `ralph-watch.ps1`), `git` (to interact with the repo), and `gh` (to authenticate and create PRs).

Here's the Dockerfile we landed on after a few iterations. The first attempt used `mcr.microsoft.com/dotnet/aspnet:8.0` as the base and came in at **2.1 GB** — we didn't need the .NET runtime at all. This is the final version, based on `ubuntu:22.04`:

```dockerfile
FROM ubuntu:22.04

# Install PowerShell 7
RUN apt-get update && apt-get install -y wget apt-transport-https software-properties-common \
    && wget -q "https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb" \
    && dpkg -i packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y powershell git curl jq

# Install Node.js 20 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
    dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
    tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh

# Install GitHub Copilot CLI extension
RUN gh extension install github/gh-copilot || true

WORKDIR /squad

# Copy squad scripts
COPY ralph-watch.ps1 .
COPY .squad/ ./.squad/

# Ralph runs as non-root
RUN useradd -ms /bin/bash ralphuser
USER ralphuser

CMD ["pwsh", "-NoProfile", "-File", "/squad/ralph-watch.ps1"]
```

The image comes in at **890 MB** — still large, but acceptable for something that runs as a long-lived workload and isn't in the hot path of an API request.

A fully stripped Alpine-based build is theoretically possible, but PowerShell on Alpine is... a journey I'm not ready to take yet. The TODO is in a comment. It has company.

---

## The Helm Chart

We package the whole Squad deployment as a Helm chart (living at `infrastructure/helm/squad-agents/` in the repo). Here's the `values.yaml` with annotations explaining the intent behind each value:

```yaml
# values.yaml — Squad Agent Helm Chart

# Which agents to run (Ralph is always on; others are optional)
agents:
  ralph:
    enabled: true
    # Ralph runs on a schedule. "*/5 * * * *" = every 5 minutes.
    # K8s CronJob handles the scheduling; no more ralph-watch loop.
    schedule: "*/5 * * * *"
    # Keep last 3 successful and 1 failed job for debugging
    successfulJobsHistoryLimit: 3
    failedJobsHistoryLimit: 1

# Container image settings
image:
  repository: your-registry.azurecr.io/squad
  tag: "latest"
  pullPolicy: IfNotPresent

# Persistent storage for Ralph's state file
# This is what keeps Ralph's memory across pod restarts
persistence:
  enabled: true
  storageClass: "managed-premium"
  size: 1Gi
  mountPath: /squad/state

# ConfigMap-mounted Squad configuration
# Your .squad/ directory becomes a ConfigMap
config:
  # Path to decisions.md in the container
  decisionsPath: /squad/config/decisions.md

# Secrets — mounted via Azure Key Vault CSI driver
# Never put values in values.yaml; these are references only
secrets:
  # GitHub PAT with repo + issues + PRs scope
  githubTokenSecret: squad-github-token
  # GitHub Copilot CLI auth token
  copilotTokenSecret: squad-copilot-token
  # Key Vault CSI provider syncs secrets from Azure Key Vault
  # into K8s Secrets automatically — no manual rotation needed
  keyVaultName: squad-keyvault

# Resource limits — Ralph is chatty but not compute-heavy
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"

# Which namespace to deploy into
namespace: squad-agents

# Teams webhook for notifications (optional but strongly recommended)
notifications:
  teamsWebhook:
    secretName: squad-teams-webhook
    key: url
```

The key template is the CronJob for Ralph. Here's the abbreviated `templates/ralph-cronjob.yaml`:

{% raw %}
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: {{ include "squad.fullname" . }}-ralph
  namespace: {{ .Values.namespace }}
spec:
  schedule: {{ .Values.agents.ralph.schedule | quote }}
  concurrencyPolicy: Forbid   # No two Ralphs at once — built in, not a lock file
  successfulJobsHistoryLimit: {{ .Values.agents.ralph.successfulJobsHistoryLimit }}
  failedJobsHistoryLimit: {{ .Values.agents.ralph.failedJobsHistoryLimit }}
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure  # K8s retries; we removed our circuit breaker
          containers:
          - name: ralph
            image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
            command: ["pwsh", "-NoProfile", "-File", "/squad/ralph-watch.ps1"]
            env:
            - name: GH_TOKEN
              valueFrom:
                secretKeyRef:
                  name: {{ .Values.secrets.githubTokenSecret }}
                  key: token
            - name: RALPH_STATE_DIR
              value: {{ .Values.persistence.mountPath }}
            volumeMounts:
            - name: squad-state
              mountPath: {{ .Values.persistence.mountPath }}
            - name: squad-config
              mountPath: /squad/config
              readOnly: true
            livenessProbe:
              exec:
                command:
                - cat
                - /squad/state/ralph-heartbeat.json
              initialDelaySeconds: 30
              periodSeconds: 60
          volumes:
          - name: squad-state
            persistentVolumeClaim:
              claimName: {{ include "squad.fullname" . }}-state
          - name: squad-config
            configMap:
              name: {{ include "squad.fullname" . }}-config
```
{% endraw %}

`concurrencyPolicy: Forbid` is the line that eliminates the entire mutex-in-git saga. The CronJob scheduler guarantees that if a previous Ralph job is still running when the next schedule fires, the new job simply doesn't start. No lock file. No git commit races. No stale locks from crashed machines. One line of YAML does what three hundred lines of PowerShell did before.

I stared at that line for a while.

---

## What Broke (The Good Stuff)

### Auth Was Not What I Expected

The first deployment failed immediately. Ralph couldn't authenticate to GitHub. The error was cryptic: `gh auth token: error getting credentials`. The full debugging saga is in [#998](https://github.com/tamirdresher/tamresearch1/issues/998).

The problem: `gh` stores credentials in the OS keyring or in `~/.config/gh/`. In a container, neither exists by default. Our `GH_CONFIG_DIR` env var pointing to `%APPDATA%\GitHub CLI` — totally sensible on Windows — means nothing in a Linux container.

Fix: Mount the GitHub token as an environment variable (`GH_TOKEN`) and configure `gh` to use it:

```powershell
# In ralph-watch.ps1, after the K8s auth fix
$env:GH_CONFIG_DIR = "/tmp/gh-config"
New-Item -ItemType Directory -Force $env:GH_CONFIG_DIR | Out-Null
# gh picks up GH_TOKEN automatically — no keyring needed
```

This took three hours to debug. I kept staring at the pod logs thinking it was a permissions issue. It was not a permissions issue. It was Windows muscle memory in a Linux world.

### The Heartbeat File Was Lying

The liveness probe checks for `/squad/state/ralph-heartbeat.json`. Ralph writes this file at the start of every run. The problem: the file persisted from the *previous* pod across a PersistentVolume. When the new pod started, K8s saw the heartbeat file immediately (it was already there) and marked the pod healthy before Ralph had actually started.

Fix: Ralph now writes a heartbeat file with a timestamp and the pod ID. The liveness probe doesn't just check file existence — it checks that the timestamp is within the last ten minutes:

```powershell
$heartbeat = @{
    timestamp = (Get-Date -Format "o")
    podName   = $env:POD_NAME ?? "local"
    round     = $roundNumber
    status    = "running"
} | ConvertTo-Json
Set-Content -Path "$env:RALPH_STATE_DIR/ralph-heartbeat.json" -Value $heartbeat
```

Now the liveness probe script checks the timestamp. Stale files from previous pods fail the check, which triggers a restart. Which is exactly what we want.

### Container Image Pulls Take Forever

The 890 MB image takes about 90 seconds to pull on first deployment. For a CronJob that fires every 5 minutes, that's unacceptable — the pod would spend 30% of its scheduled window just pulling the image.

Fix: `pullPolicy: IfNotPresent`. The image stays cached on the node. First pull is slow. Every subsequent run is instant. This is the obvious answer that I somehow didn't set for the first week of testing.

### Debugging Is Different

On my laptop, when Ralph fails, I have a terminal window with full output and color-coded PowerShell error messages. In K8s, I have:

```bash
kubectl logs -n squad-agents -l app=ralph --previous
```

The `--previous` flag was the discovery that saved me multiple times. It shows logs from the *last crashed container* — the one that's already gone. Without it, you're debugging ghosts.

I also learned to love `kubectl describe job` for CronJob failures. The events section tells you exactly why K8s killed your pod, which is usually a resource limit or an OOM kill, not the application error you're actually debugging. Layers upon layers.

---

## What Works Now

Ralph has been running on K8s for three weeks. Here's the tally:

- **Zero** instances of "Ralph stopped because the laptop slept"
- **Zero** stale lock file incidents
- **One** failed run due to a GitHub API rate limit (handled gracefully by the circuit breaker — yes, we kept that part)
- **One** pod OOM kill when a particularly large PR diff hit memory limits (fixed by bumping the memory limit to 512Mi)

The `keep-devbox-alive.ps1` script still exists in the repo. I can't quite bring myself to delete it. It's a monument to the engineering journey. A reminder that sometimes the dumbest possible solution is the one you ship, and the right solution is the one you build after you understand the problem.

Ralph's heartbeat is now stable. The squad doesn't sleep.

---

## Scaling to the Backlog: KEDA and the Rate Limit Problem

The CronJob gets Ralph running reliably. But it doesn't solve the *throughput* problem. When Neelix's tech news scan dumps 15 new issues into the queue, or when Picard decomposes a feature into 8 tasks, one Ralph processing one issue every five minutes creates a backlog that takes over an hour to clear.

The answer is [KEDA](https://keda.sh) — the Kubernetes Event-Driven Autoscaler. KEDA scales workloads based on external event sources. GitHub issues are an external event source. The connection is direct ([#1134](https://github.com/tamirdresher/tamresearch1/issues/1134)):

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ralph-scaler
  namespace: squad-agents
spec:
  scaleTargetRef:
    name: ralph
  triggers:
    - type: github-runner
      metadata:
        owner: tamirdresher
        repo: tamresearch1
    - type: metrics-api
      metadata:
        targetValue: "5"
        url: "http://squad-metrics.squad-agents:8080/pending-issues"
  minReplicaCount: 1       # Ralph is never fully scaled to zero
  maxReplicaCount: 5
  pollingInterval: 60
  cooldownPeriod: 300
```

When there's one issue in the queue, one Ralph handles it. When there are twenty, KEDA spins up more. When the queue is empty, everything scales back to one. The issue backlog *is* the demand signal.

But here's where it gets interesting — and where we ended up building something novel.

### The Copilot-Aware Scaler

Traditional autoscalers scale *up* when demand increases. Our scaler needs to scale *down* when we're rate-limited. If five Ralph pods are all hammering the GitHub Copilot API and we hit the rate limit, adding a sixth pod makes things worse, not better. What we need is the reverse: detect rate limiting, reduce concurrency, wait for the budget to refill.

This led to [#1156](https://github.com/tamirdresher/tamresearch1/issues/1156) — a KEDA external scaler that's aware of Copilot's rate limit status. We're calling it `keda-github-copilot-scaler`, and as far as we can tell, it's the first Copilot-aware autoscaler in existence.

The scaling policy uses KEDA's `behavior` block to enforce rate-aware decisions:

```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 120   # Wait 2 min before scaling up again
    policies:
      - type: Pods
        value: 2                      # Add at most 2 pods per scale event
        periodSeconds: 60
  scaleDown:
    stabilizationWindowSeconds: 300   # Wait 5 min before scaling down
    policies:
      - type: Percent
        value: 50                     # Remove at most 50% per scale event
        periodSeconds: 120
```

This gives the rate limiter time to breathe between scale events. No flapping — a burst of 10 new issues doesn't cause 10 pods to spawn simultaneously, burn through the rate limit, and then all fail together. That lesson was painfully learned in [Part 4](/blog/2026/03/17/scaling-ai-part4-distributed).

---

## Capability Routing: The Right Node for the Right Agent

On my laptop, when Ralph sees an issue labeled `needs:gpu`, it checks a local JSON file to see if the machine has a GPU. This works for one machine. It gets awkward across three machines, where each has different capabilities and Ralph instances race to claim issues before checking compatibility.

In Kubernetes, machine capabilities are node labels. We built a DaemonSet ([#999](https://github.com/tamirdresher/tamresearch1/issues/999)) that runs on every node, probes local capabilities, and writes the results as labels via the Kubernetes API:

| Issue `needs:*` Label | K8s Node Label | How It's Set |
|---|---|---|
| `needs:gpu` | `nvidia.com/gpu: "true"` | NVIDIA device plugin (automatic) |
| `needs:browser` | `squad.io/capability-browser: "true"` | Capability DaemonSet |
| `needs:teams-mcp` | `squad.io/capability-teams-mcp: "true"` | Capability DaemonSet |
| `needs:azure-speech` | `squad.io/capability-azure-speech: "true"` | Capability DaemonSet |

When the Squad operator creates an agent pod to handle an issue labeled `needs:gpu`, it injects scheduling constraints automatically. The K8s scheduler finds the right node. No manual capability checking in PowerShell. No race conditions between Ralphs on different machines.

The capability routing framework is in active development — PRs [#1286](https://github.com/tamirdresher/tamresearch1/pull/1286) and [#1290](https://github.com/tamirdresher/tamresearch1/pull/1290) implement the DaemonSet and routing logic respectively.

---

## Where This Goes

K8s as a Squad runtime opens up things that were genuinely impossible before.

**AKS Automatic for production**: We evaluated AKS tier options in [#1136](https://github.com/tamirdresher/tamresearch1/issues/1136) and landed on a clear recommendation. For dev/test, AKS Standard Free tier runs Squad comfortably at ~$55–80/month in compute — cheaper than the electricity for the always-on laptop. For production, AKS Automatic is the play: KEDA is built in (no separate install), node autoprovisioning handles GPU nodes on demand, and the managed control plane cuts operational overhead by roughly 50%. The cost is higher (~$150–200/month), but you're trading ops time for Azure's SLA.

**Multiple squads**: We're planning to run a Squad instance per team, each in its own namespace. Team A's Ralph doesn't share state with Team B's Ralph. But they share the same cluster, same monitoring, same alerting pipeline. The operational cost of "one more squad" approaches zero.

**Cross-squad MCP calls over the network**: Right now, when Picard wants to consult Worf, they're in the same process. On K8s, they can be in different pods — potentially different namespaces — with MCP calls over the cluster network. This unlocks actual agent-to-agent communication across team boundaries. Your Picard can ask my Worf for a security review. In a controlled, auditable, revocable way.

**Proper observability**: The platform my infrastructure team at Microsoft runs gives us Prometheus, Grafana, and distributed tracing out of the box. Ralph's run metrics — duration, exit code, consecutive failures, items processed — feed directly into dashboards that existed before Squad arrived. We didn't have to build any of it.

### What's In Flight

The K8s migration is live, but there's active work happening across several PRs:

- [#1285](https://github.com/tamirdresher/tamresearch1/pull/1285) — KEDA autoscaling implementation
- [#1284](https://github.com/tamirdresher/tamresearch1/pull/1284) — KEDA Copilot metrics collection
- [#1288](https://github.com/tamirdresher/tamresearch1/pull/1288) — Copilot auth infrastructure for K8s
- [#1286](https://github.com/tamirdresher/tamresearch1/pull/1286) — Capability routing framework
- [#1290](https://github.com/tamirdresher/tamresearch1/pull/1290) — Capability discoverer DaemonSet

The Borg metaphor has never felt more apt. We took an organic, duct-tape thing that lived on a laptop and gave it infrastructure. We gave it health checks and scheduling and persistence and secrets management. We gave it a home that doesn't sleep, doesn't crash on Windows Update, and doesn't require a mouse-wiggling script to stay alive.

The squad is on the cloud now.

Resistance was, as always, futile. 🟩⬛

---

*Find me on X/Twitter at [@tamir_dresher](https://twitter.com/tamir_dresher) — I post about AI agents, distributed systems, and the PowerShell scripts I'm not proud of.*

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **Part 0**: [Organized by AI — How Squad Changed My Daily Workflow](/blog/2026/03/10/organized-by-ai)
> - **Part 1**: [From Personal Repo to Work Team — Scaling Squad to Production](/blog/2026/03/11/scaling-ai-part1-first-team)
> - **Part 2**: [The Collective — Organizational Knowledge for AI Teams](/blog/2026/03/12/scaling-ai-part2-collective)
> - **Part 3**: [Unimatrix Zero — Many Teams, One Repo with SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)
> - **Part 4**: [When Eight Ralphs Fight Over One Login](/blog/2026/03/17/scaling-ai-part4-distributed)
> - **Part 5**: [Knowledge is Power — How an AI Squad Learns to Evolve Itself](/blog/2026/03/18/scaling-ai-part5-evolution)
> - **Part 6**: Assimilating the Cloud — Running Your AI Squad on Kubernetes ← You are here
