import { createHash } from "node:crypto";
import { closeSync, constants, fstatSync, fsyncSync, lstatSync, openSync, readFileSync } from "node:fs";
import { cwdPathsEqual } from "../workingDirectory.js";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
function record(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function evidenceValue(raw) {
    try {
        return JSON.parse(raw);
    }
    catch {
        throw new AutomaticAdmissionRejected("Maintenance evidence contains torn or malformed JSONL. Preserve the source and perform backed-up repair; a checkpoint cannot be inferred");
    }
}
export function maintenanceEvidence(file, operation) {
    if (file === undefined || file === "" || !lstatSync(file).isFile())
        throw new Error("Persisted maintenance checkpoint evidence is unavailable");
    const descriptor = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
        const before = fstatSync(descriptor);
        if (!before.isFile())
            throw new Error("Maintenance evidence must be a regular file");
        const text = new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(descriptor));
        const lines = text.match(/[^\n]*\n|[^\n]+$/g) ?? [];
        const header = evidenceValue(lines[0] ?? "null");
        if (!record(header) || header["type"] !== "session" || header["id"] !== operation.sessionId || (typeof header["cwd"] === "string" && !cwdPathsEqual(header["cwd"], operation.cwd)))
            throw new Error("Maintenance evidence has a different native session identity");
        const entries = new Map();
        for (const raw of lines.slice(1)) {
            if (raw.trim() === "")
                continue;
            const value = evidenceValue(raw);
            if (!record(value) || typeof value["id"] !== "string" || entries.has(value["id"]))
                throw new Error("Maintenance evidence contains malformed or duplicate entries");
            const entry = { id: value["id"], parentId: value["parentId"], type: value["type"], customType: value["customType"], data: value["data"] };
            entries.set(entry.id, { entry, raw });
        }
        if (!entries.has(operation.entryId))
            throw new Error("Maintenance checkpoint is not in the persisted native file");
        const markers = [...entries.values()].filter(({ entry }) => entry.customType === "pi-web.maintenance" && record(entry.data) && entry.data["id"] === operation.id && entry.data["sessionId"] === operation.sessionId && entry.data["cwd"] === operation.cwd && entry.data["entryId"] === operation.entryId && entry.data["generation"] === operation.generation);
        const marker = markers[0]?.entry;
        if (marker === undefined)
            throw new Error("Maintenance marker is missing");
        if (markers.length !== 1 || marker.parentId !== operation.entryId || (operation.markerEntryId !== undefined && operation.markerEntryId !== marker.id))
            throw new Error("Maintenance marker is missing, ambiguous or on a different checkpoint");
        const descendsFromMarker = (entry) => {
            const visited = new Set();
            let parent = entry.parentId;
            while (typeof parent === "string" && !visited.has(parent)) {
                if (parent === marker.id)
                    return true;
                visited.add(parent);
                parent = entries.get(parent)?.entry.parentId;
            }
            return false;
        };
        const matches = [...entries.values()].filter(({ entry }) => entry.type === "compaction" && descendsFromMarker(entry) && (operation.compactionEntryId === undefined || operation.compactionEntryId === entry.id));
        if (matches.length > 1)
            throw new Error("More than one compaction could belong to this maintenance operation");
        const compacted = matches[0];
        const after = fstatSync(descriptor);
        if (before.size !== after.size || before.mtimeMs !== after.mtimeMs || before.ctimeMs !== after.ctimeMs)
            throw new Error("Native maintenance evidence changed during observation");
        fsyncSync(descriptor);
        return { markerEntryId: marker.id, ...(compacted === undefined ? {} : { compactionEntryId: compacted.entry.id, compactionSha256: createHash("sha256").update(compacted.raw).digest("hex") }) };
    }
    finally {
        closeSync(descriptor);
    }
}
//# sourceMappingURL=sessionMaintenanceEvidence.js.map