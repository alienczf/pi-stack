import { createHash } from "node:crypto";
import { constants, closeSync, fstatSync, openSync, readFileSync } from "node:fs";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";

function sourceHash(path) {
    const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
        if (!fstatSync(fd).isFile()) throw new Error("not regular");
        return createHash("sha256").update(readFileSync(fd)).digest("hex");
    } finally { closeSync(fd); }
}

export function callbackInventory(loaded) {
    const owners = [], unproven = [];
    if (!loaded) return { known: false, owners, unproven: ["extension inventory unavailable"] };
    for (const error of loaded.errors) unproven.push("failed extension load: " + error.path);
    for (const extension of loaded.extensions) {
        const path = extension.resolvedPath;
        const declaration = extension.callbackOwnership;
        try {
            if (!declaration?.sourceSha256 || sourceHash(path) !== declaration.sourceSha256)
                throw new Error("missing declaration or changed loaded source");
            const value = declaration.snapshot();
            if (!value || !["none", "safe-to-drop", "active", "unknown"].includes(value.kind) || typeof value.revision !== "string" || !value.revision || !Array.isArray(value.owners) || value.owners.some(owner => typeof owner !== "string" || !owner) || value.kind === "none" && value.owners.length !== 0 || value.kind === "safe-to-drop" && typeof declaration.drop !== "function")
                throw new Error("invalid live declaration");
            owners.push({ path, sourceSha256: declaration.sourceSha256, kind: value.kind, revision: value.revision, owners: [...value.owners] });
            if (value.kind === "active" || value.kind === "unknown") unproven.push(`extension callback ownership: ${path} ${value.owners.join(", ")}`);
        } catch (error) { unproven.push(`extension callback ownership: ${path} ${error.message}`); }
    }
    return { known: unproven.length === 0, owners, unproven };
}

export async function prepareCallbackDrops(loaded, guard = () => {}) {
    guard();
    const before = callbackInventory(loaded);
    if (!before.known) throw new AutomaticAdmissionRejected("Extension callback ownership is unknown or active");
    for (const owner of before.owners) {
        if (owner.kind !== "safe-to-drop") continue;
        const extension = loaded.extensions.find(extension => extension.resolvedPath === owner.path);
        const current = callbackInventory(loaded).owners.find(item => item.path === owner.path);
        if (JSON.stringify(current) !== JSON.stringify(owner))
            throw new AutomaticAdmissionRejected("Extension callback ownership changed before drop");
        guard();
        const receipt = await extension.callbackOwnership.drop(owner.revision);
        guard();
        const after = callbackInventory(loaded);
        const settled = after.owners.find(item => item.path === owner.path);
        if (receipt?.droppedRevision !== owner.revision || !after.known || settled?.kind !== "none")
            throw new AutomaticAdmissionRejected("Extension callback cancellation receipt is unconfirmed");
    }
    const after = callbackInventory(loaded);
    if (!after.known || after.owners.some(owner => owner.kind !== "none"))
        throw new AutomaticAdmissionRejected("Extension callback ownership changed during cancellation");
    return after;
}
