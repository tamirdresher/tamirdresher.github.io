// Requires Node.js and the preview packages:
//   @microsoft/durabletask-js
//   @microsoft/durabletask-js-azuremanaged
//
// Set DURABLE_TASK_SCHEDULER_CONNECTION_STRING through protected environment
// configuration. This example handles one approved instance and one action per
// invocation. Verify the resulting status in a separate read before continuing.

import { OrchestrationStatus } from "@microsoft/durabletask-js";
import { createAzureManagedClient } from "@microsoft/durabletask-js-azuremanaged";

const connectionString = process.env.DURABLE_TASK_SCHEDULER_CONNECTION_STRING;
const [action, instanceId] = process.argv.slice(2);

if (!connectionString) {
    throw new Error("DURABLE_TASK_SCHEDULER_CONNECTION_STRING is required");
}

if (!instanceId || (action !== "suspend" && action !== "resume")) {
    throw new Error("Use: node admin-instance.mjs <suspend|resume> <approved-instance-id>");
}

const client = createAzureManagedClient(connectionString);

try {
    const state = await client.getOrchestrationState(instanceId, false);
    if (!state) {
        throw new Error(`Instance not found: ${instanceId}`);
    }

    if (action === "suspend") {
        if (state.runtimeStatus !== OrchestrationStatus.RUNNING) {
            throw new Error(`Expected Running, observed ${state.runtimeStatus}`);
        }

        await client.suspendOrchestration(
            instanceId,
            "Temporary containment while history growth is investigated",
        );
        console.log("Suspend request sent. Verify Suspended before continuing.");
    } else {
        if (state.runtimeStatus !== OrchestrationStatus.SUSPENDED) {
            throw new Error(`Expected Suspended, observed ${state.runtimeStatus}`);
        }

        await client.resumeOrchestration(instanceId, "Approved staged resume");
        console.log("Resume request sent. Verify the resulting status before continuing.");
    }
} finally {
    await client.stop();
}
