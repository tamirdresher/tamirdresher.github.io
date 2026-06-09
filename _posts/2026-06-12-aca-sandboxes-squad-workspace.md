---
layout: post
title: "Part 3 — Giving the Agent a Workshop: Squad Workspaces in Azure Container Apps Sandboxes"
date: 2026-06-12
tags: [ai-agents, squad, azure-container-apps, sandboxes, langgraph, sandbox, security, architecture]
series: "Scaling AI-Native Software Engineering"
series_part: 21
image: /assets/aca-sandboxes-squad-workspace/hero.png
---


In [Part 1], I put Squad inside a deterministic LangGraph workflow. In [Part 2], I moved risky tool execution into Azure Container Apps Dynamic Sessions.

That gave me a clean rule: the app owns the workflow, the graph owns the state transitions, and risky execution happens somewhere isolated instead of inside the process that is making decisions.

But then I hit the next problem.

**What happens when the agent needs a real workspace?**

Not one command. Not one tool call. A workspace. A repo checkout. A build cache. Logs. Generated artifacts. A place where the agent can stop, wait for me, and continue tomorrow without rebuilding the universe from scratch.

You *can* recreate all of that on every turn. You can also eat soup with a fork. It builds character. I do not recommend it.

So Part 3 is about the next piece of the architecture:

**Use ACA Sandboxes as persistent, isolated workspaces for agent tasks that need continuity across tool calls, checkpoints, and human review.**

---

## The Control Plane and the Tool Plane

The app from the previous posts does not go away.

The LangGraph/Squad app is still the **control plane**. It decides what should happen next, records state, routes work, pauses for human input, and decides whether an artifact is good enough to move the graph forward.

The sandbox is the **workspace/tool plane**. It is where files live, commands run, dependencies get installed, and proof artifacts are produced.

That distinction matters because I do not want the agent's brain and the agent's workshop to be the same thing.

```text
LangGraph / Squad app
        |
        | decide next step, choose approved command
        v
ACA Sandbox workspace
        |
        | run command, update files, produce artifact
        v
proof artifact
        |
        | attach result back to graph state
        v
next node, human review, or cleanup
```

The graph should be able to say: "Run the approved analysis command in this workspace, bring me back the artifact, and tell me exactly what happened."

Not "here is a shell, good luck."

That is the pattern I liked in the implementation framing Tamir pointed me to: deterministic workflow plus a sandbox validation loop. The code runs before the artifact is shown, and the workflow only advances based on something we can inspect. I am not using that as Azure product documentation; I am using it as a useful engineering shape.

---

## Dynamic Sessions vs. Sandboxes

Azure Container Apps has two similarly named primitives that I do not want to blur together.

**Dynamic Sessions** are managed, ephemeral execution environments behind a session pool. They are great when I need gloves: run one bounded action, return one artifact, clean up.

