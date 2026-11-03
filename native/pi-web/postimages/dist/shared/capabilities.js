import { PI_WEB_CAPABILITIES } from "./apiTypes.js";
export { PI_WEB_CAPABILITIES };
export const KNOWN_PI_WEB_CAPABILITIES = Object.values(PI_WEB_CAPABILITIES);
const knownPiWebCapabilities = new Set(KNOWN_PI_WEB_CAPABILITIES);
export const WEB_RUNTIME_CAPABILITIES = [
    PI_WEB_CAPABILITIES.sessionsEngineFailureRecovery,
    PI_WEB_CAPABILITIES.sessionsExtensionCallbackOwnership,
    PI_WEB_CAPABILITIES.sessionsStreamTransientRetry,
    PI_WEB_CAPABILITIES.sessionsFailureRetirement,
    PI_WEB_CAPABILITIES.sessionsFailureMaintenance,
    PI_WEB_CAPABILITIES.sessionsResumeObservation,
    PI_WEB_CAPABILITIES.sessionsFailureFork,
    PI_WEB_CAPABILITIES.sessionsFailureBoundary,
    PI_WEB_CAPABILITIES.sessionsDeleteArchived,
    PI_WEB_CAPABILITIES.sessionsBulkMutations,
    PI_WEB_CAPABILITIES.sessionsCleanup,
    PI_WEB_CAPABILITIES.sessionsReload,
    PI_WEB_CAPABILITIES.sessionsClearQueue,
    PI_WEB_CAPABILITIES.sessionsPersistedState,
    PI_WEB_CAPABILITIES.sessionsNotifications,
    PI_WEB_CAPABILITIES.sessionsUnread,
    PI_WEB_CAPABILITIES.sessionsAskUser,
    PI_WEB_CAPABILITIES.sessionsMaintenanceCheckpoint,
    PI_WEB_CAPABILITIES.sessionsStreamsDcrEvents,
    PI_WEB_CAPABILITIES.sessionsConditionalAdmission,
    PI_WEB_CAPABILITIES.promptPotetoArguments,
    PI_WEB_CAPABILITIES.promptControlGoal,
    PI_WEB_CAPABILITIES.promptRecoveryControl,
    PI_WEB_CAPABILITIES.promptAttachments,
    PI_WEB_CAPABILITIES.workspaceFileSuggestions,
    PI_WEB_CAPABILITIES.piPackagesManage,
    PI_WEB_CAPABILITIES.selectedMachineSettings,
    PI_WEB_CAPABILITIES.agentProfileConfig,
];
export const SESSIOND_RUNTIME_CAPABILITIES = [
    PI_WEB_CAPABILITIES.sessionsEngineFailureRecovery,
    PI_WEB_CAPABILITIES.sessionsExtensionCallbackOwnership,
    PI_WEB_CAPABILITIES.sessionsStreamTransientRetry,
    PI_WEB_CAPABILITIES.sessionsFailureRetirement,
    PI_WEB_CAPABILITIES.sessionsFailureMaintenance,
    PI_WEB_CAPABILITIES.sessionsResumeObservation,
    PI_WEB_CAPABILITIES.sessionsFailureFork,
    PI_WEB_CAPABILITIES.sessionsFailureBoundary,
    PI_WEB_CAPABILITIES.sessionsDeleteArchived,
    PI_WEB_CAPABILITIES.sessionsBulkMutations,
    PI_WEB_CAPABILITIES.sessionsCleanup,
    PI_WEB_CAPABILITIES.sessionsReload,
    PI_WEB_CAPABILITIES.sessionsClearQueue,
    PI_WEB_CAPABILITIES.sessionsPersistedState,
    PI_WEB_CAPABILITIES.sessionsNotifications,
    PI_WEB_CAPABILITIES.sessionsUnread,
    PI_WEB_CAPABILITIES.sessionsAskUser,
    PI_WEB_CAPABILITIES.sessionsMaintenanceCheckpoint,
    PI_WEB_CAPABILITIES.sessionsStreamsDcrEvents,
    PI_WEB_CAPABILITIES.sessionsConditionalAdmission,
    PI_WEB_CAPABILITIES.promptPotetoArguments,
    PI_WEB_CAPABILITIES.promptControlGoal,
    PI_WEB_CAPABILITIES.promptRecoveryControl,
    PI_WEB_CAPABILITIES.promptAttachments,
];
const EFFECTIVE_CAPABILITY_REQUIREMENTS = {
    [PI_WEB_CAPABILITIES.sessionsEngineFailureRecovery]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsExtensionCallbackOwnership]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsStreamTransientRetry]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsDeleteArchived]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsBulkMutations]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsCleanup]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsReload]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsClearQueue]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsPersistedState]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsNotifications]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsUnread]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsAskUser]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsMaintenanceCheckpoint]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsStreamsDcrEvents]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsConditionalAdmission]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsFailureBoundary]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsFailureFork]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsFailureMaintenance]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsFailureRetirement]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.sessionsResumeObservation]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.promptPotetoArguments]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.promptControlGoal]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.promptRecoveryControl]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.promptAttachments]: ["web", "sessiond"],
    [PI_WEB_CAPABILITIES.workspaceFileSuggestions]: ["web"],
    [PI_WEB_CAPABILITIES.piPackagesManage]: ["web"],
    [PI_WEB_CAPABILITIES.selectedMachineSettings]: ["web"],
    [PI_WEB_CAPABILITIES.agentProfileConfig]: ["web"],
};
export function isPiWebCapability(value) {
    return typeof value === "string" && knownPiWebCapabilities.has(value);
}
export function supportsPiWebCapability(source, capability) {
    return source?.capabilities?.includes(capability) === true;
}
export function parseKnownPiWebCapabilities(value) {
    if (!Array.isArray(value) || !value.every((capability) => typeof capability === "string"))
        return undefined;
    return value.filter(isPiWebCapability);
}
export function effectivePiWebCapabilities(components) {
    return KNOWN_PI_WEB_CAPABILITIES.filter((capability) => {
        const requiredComponents = EFFECTIVE_CAPABILITY_REQUIREMENTS[capability];
        return requiredComponents.every((component) => {
            const runtime = components[component];
            return runtime?.available === true && supportsPiWebCapability(runtime, capability);
        });
    });
}
//# sourceMappingURL=capabilities.js.map