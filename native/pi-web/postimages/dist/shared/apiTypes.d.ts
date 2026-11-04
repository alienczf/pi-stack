export type MachineKind = "local" | "remote";
export type MachineStatus = "unknown" | "online" | "offline" | "error";
export declare const PI_WEB_CAPABILITIES: {
    readonly sessionsDeleteArchived: "sessions.deleteArchived";
    readonly sessionsBulkMutations: "sessions.bulkMutations";
    readonly sessionsCleanup: "sessions.cleanup";
    readonly sessionsReload: "sessions.reload";
    readonly sessionsClearQueue: "sessions.clearQueue";
    readonly sessionsPersistedState: "sessions.persistedState";
    readonly sessionsNotifications: "sessions.notifications";
    readonly sessionsUnread: "sessions.unread";
    readonly sessionsAskUser: "sessions.askUser";
    readonly sessionsMaintenanceCheckpoint: "sessions.maintenanceCheckpoint";
    readonly sessionsStreamsDcrEvents: "sessions.streamsDcrEvents";
    readonly sessionsConditionalAdmission: "sessions.conditionalAdmission";
    readonly sessionsEngineFailureRecovery: "sessions.engineFailureRecovery";
    readonly sessionsExtensionCallbackOwnership: "sessions.extensionCallbackOwnership";
    readonly sessionsStreamTransientRetry: "sessions.streamTransientRetry";
    readonly sessionsFailureBoundary: "sessions.failureBoundary";
    readonly sessionsFailureFork: "sessions.failureFork";
    readonly sessionsFailureMaintenance: "sessions.failureMaintenance";
    readonly sessionsFailureRetirement: "sessions.failureRetirement";
    readonly sessionsResumeObservation: "sessions.resumeObservation";
    readonly promptPotetoArguments: "prompt.potetoArguments";
    readonly promptControlGoal: "prompt.controlGoal";
    readonly promptRecoveryControl: "prompt.recoveryControl";
    readonly promptAttachments: "prompt.attachments";
    readonly workspaceFileSuggestions: "workspace.fileSuggestions";
    readonly piPackagesManage: "piPackages.manage";
    readonly selectedMachineSettings: "settings.selectedMachine";
    readonly agentProfileConfig: "settings.agentProfile";
};
export type PiWebCapability = typeof PI_WEB_CAPABILITIES[keyof typeof PI_WEB_CAPABILITIES];
export interface Machine {
    id: string;
    name: string;
    kind: MachineKind;
    baseUrl?: string;
    createdAt: string;
    updatedAt: string;
    status?: MachineStatus;
    statusMessage?: string;
}
export interface MachineHealth {
    machineId: string;
    ok: boolean;
    checkedAt: string;
    status?: MachineStatus;
    web?: PiWebComponentStatus;
    sessiond?: PiWebComponentStatus;
    error?: string;
}
export interface MachineRuntime {
    machineId: string;
    ok: boolean;
    checkedAt: string;
    packageName?: string;
    generatedAt?: string;
    components?: PiWebRuntimeResponse["components"];
    capabilities?: PiWebCapability[];
    error?: string;
}
export type PiWebShortcutConfig = Record<string, string | null>;
export type PiWebPluginSettings = Record<string, unknown>;
export type PiWebPluginConfigMap = Record<string, PiWebPluginConfig>;
export interface PiWebPluginConfig {
    enabled?: boolean;
    settings?: PiWebPluginSettings;
    [key: string]: unknown;
}
export interface PiWebPathAccessConfig {
    allowedPaths?: string[];
}
export interface PiWebUploadsConfig {
    defaultFolder?: string;
}
export interface PiWebAgentConfig {
    /** Pi-compatible companion CLI used for diagnostics and safe package-managed updates. */
    command?: string;
    /** Pi-compatible profile directory containing auth.json, models.json, settings.json, and sessions/. */
    dir?: string;
}
export interface PiWebConfigValues {
    host?: string;
    port?: number;
    allowedHosts?: string[] | true;
    shortcuts?: PiWebShortcutConfig;
    plugins?: PiWebPluginConfigMap;
    /** External filesystem roots PI WEB may expose outside a workspace. */
    pathAccess?: PiWebPathAccessConfig;
    /** Workspace-relative defaults for manual file uploads. */
    uploads?: PiWebUploadsConfig;
    /** Maximum accepted HTTP request body size in bytes (uploads/attachments). */
    maxUploadBytes?: number;
    /** When true, LLMs can start new sessions via the spawn_session tool. */
    spawnSessions?: boolean;
    /**
     * Beta: when true, LLMs can start tracked child sessions via the
     * spawn_subsession / list_subsessions / check_subsession / read_subsession
     * tools. Off by default
     * while the capability stabilizes. Requires spawnSessions to be enabled.
     */
    subsessions?: boolean;
    /**
     * When true, LLMs can post a question set to the browser via the ask_user
     * tool. On by default; set to `false` to remove the tool from the runtime.
     */
    askUser?: boolean;
    /**
     * How long an extension dialog may wait for an answer before the daemon
     * auto-cancels it, in milliseconds. Applies only when the extension set no
     * `timeout` of its own (the sooner of the two wins); `0` waits forever.
     * Tuning knob only — extension dialogs are always enabled.
     */
    extensionDialogsTimeoutMs?: number;
    /** Desired Pi-compatible agent profile and companion CLI (Pi by default). */
    agent?: PiWebAgentConfig;
}
export type PiWebPluginScope = "bundled" | "local" | "user" | "project";
export interface PiWebPluginInfo {
    id: string;
    module: string;
    source: string;
    scope: PiWebPluginScope;
    machineSpecific: boolean;
    enabled: boolean;
}
export interface PiWebPluginsResponse {
    plugins: PiWebPluginInfo[];
}
export type PiPackageScope = "user" | "project";
export interface PiPackageInfo {
    source: string;
    scope: PiPackageScope;
    filtered: boolean;
    installedPath?: string;
}
export interface PiPackagesResponse {
    packages: PiPackageInfo[];
}
export interface PiPackageInstallRequest {
    source: string;
}
export interface PiPackageRemoveRequest {
    source: string;
    /** Optional known scope from a listed package; not an install-location picker. */
    scope?: PiPackageScope;
}
export interface PiPackageUpdateRequest {
    /** Omit to update all configured Pi packages. */
    source?: string;
}
export type PiPackageMutationAction = "install" | "remove" | "update";
export interface PiPackageMutationResponse extends PiPackagesResponse {
    action: PiPackageMutationAction;
    source?: string;
    scope?: PiPackageScope;
    removed?: boolean;
}
export type PiWebAgentDirEnvSource = "pi-web" | "pi-compatibility";
export interface PiWebConfigEnvOverrides {
    host: boolean;
    port: boolean;
    allowedHosts: boolean;
    spawnSessions: boolean;
    subsessions: boolean;
    askUser: boolean;
    agentCommand: boolean;
    agentDir: boolean;
    /** The configured directory environment source, even when Pi compatibility is inactive for the desired command. */
    agentDirSource?: PiWebAgentDirEnvSource;
    agentSessionDir: boolean;
}
export interface PiWebConfigResponse {
    path: string;
    exists: boolean;
    config: PiWebConfigValues;
    effectiveConfig: PiWebConfigValues;
    envOverrides: PiWebConfigEnvOverrides;
}
export interface Project {
    id: string;
    name: string;
    path: string;
    createdAt: string;
}
export interface WorkspaceEffectiveConfig {
    uploads?: PiWebUploadsConfig;
}
export interface Workspace {
    id: string;
    projectId: string;
    path: string;
    label: string;
    branch?: string;
    isMain: boolean;
    isGitRepo: boolean;
    isGitWorktree: boolean;
    /** Workspace-effective project/global settings needed by workspace UI features. */
    effectiveConfig?: WorkspaceEffectiveConfig;
}
export interface SessionRef {
    id: string;
    cwd: string;
}
export declare const SESSION_UNREAD_LIMIT = 1000;
export declare const SESSION_UNREAD_SESSION_ID_MAX_LENGTH = 512;
export declare const SESSION_UNREAD_CWD_MAX_LENGTH: number;
export declare const SESSION_UNREAD_CATALOG_ID_MAX_LENGTH = 512;
export declare const SESSION_UNREAD_COMPLETED_AT_MAX_LENGTH = 64;
export interface SessionUnreadSummary {
    sessionId: string;
    cwd: string;
    /** Monotonic within a catalog and never greater than its containing revision. */
    completionOrder: number;
    completedAt: string;
}
export interface SessionUnreadCatalogSnapshot {
    /** Stable for one persisted catalog epoch; changes when unread state is reset. */
    catalogId: string;
    /** Monotonic catalog mutation revision; at least every contained completion order. */
    catalogRevision: number;
    /** Bounded by `SESSION_UNREAD_LIMIT` and ordered newest completion first. */
    sessions: SessionUnreadSummary[];
}
export interface SessionUnreadAcknowledgeRequest {
    cwd: string;
    /** The catalog epoch in which `throughCompletionOrder` was observed. */
    catalogId: string;
    throughCompletionOrder: number;
}
/** Authoritative delta for one session in the daemon-owned unread catalog. */
export interface SessionUnreadEvent {
    type: "sessions.unread";
    catalogId: string;
    /** At least `unread.completionOrder` when carrying an unread summary. */
    catalogRevision: number;
    sessionId: string;
    cwd: string;
    unread: SessionUnreadSummary | null;
}
export declare const SESSION_NOTIFICATION_LIMIT = 100;
export declare const SESSION_NOTIFICATION_MESSAGE_BYTES: number;
export type SessionNotificationSeverity = "info" | "warning" | "error";
export interface SessionNotification {
    id: string;
    message: string;
    truncated: boolean;
    severity: SessionNotificationSeverity;
    receivedAt: string;
    order: number;
}
export interface SessionNotificationSummary {
    sessionId: string;
    cwd: string;
    inboxRevision: number;
    retainedCount: number;
    discardedCount: number;
    highestSeverity?: SessionNotificationSeverity;
}
export interface SessionNotificationDismissThrough {
    order: number;
    overflowWatermark: number;
}
export interface SessionNotificationInboxSnapshot {
    daemonInstanceId: string;
    catalogRevision: number;
    summary: SessionNotificationSummary;
    notifications: SessionNotification[];
    dismissThrough: SessionNotificationDismissThrough;
}
export interface SessionNotificationCatalogSnapshot {
    daemonInstanceId: string;
    catalogRevision: number;
    sessions: SessionNotificationSummary[];
}
export interface SessionNotificationDismissRequest {
    cwd: string;
    daemonInstanceId: string;
    notificationId: string;
}
export interface SessionNotificationDismissAllRequest {
    cwd: string;
    daemonInstanceId: string;
    throughOrder: number;
    throughOverflowWatermark: number;
}
export type SessionNotificationClearReason = "runtime-close" | "archive" | "delete" | "restore" | "archive-reconcile" | "replacement" | "initialization-failed" | "service-dispose";
export type SessionNotificationInboxDelta = {
    kind: "added";
    notification: SessionNotification;
    evictedNotificationId?: string;
} | {
    kind: "dismissed";
    notificationIds: string[];
} | {
    kind: "cleared";
    reason: SessionNotificationClearReason;
} | {
    kind: "resync";
};
export interface SessionNotificationInboxEvent {
    type: "notifications.inbox";
    daemonInstanceId: string;
    catalogRevision: number;
    summary: SessionNotificationSummary;
    dismissThrough: SessionNotificationDismissThrough;
    delta: SessionNotificationInboxDelta;
}
export interface SessionNotificationSummaryEvent {
    type: "notifications.summary";
    daemonInstanceId: string;
    catalogRevision: number;
    summary: SessionNotificationSummary;
}
export interface SessionInfo extends SessionRef {
    path: string;
    /** True when the server has verified a backing session file exists; false when known transient. */
    persisted?: boolean;
    name?: string;
    created: string;
    modified: string;
    messageCount: number;
    firstMessage: string;
    parentSessionPath?: string;
    /**
     * Working directory of the parent session, read from the parent session file
     * header. Only populated when the parent is outside this listing's cwd, so a
     * child whose parent lives in another worktree can point at it instead of
     * only reporting that the parent is unavailable here.
     */
    parentSessionCwd?: string;
    /** Session id of an out-of-cwd parent, so the browser can select it after switching workspace. */
    parentSessionId?: string;
    /**
     * Number of sessions in other workspaces of the same project that record this
     * session as their parent. Only set when non-zero, so a parent can show that
     * it has children which are not nested beneath it in this workspace.
     */
    childSessionsElsewhere?: number;
    archived?: boolean;
    archivedAt?: string;
    archivePath?: string;
}
export interface ArchiveSessionsResponse {
    archived: true;
    sessionIds?: string[];
    archivedCount?: number;
    skippedAlreadyArchivedCount?: number;
}
export interface SessionBulkMutationRef {
    id: string;
    cwd?: string;
}
export interface SessionBulkMutationRequest {
    sessions: SessionBulkMutationRef[];
}
export interface SessionBulkFailure {
    sessionId: string;
    error: string;
}
export interface SessionBulkArchiveResponse {
    archived: true;
    archivedSessionIds: string[];
    failures: SessionBulkFailure[];
    generatedAt: string;
}
export interface SessionBulkDeleteArchivedResponse {
    deleted: true;
    deletedSessionIds: string[];
    failures: SessionBulkFailure[];
    generatedAt: string;
}
export interface SessionCleanupRequest {
    /** Archive non-archived sessions whose modified time is older than this many days. Omit/null to disable. */
    archiveIdleDays?: number | null;
    /** Permanently delete archived sessions whose archivedAt time is older than this many days. Omit/null to disable. */
    deleteArchivedDays?: number | null;
    /** Stored cwd paths selected from a preview. Omit/null to include all discovered project/workspace paths. */
    projectCwds?: string[] | null;
}
export interface SessionCleanupThresholds {
    archiveIdleDays?: number;
    deleteArchivedDays?: number;
}
export interface SessionCleanupProjectSummary {
    cwd: string;
    archiveCount: number;
    deleteCount: number;
}
export interface SessionCleanupTotals {
    archiveCount: number;
    deleteCount: number;
}
export interface SessionCleanupPreviewResponse {
    generatedAt: string;
    thresholds: SessionCleanupThresholds;
    projects: SessionCleanupProjectSummary[];
    totals: SessionCleanupTotals;
    skippedBusySessionIds?: string[];
}
export interface SessionCleanupExecuteResponse extends SessionCleanupPreviewResponse {
    archivedSessionIds: string[];
    deletedSessionIds: string[];
}
export interface SessionActivity {
    sessionId: string;
    phase: "active" | "idle" | "error";
    label: string;
    detail?: string;
    at: string;
    /**
     * Set only on the startup window's own reports. A startup phase is genuinely
     * in progress, so it is published as `active` and rendered like any other
     * activity, but *starting* a session is not *working* in it: there is nothing
     * to stop, nothing that blocks reloading from disk, and no workspace-level
     * work to report. `isSessionActive()` reads this to keep the two apart.
     */
    startup?: boolean;
}
export interface QueuedSessionMessage {
    kind: "steer" | "followUp";
    text: string;
}
/**
 * `customType` of the follow-up custom message that carries a closed ask back to
 * the model and into the transcript. Its `details` are an {@link AskUserOutcome}.
 */
