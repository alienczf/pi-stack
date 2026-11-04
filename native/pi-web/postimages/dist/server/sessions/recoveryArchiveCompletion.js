import { createHash, randomUUID } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { closeSync, constants, fstatSync, fsyncSync, linkSync, lstatSync, mkdirSync, openSync, readFileSync, readdirSync, renameSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
import { retirementSource } from "./sessionFailureRetirement.js";

const digest = raw => createHash("sha256").update(raw).digest("hex");
const reject = message => { throw new AutomaticAdmissionRejected(message); };
const missing = error => error?.code === "ENOENT";
const phases = ["claimed", "staged", "artifact", "published", "original-retired", "quarantined", "deleted"];
let localOwner;
function regular(file) {
    const fd = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
        const before = fstatSync(fd);
        if (!before.isFile()) reject("Recovery journal must be regular");
        const raw = readFileSync(fd);
        const after = fstatSync(fd), path = lstatSync(file);
        if ([after, path].some(stat => ["dev", "ino", "size", "mtimeMs", "ctimeMs"].some(key => stat[key] !== before[key])))
            reject("Recovery journal changed while reading");
        return raw;
    } finally { closeSync(fd); }
}
function optional(file) {
    try { return regular(file); } catch (error) { if (!missing(error)) throw error; return undefined; }
}
function inode(file) {
    const stat = lstatSync(file);
    if (!stat.isFile()) reject("Recovery artifact must be regular");
    return { dev: stat.dev, ino: stat.ino };
}
function sameInode(file, receipt) {
    const current = inode(file);
    return current.dev === receipt.dev && current.ino === receipt.ino;
}
function exists(file) {
    try { lstatSync(file); return true; } catch (error) { if (!missing(error)) throw error; return false; }
}
function safeParent(file) {
    let directory = dirname(resolve(file));
    while (true) {
        try { if (!lstatSync(directory).isDirectory()) reject("Recovery artifact parent must be a nonsymlink directory"); }
        catch (error) { if (!missing(error)) throw error; }
        const parent = dirname(directory);
        if (parent === directory) return;
        directory = parent;
    }
}
function syncFile(file) {
    const fd = openSync(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try { if (!fstatSync(fd).isFile()) reject("Recovery artifact must be regular"); fsyncSync(fd); } finally { closeSync(fd); }
}
function syncDirectory(file) {
    const fd = openSync(dirname(file), constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
    try { fsyncSync(fd); } finally { closeSync(fd); }
}
function processIdentity(pid) {
    try {
        const raw = readFileSync(`/proc/${pid}/stat`, "utf8");
        return raw.slice(raw.lastIndexOf(")") + 2).split(" ")[19];
    } catch (error) { if (!missing(error)) throw error; return undefined; }
}
function writerFence(previous) {
    if (process.platform !== "linux") reject("Recovery completion requires the Linux native writer fence");
    const boot = readFileSync("/proc/sys/kernel/random/boot_id", "utf8").trim();
    const start = processIdentity(process.pid);
    if (!start) reject("Native writer process identity is unconfirmed");
    localOwner ??= { boot, pid: process.pid, start, token: randomUUID() };
    if (previous && previous.token !== localOwner.token && previous.boot === boot && processIdentity(previous.pid) === previous.start)
        reject("A live recovery journal owner must be fenced before takeover");
    const executable = statSync("/proc/self/exe");
    for (const pid of readdirSync("/proc").filter(name => /^\d+$/.test(name) && Number(name) !== process.pid)) {
        try {
            const peer = statSync(`/proc/${pid}/exe`);
            if (peer.dev === executable.dev && peer.ino === executable.ino)
                reject("Another pinned native Node process must exit before recovery completion");
        } catch (error) {
            if (missing(error)) continue;
            let uid;
            try { uid = statSync(`/proc/${pid}`).uid; } catch (gone) { if (missing(gone)) continue; throw gone; }
            if (uid === process.getuid() || error instanceof AutomaticAdmissionRejected) throw error;
        }
    }
    return localOwner;
}
function binding(intent) {
    return { version: 1, id: intent.id, originalSessionId: intent.originalSessionId, forkSessionId: intent.forkSessionId, cwd: intent.cwd, originalFile: intent.originalFile, originalLeaf: intent.originalLeaf, sourceSha256: intent.sourceSha256, cacheFile: intent.cacheFile, operation: intent.operation, observation: intent.observation, model: intent.model };
}
function recoveryCompletionLocation(store, intent) {
    const key = digest(JSON.stringify([intent.cwd, intent.originalSessionId, intent.forkSessionId, intent.id]));
    return { key, file: `${store.filePath}.recovery-${key}.json`, artifact: join(store.archiveDir, `.recovery-${key}.archive`), originalQuarantine: join(dirname(intent.originalFile), `.recovery-${key}.original-retired`) };
}
function readJournal(location, intent) {
    const raw = optional(location.file);
    if (raw === undefined) return undefined;
    const journal = JSON.parse(raw.toString("utf8"));
    const identity = value => value && Number.isSafeInteger(value.dev) && Number.isSafeInteger(value.ino);
    const phase = phases.indexOf(journal.phase);
    if (journal.version !== 1 || journal.historicalArchiveOutcome !== "not-inferred" || !isDeepStrictEqual(journal.binding, JSON.parse(JSON.stringify(binding(intent)))) || journal.key !== location.key || phase < 0 || !journal.owner || !Number.isSafeInteger(journal.owner.pid) || journal.owner.pid < 1 || !["boot", "start", "token"].every(key => typeof journal.owner[key] === "string" && journal.owner[key] !== "") || !identity(journal.originalIdentity) || phase >= 1 && !identity(journal.artifactReceipt) || phase >= 4 && !identity(journal.originalReceipt) || phase >= 5 && !identity(journal.deletedReceipt) || journal.originalQuarantine !== location.originalQuarantine || typeof journal.archivePath !== "string" || journal.archivePath === intent.originalFile || journal.archiveQuarantine !== `${journal.archivePath}.recovery-${location.key}.deleted` || !ownedRecord(journal.record, intent) || journal.record.archivePath !== journal.archivePath || journal.record.recoveryCompletionId !== location.key || journal.tombstone?.recoveryCompletionId !== location.key || journal.tombstone?.recoveryDeleted !== true || journal.tombstone?.archivePath !== undefined || phase === 1 && (typeof journal.stage !== "string" || !journal.stage.startsWith(`${location.artifact}.`) || !journal.stage.endsWith(".stage")))
        reject("Recovery completion journal identity or version changed");
    const { archivePath: omitted, ...metadata } = journal.record;
    if (!isDeepStrictEqual(journal.tombstone, { ...metadata, recoveryDeleted: true }) || journal.originalReceipt && !isDeepStrictEqual(journal.originalReceipt, journal.originalIdentity) || journal.deletedReceipt && !isDeepStrictEqual(journal.deletedReceipt, journal.artifactReceipt) || journal.priorRecord !== undefined && (!ownedRecord(journal.priorRecord, intent) || journal.priorRecord.archivePath !== journal.archivePath || journal.priorRecord.recoveryCompletionId !== undefined))
        reject("Recovery positive ownership receipts changed");
    return journal;
}
function source(file, intent, identity) {
    if (digest(retirementSource(file, intent.originalSessionId, intent.cwd)) !== intent.sourceSha256 || identity && !sameInode(file, identity))
        reject("Recovery artifact content or inode changed");
}
function recoveryOriginalEvidence(journal, intent) {
    if (journal === undefined) {
        source(intent.originalFile, intent);
        return intent.originalFile;
    }
    if (exists(intent.originalFile)) {
        source(intent.originalFile, intent, journal.originalIdentity);
        return intent.originalFile;
    }
    if (!journal.originalReceipt) reject("Original absence is not an owned retirement receipt");
    source(journal.originalQuarantine, intent, journal.originalReceipt);
    return journal.originalQuarantine;
}
function ownedRecord(record, intent) {
    return record?.sessionId === intent.originalSessionId && record.cwd === intent.cwd && record.originalPath === intent.originalFile && record.recoveryOperationId === intent.id && typeof record.archivePath === "string";
}
function exactRecord(actual, expected) {
    return actual !== undefined && isDeepStrictEqual(actual, expected);
}

export async function completeRecoveryArchive(store, intent, hooks) {
    return store.exclusive(async () => {
        if (digest(Buffer.from(intent.sourceBase64, "base64")) !== intent.sourceSha256)
            reject("Protected retirement cache changed");
        const location = recoveryCompletionLocation(store, intent);
        let journal = readJournal(location, intent);
        const owner = writerFence(journal?.owner);
        const evidence = () => {
            writerFence(journal?.owner);
            const current = readJournal(location, intent);
            if (journal === undefined ? current !== undefined : JSON.stringify(current) !== JSON.stringify(journal))
                reject("Recovery completion ownership changed before preparation");
            return recoveryOriginalEvidence(journal, intent);
        };
        const engineGuard = await hooks.prepare(evidence);
        const guard = () => {
            for (const file of [location.file, location.artifact, intent.originalFile, ...(journal === undefined ? [] : [journal.archivePath, journal.archiveQuarantine])]) safeParent(file);
            engineGuard(evidence());
            writerFence(journal?.owner);
            if (journal?.artifactReceipt !== undefined) {
                if (exists(journal.archivePath)) source(journal.archivePath, intent, journal.artifactReceipt);
                else if (journal.deletedReceipt !== undefined) source(journal.archiveQuarantine, intent, journal.deletedReceipt);
                else if (journal.phase === "staged") source(journal.stage, intent, journal.artifactReceipt);
                else reject("Owned archive artifact disappeared without a positive quarantine receipt");
            }
            const current = readJournal(location, intent);
            if (journal === undefined ? current !== undefined : JSON.stringify(current) !== JSON.stringify(journal))
                reject("Recovery completion ownership changed");
        };
        const mutate = effect => { guard(); return effect(); };
        const ensureDirectory = directory => {
            if (exists(directory)) {
                if (!lstatSync(directory).isDirectory()) reject("Recovery artifact directory is not regular");
                return;
            }
            ensureDirectory(dirname(directory));
            mutate(() => mkdirSync(directory, { mode: 0o700 }));
            mutate(() => syncDirectory(directory));
        };
        const durable = (file, raw, replace, published = () => {}) => {
            const temporary = `${file}.${owner.token}.${randomUUID()}.tmp`;
            const fd = mutate(() => openSync(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600));
            try {
                mutate(() => writeFileSync(fd, raw));
                mutate(() => fsyncSync(fd));
            } finally { closeSync(fd); }
            mutate(() => replace ? renameSync(temporary, file) : linkSync(temporary, file));
            published();
            mutate(() => syncDirectory(file));
            mutate(() => unlinkSync(temporary));
        };
        const save = next => {
            durable(location.file, `${JSON.stringify(next)}\n`, journal !== undefined, () => { journal = next; });
        };
        const readRegistry = () => store.parseRecoveryRegistry(JSON.parse((optional(store.filePath) ?? Buffer.from('{"sessions":[]}')).toString("utf8")));
        const publishRegistry = record => {
            const data = readRegistry();
            const existing = data.sessions.filter(item => item.sessionId === intent.originalSessionId);
            if (existing.length > 1 || existing.length === 1 && !exactRecord(existing[0], journal.record) && !exactRecord(existing[0], journal.tombstone))
                reject("Conflicting recovery archive registry ownership");
            durable(store.filePath, `${JSON.stringify({ sessions: [...data.sessions.filter(item => item.sessionId !== intent.originalSessionId), record] }, null, 2)}\n`, exists(store.filePath));
        };
        guard();
        hooks.dispatched();
        if (journal === undefined) {
            const records = readRegistry().sessions.filter(item => item.sessionId === intent.originalSessionId);
            if (records.length > 1 || records.length === 1 && (!ownedRecord(records[0], intent) || records[0].recoveryCompletionId !== undefined))
                reject("Existing archive registry belongs to another or unknown intent");
            const existing = records[0];
            const archivePath = existing?.archivePath ?? location.artifact;
            if (archivePath === intent.originalFile || exists(location.originalQuarantine) || exists(`${archivePath}.recovery-${location.key}.deleted`) || !existing && exists(archivePath))
                reject("Unexplained recovery artifact is preserved, not adopted");
            if (existing) source(archivePath, intent);
            const record = existing ?? { sessionId: intent.originalSessionId, cwd: intent.cwd, originalPath: intent.originalFile, archivePath, archivedAt: new Date().toISOString(), recoveryOperationId: intent.id };
            const owned = { ...record, recoveryCompletionId: location.key };
            const { archivePath: omitted, ...metadata } = owned;
            ensureDirectory(dirname(location.file));
            save({ version: 1, historicalArchiveOutcome: "not-inferred", binding: binding(intent), key: location.key, owner, phase: existing ? "artifact" : "claimed", archivePath, originalQuarantine: location.originalQuarantine, archiveQuarantine: `${archivePath}.recovery-${location.key}.deleted`, originalIdentity: inode(intent.originalFile), ...(existing ? { artifactReceipt: inode(archivePath) } : {}), record: owned, priorRecord: existing, tombstone: { ...metadata, recoveryDeleted: true } });
        } else if (journal.owner.token !== owner.token) {
            save({ ...journal, owner });
        }
        const advance = (phase, additions = {}) => save({ ...journal, ...additions, phase });
        const at = phase => phases.indexOf(journal.phase) <= phases.indexOf(phase);
        if (at("claimed")) {
            ensureDirectory(store.archiveDir);
            const stage = `${location.artifact}.${owner.token}.${randomUUID()}.stage`;
            durable(stage, Buffer.from(intent.sourceBase64, "base64"), false);
            source(stage, intent);
            advance("staged", { stage, artifactReceipt: inode(stage) });
        }
        if (at("staged")) {
            source(journal.stage, intent, journal.artifactReceipt);
            if (!exists(journal.archivePath)) mutate(() => linkSync(journal.stage, journal.archivePath));
            source(journal.archivePath, intent, journal.artifactReceipt);
            mutate(() => syncDirectory(journal.archivePath));
            advance("artifact");
        }
        if (at("artifact")) {
            source(journal.archivePath, intent, journal.artifactReceipt);
            mutate(() => syncFile(journal.archivePath));
            mutate(() => syncDirectory(journal.archivePath));
            const data = readRegistry();
            const existing = data.sessions.filter(item => item.sessionId === intent.originalSessionId);
            if (existing.length > 1 || existing.length === 1 && !exactRecord(existing[0], journal.record) && !exactRecord(existing[0], journal.priorRecord))
                reject("Archive receipt publication conflicts with existing ownership");
            durable(store.filePath, `${JSON.stringify({ sessions: [...data.sessions.filter(item => item.sessionId !== intent.originalSessionId), journal.record] }, null, 2)}\n`, exists(store.filePath));
            advance("published");
        }
        const quarantine = (file, target, receiptKey) => {
            if (!journal[receiptKey]) {
                source(file, intent, file === intent.originalFile ? journal.originalIdentity : journal.artifactReceipt);
                if (exists(target)) {
                    if (!sameInode(target, inode(file))) reject("Unexplained quarantine is preserved");
                } else mutate(() => linkSync(file, target));
                source(target, intent, inode(file));
                mutate(() => syncFile(target));
                mutate(() => syncDirectory(target));
                save({ ...journal, [receiptKey]: inode(target) });
            }
            source(target, intent, journal[receiptKey]);
            if (exists(file)) {
                source(file, intent, journal[receiptKey]);
                mutate(() => unlinkSync(file));
            }
            mutate(() => syncDirectory(file));
            if (exists(file)) reject("Retired session path reappeared");
        };
        if (at("published")) {
            if (!exactRecord(readRegistry().sessions.find(item => item.sessionId === intent.originalSessionId), journal.record))
                reject("Positive archive ownership must precede original retirement");
            source(journal.archivePath, intent, journal.artifactReceipt);
            quarantine(intent.originalFile, journal.originalQuarantine, "originalReceipt");
            advance("original-retired");
        }
        if (at("original-retired")) {
            quarantine(journal.archivePath, journal.archiveQuarantine, "deletedReceipt");
            advance("quarantined");
        }
        if (at("quarantined")) {
            source(journal.archiveQuarantine, intent, journal.deletedReceipt);
            publishRegistry(journal.tombstone);
            advance("deleted");
        }
        const verify = () => {
            guard();
            source(journal.archiveQuarantine, intent, journal.deletedReceipt);
            if (exists(intent.originalFile) || exists(journal.archivePath) || !exactRecord(readRegistry().sessions.find(item => item.sessionId === intent.originalSessionId), journal.tombstone))
                reject("Owned deletion has not durably removed runnable lookup paths");
        };
        verify();
        return { verify, archive: journal.record, deleted: { sessionId: intent.originalSessionId, archivePath: journal.archivePath, sourceSha256: intent.sourceSha256, protocol: "intent-quarantine-v1", completionId: location.key, journalFile: location.file, originalQuarantine: journal.originalQuarantine, archiveQuarantine: journal.archiveQuarantine } };
    });
}
