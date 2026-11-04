import { createHash, randomUUID } from "node:crypto";
import { closeSync, constants, fstatSync, lstatSync, openSync, readFileSync } from "node:fs";
import { link, mkdir, open, rename, unlink } from "node:fs/promises";
import { join } from "node:path";
import { piWebDataDir } from "../../config.js";
import { canonicalizeStoredCwd } from "../workingDirectory.js";
export class AutomaticAdmissionRejected extends Error {
}
export function defaultAutomaticAdmissionDir(env = process.env) {
    return join(piWebDataDir(env), "automatic-admission");
}
function isRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
export function validControlGoalInvocation(text, goal, kind) {
    const invocation = `/poteto-mode ${goal}`;
    if (kind === "wake")
        return text === invocation;
    if (kind !== "recovery" || !text.endsWith(invocation))
        return false;
    const prefix = text.slice(0, -invocation.length);
    return (prefix === "" || prefix.endsWith("\n")) && !prefix.trimStart().startsWith("/");
}
function validControlGoal(value, ref) {
    if (!isRecord(value) || value["version"] !== 1 || value["sessionId"] !== ref.id || value["cwd"] !== canonicalizeStoredCwd(ref.cwd) || !["id", "runId", "text", "potetoGoal"].every((key) => typeof value[key] === "string") || !Number.isSafeInteger(value["sequence"]) || Number(value["sequence"]) < 1 || !["queued", "sending", "ended", "uncertain", "superseded"].includes(String(value["state"])) || value["detail"] !== undefined && typeof value["detail"] !== "string")
        return false;
    if (typeof value["id"] !== "string" || value["id"].trim() === "" || typeof value["runId"] !== "string" || value["runId"].trim() === "" || typeof value["potetoGoal"] !== "string" || value["potetoGoal"].trim() === "")
        return false;
    const automatic = parseAutomaticAdmission(value["automaticAdmission"]);
    return automatic?.sessionId === ref.id && automatic.cwd === canonicalizeStoredCwd(ref.cwd) && typeof value["text"] === "string" && validControlGoalInvocation(value["text"], value["potetoGoal"], automatic.kind);
}
export function parseAutomaticAdmission(value) {
    if (value === undefined)
        return undefined;
    if (!isRecord(value))
        throw new Error("automaticAdmission must be an object");
    const data = value;
    const { sessionId, cwd, generation, kind } = data;
    if (typeof sessionId !== "string" || sessionId.trim() === "" || typeof cwd !== "string" || cwd.trim() === "" || typeof generation !== "string" || generation.trim() === "") {
        throw new Error("automaticAdmission requires exact session, cwd and generation");
    }
    if (kind !== "wake" && kind !== "recovery" && kind !== "resume")
        throw new Error("invalid automatic admission kind");
    return { sessionId, cwd: canonicalizeStoredCwd(cwd), generation, kind };
}
function identity(ref) {
    const cwd = canonicalizeStoredCwd(ref.cwd);
    return { key: JSON.stringify([cwd, ref.id]), cwd };
}
function nodeError(error, code) {
    return error instanceof Error && "code" in error && error.code === code;
}
export class AutomaticAdmissionStore {
    constructor(directory) {
        this.directory = directory;
        this.records = new Map();
        this.operations = new Map();
        this.writing = new Set();
        this.failed = new Set();
        this.denied = new Map();
    }
    snapshot(ref) {
        const { key, cwd } = identity(ref);
        const record = this.read(ref);
        const durable = record !== undefined && this.directory !== undefined && !this.writing.has(key) && !this.failed.has(key);
        return { sessionId: ref.id, cwd, generation: record?.generation ?? "unarmed", allowed: durable && !this.denied.has(key) && record.allowed, durable };
    }
    assertSettled(ref) {
        if (this.operations.has(identity(ref).key))
            throw new AutomaticAdmissionRejected("Receiving control mutation is pending; preserve recovery originals");
    }
    initialize(ref) {
        return this.serial(ref, async () => {
            if (this.read(ref) !== undefined)
                return this.snapshot(ref);
            return this.publish(ref, true);
        });
    }
    initializeIfAbsent(ref) {
        return this.serial(ref, async () => {
            const { key } = identity(ref);
            if (this.directory === undefined)
                throw new AutomaticAdmissionRejected("Durable automatic admission capability is unavailable");
            this.records.delete(key);
            if (this.read(ref) !== undefined)
                return this.snapshot(ref);
            if (this.failed.has(key) || this.denied.has(key))
                throw new AutomaticAdmissionRejected("Initial automatic admission absence is unproven");
            return this.publish(ref, true, true);
        });
    }
    setAllowed(ref, allowed) {
        const { key } = identity(ref);
        const previousDenial = this.denied.get(key);
        if (!allowed)
            this.denied.set(key, Symbol());
        return this.serial(ref, async () => {
            this.read(ref);
            await this.publish(ref, allowed);
            if (allowed && this.denied.get(key) === previousDenial)
                this.denied.delete(key);
            return this.snapshot(ref);
        });
    }
    setAllowedAtGeneration(ref, allowed, generation) {
        const { key } = identity(ref);
        const previousDenial = this.denied.get(key);
        return this.serial(ref, async () => {
            const state = this.snapshot(ref);
            if (!state.durable || !generation || state.generation !== generation)
                throw new AutomaticAdmissionRejected("Conditional control generation is stale or not durable");
            if (!allowed)
                this.denied.set(key, Symbol());
            await this.publish(ref, allowed);
            if (allowed && this.denied.get(key) === previousDenial)
                this.denied.delete(key);
            return this.snapshot(ref);
        });
    }
    pauseAtGeneration(ref, generation) {
        return this.serial(ref, async () => {
            const { key } = identity(ref);
            const state = this.snapshot(ref);
            if (!state.durable || state.generation !== generation)
                throw new AutomaticAdmissionRejected("Retirement checkpoint generation is stale or not durable");
            this.denied.set(key, Symbol());
            return this.publish(ref, false);
        });
    }
    explicitInput(ref) {
        return this.serial(ref, async () => {
            const { key } = identity(ref);
            const allowed = !this.failed.has(key) && !this.denied.has(key) && (this.read(ref)?.allowed ?? false);
            return this.publish(ref, allowed);
        });
    }
    controlGoal(ref) {
        const goal = this.read(ref)?.controlGoal;
        return goal === undefined ? undefined : structuredClone(goal);
    }
    saveControlGoal(ref, goal) {
        return this.serial(ref, async () => {
            this.assertCurrent(ref, goal.automaticAdmission);
            if (!validControlGoal(goal, ref))
                throw new AutomaticAdmissionRejected("Invalid correlated control goal");
            const data = this.read(ref);
            if (data === undefined)
                throw new AutomaticAdmissionRejected("Durable automatic control is unavailable");
            const previous = data.controlGoal;
            if (previous !== undefined) {
                if (previous.id === goal.id) {
                    const intent = (item) => [item.id, item.runId, item.sequence, item.text, item.potetoGoal, item.automaticAdmission];
                    if (JSON.stringify(intent(previous)) !== JSON.stringify(intent(goal)))
                        throw new AutomaticAdmissionRejected("Control goal identity changed intent");
                    return structuredClone(previous);
                }
                if (previous.state === "sending" || previous.state === "uncertain")
                    throw new AutomaticAdmissionRejected("Earlier control goal admission is unresolved; retain the current goal without replay");
                if (previous.automaticAdmission.generation === goal.automaticAdmission.generation && (previous.runId !== goal.runId || goal.sequence <= previous.sequence))
                    throw new AutomaticAdmissionRejected("Older or changed control transport sequence is superseded");
            }
            await this.persist(ref, { ...data, controlGoal: structuredClone(goal) });
            return structuredClone(goal);
        });
    }
    updateControlGoal(ref, id, change) {
        return this.serial(ref, async () => {
            const data = this.read(ref);
            if (data?.controlGoal?.id !== id)
                return undefined;
            if (!this.snapshot(ref).durable)
                throw new AutomaticAdmissionRejected("Control durability is unconfirmed; a goal receipt cannot repair or rearm it");
            const goal = structuredClone(data.controlGoal);
            change(goal);
            if (!validControlGoal(goal, ref))
                throw new Error("Control goal update produced invalid metadata");
            await this.persist(ref, { ...data, controlGoal: goal });
            return structuredClone(goal);
        });
    }
    assertCurrent(ref, request) {
        const state = this.snapshot(ref);
        if (request.sessionId !== state.sessionId || request.cwd !== state.cwd || request.generation !== state.generation || !state.allowed || !state.durable) {
            throw new AutomaticAdmissionRejected("Automatic admission is stale, disabled or not durable");
        }
    }
    async serial(ref, operation) {
        const { key } = identity(ref);
        const previous = this.operations.get(key) ?? Promise.resolve();
        const current = previous.catch(() => undefined).then(operation);
        this.operations.set(key, current);
        try {
            return await current;
        }
        finally {
            if (this.operations.get(key) === current)
                this.operations.delete(key);
        }
    }
    file(ref) {
        if (this.directory === undefined)
            return undefined;
        return join(this.directory, `${createHash("sha256").update(identity(ref).key).digest("hex")}.json`);
    }
    read(ref) {
        const { key, cwd } = identity(ref);
        if (this.records.has(key))
            return this.records.get(key);
        const file = this.file(ref);
        if (file === undefined)
            return undefined;
        let descriptor;
        try {
            if (!lstatSync(file).isFile())
                throw new Error("Automatic admission metadata is not a regular file");
            descriptor = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
            if (!fstatSync(descriptor).isFile())
                throw new Error("Automatic admission metadata is not a regular file");
            const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(descriptor)));
            if (!isRecord(value))
                throw new Error("Invalid automatic admission metadata");
            const data = value;
            if (data["version"] !== 1 || data["sessionId"] !== ref.id || data["cwd"] !== cwd || typeof data["generation"] !== "string" || data["generation"] === "" || typeof data["allowed"] !== "boolean") {
                throw new Error("Invalid automatic admission metadata");
            }
            const goal = data["controlGoal"];
            if (goal !== undefined && !validControlGoal(goal, ref))
                throw new Error("Invalid control goal metadata");
            const record = { version: 1, sessionId: ref.id, cwd, generation: data["generation"], allowed: data["allowed"], ...(goal === undefined ? {} : { controlGoal: goal }) };
            this.records.set(key, record);
            return record;
        }
        catch (error) {
            if (nodeError(error, "ENOENT")) {
                this.records.set(key, undefined);
                return undefined;
            }
            this.failed.add(key);
            throw error;
        }
        finally {
            if (descriptor !== undefined)
                closeSync(descriptor);
        }
    }
    async publish(ref, allowed, ifAbsent = false) {
        const { cwd } = identity(ref);
        const controlGoal = this.read(ref)?.controlGoal;
        const record = { version: 1, sessionId: ref.id, cwd, generation: randomUUID(), allowed, ...(controlGoal === undefined ? {} : { controlGoal }) };
        await this.persist(ref, record, ifAbsent);
        return this.snapshot(ref);
    }
    async persist(ref, record, ifAbsent = false) {
        const { key } = identity(ref);
        this.writing.add(key);
        try {
            const file = this.file(ref);
            if (file !== undefined && this.directory !== undefined) {
                await mkdir(this.directory, { recursive: true, mode: 0o700 });
                const temporary = `${file}.${randomUUID()}.tmp`;
                try {
                    const handle = await open(temporary, "wx", 0o600);
                    try {
                        await handle.writeFile(`${JSON.stringify(record)}\n`, "utf8");
                        await handle.sync();
                    }
                    finally {
                        await handle.close();
                    }
                    if (ifAbsent) {
                        try {
                            await link(temporary, file);
                        }
                        catch (error) {
                            if (!nodeError(error, "EEXIST"))
                                throw error;
                        }
                    }
                    else {
                        await rename(temporary, file);
                    }
                    const directory = await open(this.directory, constants.O_RDONLY | constants.O_DIRECTORY);
                    try {
                        await directory.sync();
                    }
                    finally {
                        await directory.close();
                    }
                    if (ifAbsent) {
                        this.records.delete(key);
                        record = this.read(ref);
                        if (record === undefined)
                            throw new AutomaticAdmissionRejected("Initial automatic admission publication is unconfirmed");
                    }
                }
                finally {
                    await unlink(temporary).catch((error) => { if (!nodeError(error, "ENOENT"))
                        throw error; });
                }
            }
            this.records.set(key, record);
            this.failed.delete(key);
        }
        catch (error) {
            this.failed.add(key);
            throw error;
        }
        finally {
            this.writing.delete(key);
        }
    }
}
//# sourceMappingURL=automaticAdmissionStore.js.map