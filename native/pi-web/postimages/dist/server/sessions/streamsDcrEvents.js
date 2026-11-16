import { spawn } from "node:child_process";
import { closeSync, constants, fsyncSync, fstatSync, openSync } from "node:fs";
import { isAbsolute } from "node:path";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
function record(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
function requestFor(session, value) {
    if (!record(value) || typeof value["id"] !== "string" || value["id"].trim() === "" || /[\r\n\0]/.test(value["id"]) || typeof value["index"] !== "string" || !isAbsolute(value["index"]) || typeof value["stream"] !== "string" || !/^[a-z0-9][a-z0-9-]*$/.test(value["stream"]) || typeof value["generation"] !== "string" || value["generation"] === "")
        throw new AutomaticAdmissionRejected("DCR events require their exact operation, absolute index, stream and saved generation");
    return { id: value["id"], index: value["index"], stream: value["stream"], generation: value["generation"], sessionId: session.sessionId, cwd: session.sessionManager.getCwd() };
}
function append(session, request, state) {
    if (session.sessionManager.appendCustomEntry === undefined || session.sessionFile === undefined)
        throw new AutomaticAdmissionRejected("Persisted DCR event capability is unavailable");
    const entryId = session.sessionManager.appendCustomEntry("pi-web.streams-dcr", { ...request, state });
    const descriptor = openSync(session.sessionFile, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
        if (!fstatSync(descriptor).isFile()) throw new Error("DCR event journal is not a regular native file");
        fsyncSync(descriptor);
    }
    finally { closeSync(descriptor); }
    return entryId;
}
export function runStreamsDcrAdvance(request) {
    return new Promise((resolve, reject) => {
        const child = spawn(process.env["PI_STREAMS_BIN"] ?? "pi-streams", ["dcr", "advance", request.stream, "--home", request.index, "--session", request.sessionId, "--operation", request.id], { cwd: request.cwd, stdio: ["ignore", "ignore", "pipe"], timeout: 30000, killSignal: "SIGKILL" });
        let detail = "";
        child.stderr.setEncoding("utf8");
        child.stderr.on("data", value => { detail = (detail + value).slice(-4096); });
        child.once("error", reject);
        child.once("close", code => code === 0 ? resolve() : reject(new Error(detail.trim() || `pi-streams DCR advance exited ${String(code)}`)));
    });
}
export class StreamsDcrEvents {
    constructor(advance, idle, failure) {
        this.advance = advance;
        this.idle = idle;
        this.failure = failure;
        this.watchers = new Map();
        this.needed = new Set();
        this.scheduled = new Set();
        this.advancing = new Set();
    }
    restore(session) {
        let latest;
        for (const entry of session.sessionManager.getBranch()) {
            if (!record(entry) || entry.customType !== "pi-web.streams-dcr" || typeof entry.id !== "string" || !record(entry.data)) continue;
            const data = entry.data;
            if (data.sessionId !== session.sessionId || data.cwd !== session.sessionManager.getCwd()) continue;
            try {
                const request = requestFor(session, data);
                latest = data.state === "active" ? { request, entryId: entry.id } : undefined;
            }
            catch { latest = undefined; }
        }
        if (latest !== undefined) this.watchers.set(session, latest);
    }
    watch(session, value) {
        const request = requestFor(session, value);
        const previous = this.watchers.get(session);
        if (previous !== undefined) {
            if (JSON.stringify(previous.request) !== JSON.stringify(request)) throw new AutomaticAdmissionRejected("Another or changed DCR event operation is already active");
            return { id: request.id, entryId: previous.entryId };
        }
        const prior = session.sessionManager.getBranch().filter(entry => entry.customType === "pi-web.streams-dcr" && entry.data?.id === request.id).at(-1);
        if (prior?.data.state === "closed") throw new AutomaticAdmissionRejected("Closed DCR operation is not replayed");
        const entryId = append(session, request, "active");
        this.watchers.set(session, { request, entryId });
        this.notify(session);
        return { id: request.id, entryId };
    }
    unwatch(session, id) {
        const previous = this.watchers.get(session);
        if (previous === undefined) return { id, entryId: session.sessionManager.getLeafId(), closed: true };
        if (previous.request.id !== id) throw new AutomaticAdmissionRejected("DCR event operation changed before close");
        this.forget(session);
        const entryId = append(session, previous.request, "closed");
        return { id, entryId, closed: true };
    }
    forget(session) { this.watchers.delete(session); this.needed.delete(session); }
    notify(session) {
        if (!this.watchers.has(session)) return;
        this.needed.add(session);
        if (this.scheduled.has(session) || this.advancing.has(session)) return;
        this.scheduled.add(session);
        setImmediate(() => {
            this.scheduled.delete(session);
            const watcher = this.watchers.get(session);
            if (watcher === undefined || !this.needed.has(session) || !this.idle(session)) return;
            this.needed.delete(session);
            this.advancing.add(session);
            void Promise.resolve().then(() => this.advance(watcher.request)).catch(error => {
                this.forget(session);
                try { append(session, watcher.request, "closed"); } catch {}
                try { this.failure(session, error instanceof Error ? error.message : String(error)); } catch {}
            }).finally(() => {
                this.advancing.delete(session);
                if (this.needed.has(session)) this.notify(session);
            });
        });
    }
}