export declare const ASK_USER_ANSWERS_CUSTOM_TYPE = "pi-web.ask.answers";
/** Largest question set one `ask_user` call may post. */
export declare const ASK_USER_QUESTION_LIMIT = 20;
/** Largest option list one question may offer. */
export declare const ASK_USER_OPTION_LIMIT = 12;
/** Length bound for ids: the ask id, question ids, and option values. */
export declare const ASK_USER_ID_MAX_LENGTH = 128;
/** Length bound for model-authored prose: questions, details, and option labels. */
export declare const ASK_USER_TEXT_MAX_LENGTH = 1000;
/** Length bound for the free text a user types as a custom answer. */
export declare const ASK_USER_OTHER_TEXT_MAX_LENGTH = 4000;
/** One selectable option of an {@link AskUserQuestion}. */
export interface AskUserQuestionOption {
    /** Stable machine value reported back to the model. */
    value: string;
    /** Short human label rendered in the browser. */
    label: string;
    /** Optional clarifying line rendered under the label. */
    detail?: string;
}
/**
 * One question of an `ask_user` set. Questions are never required: the user may
 * submit while leaving any of them untouched, and unanswered questions are
 * reported to the model as such.
 */
export interface AskUserQuestion {
    /** Unique within the ask; used as the answer key. */
    id: string;
    /** The question itself, as one plain-text line. */
    question: string;
    /** Optional supporting context rendered under the question. */
    detail?: string;
    /** Offered options; may be empty when only free text makes sense. */
    options: AskUserQuestionOption[];
    /**
     * Compatibility marker for older clients. Canonical questions set this to
     * true because every question offers a custom free-text answer.
     */
    allowOther?: boolean;
    /** When true, several options may be selected at once. */
    multiple?: boolean;
}
/**
 * The open, unanswered question set of a session. Daemon-owned and reported in
 * {@link SessionStatus}, so a reconnecting or reloading browser rehydrates it
 * without depending on having seen the `ask.opened` event.
 */