**[ACA Sandboxes](https://learn.microsoft.com/en-us/azure/container-apps/sandboxes-overview)** are first-class preview sandbox resources under `Microsoft.App/SandboxGroups`. They are a better fit when I need a desk. Or a workshop.

Dynamic Sessions ask:

> Where can I safely run this one risky thing?

Sandboxes ask:

> Where can this agent have an isolated workspace that survives long enough to be useful?

For a real Squad workflow, that second question matters. An agent fixing a bug may need to clone a repo, install dependencies, reproduce a failing test, generate a review file, pause for human review, and resume from the same directory after I reply. Even a short-lived validation run starts leaning toward Sandboxes once it needs a real filesystem and multiple command phases like restore, build, test, smoke-run, score, and refine.

The sandbox is not the brain. It is the workbench. The durable decision state still belongs in the app, graph, issue, PR, or repo. The sandbox preserves operational continuity: files, caches, outputs, logs, and artifacts.

---

## The Overall Flow

Here is the boring version of the workflow I want.

```text
1. Create a sandbox group.
2. Add a sandbox-group credential.
3. Create or choose a disk image with the tools I need.
4. Create a sandbox from that image with explicit egress rules.
5. Run only allowlisted commands.
6. Export the proof artifact back to graph state.
7. Suspend, snapshot, or delete the sandbox.
```

Boring is good. Boring survives contact with calendars.

There are a few important details hiding inside that list.

The sandbox group is the administrative boundary. The credential belongs to the group, not to my laptop. The disk image contains tools, not my browser profile. The sandbox gets egress intentionally, not accidentally. The agent gets a command catalog, not arbitrary shell. The artifact comes back to the graph as evidence, not vibes.

That last part is important enough to name plainly: **proof artifacts**. The command log, the manifest, the generated review file, and the cleanup result. Basically: what can I prove happened?

---

## Credentials: The Part That Needs to Be Boring on Purpose

This is the part that needs to be boring on purpose.

A credential, in this context, is a token or provider connection the sandbox can use to authenticate to an external service. For this post, the interesting provider is GitHub Copilot. If I want a Copilot-backed Squad command to run inside the sandbox, the sandbox needs a way to authenticate.

The wrong way is to copy my host machine's token store, `gh` profile, browser cookies, or local credential cache into the sandbox. That would make the demo easier and the architecture worse.

The right shape is a **sandbox-group credential**:

- it is configured on the sandbox group;
- it can be shared by sandboxes in that group;
- it is injected into the sandbox through the platform path;
- it can be rotated or removed without baking secrets into a disk image;
- it keeps the custom disk focused on tools, not identity.

The Sandboxes UI is at <https://sandboxes.azure.com/>. Once you open your sandbox group, the path is:

```text
Sandbox group > Credentials > Provider Tokens > GitHub Copilot > Set Token
```

![Blurred ACA Sandboxes Credentials page showing Provider Tokens for GitHub Copilot and Claude](/assets/aca-sandboxes-squad-workspace/aca-sandboxes-credentials-ui-blurred.png)

That screenshot is from the real Sandboxes UI, with account and sandbox group details blurred. The important product point is still visible: provider tokens are attached to the sandbox group, and sandboxes in that group can use them without baking credentials into the disk image.

The UI is not required, though. For this architecture, I want the setup to be boring and scriptable.

First, bootstrap the group with the preview `aca` CLI. This is not `az containerapp`; Sandboxes use the separate `aca` command surface.

```bash
# Install once, then authenticate only when needed.
curl -fsSL https://aka.ms/aca-cli-install | sh
az account show -o none || az login
aca auth status || aca auth login

aca sandboxgroup create \
  --name <SANDBOX_GROUP> \
  --location <REGION> \
  --set-config

aca doctor
```

`aca sandboxgroup create` auto-assigns the caller the `Container Apps SandboxGroup Data Owner` role unless you opt out with `--skip-role-check`. For another principal, assign it explicitly:

```bash
aca sandboxgroup role create \
  --group <SANDBOX_GROUP> \
  --role "Container Apps SandboxGroup Data Owner" \
  --principal-id <PRINCIPAL_OBJECT_ID>
```

There is no YAML file to apply for this credential in the current flow. The earlier YAML-shaped sketch was conceptual; it was not a real manifest. The credential is a sandbox-group resource you create through the UI or the preview `aca` CLI. This is where the token value is set: in the UI, you paste it into the GitHub Copilot provider token field; in the CLI, `aca sandboxgroup credential create` stores it on the sandbox group and returns a credential id.

```bash
# Safer local flow: omit --token and let the CLI prompt for the value.
GITHUB_COPILOT_CREDENTIAL_ID=$(aca sandboxgroup credential create \
  --group <SANDBOX_GROUP> \
  --type github-copilot \
  -o json | jq -r .id)

aca sandboxgroup credential list \
  --group <SANDBOX_GROUP> \
  -o json

aca sandboxgroup credential delete \
  --group <SANDBOX_GROUP> \
  --id "$GITHUB_COPILOT_CREDENTIAL_ID" \
  --yes
```

For CI, use your secret store to provide the token to that command; do not hard-code it in source, `.env`, screenshots, or logs. The current preview credential types exposed by the CLI are `github-copilot` and `anthropic-claude`. For GitHub Copilot, the CLI validates a fine-grained GitHub PAT prefix (`github_pat_...`) and rejects classic `ghp_...` tokens. Use a disposable, tightly scoped token and rotate it. If it ships, it ships reliably.

The sandbox create path is also scriptable. The public disk path uses `--disk`; private or committed disks use `--disk-id`; credentials are attached by id; egress starts with a default action plus host allow rules. These flags are preview surface, so I would re-check `aca sandbox create --help` and `aca sandbox egress set --help` before automating them in CI.

```bash
aca sandbox create \
  --group <SANDBOX_GROUP> \
  --disk copilot \
  --credential "$GITHUB_COPILOT_CREDENTIAL_ID" \
  --egress-default Deny \
  --egress-rule "github.com:Allow" \
  --egress-rule "api.github.com:Allow" \
  --egress-rule "*.githubcopilot.com:Allow" \
  -o json

aca sandbox create \
  --group <SANDBOX_GROUP> \
  --disk-id <PRIVATE_OR_COMMITTED_DISK_ID> \
  --credential "$GITHUB_COPILOT_CREDENTIAL_ID" \
  --egress-default Deny \
  --egress-rule "github.com:Allow" \
  --egress-rule "api.github.com:Allow" \
  --egress-rule "*.githubcopilot.com:Allow" \
  -o json
```

For a sandbox that already exists, the same egress policy can be set or inspected without recreating the sandbox:

```bash
# Current aca preview build used in this validation:
aca sandbox egress set \
  --id <SANDBOX_ID> \
  --default Deny \
  --rule "github.com:Allow" \
  --rule "api.github.com:Allow" \
  --rule "*.githubcopilot.com:Allow" \
  --traffic-inspection Full

# If your aca build exposes --host-allow instead, use the equivalent form:
aca sandbox egress set \
  --id <SANDBOX_ID> \
  --default Deny \
  --host-allow "github.com" \
  --host-allow "api.github.com" \
  --host-allow "*.githubcopilot.com" \
  --traffic-inspection Full

aca sandbox egress show --id <SANDBOX_ID>
```

The important detail is the handoff: the credential id is passed to `aca sandbox create --credential`. That is how the sandbox gets access to the provider token. The token is not in the disk image, not in the repo, and not copied from my host profile.

For ARM/Bicep, I am drawing a hard line: Bicep can create the sandbox group control-plane resource, but I am not inventing Bicep children for provider credentials or individual runtime sandboxes. The published ARM template reference I could verify exposes `Microsoft.ContainerInstance/sandboxGroups@2026-06-01-preview`; the Sandboxes preview material and `aca` command surface also refer to the ACA sandbox group as `Microsoft.App/SandboxGroups`. In practice, validate the provider namespace registered for your preview subscription and keep runtime operations on the supported preview CLI/SDK/data plane.

The public Bicep shape is group-level only:

```bicep
param location string = resourceGroup().location
param sandboxGroupName string
param sandboxSubnetId string

resource sandboxGroup 'Microsoft.ContainerInstance/sandboxGroups@2026-06-01-preview' = {
  name: sandboxGroupName
  location: location
  properties: {
    networkProfile: {
      subnets: [
        {
          id: sandboxSubnetId
        }
      ]
    }
  }
}
```

So the clean no-UI split is:

```text
ARM/Bicep:
  create the sandbox group boundary, network profile, identity/tags where supported

aca CLI / SDK / data plane:
  create/list/delete credentials
  create sandboxes from disks or snapshots
  attach credentials
  set egress policy
  exec, shell, files, ports, lifecycle, snapshot, cleanup
```

For my custom disk path, the sample still expects the future prompt proof to use `COPILOT_GITHUB_TOKEN` inside the sandbox, but only after I verify the exact credential-injection behavior for the custom disk and wire delete-after-run cleanup. Until then, prompt-level proof stays fail-closed.

---

## Gates Before Commands

Before showing the command catalog, I need one more piece: gates.

`SandboxGates` is the set of switches that prevents the demo from quietly becoming more powerful than I intended. Creating infrastructure, deleting resources, requiring egress verification, or running an authenticated Copilot prompt should all be explicit choices.

```python
@dataclass(frozen=True)
class SandboxGates:
    allow_create: bool
    delete_after_run: bool
    require_verified_egress: bool
    allow_copilot_prompt: bool
```

The point is not the dataclass. The point is the policy.

If `allow_create` is false, the sample should attach to an existing workspace instead of creating new infrastructure. If `delete_after_run` is false, cleanup should not pretend it deleted things. If `require_verified_egress` is true, the run should fail unless the egress allowlist was checked. And if `allow_copilot_prompt` is false, the authenticated Copilot/Squad proof command should not run.

Then comes `COMMANDS`.

`COMMANDS: dict[str, CommandSpec]` is the allowlist. It is the difference between "the agent can run a shell" and "the coordinator can request one of these known operations."

```python
COMMANDS: dict[str, CommandSpec] = {
    "prepare_workspace": CommandSpec(
        argv=["python", "-m", "demo.prepare"],
        writes=["/workspace/manifest.json"],
    ),
    "analyze_workspace": CommandSpec(
        argv=["python", "-m", "demo.analyze"],
        reads=["/workspace/manifest.json"],
        writes=["/workspace/review.md"],
    ),
    "read_artifact": CommandSpec(
        argv=["python", "-m", "demo.read_artifact"],
        reads=["/workspace/review.md"],
    ),
    "copilot_squad_proof": CommandSpec(
        argv=["python", "-m", "demo.copilot_squad_proof"],
        requires=[
            "COPILOT_GITHUB_TOKEN",
            "delete_after_run",
            "verified_egress_allowlist",
        ],
    ),
}
```

The last command is the interesting one. It represents the future proof I actually want: run a real Copilot-backed Squad prompt inside the sandbox, using a sandbox-group credential, with egress verified and cleanup enforced.

But the command being present in the allowlist is not the same as the proof being complete.

---

## What We Can Prove Right Now

Here is the honest state of the implementation.

The local workspace path works. The package compiles, tests pass, and the local demo produces a deterministic review artifact.

The live Azure sandbox path works for the bounded demo commands. A disposable sandbox was created, default-deny egress was used, the approved workspace commands ran, a snapshot path was exercised, suspend-at-end was used, and cleanup removed the disposable resources.

The custom disk/toolchain path works without secrets. The proof artifact says the sandbox could run help/version checks for `git`, `gh`, Node, npm, GitHub Copilot CLI, and Squad.

![Blurred ACA Sandboxes sandbox detail page showing a running sandbox, terminal, network audit, and resource cards](/assets/aca-sandboxes-squad-workspace/aca-sandbox-detail-running-blurred.png)

This is the real sandbox detail view, redacted. It shows the pieces engineers actually need to understand: lifecycle state, terminal access, network audit, resource usage, disk image, and the surrounding sandbox group navigation.

What I cannot claim yet is the thing Tamir correctly pushed on:

```text
Proved so far:
  workspace lifecycle
  default-deny sandbox path
  allowlisted demo commands
  custom disk/toolchain inspection
  proof artifact export
  cleanup of disposable resources

Current implementation gap:
  authenticated Copilot-backed Squad prompt inside the sandbox

Next engineering gate for prompt-level proof:
  credential-backed prompt using the sandbox-group credential path,
  delete-after-run enabled,
  verified egress allowlist,
  and confirmation from the infrastructure/code reviewers that it actually ran
```

That is less flashy than "Copilot ran in the sandbox."

It is also the version I can defend.

So my recommendation is simple: keep the claim narrow until the authenticated Copilot/Squad proof runs for real. The architecture is useful now; the final proof still has one gate left.

---

## Cleanup Is Part of the Feature

Persistent workspaces are useful because they preserve state. That also makes cleanup part of the design, not an afterthought.

For a Squad sandbox workflow, I want the cleanup contract to be explicit:

```yaml
cleanup:
  export:
    - sanitized-command-log
    - manifest-hash
    - approved-artifacts
  redact:
    - resource-paths
    - sandbox-identifiers
    - snapshot-identifiers
    - account-details
  afterRun:
    - delete-disposable-snapshots
    - suspend-or-delete-disposable-sandbox
    - verify-no-unapproved-resources-remain
```

If I cannot explain why a workspace still exists, it should not still exist.

---

## Sample Walkthrough

The companion sample is here:

<https://github.com/tamirdresher/squad-aca-sandboxes-workspace>

The important implementation details are concrete. I validated the workspace as a working companion implementation, not just as a diagram with aspirations and a nice haircut.

---

## Where Dynamic Sessions Still Win

This is not "Sandboxes are better, forget Dynamic Sessions." That would be wrong.

Dynamic Sessions still feel like the right primitive when the work is short-lived, the result is one structured artifact, and I do not want state preserved after the tool call.

Use the gloves when the task is one risky action.

Use the workshop when the task needs a place to live.

The mistake is pretending they solve the same problem because both have the word "sandbox" nearby.

---

## The Point

Part 1 made Squad deterministic enough to reason about.

Part 2 made tool execution isolated enough to trust for short-lived actions.

Part 3 is about making agent workspaces persistent enough to review, resume, and govern.

```text
deterministic workflow
        +
isolated risky execution
        +
persistent isolated workspace
        =
agent work I can inspect, resume, and prove
```

That is the story I want this post to tell.

But the final proof matters. Until a real Copilot-backed Squad prompt runs inside the sandbox through the sandbox-group credential path, the honest claim is workspace plus toolchain validation, not full Copilot-backed Squad execution.

Agents do not just need brains. They need places to work. And if we give them a workshop, I want it to have a door, a lock, an allowlist, a cleanup policy, and a very boring manifest that tells me exactly what happened.

---

## Sources

- [Azure Container Apps Sandboxes overview](https://learn.microsoft.com/en-us/azure/container-apps/sandboxes-overview)
- [Introducing Azure Container Apps Sandboxes: Secure Infrastructure for Agentic Workloads](https://techcommunity.microsoft.com/blog/appsonazureblog/introducing-azure-container-apps-sandboxes-secure-infrastructure-for-agentic-wor/4524131)
- [Azure Container Apps Sandboxes CLI preview](https://github.com/microsoft/azure-container-apps/tree/main/aca-cli/preview)
- [ACA Sandboxes CLI reference skill](https://github.com/microsoft/azure-container-apps/blob/main/plugin/skills/aca-sandboxes/SKILL.md)
- [ARM template reference: `Microsoft.ContainerInstance/sandboxGroups@2026-06-01-preview`](https://learn.microsoft.com/azure/templates/microsoft.containerinstance/2026-06-01-preview/sandboxgroups)
- [Dynamic sessions in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/sessions)
- Companion sample workspace: <https://github.com/tamirdresher/squad-aca-sandboxes-workspace>, validated live for the bounded demo path, including local validation, live sandbox lifecycle, toolchain checks, and cleanup.
- A sanitized proof artifact accompanies the post at `/assets/aca-sandboxes-squad-workspace/live-validation-evidence.md`.

[Part 1]: /blog/2026/06/10/deterministic-langgraph-non-deterministic-squad
[Part 2]: /blog/2026/06/12/aca-dynamic-sessions-squad
