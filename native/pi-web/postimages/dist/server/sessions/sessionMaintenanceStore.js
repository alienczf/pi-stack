import { createHash, randomUUID } from "node:crypto";
import { closeSync, constants, existsSync, fstatSync, fsyncSync, lstatSync, mkdirSync, openSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { piWebDataDir } from "../../config.js";
import { canonicalizeStoredCwd } from "../workingDirectory.js";
import { validFailureRetirement } from "./sessionFailureRetirement.js";
const STATES = new Set(["prepared", "compacting", "complete", "failed", "uncertain", "superseded", "resuming", "resumed"]);
const INPUT_STATES = new Set(["queued", "sending", "admitted", "uncertain", "cancelled"]);
function record(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
function fileVersion(stat) {
    return [stat.dev, stat.ino, stat.mode, stat.size, stat.mtimeNs, stat.ctimeNs].join(":");
}
function directoryVersion(stat) {
    return [stat.dev, stat.ino, stat.mode].join(":");
}
function validOperation(value, ref) {
    if (!record(value) || value["version"] !== 1 || value["sessionId"] !== ref.id || value["cwd"] !== ref.cwd || !Array.isArray(value["inputs"]))
        return false;
    if (!["id", "entryId", "generation", "instructions", "lastInputGeneration", "state"].every((key) => typeof value[key] === "string") || !STATES.has(String(value["state"])) || !Number.isSafeInteger(value["inputSequence"]))
        return false;
    if (value["cancelledByStop"] !== undefined && typeof value["cancelledByStop"] !== "boolean")
        return false;
    if (value["retirement"] !== undefined && !validFailureRetirement(value["retirement"], ref, String(value["id"])))
        return false;
    const resume = value["resume"];
    if (resume !== undefined && (!record(resume) || resume["potetoGoal"] !== undefined && typeof resume["potetoGoal"] !== "string"))
        return false;
    const observation = record(resume) ? resume["observation"] : undefined;
    if (observation !== undefined && (!record(observation) || observation["kind"] !== "assistant-stop" || !["entryId", "sha256", "deliveryId", "compactionEntryId", "userEntryId", "assistantEntryId", "assistantSha256"].every(key => typeof observation[key] === "string" && observation[key] !== "") || observation["deliveryId"] !== resume?.["deliveryId"] || observation["compactionEntryId"] !== value["compactionEntryId"]))
        return false;
    if (record(observation) && observation["userSha256"] !== undefined && (typeof observation["userSha256"] !== "string" || !/^[a-f0-9]{64}$/.test(observation["userSha256"])))
        return false;
    const inputs = value["inputs"];
    return value["inputSequence"] === inputs.length && inputs.every((input, index) => record(input)
        && input["sequence"] === index + 1 && ["id", "text", "generation"].every((key) => typeof input[key] === "string")
        && (input["kind"] === "steer" || input["kind"] === "followUp") && typeof input["echoUserMessage"] === "boolean"
        && (input["potetoGoal"] === undefined || typeof input["potetoGoal"] === "string")
        && INPUT_STATES.has(String(input["state"])) && Array.isArray(input["attachments"]) && Array.isArray(input["images"])
        && input["images"].every((image) => record(image) && image["type"] === "image" && typeof image["data"] === "string" && typeof image["mimeType"] === "string"));
}
export function defaultMaintenanceDir(env = process.env) {
    return join(piWebDataDir(env), "session-maintenance");
}
export class SessionMaintenanceStore {
    constructor(directory) {
        this.directory = directory;
        this.pendingInputs = new Map();
    }
    location(ref) { return this.file(ref); }
    pending(ref) {
        const file = this.file(ref);
        try {
            const version = this.pendingVersion(file);
            if (version === undefined) {
                this.pendingInputs.delete(file);
                return [];
            }
            const cached = this.pendingInputs.get(file);
            if (cached?.version === version)
                return structuredClone(cached.inputs);
            this.pendingInputs.delete(file);
            const data = this.read(ref);
            if (data === undefined || this.pendingVersion(file) !== version)
                throw new Error("Maintenance metadata changed during queued input read");
            const inputs = data.operations[data.current].inputs.filter(input => input.state === "queued");
            this.pendingInputs.set(file, { version, inputs });
            return structuredClone(inputs);
        }
        catch (error) {
            this.pendingInputs.delete(file);
            throw error;
        }
    }
    pendingVersion(file) {
        let directory, descriptor;
        try {
            const pathDirectory = lstatSync(this.directory, { bigint: true });
            if (!pathDirectory.isDirectory() || pathDirectory.isSymbolicLink())
                throw new Error("Maintenance directory must be real and owned");
            directory = openSync(this.directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
            const openedDirectory = fstatSync(directory, { bigint: true });
            if (!openedDirectory.isDirectory() || directoryVersion(openedDirectory) !== directoryVersion(pathDirectory))
                throw new Error("Maintenance directory changed during queued input read");
            if (!lstatSync(file, { bigint: true }).isFile())
                throw new Error("Maintenance metadata is not a regular file");
            descriptor = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
            const opened = fstatSync(descriptor, { bigint: true });
            const path = lstatSync(file, { bigint: true });
            const currentDirectory = lstatSync(this.directory, { bigint: true });
            if (!opened.isFile() || !path.isFile() || fileVersion(opened) !== fileVersion(path) || !currentDirectory.isDirectory() || directoryVersion(openedDirectory) !== directoryVersion(currentDirectory))
                throw new Error("Maintenance metadata changed during queued input read");
            return `${directoryVersion(openedDirectory)}:${fileVersion(opened)}`;
        }
        catch (error) {
            if (error instanceof Error && "code" in error && error.code === "ENOENT")
                return undefined;
            throw error;
        }
        finally {
            if (descriptor !== undefined)
                closeSync(descriptor);
            if (directory !== undefined)
                closeSync(directory);
        }
    }
    current(ref) {
        const data = this.read(ref);
        return data === undefined ? undefined : structuredClone(data.operations[data.current]);
    }
    get(ref, id) {
        const data = this.read(ref);
        return data !== undefined && Object.hasOwn(data.operations, id) ? structuredClone(data.operations[id]) : undefined;
    }
    create(ref, operation) {
        const previous = this.get(ref, operation.id);
        if (previous !== undefined) {
            if (["sessionId", "cwd", "entryId", "generation", "instructions"].some((key) => Reflect.get(previous, key) !== Reflect.get(operation, key)))
                throw new Error("Maintenance identity has changed intent");
            return previous;
        }
        const active = this.current(ref);
        if (active !== undefined && (!(active.state === "resumed" || active.state === "superseded") || active.inputs.some((input) => input.state !== "admitted" && input.state !== "cancelled")))
            throw new Error("Prior maintenance is unresolved; retain its operation and input");
        const data = this.read(ref) ?? { version: 1, sessionId: ref.id, cwd: canonicalizeStoredCwd(ref.cwd), current: operation.id, operations: {} };
        data.current = operation.id;
        data.operations = { ...data.operations, [operation.id]: structuredClone(operation) };
        this.write(ref, data);
        return structuredClone(operation);
    }
    update(ref, id, change) {
        const data = this.read(ref);
        if (data === undefined || !Object.hasOwn(data.operations, id))
            throw new Error("Maintenance operation is unavailable");
        const operation = data.operations[id];
        if (operation === undefined)
            throw new Error("Maintenance operation is unavailable");
        change(operation);
        if (!validOperation(operation, { id: ref.id, cwd: canonicalizeStoredCwd(ref.cwd) }))
            throw new Error("Maintenance update produced invalid operation or input state");
        this.write(ref, data);
        return structuredClone(operation);
    }
    file(ref) {
        return join(this.directory, `${createHash("sha256").update(JSON.stringify([canonicalizeStoredCwd(ref.cwd), ref.id])).digest("hex")}.json`);
    }
    read(ref) {
        const identity = { id: ref.id, cwd: canonicalizeStoredCwd(ref.cwd) };
        const file = this.file(identity);
        try {
            if (!lstatSync(this.directory).isDirectory() || lstatSync(this.directory).isSymbolicLink())
                throw new Error("Maintenance directory must be real and owned");
            lstatSync(file);
        }
        catch (error) {
            if (error instanceof Error && "code" in error && error.code === "ENOENT")
                return undefined;
            throw error;
        }
        let descriptor;
        try {
            if (!lstatSync(file).isFile())
                throw new Error("Maintenance metadata is not a regular file");
            descriptor = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
            if (!fstatSync(descriptor).isFile())
                throw new Error("Maintenance metadata is not a regular file");
            const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(descriptor)));
            if (!record(value) || value["version"] !== 1 || value["sessionId"] !== ref.id || value["cwd"] !== identity.cwd || typeof value["current"] !== "string" || !record(value["operations"]))
                throw new Error("Invalid maintenance metadata identity");
            const rawOperations = value["operations"];
            if (!Object.hasOwn(rawOperations, value["current"]))
                throw new Error("Invalid maintenance current operation");
            const operations = Object.fromEntries(Object.entries(rawOperations).map(([id, operation]) => {
                if (!validOperation(operation, identity) || operation.id !== id)
                    throw new Error("Invalid maintenance operation or input metadata");
                return [id, operation];
            }));
            return { version: 1, sessionId: ref.id, cwd: identity.cwd, current: value["current"], operations };
        }
        finally {
            if (descriptor !== undefined)
                closeSync(descriptor);
        }
    }
    write(ref, data) {
        this.pendingInputs.delete(this.file(ref));
        mkdirSync(this.directory, { recursive: true, mode: 0o700 });
        if (lstatSync(this.directory).isSymbolicLink())
            throw new Error("Maintenance directory must not be symlinked");
        const file = this.file(ref);
        const temporary = `${file}.${randomUUID()}.tmp`;
        try {
            const descriptor = openSync(temporary, "wx", 0o600);
            try {
                writeFileSync(descriptor, `${JSON.stringify(data)}\n`, "utf8");
                fsyncSync(descriptor);
            }
            finally {
                closeSync(descriptor);
            }
            renameSync(temporary, file);
            const directory = openSync(this.directory, constants.O_RDONLY | constants.O_DIRECTORY);
            try {
                fsyncSync(directory);
            }
            finally {
                closeSync(directory);
            }
        }
        finally {
            if (existsSync(temporary))
                unlinkSync(temporary);
        }
    }
}
//# sourceMappingURL=sessionMaintenanceStore.js.map