export interface PendingAskUser {
    askId: string;
    askedAt: string;
    questions: AskUserQuestion[];
}
/** Why an ask stopped being the session's open ask. */
export type AskUserCloseReason = "submitted" | "superseded" | "cancelled";
/**
 * What the user replied to one question. Absent from a submission means the
 * question was left untouched; an empty `values` with no `otherText` means the
 * same thing.
 */
export interface AskUserAnswer {
    /** Matches an {@link AskUserQuestion.id} of the open ask. */
    id: string;
    /** Selected {@link AskUserQuestionOption.value} entries; several only when the question allows it. */
    values: string[];
    /** Free text typed as the question's custom answer. */
    otherText?: string;
}
/** One submit of the open ask: answers for some or all of its questions. */
export interface AskUserSubmission {
    answers: AskUserAnswer[];
}
/**
 * One question of a closed ask paired with what came back for it. Carries the
 * question itself so the record renders without the original ask still existing.
 */
export interface AskUserQuestionRecord {
    question: AskUserQuestion;
    /** True when at least one option was selected or custom text was given. */
    answered: boolean;
    values: string[];
    otherText?: string;
}
/**
 * The complete result of an ask, computed when it closes. Shared by the
 * model-facing follow-up message and the browser's read-only record, so both
 * report the same answered and unanswered questions.
 */
