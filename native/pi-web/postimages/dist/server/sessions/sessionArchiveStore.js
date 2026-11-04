import { randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { access, copyFile, mkdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";
import { piWebDataDir } from "../../config.js";
import { canonicalizeStoredCwd } from "../workingDirectory.js";
import { completeRecoveryArchive } from "./recoveryArchiveCompletion.js";
const archiveQueues = new Map();
export function defaultSessionArchiveFilePath(env = process.env, cwd = process.cwd()) {
    return join(piWebDataDir(env, cwd), "archived-sessions.json");
}
export class SessionArchiveStore {
    constructor(filePath = defaultSessionArchiveFilePath(), archiveDir = join(dirname(filePath), "archived-sessions")) {
        this.filePath = filePath;
        this.archiveDir = archiveDir;
        this.operationQueue = Promise.resolve();
    }
    completeRecoveryOriginal(intent, hooks) {
        return completeRecoveryArchive(this, intent, hooks);
    }
    parseRecoveryRegistry(value) {
        return parseSessionArchiveFile(value);
    }
    async list() {
        return (await this.read()).sessions;
    }
    async get(sessionId) {
        const sessions = (await this.read()).sessions;
        return sessions.find((session) => session.sessionId === sessionId) ?? sessions.find((session) => session.sessionId.startsWith(sessionId));
    }
    async archive(session) {
        const [record] = await this.archiveMany([session]);
        if (record === undefined)
            throw new Error("Archive operation did not produce a record");
        return record;
    }
    async archiveMany(sessions) {
        if (sessions.length === 0)
            return [];
        return this.exclusive(async () => {
            const data = await this.read();
            const records = [];
            const filesToRemove = [];
            for (const session of sessions) {
                const existingIndex = data.sessions.findIndex((record) => record.sessionId === session.sessionId);
                const existing = existingIndex === -1 ? undefined : data.sessions[existingIndex];
                if (existing?.recoveryCompletionId !== undefined)
                    throw new Error("Recovery completion owns this archive; ordinary archive cannot replace it");
                const archivePath = existing?.archivePath ?? this.archivePathFor(session);
                const record = archiveRecordFromInput(session, {
                    archivedAt: existing?.archivedAt ?? new Date().toISOString(),
                    originalPath: existing?.originalPath ?? session.path,
                    archivePath,
                });
                await copySessionFileToArchive(session.path, archivePath);
                if (existingIndex === -1)
                    data.sessions.push(record);
                else
                    data.sessions[existingIndex] = record;
                records.push(record);
                filesToRemove.push({ source: session.path, archivePath });
            }
            await this.write(data);
            for (const file of filesToRemove)
                await removeActiveSessionFile(file.source, file.archivePath);
            return records;
        });
    }
    async restore(sessionId) {
        await this.exclusive(async () => {
            const data = await this.read();
            const record = data.sessions.find((session) => session.sessionId === sessionId);
            if (record === undefined)
                return;
            if (record.recoveryCompletionId !== undefined)
                throw new Error("Recovery completion archives cannot be restored");
            if (record.archivePath !== undefined && record.originalPath !== undefined) {
                await restoreSessionFile(record.archivePath, record.originalPath);
            }
            const sessions = data.sessions.filter((session) => session.sessionId !== sessionId);
            await this.write({ sessions });
        });
    }
    async deleteArchived(sessionId) {
        await this.deleteArchivedMany([sessionId]);
    }
    async deleteRecoveryOriginal(expected, recoveryOperationId, guard) {
        await this.exclusive(async () => {
            const data = await this.read();
            const record = data.sessions.find(item => item.sessionId === expected.sessionId);
            if (record?.recoveryCompletionId !== undefined)
                throw new Error("Recovery completion requires its positive quarantine protocol");
            if (record?.archivePath === undefined || record.recoveryOperationId !== recoveryOperationId || ["sessionId", "cwd", "archivePath", "originalPath", "archivedAt"].some(key => record[key] !== expected[key]))
                throw new Error("Exact recovery archive identity is unavailable");
            if (!await pathExists(record.archivePath))
                throw new Error("Archived original is missing without an owned deletion receipt");
            guard();
            await unlink(record.archivePath);
            await this.write({ sessions: data.sessions.filter(item => item.sessionId !== expected.sessionId) });
        });
    }
    async deleteArchivedMany(sessionIds) {
        const targetIds = uniqueStrings(sessionIds);
        if (targetIds.length === 0)
            return [];
        return this.exclusive(async () => {
            const data = await this.read();
            const targetIdSet = new Set(targetIds);
            const records = data.sessions.filter((session) => targetIdSet.has(session.sessionId));
            if (records.length === 0)
                return [];
            if (records.some(record => record.recoveryCompletionId !== undefined))
                throw new Error("Recovery completion tombstones cannot be removed by ordinary deletion");
            for (const record of records) {
                if (record.archivePath !== undefined && await pathExists(record.archivePath))
                    await unlink(record.archivePath);
            }
            const sessions = data.sessions.filter((session) => !targetIdSet.has(session.sessionId));
            await this.write({ sessions });
            const deletedIds = new Set(records.map((record) => record.sessionId));
            return targetIds.filter((sessionId) => deletedIds.has(sessionId));
        });
    }
    async isArchived(sessionId) {
        return (await this.get(sessionId)) !== undefined;
    }
    archivePathFor(session) {
        const sourceName = basename(session.path);
        const fileName = sourceName === "" ? `${safeFileName(session.sessionId)}.jsonl` : sourceName;
        return join(this.archiveDir, fileName);
    }
    async exclusive(operation) {
        const key = resolve(this.filePath);
        const previous = archiveQueues.get(key) ?? this.operationQueue;
        let release = () => undefined;
        const queued = new Promise((resolve) => { release = resolve; });
        this.operationQueue = queued;
        archiveQueues.set(key, queued);
        await previous.catch(() => undefined);
        try {
            return await operation();
        }
        finally {
            release();
            if (archiveQueues.get(key) === queued) archiveQueues.delete(key);
        }
    }
    async read() {
        try {
            const value = JSON.parse(await readFile(this.filePath, "utf8"));
            return parseSessionArchiveFile(value);
        }
        catch (error) {
            if (isNodeErrorWithCode(error, "ENOENT"))
                return { sessions: [] };
            throw error;
        }
    }
    async write(data) {
        await mkdir(dirname(this.filePath), { recursive: true });
        const tempPath = join(dirname(this.filePath), `.${basename(this.filePath)}.${String(process.pid)}.${Date.now().toString()}.${randomUUID()}.tmp`);
        try {
            await writeFile(tempPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
            await rename(tempPath, this.filePath);
        }
        catch (error) {
            await unlink(tempPath).catch(() => undefined);
            throw error;
        }
    }
}
function archiveRecordFromInput(session, archive) {
    return {
        sessionId: session.sessionId,
        cwd: canonicalizeStoredCwd(session.cwd),
        archivedAt: archive.archivedAt,
        originalPath: archive.originalPath,
        archivePath: archive.archivePath,
        created: session.created,
        modified: session.modified,
        messageCount: session.messageCount,
        firstMessage: session.firstMessage,
        ...(session.name === undefined ? {} : { name: session.name }),
        ...(session.parentSessionPath === undefined ? {} : { parentSessionPath: session.parentSessionPath }),
        ...(session.recoveryOperationId === undefined ? {} : { recoveryOperationId: session.recoveryOperationId }),
    };
}
async function copySessionFileToArchive(source, archivePath) {
    if (source === archivePath)
        return;
    await mkdir(dirname(archivePath), { recursive: true });
    if (await pathExists(archivePath))
        return;
    await copyFile(source, archivePath);
}
async function removeActiveSessionFile(source, archivePath) {
    if (source === archivePath)
        return;
    if (await pathExists(source))
        await unlink(source);
}
async function restoreSessionFile(archivePath, originalPath) {
    if (archivePath === originalPath)
        return;
    if (await pathExists(originalPath))
        throw new Error(`Cannot restore archived session because a session already exists at ${originalPath}`);
    await mkdir(dirname(originalPath), { recursive: true });
    await moveFile(archivePath, originalPath);
}
async function moveFile(source, destination) {
    try {
        await rename(source, destination);
    }
    catch (error) {
        if (!isNodeErrorWithCode(error, "EXDEV"))
            throw error;
        await copyFile(source, destination);
        await unlink(source);
    }
}
async function pathExists(path) {
    try {
        await access(path, constants.F_OK);
        return true;
    }
    catch (error) {
        if (isNodeErrorWithCode(error, "ENOENT"))
            return false;
        throw error;
    }
}
export function parseSessionArchiveFile(value) {
    if (!isRecord(value) || !Array.isArray(value["sessions"]))
        throw new Error("Invalid archive file");
    return { sessions: value["sessions"].map(parseArchivedSessionRecord) };
}
function parseArchivedSessionRecord(value) {
    if (!isRecord(value))
        throw new Error("Invalid archived session record");
    const sessionId = value["sessionId"];
    const cwd = value["cwd"];
    const archivedAt = value["archivedAt"];
    if (typeof sessionId !== "string" || typeof cwd !== "string" || typeof archivedAt !== "string")
        throw new Error("Invalid archived session record");
    const canonicalCwd = canonicalizeStoredCwd(cwd);
    const originalPath = optionalString(value, "originalPath");
    const archivePath = optionalString(value, "archivePath");
    const created = optionalString(value, "created");
    const modified = optionalString(value, "modified");
    const messageCount = optionalNumber(value, "messageCount");
    const firstMessage = optionalString(value, "firstMessage");
    const name = optionalString(value, "name");
    const parentSessionPath = optionalString(value, "parentSessionPath");
    const recoveryOperationId = optionalString(value, "recoveryOperationId");
    const recoveryCompletionId = optionalString(value, "recoveryCompletionId");
    const recoveryDeleted = value["recoveryDeleted"];
    if (recoveryDeleted !== undefined && (recoveryDeleted !== true || recoveryCompletionId === undefined || archivePath !== undefined))
        throw new Error("Invalid recovery completion tombstone");
    return {
        sessionId,
        cwd: canonicalCwd,
        archivedAt,
        ...(originalPath === undefined ? {} : { originalPath }),
        ...(archivePath === undefined ? {} : { archivePath }),
        ...(created === undefined ? {} : { created }),
        ...(modified === undefined ? {} : { modified }),
        ...(messageCount === undefined ? {} : { messageCount }),
        ...(firstMessage === undefined ? {} : { firstMessage }),
        ...(name === undefined ? {} : { name }),
        ...(parentSessionPath === undefined ? {} : { parentSessionPath }),
        ...(recoveryOperationId === undefined ? {} : { recoveryOperationId }),
        ...(recoveryCompletionId === undefined ? {} : { recoveryCompletionId }),
        ...(recoveryDeleted === undefined ? {} : { recoveryDeleted }),
    };
}
function optionalString(record, key) {
    const value = record[key];
    if (value === undefined)
        return undefined;
    if (typeof value !== "string")
        throw new Error("Invalid archived session record");
    return value;
}
function optionalNumber(record, key) {
    const value = record[key];
    if (value === undefined)
        return undefined;
    if (typeof value !== "number")
        throw new Error("Invalid archived session record");
    return value;
}
function safeFileName(value) {
    return value.replace(/[^a-zA-Z0-9._-]/g, "_") || "session";
}
function uniqueStrings(values) {
    return [...new Set(values)];
}
function isRecord(value) {
    return typeof value === "object" && value !== null;
}
function isNodeErrorWithCode(error, code) {
    return error instanceof Error && "code" in error && error.code === code;
}
//# sourceMappingURL=sessionArchiveStore.js.map