# Part 3 ACA Sandboxes live validation evidence

This is a sanitized review artifact for the post. It intentionally omits
subscription IDs, resource IDs, sandbox IDs, snapshot IDs, tenant/account details,
and local machine paths.

## Sample

- Sample repo: companion sample
- Validated revision: current sample revision used for the post
- Mode validated: local simulation and live Azure ACA Sandboxes mode

## Local validation

- Editable install: passed
- Unit tests: 14 tests passed
- Compile check: passed for source and tests
- Local demo: passed
- Local commands:
  - `prepare_workspace`: exit `0`
  - `analyze_workspace`: exit `0`
  - `read_artifact`: exit `0`
- Review result: `REVIEW: approved for demo. Artifact is fictional, deterministic, and contains no customer data.`

## Live ACA Sandboxes validation

- Azure mode created a disposable sandbox instead of resuming the existing visible sandbox.
- New sandbox used the default-deny egress path.
- Snapshot creation was enabled and produced only an opaque snapshot token.
- Suspend-at-end was enabled.
- Live commands:
  - `prepare_workspace`: exit `0`
  - `analyze_workspace`: exit `0`
  - `read_artifact`: exit `0`
- Azure review result: `REVIEW: approved for demo. Artifact is fictional, deterministic, and contains no customer data.`

## Custom disk and toolchain validation

- Custom disk/toolchain validation was run without secrets.
- Custom disk label: `sample-node22-gh-copilot-squad-toolchain`
- Custom disk was created from the public Node 22 sandbox path by bootstrapping and saving the sandbox state.
- Local Docker was unavailable for this validation, so no local Docker image build is claimed.
- Validated inside ACA Sandbox:
  - `git 2.39.5`
  - `gh 2.93.0`
  - `node v22.22.2`
  - `npm 10.9.2`
  - `GitHub Copilot CLI 1.0.60`
  - `Squad v0.9.4`
- `copilot --help`: succeeded
- `squad --help`: succeeded
- No authenticated Copilot prompt ran.
- Custom disk and proof sandbox remain available for inspection.

## Publication hygiene

- Sanitized Azure demo output check: passed
- Raw GUID scan: passed
- Raw subscription/resource path scan: passed
- Local temp path scan: passed
- Output used opaque identifiers only

## Security review

- Final security review status: passed with notes
- No credential/API key/token patterns were found in the post, evidence, or tracked sample files.
- No raw Azure subscription/resource paths, GUID-shaped Azure IDs, tenant/account details, sandbox IDs, or snapshot IDs were found in the post or evidence.
- The post avoids claiming ACA Sandboxes are a guaranteed security boundary.
- The post avoids implying arbitrary shell execution is safe.
- The post calls out default-deny egress, fixed command allowlists, snapshot persistence risk, redaction, and cleanup.
- Screenshot guidance remains gated: any future screenshot must get a separate raw-ID/account-detail review.

## Cleanup

- Disposable snapshot: deleted
- Disposable sample sandbox: deleted
- Disposable sample sandboxes left: `0`
- Snapshots left in validation sandbox group: `0`
- Existing non-disposable visible sandbox left intact for manual inspection