export interface AskUserOutcome {
    askId: string;
    reason: AskUserCloseReason;
    askedAt: string;
    closedAt: string;
    questions: AskUserQuestionRecord[];
    answeredCount: number;
    /** Ids of the questions left unanswered, in the order they were asked. */
    unansweredIds: string[];
    /** One line, for example `Answered 3 of 5; unanswered: q2, q5`. */
    summary: string;
}
/**
 * Result of the browser closing an ask by submitting or cancelling it.
 *
 * `"stale"` is an ordinary race rather than an error: the named ask was already
 * submitted, superseded by a newer one, or gone with its session runtime. The
 * browser drops its card and trusts `sessionStatus`, which is returned in both
 * cases so closing an ask needs no follow-up status request.
 */
export interface AskUserCloseResponse {
    result: "closed" | "stale";
    /** Present only when this call is the one that closed the ask. */
    outcome?: AskUserOutcome;
    sessionStatus: SessionStatus;
}
/** Length bound for extension-dialog ids. */
export declare const EXTENSION_DIALOG_ID_MAX_LENGTH = 128;
/** Length bound for extension-authored dialog prose: titles, messages, options, placeholders. */
export declare const EXTENSION_DIALOG_TEXT_MAX_LENGTH = 1000;
/** Largest option list one `select` dialog may offer. */
export declare const EXTENSION_DIALOG_OPTION_LIMIT = 24;
/** Length bound for the text a user types into an `input` dialog. */
export declare const EXTENSION_DIALOG_INPUT_MAX_LENGTH = 4000;
/** Which extension UI dialog primitive a pending dialog belongs to. */
export type ExtensionDialogKind = "confirm" | "select" | "input";
/**
 * The value a user gave in an extension dialog: a boolean for `confirm`, the
 * chosen option for `select`, the typed text for `input`. Absent when the
 * dialog closed without an answer.
 */
export type ExtensionDialogAnswer = boolean | string;
/**
 * Why a dialog stopped being open. `"answered"` carries an
 * {@link ExtensionDialogAnswer}; every other reason is a close without one.
 */
export type ExtensionDialogCloseReason = "answered" | "cancelled" | "timeout" | "aborted" | "session-ended";
/**
 * One open extension dialog of a session, opened by `ctx.ui.confirm()`,
 * `ctx.ui.select()`, or `ctx.ui.input()`. Daemon-owned and reported in
 * {@link SessionStatus.pendingDialogs}, so a reconnecting or reloading browser
 * rehydrates it without depending on having seen the `dialog.opened` event.
 *
 * Unlike asks, several dialogs may be open per session at once: each dialog is
 * an independent blocking wait inside extension code, so opening never
 * supersedes an existing one.
 */
export interface PendingExtensionDialog {
    dialogId: string;
    kind: ExtensionDialogKind;
    title: string;
    /** Supporting line of a `confirm` dialog. */
    message?: string;
    /** Offered choices of a `select` dialog. */
    options?: string[];
    /** Placeholder text of an `input` dialog. */
    placeholder?: string;
    askedAt: string;
    /**
     * When the dialog auto-cancels, as ISO: the sooner of the extension's own
     * `timeout` and the daemon's `extensionDialogsTimeoutMs` default. Absent
     * when the dialog waits forever.
     */
    timeoutAt?: string;
    /** Opened while a run was in flight, so `agent_end` settles it as `"aborted"`. */
    runScoped: boolean;
}
/**
 * The complete result of a closed extension dialog. Unlike an ask outcome it
 * stays small — the dialog itself is not embedded, because a settled card is a
 * browser-local record that stays until the user dismisses it; reloads
 * rehydrate open dialogs from {@link SessionStatus.pendingDialogs} alone.
 */
export interface ExtensionDialogOutcome {
    dialogId: string;
    reason: ExtensionDialogCloseReason;
    /** Present only when `reason` is `"answered"`. */
    answer?: ExtensionDialogAnswer;
    askedAt: string;
    closedAt: string;
}
/**
 * Browser request to answer an open extension dialog with the user's value.
 * `cwd` rides along as the standard session-lookup field, as on every other
 * session route; whether the value fits the dialog's kind is the store's call,
 * so an ill-fitting answer is a 400 that leaves the dialog open.
 */
export interface ExtensionDialogAnswerRequest {
    cwd?: string;
    dialogId: string;
    value: ExtensionDialogAnswer;
}
/** Browser request to dismiss an open extension dialog without an answer. */
export interface ExtensionDialogCancelRequest {
    cwd?: string;
    dialogId: string;
}
/**
 * Result of the browser answering or cancelling an extension dialog. Mirrors
 * {@link AskUserCloseResponse}: `"stale"` is an ordinary lost race — another
 * browser, a timeout, or a teardown closed the dialog first — not an error.
 * The browser drops its card and trusts `sessionStatus`, which is returned in
 * both cases so closing a dialog needs no follow-up status request.
 */
export interface ExtensionDialogCloseResponse {
    result: "closed" | "stale";
    /** Present only when this call is the one that closed the dialog. */
    outcome?: ExtensionDialogOutcome;
    sessionStatus: SessionStatus;
}
/**
 * Progress of the session startup window, where the daemon is still
 * constructing the agent session and no `PiAgentSession` exists yet, so
 * `activity.update` cannot be published for it.
 *
 * `startupToken` is the opaque label a create request supplied, echoed back so a
 * browser row still waiting for a session id recognises its own construction.
 * The daemon never interprets it and it never becomes the session id:
 * `activity.sessionId` always carries the real id, which is how an *open* of a
 * session the browser already knows is routed instead.
 *
 * `activity.phase === "idle"` means the startup window ended with nothing left
 * to report, so a browser that substituted its own text should restore it.
 */
export interface SessionStartupProgressEvent {
    type: "session.startup";
    startupToken?: string;
    activity: SessionActivity;
}
/**
 * A pi-native image attachment carried with a prompt. The wire format mirrors
 * pi's own `ImageContent` shape (`{ type: "image", data, mimeType }`) so these
 * attachments are compatible with native multimodal delivery after validation.
 */
