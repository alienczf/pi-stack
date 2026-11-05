import { readdir } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { SessionManager, SettingsManager } from "@earendil-works/pi-coding-agent";
import { canonicalizeStoredCwd, cwdPathsEqual } from "../workingDirectory.js";
import { readSessionHeaderSummary } from "./sessionFileHeader.js";
export class SessionDirResolver {
    constructor(options) {
        this.agentDir = options.agentDir;
        this.envSessionDir = options.sessionDirEnvKeys
            .map((key) => options.env[key])
            .find((value) => value !== undefined && value !== "");
        const configuredHome = options.env["HOME"];
        this.homeDir = configuredHome !== undefined && configuredHome !== "" && isAbsolute(configuredHome) ? configuredHome : homedir();
    }
    defaultSessionsRoot() {
        return defaultPiSessionsRoot(this.agentDir);
    }
    globalEnvSessionDir() {
        if (this.envSessionDir === undefined)
            return undefined;
        const expanded = expandTildePath(this.envSessionDir, this.homeDir);
        return isAbsolute(expanded) ? expanded : undefined;
    }
    resolve(cwd) {
        if (this.envSessionDir !== undefined) {
            return { source: "env", sessionDir: resolveConfiguredPath(this.envSessionDir, cwd, this.homeDir), usesConfiguredSessionDir: true };
        }
        const settingsSessionDir = SettingsManager.create(cwd, this.agentDir).getSessionDir();
        if (settingsSessionDir !== undefined && settingsSessionDir !== "") {
            return { source: "settings", sessionDir: resolveConfiguredPath(settingsSessionDir, cwd, this.homeDir), usesConfiguredSessionDir: true };
        }
        return { source: "pi-default", sessionDir: defaultPiSessionDir(cwd, this.agentDir), usesConfiguredSessionDir: false };
    }
}
export function createPiSessionManagerGateway(options) {
    return new SettingsAwarePiSessionManagerGateway(new SessionDirResolver(options));
}
class SettingsAwarePiSessionManagerGateway {
    constructor(resolver) {
        this.resolver = resolver;
    }
    async list(cwd) {
        const resolution = this.resolver.resolve(cwd);
        return filterSessionsForCwd(await listSessionsInDir(resolution.sessionDir), cwd);
    }
    async listHeaders(cwd) {
        const resolution = this.resolver.resolve(cwd);
        return filterSessionsForCwd(await listHeaderDescriptors(resolution.sessionDir), cwd);
    }
    async locate(id, cwd) {
        let descriptors;
        if (cwd !== undefined) {
            descriptors = await this.listHeaders(cwd);
        }
        else {
            let entries = [];
            const root = this.resolver.defaultSessionsRoot();
            try {
                entries = await readdir(root, { withFileTypes: true });
            }
            catch {}
            const dirs = entries.filter((entry) => entry.isDirectory()).map((entry) => join(root, entry.name));
            const envDir = this.resolver.globalEnvSessionDir();
            if (envDir !== undefined)
                dirs.push(envDir);
            descriptors = [];
            for (const dir of new Set(dirs))
                descriptors.push(...await listHeaderDescriptors(dir));
        }
        const matches = new Map(descriptors.filter((entry) => entry.id.startsWith(id)).map((entry) => [entry.path, entry]));
        const exact = [...matches.values()].filter((entry) => entry.id === id);
        const candidates = exact.length > 0 ? exact : [...matches.values()];
        if (candidates.length > 1)
            throw new Error("Ambiguous session ID");
        return candidates[0];
    }
    create(cwd, options) {
        const resolution = this.resolver.resolve(cwd);
        return SessionManager.create(cwd, resolution.sessionDir, options?.parentSession === undefined ? undefined : { parentSession: options.parentSession });
    }
    async listAll() {
        const envSessionDir = this.resolver.globalEnvSessionDir();
        const [defaultSessions, envSessions] = await Promise.all([
            listSessionsInDefaultPiStore(this.resolver.defaultSessionsRoot()),
            envSessionDir === undefined ? Promise.resolve([]) : listSessionsInDir(envSessionDir),
        ]);
        return uniqueSessionsByPath([...defaultSessions, ...envSessions]);
    }
    open(path) {
        return SessionManager.open(path, dirname(path));
    }
}
export async function listSessionsInDir(sessionDir) {
    // listAll(sessionDir) lists without the SDK's internal cwd filter, which would
    // otherwise compare against this process's cwd and drop other projects' sessions.
    // Cwd filtering is applied explicitly by filterSessionsForCwd where needed.
    // Session file headers are written by external tools (Pi CLI, SDK consumers),
    // so their cwd is canonicalized here before it enters pi-web.
    const sessions = await SessionManager.listAll(sessionDir);
    return sessions.map((session) => ({ ...session, cwd: canonicalizeStoredCwd(session.cwd) }));
}
export async function listSessionsInDefaultPiStore(storeRoot) {
    let entries;
    try {
        entries = await readdir(storeRoot, { withFileTypes: true });
    }
    catch {
        return [];
    }
    const sessionDirs = entries.filter((entry) => entry.isDirectory()).map((entry) => join(storeRoot, entry.name));
    const sessions = (await Promise.all(sessionDirs.map((dir) => listSessionsInDir(dir)))).flat();
    return sessions.sort((a, b) => b.modified.getTime() - a.modified.getTime());
}
export function filterSessionsForCwd(sessions, cwd) {
    // Sessions with an empty cwd (old session files) are excluded: resolve("") would
    // resolve to this process's cwd and produce false matches.
    return sessions.filter((session) => session.cwd !== "" && cwdPathsEqual(session.cwd, cwd));
}
function uniqueSessionsByPath(sessions) {
    const byPath = new Map();
    for (const session of sessions)
        byPath.set(session.path, session);
    return [...byPath.values()].sort((a, b) => b.modified.getTime() - a.modified.getTime());
}
export function defaultPiSessionsRoot(agentDir) {
    return join(agentDir, "sessions");
}
export function defaultPiSessionDir(cwd, agentDir) {
    return sessionDirInDefaultPiStore(defaultPiSessionsRoot(agentDir), cwd);
}
export function sessionDirInDefaultPiStore(storeRoot, cwd) {
    const safePath = `--${cwd.replace(/^[/\\]/u, "").replace(/[/\\:]/gu, "-")}--`;
    return join(storeRoot, safePath);
}
export function resolveConfiguredPath(path, cwd, homeDir) {
    const expanded = expandTildePath(path, homeDir);
    return isAbsolute(expanded) ? expanded : resolve(cwd, expanded);
}
function expandTildePath(path, homeDir) {
    if (path === "~")
        return homeDir;
    if (path.startsWith("~/"))
        return join(homeDir, path.slice(2));
    return path;
}
//# sourceMappingURL=piSessionManagerGateway.js.map
async function listHeaderDescriptors(sessionDir) {
    let entries;
    try {
        entries = await readdir(sessionDir);
    }
    catch {
        return [];
    }
    const descriptors = [];
    for (const name of entries) {
        if (!name.endsWith(".jsonl"))
            continue;
        const path = join(sessionDir, name);
        const header = await readSessionHeaderSummary(path);
        if (header === undefined || header.cwd === undefined)
            continue;
        descriptors.push({ path, id: header.id, cwd: canonicalizeStoredCwd(header.cwd), parentSessionPath: header.parentSession });
    }
    return descriptors;
}
