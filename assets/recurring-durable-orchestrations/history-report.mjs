// Requires Node.js and the preview package:
//   @microsoft/durabletask-js-azuremanaged
//
// Set DURABLE_TASK_SCHEDULER_CONNECTION_STRING through protected environment
// configuration. Populate approvedInstanceIds only after metadata discovery and
// human review. History can contain sensitive input and output payloads.

import { createAzureManagedClient } from "@microsoft/durabletask-js-azuremanaged";

const connectionString = process.env.DURABLE_TASK_SCHEDULER_CONNECTION_STRING;
const approvedInstanceIds = [
    "reviewed-instance-id-1",
    "reviewed-instance-id-2",
];

if (!connectionString) {
    throw new Error("DURABLE_TASK_SCHEDULER_CONNECTION_STRING is required");
}

const client = createAzureManagedClient(connectionString);
const results = [];

try {
    for (const instanceId of approvedInstanceIds) {
        try {
            const state = await client.getOrchestrationState(instanceId, false);
            if (!state) {
                results.push({
                    InstanceId: instanceId,
                    RuntimeStatus: "Missing",
                    ReturnedHistoryEntries: null,
                    Result: "Instance was not found",
                });
                continue;
            }

            const history = await client.getOrchestrationHistory(instanceId);
            results.push({
                InstanceId: instanceId,
                RuntimeStatus: state.runtimeStatus,
                ReturnedHistoryEntries: history.length,
                Result: "OK",
            });
        } catch (error) {
            results.push({
                InstanceId: instanceId,
                RuntimeStatus: "Unknown",
                ReturnedHistoryEntries: null,
                Result: error instanceof Error ? error.message : "Unknown error",
            });
        }
    }
} finally {
    await client.stop();
}

results.sort(
    (left, right) =>
        (right.ReturnedHistoryEntries ?? -1) -
        (left.ReturnedHistoryEntries ?? -1),
);
console.table(results);