export interface PromptImageAttachment {
    kind: "image";
    /** Supported image MIME type (image/png, image/jpeg, image/gif, or image/webp). */
    mimeType: string;
    /** Base64-encoded binary payload (no data: URL prefix). */
    data: string;
    /** Optional original filename, used for previews and folder-mode filenames. */
    name?: string;
}
/** A general file attachment that must be saved into the workspace before use. */
export interface PromptFileAttachment {
    kind: "file";
    /** Non-empty IANA MIME type (for example "application/pdf"). */
    mimeType: string;
    /** Base64-encoded binary payload (no data: URL prefix). Empty for zero-byte files. */
    data: string;
    /** Optional original filename, used for previews and folder-mode filenames. */
    name?: string;
}
export type PromptAttachment = PromptImageAttachment | PromptFileAttachment;
/**
 * How prompt attachments should be delivered to the session.
 * - "inline": send the binary to pi as native image content (multimodal input).
 * - "folder": save the file into the workspace and reference it from the prompt
 *   text so the agent reads it with its own tools.
 */
export type PromptAttachmentDelivery = "inline" | "folder";
export interface SavedPromptAttachment {
    /** Workspace-relative path the attachment was written to. */
    path: string;
    mimeType: string;
    size: number;
}
export interface SessionModel {
    provider?: string;
    id?: string;
    name?: string;
    contextWindow?: number;
    reasoning?: unknown;
}
export type { ThinkingLevel } from "./thinkingLevels.js";
export type AuthType = "oauth" | "api_key";
export type AuthStatusSource = "stored" | "runtime" | "environment" | "fallback" | "models_json_key" | "models_json_command";
export interface AuthProviderStatus {
    configured: boolean;
    source?: AuthStatusSource;
    label?: string;
}
export interface AuthProviderOption {
    id: string;
    name: string;
    authType: AuthType;
    status: AuthProviderStatus;
    /** Additive hint: use the generic AuthInteraction transport instead of the legacy one-secret form. */
    loginFlow?: "interactive";
}
export interface AuthProvidersResponse {
    providers: AuthProviderOption[];
}
export interface OAuthFlowState {
    flowId: string;
    providerId: string;
    providerName: string;
    status: "running" | "complete" | "error" | "cancelled";
    auth?: {
        url: string;
        instructions?: string;
        deviceCode?: {
            userCode: string;
            intervalSeconds?: number;
            expiresInSeconds?: number;
        };
    };
    prompt?: {
        requestId: string;
        message: string;
        placeholder?: string;
        allowEmpty?: boolean;
        /** Additive semantic detail; legacy peers continue to use `kind`. */
        promptType?: "text" | "secret" | "manual_code";
        kind: "prompt" | "manual";
    };
    select?: {
        requestId: string;
        message: string;
        options: CommandOption[];
    };
    progress: string[];
    info?: {
        message: string;
        links?: {
            url: string;
            label?: string;
        }[];
    }[];
    error?: string;
}
export interface ModelSelectionResponse {
    models: SessionModel[];
}
export interface ThinkingLevelsResponse {
    levels: string[];
}
export type SessionWarningSeverity = "info" | "warning" | "error";
/**
 * A live, runtime-scoped warning surfaced to the browser (skill/resource
 * diagnostics, extension load errors, subscription-auth billing notice, etc.).
 *
 * Warnings are recomputed whenever the runtime is (re)built inside sessiond and
 * are not persisted chat messages. `source` is an optional short origin label
 * (e.g. `"skill"`, `"extension"`, `"anthropic"`); `path` carries a related file
 * path when the warning came from a resource diagnostic.
 *
 * `dismiss` is present only when the warning has a durable, first-class
 * off-switch in the underlying `pi` agent (not a UI-only hide). Its `id` is the
 * opaque token the server maps back to that suppression; the client renders a
 * dismiss control for any warning carrying it, without knowing what it means.
 */
export interface SessionWarning {
    severity: SessionWarningSeverity;
    message: string;
    source?: string;
    path?: string;
    dismiss?: {
        id: string;
    };
}
export interface AutomaticAdmissionRequest {
    sessionId: string;
    cwd: string;
    generation: string;
    kind: "wake" | "recovery" | "resume";
}
export type RecoveryAuthority = { kind: "engine-policy"; policyId: "enrolled-prefix-v1"; enrollmentId: string };
export type StreamRetryDisposition = {
    version: 1; sessionId: string; cwd: string;
    failure: { entryId: string; sha256: string };
    identity: { provider: string; model: string; thinking: string; generation: string };
    attempt: number; delayMs: 5000;
} & ({ state: "pending"; phase: "scheduled" | "attempting" } | { state: "resolved"; completion: { entryId: string; sha256: string } } | { state: "superseded"; input: { entryId: string; sha256: string } } | { state: "terminal" | "cancelled" | "uncertain"; detail?: string; reason?: "new-input" });
export interface SessionFailureBoundary {
    enrollment?: { id: string; policyId: "enrolled-prefix-v1"; role: string; assignment: string; assignmentSha256: string; generation: string };
    parking?: { generation: string; owned: boolean };
    version: 1;
    sessionId: string;
    cwd: string;
    stream: string;
    root: string;
    state: "watching" | "parked" | "uncertain" | "recovering";
    recovery?: {
        id: string;
        originalSessionId: string;
    };
    checkpoint?: {
        entryId: string;
        sha256: string;
    };
    failure?: {
        entryId: string;
        sha256: string;
        kind: string;
    };
    detail?: string;
}
export type FailureRecoveryOperation = {
    version: 1;
    id: string;
    episode: string;
    originalSessionId: string;
    cwd: string;
    root: string;
    stream: string;
    checkpoint: {
        entryId: string;
        sha256: string;
    };
    failure: {
        entryId: string;
        sha256: string;
        kind: string;
    };
    maintenance?: {
        id: string;
        expectedGeneration: string;
        phase: "preparing" | "ready" | "uncertain";
        generation?: string;
        sync?: {
            text: string;
            deliveryId: string;
            state: "sending" | "ended" | "uncertain";
        };
    };
    intentSha256: string;
    generation: string;
    state: "fork-sending" | "forked" | "cancelled" | "uncertain";
    forkSessionId?: string;
    forkFile?: string;
    forkGeneration?: string;
    detail?: string;
    authority: RecoveryAuthority;
    continuation: { role: string; assignment: string; assignmentSha256: string };
};
export interface FailureMaintenanceResult {
    operation: FailureRecoveryOperation;
    automaticAdmission: AutomaticAdmissionState;
    maintenance?: SessionMaintenance;
    events?: {
        id: string;
        entryId: string | null;
        closed?: true;
    };
}
export interface SessionControlGoal {
    version: 1;
    id: string;
    sessionId: string;
    cwd: string;
    runId: string;
    sequence: number;
    text: string;
    potetoGoal: string;
    automaticAdmission: AutomaticAdmissionRequest;
    state: "queued" | "sending" | "ended" | "uncertain" | "superseded";
    detail?: string;
}
export type AutomaticAdmissionControlRequest = { cwd?: string } & (
    | { allowed: true; initializeIfAbsent: true; expectedGeneration?: never }
    | { allowed: boolean; expectedGeneration?: string; initializeIfAbsent?: never }
);
export interface AutomaticAdmissionState {
    sessionId: string;
    cwd: string;
    generation: string;
    allowed: boolean;
    durable: boolean;
}
export interface ExpectedIdleCheckpoint {
    sessionId: string;
    cwd: string;
    entryId: string;
    generation: string;
}
export interface MaintenanceInput {
    id: string;
    sequence: number;
    text: string;
    kind: "steer" | "followUp";
    images: {
        type: "image";
        data: string;
        mimeType: string;
    }[];
    attachments: PromptAttachment[];
    echoUserMessage: boolean;
    generation: string;
    potetoGoal?: string;
    state: "queued" | "sending" | "admitted" | "uncertain" | "cancelled";
}
export interface SessionResumeObservation {
    kind: "assistant-stop";
    entryId: string;
    sha256: string;
    deliveryId: string;
    compactionEntryId: string;
    userEntryId: string;
    userSha256?: string;
    assistantEntryId: string;
    assistantSha256: string;
}
export interface FailureRetirement {
    version: 1;
    id: string;
    originalSessionId: string;
    forkSessionId: string;
    cwd: string;
    operation: FailureRecoveryOperation;
    observation: SessionResumeObservation;
    originalFile: string;
    cacheFile: string;
    originalLeaf: string;
    model: {
        provider: string;
        id: string;
        thinking: string;
    };
    sourceSha256: string;
    sourceBase64: string;
    state: "prepared" | "archive-sending" | "archived" | "delete-sending" | "deleted" | "released" | "uncertain";
    archive?: {
        sessionId: string;
        cwd: string;
        originalPath: string;
        archivePath: string;
        archivedAt: string;
    };
    deleted?: {
        sessionId: string;
        archivePath: string;
        sourceSha256: string;
    };
    release?: {
        entryId: string;
        sha256: string;
    };
}
export type FailureRetirementReceipt = Omit<FailureRetirement, "sourceBase64">;
export interface SessionMaintenance {
    targetTokens: 150000;
    tokensBefore: number;
    tokensAfter?: number;
    version: 1;
    id: string;
    sessionId: string;
    cwd: string;
    entryId: string;
    generation: string;
    instructions: string;
    state: "prepared" | "compacting" | "complete" | "failed" | "uncertain" | "superseded" | "resuming" | "resumed";
    inputSequence: number;
    lastInputGeneration: string;
    inputs: MaintenanceInput[];
    cancelledByStop?: boolean;
    retirement?: FailureRetirement;
    markerEntryId?: string;
    compactionEntryId?: string;
    compactionSha256?: string;
    detail?: string;
    resume?: {
        deliveryId: string;
        text: string;
        generation: string;
        inputSequence: number;
        potetoGoal?: string;
        state: "sending" | "admitted" | "uncertain";
        observation?: SessionResumeObservation;
    };
}
export interface RotationSafety {
    callbackOwners?: { path: string; sourceSha256: string; kind: "none" | "safe-to-drop" | "active" | "unknown"; revision: string; owners: string[] }[];
    callbackRevision?: string;
    entryId: string | null;
    callbacksKnown: boolean;
    callbackInventory: "native-and-extension-v1";
    nativeChildCallbacks: string[];
    unprovenCallbacks: string[];
}
export interface SessionStatus {
    sessionId: string;
    automaticAdmission?: AutomaticAdmissionState;
    rotationSafety?: RotationSafety;
    maintenanceSupport?: "checkpoint-input-v1";
    maintenanceTargetSupport?: "below-150000-v1";
    recoveryReadinessSupport?: "same-provider-v1";
    resumeObservationSupport?: "completed-assistant-v1";
    potetoInvocationSupport?: "exact-goal-v1";
    dcrEventSupport?: "phase-v1";
    failureMaintenanceSupport?: "operation-scoped-v1";
    failureRetirementSupport?: "singular-original-v1";
    failureForkSupport?: "engine-prefix-v1";
    engineFailureRecoverySupport?: "enrolled-prefix-v1";
    cleanPolicyAnalysisSupport?: "clean-policy-analysis-v1";
    streamRetrySupport?: "entry-bound-v1";
    streamRetry?: StreamRetryDisposition;
    failureBoundarySupport?: "persisted-turn-v1";
    failureBoundary?: SessionFailureBoundary;
    controlGoalSupport?: "preserve-ask-v1";
    conditionalAdmissionSupport?: "generation-cas-v1";
    recoveryControlSupport?: "question-safe-v1";
    controlGoal?: SessionControlGoal;
    /** True when the server has verified a backing session file exists; false when known transient. */
    persisted?: boolean;
    model?: SessionModel;
    thinkingLevel?: string;
    isStreaming: boolean;
    isCompacting: boolean;
    isBashRunning: boolean;
    pendingMessageCount: number;
    queuedMessages: QueuedSessionMessage[];
    messageCount?: number;
    tokens: {
        input: number;
        output: number;
        cacheRead: number;
        cacheWrite: number;
        total: number;
    };
    cost: number;
    contextUsage?: {
        tokens: number | null;
        contextWindow: number;
        percent: number | null;
    };
    /**
     * Live, runtime-scoped warnings for this session (skill/resource diagnostics,
     * extension load errors, Anthropic subscription-auth billing notice, etc.).
     * Recomputed on each status read from the current runtime; absent/empty when
     * there are none. See {@link SessionWarning}.
     */
    warnings?: SessionWarning[];
    /**
     * The session's open `ask_user` question set, when one is waiting for the
     * user. Daemon-owned, so it survives browser reload and web/API restarts.
     */
    pendingAsk?: PendingAskUser;
    /**
     * The session's open extension dialogs, oldest first, when any are waiting
     * for the user. Daemon-owned, so they survive browser reload and web/API
     * restarts. Several may be open at once; the UI presents them as a queue.
     */
    pendingDialogs?: PendingExtensionDialog[];
}
export interface WorkspaceActivity {
    cwd: string;
    hasSessionActivity: boolean;
    hasTerminalActivity: boolean;
    updatedAt: string;
}
export interface WorkspaceActivityResponse {
    workspaces: WorkspaceActivity[];
    generatedAt: string;
}
export interface SlashCommand {
    name: string;
    description?: string;
    source: "extension" | "prompt" | "skill" | "builtin";
}
export interface FileSuggestion {
    path: string;
    kind: "tracked" | "untracked" | "other";
}
export interface FileTreeEntry {
    name: string;
    path: string;
    type: "file" | "directory" | "symlink";
    size?: number;
    modifiedAt?: string;
}
export interface FileTreeResponse {
    path: string;
    entries: FileTreeEntry[];
    scannedAt: string;
    truncated: boolean;
}
export type FileContentMediaType = "image";
export interface FileContentResponse {
    path: string;
    language?: string;
    mediaType?: FileContentMediaType;
    mimeType?: string;
    encoding: "utf8";
    size: number;
    modifiedAt: string;
    content: string;
    truncated: boolean;
    binary: boolean;
}
export interface WriteWorkspaceFileOptions {
    createDirs?: boolean;
    overwrite?: boolean;
}
export interface WriteWorkspaceFileResponse {
    path: string;
    size: number;
    modifiedAt: string;
    created: boolean;
}
export interface DeleteWorkspaceFileResponse {
    path: string;
    existed: boolean;
}
export interface MoveWorkspaceFileOptions {
    createDirs?: boolean;
    overwrite?: boolean;
}
export interface MoveWorkspaceFileResponse {
    fromPath: string;
    toPath: string;
    size: number;
    modifiedAt: string;
}
export type GitFileState = "unmodified" | "modified" | "added" | "deleted" | "renamed" | "copied" | "untracked" | "ignored" | "conflicted";
export interface GitStatusFile {
    path: string;
    oldPath?: string;
    index: GitFileState;
    workingTree: GitFileState;
    submoduleFromCommit?: string;
    submoduleToCommit?: string;
}
export interface GitStatusResponse {
    isGitRepo: boolean;
    hash: string;
    branch?: string;
    upstream?: string;
    ahead?: number;
    behind?: number;
    files: GitStatusFile[];
    submodules: string[];
}
export interface GitDiffResponse {
    path?: string;
    staged: boolean;
    hash: string;
    diff: string;
    truncated: boolean;
}
export interface TerminalInfo {
    id: string;
    cwd: string;
    name: string;
    createdAt: string;
    exited: boolean;
    exitCode?: number;
    commandRunId?: string;
}
export type TerminalCommandRunStatus = "queued" | "running" | "succeeded" | "failed";
export interface TerminalCommandRun {
    id: string;
    origin: string;
    projectId: string;
    workspaceId: string;
    terminalId: string;
    title: string;
    command: string;
    status: TerminalCommandRunStatus;
    exitCode?: number;
    createdAt: string;
    startedAt?: string;
    completedAt?: string;
    metadata: Record<string, string>;
}
export interface RunTerminalCommandInput {
    workspace: Workspace;
    title: string;
    command: string;
    metadata?: Record<string, string>;
    open?: boolean;
}
export interface TerminalCommandRunHandle {
    run: TerminalCommandRun;
    completed: Promise<TerminalCommandRun>;
}
export interface TerminalCommandRunFilter {
    projectId?: string;
    workspaceId?: string;
    terminalId?: string;
    statuses?: TerminalCommandRunStatus[];
    metadata?: Record<string, string>;
}
export type PiWebServiceComponent = "web" | "sessiond";
export type PiWebStatusSeverity = "info" | "warning" | "error";
export type PiWebInstallationKind = "pi-package" | "npm-global" | "local" | "docker" | "unknown";
export type PiWebDockerMode = "runtime" | "dev";
export interface PiWebInstallationInfo {
    kind: PiWebInstallationKind;
    path?: string;
    source?: string;
    scope?: "user" | "project";
    npmRoot?: string;
    dockerMode?: PiWebDockerMode;
}
export interface PiWebComponentStatus {
    component: PiWebServiceComponent;
    label: string;
    runtimeVersion?: string;
    installedVersion?: string;
    stale: boolean;
    available: boolean;
    installation?: PiWebInstallationInfo;
    error?: string;
}
/** Secret-free identity of the Pi-compatible CLI/state profile fixed for one sessiond lifetime. */
export interface ActiveAgentProfileDescriptor {
    readonly schemaVersion: 1;
    readonly revision: string;
    readonly command: string;
    readonly dir: string;
    readonly sessionDirEnvKeys: readonly string[];
}
export interface PiWebRuntimeComponent {
    component: PiWebServiceComponent;
    label: string;
    runtimeVersion?: string;
    available: boolean;
    capabilities: PiWebCapability[];
    /** Present only for a session daemon that supports active-profile reporting. */
    activeAgentProfile?: ActiveAgentProfileDescriptor;
    error?: string;
}
export interface PiWebReleaseStatus {
    packageName: string;
    latestVersion?: string;
    updateAvailable: boolean;
    checkedAt?: string;
    skipped?: boolean;
    error?: string;
}
export interface PiWebStatusMessage {
    id: string;
    severity: PiWebStatusSeverity;
    title: string;
    body: string;
    command?: string;
}
export interface PiWebVersionResponse {
    packageName: string;
    generatedAt: string;
    components: {
        web: PiWebComponentStatus;
        sessiond: PiWebComponentStatus;
    };
}
export interface PiWebRuntimeResponse {
    packageName: string;
    generatedAt: string;
    components: {
        web: PiWebRuntimeComponent;
        sessiond: PiWebRuntimeComponent;
    };
    capabilities: PiWebCapability[];
}
export interface PiWebStatusResponse extends PiWebVersionResponse {
    release: PiWebReleaseStatus;
    commands: {
        update?: string;
        restart?: string;
        restartWeb?: string;
        restartSessiond?: string;
        status?: string;
    };
    messages: PiWebStatusMessage[];
}
export type TerminalUiEvent = {
    type: "terminal.created";
    terminal: TerminalInfo;
} | {
    type: "terminal.exited";
    terminal: TerminalInfo;
} | {
    type: "terminal.closed";
    terminalId: string;
    cwd: string;
};
export interface WorkspaceActivityUiEvent {
    type: "workspace.activity";
    activity: WorkspaceActivity;
}
export interface CommandOption {
    value: string;
    label: string;
    description?: string;
}
export type SessionTreeNodeKind = "user" | "assistant" | "tool-result" | "bash" | "custom-message" | "compaction" | "branch-summary" | "model-change" | "thinking-level-change" | "session-info" | "label" | "custom" | "other";
export interface SessionTreeNode {
    id: string;
    parentId: string | null;
    kind: SessionTreeNodeKind;
    summary: string;
    timestamp?: string;
    label?: string;
}
export interface SessionTreeSnapshot {
    /** Pre-order, parent-linked projection of all retained roots and descendants. */
    nodes: SessionTreeNode[];
    activeLeafId: string | null;
    /** Root-to-leaf IDs for explicit, non-color-only active-path rendering. */
    activePathIds: string[];
}
export declare const SESSION_TREE_CUSTOM_INSTRUCTIONS_MAX_LENGTH = 10000;
export type SessionTreeSummaryChoice = {
    mode: "none";
} | {
    mode: "default";
} | {
    mode: "custom";
    instructions: string;
};
export interface SessionTreeNavigateRequest {
    targetId: string;
    /** Leaf shown when the navigator opened; null is valid for an empty/root position. */
    expectedLeafId: string | null;
    summary: SessionTreeSummaryChoice;
}
export type SessionTreeNavigateResult = {
    cancelled: false;
    editorText?: string;
} | {
    cancelled: true;
    aborted?: boolean;
};
export interface MessagePage {
    messages: unknown[];
    start: number;
    total: number;
}
/**
 * Join-time snapshot of a session's in-flight assistant stream. `seq` is the
 * `SessionEventHub` watermark captured together with `partial` in a single tick,
 * so a joining client can seed `partial` and then apply only buffered live events
 * with `seq > snapshot.seq` (exactly-once). `partial` is a browser-projected
 * in-flight `AssistantMessage` (thinking signatures stripped), or `null` when the
 * session is not mid assistant-message stream.
 */
export interface SessionStreamSnapshot {
    seq: number;
    /** Browser-projected in-flight `AssistantMessage`, or `null` when idle. */
    partial: unknown;
}
export type CommandResult = {
    type: "done";
    message?: string;
    session?: SessionInfo;
    promptDraft?: string;
} | {
    type: "select";
    requestId: string;
    title: string;
    options: CommandOption[];
} | {
    type: "tree";
    tree: SessionTreeSnapshot;
} | {
    type: "unsupported";
    message: string;
};
/**
 * Transport-level per-session sequence stamp. `SessionEventHub.publish` assigns a
 * monotonic `seq` to every per-session event as it is serialized to the socket.
 * Clients use it as a watermark against the join-time stream snapshot so buffered
 * live events are applied exactly once. Existing consumers may ignore it.
 */
export type SessionUiEvent = SessionUiEventBody & {
    seq?: number;
};
type SessionUiEventBody = {
    type: "message.append";
    message: unknown;
} | {
    type: "assistant.delta";
    text: string;
} | {
    type: "assistant.thinking.delta";
    text: string;
} | {
    type: "tool.start";
    toolName: string;
    toolCallId: string;
    summary: string;
    args?: unknown;
} | {
    type: "tool.update";
    toolName: string;
    toolCallId: string;
    text: string;
    content?: unknown;
    details?: unknown;
} | {
    type: "tool.end";
    toolName: string;
    toolCallId: string;
    text: string;
    isError: boolean;
    content?: unknown;
    details?: unknown;
} | {
    type: "shell.start";
    command: string;
    excludeFromContext?: boolean;
} | {
    type: "shell.chunk";
    chunk: string;
} | {
    type: "shell.end";
    output?: string;
    exitCode?: number | null;
    cancelled?: boolean;
    truncated?: boolean;
    fullOutputPath?: string;
    isError?: boolean;
} | {
    type: "agent.start";
} | {
    type: "agent.end";
} | {
    type: "message.end";
    message?: unknown;
} | {
    type: "status.update";
    status: SessionStatus;
} | {
    type: "activity.update";
    activity: SessionActivity;
} | {
    type: "command.output";
    level: "info" | "success" | "error";
    message: string;
    notificationId?: string;
} | SessionNotificationInboxEvent | {
    type: "session.error";
    message: string;
} | {
    type: "ask.opened";
    ask: PendingAskUser;
} | {
    type: "ask.closed";
    askId: string;
    reason: AskUserCloseReason;
} | {
    type: "dialog.opened";
    dialog: PendingExtensionDialog;
} | {
    type: "dialog.closed";
    dialogId: string;
    reason: ExtensionDialogCloseReason;
    answer?: ExtensionDialogAnswer;
} | {
    type: "session.name";
    sessionId: string;
    name?: string;
} | {
    type: "session.created";
    session: SessionInfo;
} | {
    type: "pi.event";
    eventType: string;
};
export type GlobalSessionEvent = Extract<SessionUiEventBody, {
    type: "status.update" | "activity.update" | "session.name" | "session.created";
}> | SessionNotificationSummaryEvent | SessionUnreadEvent | SessionStartupProgressEvent;
export type RealtimeEvent = GlobalSessionEvent | TerminalUiEvent | WorkspaceActivityUiEvent;
