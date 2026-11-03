import { ASK_USER_ID_MAX_LENGTH, ASK_USER_OPTION_LIMIT, ASK_USER_OTHER_TEXT_MAX_LENGTH, ASK_USER_QUESTION_LIMIT, EXTENSION_DIALOG_ID_MAX_LENGTH, EXTENSION_DIALOG_INPUT_MAX_LENGTH, SESSION_TREE_CUSTOM_INSTRUCTIONS_MAX_LENGTH, SESSION_UNREAD_CATALOG_ID_MAX_LENGTH, SESSION_UNREAD_CWD_MAX_LENGTH, SESSION_UNREAD_SESSION_ID_MAX_LENGTH } from "../../shared/apiTypes.js";
import { projectBrowserMessageResponse } from "../browserMessageProjection.js";
import { normalizeRequestCwd } from "../workingDirectory.js";
import { normalizeSessionCleanupRequest } from "./sessionCleanup.js";
import { AutomaticAdmissionRejected } from "./automaticAdmissionStore.js";
const MAX_NOTIFICATION_SESSION_ID_LENGTH = 512;
const MAX_NOTIFICATION_CWD_LENGTH = 32 * 1024;
const MAX_NOTIFICATION_DAEMON_ID_LENGTH = 512;
const MAX_NOTIFICATION_ID_LENGTH = 1024;
export function registerSessionRoutes(app, sessions, eventHub, prefix = "") {
    app.get(`${prefix}/sessions`, async (request, reply) => {
        if (request.query.cwd === undefined || request.query.cwd === "")
            return reply.code(400).send({ error: "cwd query parameter is required" });
        try {
            return await sessions.list(normalizeRequestCwd(request.query.cwd));
        }
        catch (error) {
            return reply.code(400).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            // An opaque label the caller uses to recognise its own construction's
            // startup reports. Optional: only a browser row waiting for a session id
            // has anything to correlate.
            const startupToken = body["startupToken"] === undefined ? undefined : requireNonEmptyString(body, "startupToken");
            return await sessions.start(normalizeRequestCwd(requireString(body, "cwd")), optionalField("startupToken", startupToken));
        }
        catch (error) {
            return reply.code(400).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/notifications`, async (_request, reply) => {
        try {
            return await sessions.notificationCatalog();
        }
        catch (error) {
            return reply.code(400).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/unread`, async (_request, reply) => {
        try {
            return await sessions.unreadCatalog();
        }
        catch (error) {
            return reply.code(503).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/unread/acknowledge`, async (request, reply) => {
        let sessionId;
        let acknowledgement;
        try {
            const body = requireRecord(request.body);
            sessionId = requireNonEmptyBoundedString(request.params.sessionId, "sessionId", SESSION_UNREAD_SESSION_ID_MAX_LENGTH);
            acknowledgement = {
                cwd: normalizeRequestCwd(requireNonEmptyBoundedString(body["cwd"], "cwd", SESSION_UNREAD_CWD_MAX_LENGTH)),
                catalogId: requireNonEmptyBoundedString(body["catalogId"], "catalogId", SESSION_UNREAD_CATALOG_ID_MAX_LENGTH),
                throughCompletionOrder: requirePositiveSafeInteger(body["throughCompletionOrder"], "throughCompletionOrder"),
            };
        }
        catch (error) {
            return reply.code(400).send({ error: errorMessage(error) });
        }
        try {
            return await sessions.acknowledgeUnread(sessionId, acknowledgement);
        }
        catch (error) {
            return reply.code(503).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/cleanup/preview`, async (request, reply) => {
        try {
            return await sessions.cleanupPreview(normalizeSessionCleanupRequest(optionalRecord(request.body)));
        }
        catch (error) {
            return reply.code(400).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/cleanup`, async (request, reply) => {
        try {
            return await sessions.cleanup(normalizeSessionCleanupRequest(optionalRecord(request.body)));
        }
        catch (error) {
            return reply.code(400).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/bulk/archive`, async (request, reply) => {
        try {
            return await sessions.archiveMany(bulkMutationRefsFromBody(request.body));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/bulk/delete-archived`, async (request, reply) => {
        try {
            return await sessions.deleteArchivedMany(bulkMutationRefsFromBody(request.body));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/notifications`, async (request, reply) => {
        try {
            return await sessions.notificationInbox(notificationRefFromQuery(request.params.sessionId, request.query));
        }
        catch (error) {
            return reply.code(notificationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/notifications/dismiss`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            const ref = notificationRefFromBody(request.params.sessionId, body);
            return await sessions.dismissNotification(ref, {
                daemonInstanceId: requireNonEmptyBoundedString(body["daemonInstanceId"], "daemonInstanceId", MAX_NOTIFICATION_DAEMON_ID_LENGTH),
                notificationId: requireNonEmptyBoundedString(body["notificationId"], "notificationId", MAX_NOTIFICATION_ID_LENGTH),
            });
        }
        catch (error) {
            return reply.code(notificationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/notifications/dismiss-all`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            const ref = notificationRefFromBody(request.params.sessionId, body);
            return await sessions.dismissAllNotifications(ref, {
                daemonInstanceId: requireNonEmptyBoundedString(body["daemonInstanceId"], "daemonInstanceId", MAX_NOTIFICATION_DAEMON_ID_LENGTH),
                throughOrder: requireNonNegativeSafeInteger(body["throughOrder"], "throughOrder"),
                throughOverflowWatermark: requireNonNegativeSafeInteger(body["throughOverflowWatermark"], "throughOverflowWatermark"),
            });
        }
        catch (error) {
            return reply.code(notificationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/messages`, async (request, reply) => {
        try {
            const page = { ...optionalField("before", optionalNumber(request.query.before)), ...optionalField("limit", optionalNumber(request.query.limit)) };
            const messages = await sessions.messages(sessionLookupFromQuery(request.params.sessionId, request.query), page);
            return projectBrowserMessageResponse(messages);
        }
        catch (error) {
            return reply.code(404).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/status`, async (request, reply) => {
        try {
            return await sessions.status(sessionLookupFromQuery(request.params.sessionId, request.query));
        }
        catch (error) {
            return reply.code(404).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/stream-snapshot`, async (request, reply) => {
        try {
            return await sessions.streamSnapshot(sessionLookupFromQuery(request.params.sessionId, request.query));
        }
        catch (error) {
            return reply.code(404).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/models`, async (request, reply) => {
        try {
            return { models: await sessions.availableModels(sessionLookupFromQuery(request.params.sessionId, request.query)) };
        }
        catch (error) {
            return reply.code(404).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/model`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            return await sessions.setModel(sessionLookupFromBody(request.params.sessionId, body), requireString(body, "provider"), requireString(body, "modelId"));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/model/cycle`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            const direction = body["direction"];
            if (direction !== undefined && direction !== "forward" && direction !== "backward")
                throw new Error("direction must be forward or backward");
            return await sessions.cycleModel(sessionLookupFromBody(request.params.sessionId, body), direction ?? "forward");
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/thinking-levels`, async (request, reply) => {
        try {
            return { levels: await sessions.availableThinkingLevels(sessionLookupFromQuery(request.params.sessionId, request.query)) };
        }
        catch (error) {
            return reply.code(404).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/thinking-level`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            // The level string is validated against the session's live available levels
            // in the service, so it stays correct if pi changes the set.
            return await sessions.setThinkingLevel(sessionLookupFromBody(request.params.sessionId, body), requireThinkingLevel(body["level"]));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/thinking-level/cycle`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            return await sessions.cycleThinkingLevel(sessionLookupFromBody(request.params.sessionId, body));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/commands`, async (request, reply) => {
        try {
            return await sessions.commands(sessionLookupFromQuery(request.params.sessionId, request.query));
        }
        catch (error) {
            return reply.code(404).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/prompt`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            const deliveryId = body["deliveryId"];
            const automaticAdmission = body["automaticAdmission"];
            const potetoGoal = body["potetoGoal"];
            if (deliveryId === undefined && automaticAdmission === undefined) {
                if (potetoGoal === undefined)
                    await sessions.prompt(sessionLookupFromBody(request.params.sessionId, body), body["text"], body["streamingBehavior"], body["attachments"]);
                else
                    await sessions.prompt(sessionLookupFromBody(request.params.sessionId, body), body["text"], body["streamingBehavior"], body["attachments"], { potetoGoal });
                return { accepted: true };
            }
            if (typeof deliveryId !== "string" || deliveryId.trim() === "")
                throw new Error("deliveryId must be a nonempty string");
            await sessions.prompt(sessionLookupFromBody(request.params.sessionId, body), body["text"], body["streamingBehavior"], body["attachments"], { deliveryId, ...(automaticAdmission === undefined ? {} : { automaticAdmission }), ...(potetoGoal === undefined ? {} : { potetoGoal }) });
            return { accepted: true, deliveryId };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/failure-recovery/retire`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.retireFailure === undefined)
                throw new AutomaticAdmissionRejected("Scoped original retirement is unavailable");
            return await sessions.retireFailure(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/failure-recovery/maintenance`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.failureMaintenance === undefined)
                throw new AutomaticAdmissionRejected("Operation-scoped recovery maintenance is unavailable");
            return await sessions.failureMaintenance(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/failure-recovery/readiness`, async (request, reply) => {
        try {
            if (sessions.recoveryReadiness === undefined)
                throw new AutomaticAdmissionRejected("Safe recovery readiness is unavailable");
            return await sessions.recoveryReadiness(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.query)));
        } catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/failure-recovery/fork`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.forkFailureAtCheckpoint === undefined)
                throw new AutomaticAdmissionRejected("Exact engine-owned failure fork is unavailable");
            return await sessions.forkFailureAtCheckpoint(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error), ...(error instanceof AutomaticAdmissionRejected && error.admission ? { admission: error.admission } : {}) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/failure-boundary`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.watchFailureBoundary === undefined)
                throw new AutomaticAdmissionRejected("Persisted failure boundary capability is unavailable");
            return await sessions.watchFailureBoundary(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/control-goal`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.controlGoal === undefined)
                throw new AutomaticAdmissionRejected("Question-preserving current-goal control is unavailable");
            return await sessions.controlGoal(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/control-goal/:deliveryId`, async (request, reply) => {
        try {
            if (sessions.controlGoalStatus === undefined)
                throw new AutomaticAdmissionRejected("Question-preserving current-goal control is unavailable");
            return await sessions.controlGoalStatus(sessionLookupFromBody(request.params.sessionId, request.query), request.params.deliveryId);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/maintenance/events/watch`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.watchStreamsDcr === undefined)
                throw new AutomaticAdmissionRejected("Native DCR event capability is unavailable");
            return await sessions.watchStreamsDcr(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/maintenance/events/close`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.unwatchStreamsDcr === undefined)
                throw new AutomaticAdmissionRejected("Native DCR event capability is unavailable");
            return await sessions.unwatchStreamsDcr(sessionLookupFromBody(request.params.sessionId, body), requireString(body, "id"));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/maintenance/compact`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.compactAtCheckpoint === undefined)
                throw new AutomaticAdmissionRejected("Durable maintenance capability is unavailable");
            return await sessions.compactAtCheckpoint(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/maintenance/:operationId`, async (request, reply) => {
        try {
            if (sessions.maintenanceStatus === undefined)
                throw new AutomaticAdmissionRejected("Durable maintenance capability is unavailable");
            return await sessions.maintenanceStatus(sessionLookupFromQuery(request.params.sessionId, request.query), request.params.operationId);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/maintenance/:operationId/reconcile`, async (request, reply) => {
        try {
            if (sessions.reconcileMaintenance === undefined)
                throw new AutomaticAdmissionRejected("Durable maintenance capability is unavailable");
            return await sessions.reconcileMaintenance(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)), request.params.operationId);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/maintenance/resume`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (sessions.resumeAtMaintenance === undefined)
                throw new AutomaticAdmissionRejected("Durable maintenance capability is unavailable");
            return await sessions.resumeAtMaintenance(sessionLookupFromBody(request.params.sessionId, body), body);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/automatic-admission`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            if (typeof body["allowed"] !== "boolean")
                throw new Error("allowed must be a boolean");
            if (sessions.setAutomaticAdmission === undefined)
                throw new AutomaticAdmissionRejected("Durable automatic admission capability is unavailable");
            if (body["expectedGeneration"] !== undefined)
                return await sessions.setAutomaticAdmission(sessionLookupFromBody(request.params.sessionId, body), body["allowed"], body["expectedGeneration"]);
            return await sessions.setAutomaticAdmission(sessionLookupFromBody(request.params.sessionId, body), body["allowed"]);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/queue/clear`, async (request, reply) => {
        try {
            return await sessions.clearQueue(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/ask/submit`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            const askId = requireBoundedId(body["askId"], "askId");
            return await sessions.submitAsk(sessionLookupFromBody(request.params.sessionId, body), askId, askUserSubmissionFromBody(body));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/ask/cancel`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            return await sessions.cancelAsk(sessionLookupFromBody(request.params.sessionId, body), requireBoundedId(body["askId"], "askId"));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/dialogs/answer`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            const answer = extensionDialogAnswerFromBody(body);
            return await sessions.answerDialog(sessionLookupFromBody(request.params.sessionId, body), answer.dialogId, answer.value);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/dialogs/cancel`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            const cancel = extensionDialogCancelFromBody(body);
            return await sessions.cancelDialog(sessionLookupFromBody(request.params.sessionId, body), cancel.dialogId);
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/warnings/dismiss`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            return await sessions.dismissWarning(sessionLookupFromBody(request.params.sessionId, body), requireString(body, "dismissId"));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/attachments`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            const folder = body["folder"];
            if (folder !== undefined && typeof folder !== "string")
                throw new Error("folder field must be a string");
            const attachments = await sessions.saveAttachments(sessionLookupFromBody(request.params.sessionId, body), body["attachments"], folder);
            return { attachments };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/shell`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            await sessions.shell(sessionLookupFromBody(request.params.sessionId, body), requireString(body, "text"));
            return { accepted: true };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/commands/run`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            return await sessions.runCommand(sessionLookupFromBody(request.params.sessionId, body), requireString(body, "text"));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/commands/respond`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            return await sessions.respondToCommand(sessionLookupFromBody(request.params.sessionId, body), requireString(body, "requestId"), requireString(body, "value"));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/tree/navigate`, async (request, reply) => {
        try {
            const body = requireRecord(request.body);
            return await sessions.navigateTree(sessionLookupFromBody(request.params.sessionId, body), sessionTreeNavigateRequestFromBody(body));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/abort`, async (request, reply) => {
        try {
            await sessions.abort(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)));
            return { aborted: true };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/stop`, async (request, reply) => {
        try {
            await sessions.stop(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)));
            return { stopped: true };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/archive`, async (request, reply) => {
        try {
            const body = optionalRecord(request.body);
            const ref = sessionLookupFromBody(request.params.sessionId, body);
            if (body["expectedIdle"] === undefined) {
                await sessions.archive(ref);
                return { archived: true };
            }
            if (sessions.archiveAtCheckpoint === undefined)
                throw new AutomaticAdmissionRejected("Replacement checkpoint capability is unavailable");
            const frozen = await sessions.archiveAtCheckpoint(ref, body["expectedIdle"]);
            return { archived: true, automaticAdmission: frozen };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/archive-tree`, async (request, reply) => {
        try {
            return await sessions.archiveTree(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)));
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/restore`, async (request, reply) => {
        try {
            await sessions.restore(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)));
            return { restored: true };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.delete(`${prefix}/sessions/:sessionId`, async (request, reply) => {
        try {
            await sessions.deleteArchived(sessionLookupFromQuery(request.params.sessionId, request.query));
            return { deleted: true };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/reload`, async (request, reply) => {
        try {
            await sessions.reload(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)));
            return { reloaded: true };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.post(`${prefix}/sessions/:sessionId/detach-parent`, async (request, reply) => {
        try {
            await sessions.detachParent(sessionLookupFromBody(request.params.sessionId, optionalRecord(request.body)));
            return { detached: true };
        }
        catch (error) {
            return reply.code(mutationErrorStatus(error)).send({ error: errorMessage(error) });
        }
    });
    app.get(`${prefix}/sessions/:sessionId/events`, { websocket: true }, (socket, request) => {
        // Only the id matters for event subscription; cwd is intentionally ignored
        // so a malformed value cannot throw inside the websocket handler.
        eventHub.add(request.params.sessionId, socket);
    });
    app.get(`${prefix}/sessions/events`, { websocket: true }, (socket) => {
        eventHub.addGlobal(socket);
    });
    app.get(`${prefix}/events`, { websocket: true }, (socket) => {
        eventHub.addGlobal(socket);
    });
}
function bulkMutationRefsFromBody(body) {
    const record = requireRecord(body);
    const sessions = record["sessions"];
    if (!Array.isArray(sessions))
        throw new Error("sessions field must be an array");
    return sessions.map(parseBulkMutationRef);
}
function parseBulkMutationRef(value) {
    const record = requireRecord(value);
    const id = requireString(record, "id").trim();
    if (id === "")
        throw new Error("id field must not be empty");
    const cwd = record["cwd"];
    if (cwd === undefined || cwd === "")
        return { id };
    if (typeof cwd !== "string")
        throw new Error("cwd field must be a string");
    return { id, cwd: normalizeRequestCwd(cwd) };
}
function notificationRefFromQuery(id, query) {
    const cwd = requireNonEmptyBoundedString(query.cwd, "cwd", MAX_NOTIFICATION_CWD_LENGTH);
    return notificationRef(id, cwd);
}
function notificationRefFromBody(id, body) {
    const cwd = requireNonEmptyBoundedString(body["cwd"], "cwd", MAX_NOTIFICATION_CWD_LENGTH);
    return notificationRef(id, cwd);
}
function notificationRef(id, cwd) {
    return {
        id: requireNonEmptyBoundedString(id, "sessionId", MAX_NOTIFICATION_SESSION_ID_LENGTH),
        cwd: normalizeRequestCwd(cwd),
    };
}
function sessionLookupFromQuery(id, query) {
    return sessionLookupFromCwd(id, query.cwd);
}
function sessionLookupFromBody(id, body) {
    const cwd = body["cwd"];
    if (cwd === undefined || cwd === "")
        return id;
    if (typeof cwd !== "string")
        throw new Error("cwd field must be a string");
    return { id, cwd: normalizeRequestCwd(cwd) };
}
function sessionLookupFromCwd(id, cwd) {
    // Legacy id-only lookups (no cwd) remain supported; a supplied cwd is
    // normalized here so everything past the route layer sees canonical paths.
    return cwd === undefined || cwd === "" ? id : { id, cwd: normalizeRequestCwd(cwd) };
}
function sessionTreeNavigateRequestFromBody(body) {
    const targetId = requireNonEmptyString(body, "targetId");
    const expectedLeafId = requireNullableString(body, "expectedLeafId");
    return { targetId, expectedLeafId, summary: sessionTreeSummaryChoice(body["summary"]) };
}
function sessionTreeSummaryChoice(value) {
    const summary = requireRecord(value);
    const mode = requireString(summary, "mode");
    if (mode === "none" || mode === "default") {
        if (Object.hasOwn(summary, "instructions"))
            throw new Error(`instructions field is not valid for ${mode} summary mode`);
        requireExactFields(summary, ["mode"], "summary");
        return { mode };
    }
    if (mode === "custom") {
        requireExactFields(summary, ["mode", "instructions"], "summary");
        const instructions = requireString(summary, "instructions");
        if (instructions.trim() === "")
            throw new Error("instructions field must not be blank");
        if (instructions.length > SESSION_TREE_CUSTOM_INSTRUCTIONS_MAX_LENGTH) {
            throw new Error(`instructions field must be at most ${String(SESSION_TREE_CUSTOM_INSTRUCTIONS_MAX_LENGTH)} characters`);
        }
        return { mode, instructions: instructions.trim() };
    }
    throw new Error("summary mode is invalid");
}
function requireExactFields(record, fields, label) {
    const allowed = new Set(fields);
    const unexpected = Object.keys(record).find((field) => !allowed.has(field));
    if (unexpected !== undefined)
        throw new Error(`${label} field contains unsupported property: ${unexpected}`);
}
/**
 * Shape-check one submitted answer set. Only transport-level checks belong here:
 * whether the answers fit the questions that were actually asked is the pending
 * ask store's job, since only it knows the open ask.
 */
function askUserSubmissionFromBody(body) {
    const answers = body["answers"];
    if (!Array.isArray(answers))
        throw new Error("answers field must be an array");
    if (answers.length > ASK_USER_QUESTION_LIMIT)
        throw new Error("answers field has too many entries");
    return { answers: answers.map(askUserAnswerFromValue) };
}
function askUserAnswerFromValue(value) {
    const record = requireRecord(value);
    const values = record["values"];
    if (!Array.isArray(values))
        throw new Error("values field must be an array");
    if (values.length > ASK_USER_OPTION_LIMIT)
        throw new Error("values field has too many entries");
    const otherText = record["otherText"];
    if (otherText !== undefined && typeof otherText !== "string")
        throw new Error("otherText field must be a string");
    if (typeof otherText === "string" && otherText.length > ASK_USER_OTHER_TEXT_MAX_LENGTH)
        throw new Error("otherText field is too long");
    return {
        id: requireBoundedId(record["id"], "id"),
        values: values.map((entry) => requireBoundedId(entry, "values entry")),
        ...(otherText === undefined ? {} : { otherText }),
    };
}
function requireBoundedId(value, field) {
    return requireNonEmptyBoundedString(value, field, ASK_USER_ID_MAX_LENGTH);
}
/**
 * Shape-check one dialog answer. Only transport-level checks belong here:
 * whether the value fits the answered dialog's kind is the pending dialog
 * store's job, since only it knows the open dialog.
 */
function extensionDialogAnswerFromBody(body) {
    const dialogId = requireNonEmptyBoundedString(body["dialogId"], "dialogId", EXTENSION_DIALOG_ID_MAX_LENGTH);
    const value = body["value"];
    if (typeof value === "boolean")
        return { dialogId, value };
    if (typeof value === "string") {
        if (value.length > EXTENSION_DIALOG_INPUT_MAX_LENGTH)
            throw new Error("value field is too long");
        return { dialogId, value };
    }
    throw new Error("value field must be a string or a boolean");
}
function extensionDialogCancelFromBody(body) {
    return { dialogId: requireNonEmptyBoundedString(body["dialogId"], "dialogId", EXTENSION_DIALOG_ID_MAX_LENGTH) };
}
function optionalRecord(value) {
    if (value === undefined || value === null)
        return {};
    return requireRecord(value);
}
function requireRecord(value) {
    if (!isRecord(value))
        throw new Error("request body must be an object");
    return value;
}
function requireString(record, field) {
    const value = record[field];
    if (typeof value !== "string")
        throw new Error(`${field} field must be a string`);
    return value;
}
function requireNonEmptyString(record, field) {
    const value = requireString(record, field);
    if (value.trim() === "")
        throw new Error(`${field} field must not be empty`);
    return value;
}
function requireNullableString(record, field) {
    if (!Object.hasOwn(record, field))
        throw new Error(`${field} field is required`);
    const value = record[field];
    if (value === null)
        return null;
    if (typeof value !== "string")
        throw new Error(`${field} field must be a string or null`);
    if (value.trim() === "")
        throw new Error(`${field} field must not be empty`);
    return value;
}
function requireNonEmptyBoundedString(value, field, maxLength) {
    if (typeof value !== "string")
        throw new Error(`${field} field must be a string`);
    if (value === "")
        throw new Error(`${field} field must not be empty`);
    if (value.length > maxLength)
        throw new Error(`${field} field is too long`);
    return value;
}
function requireNonNegativeSafeInteger(value, field) {
    if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
        throw new Error(`${field} field must be a non-negative safe integer`);
    }
    return value;
}
function requirePositiveSafeInteger(value, field) {
    const parsed = requireNonNegativeSafeInteger(value, field);
    if (parsed === 0)
        throw new Error(`${field} field must be positive`);
    return parsed;
}
function requireThinkingLevel(value) {
    if (typeof value !== "string" || value === "")
        throw new Error("level field is invalid");
    return value;
}
function optionalField(key, value) {
    return value === undefined ? {} : { [key]: value };
}
function optionalNumber(value) {
    if (value === undefined || value === "")
        return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
}
function errorMessage(error) {
    return error instanceof Error ? error.message : String(error);
}
function mutationErrorStatus(error) {
    if (error instanceof AutomaticAdmissionRejected)
        return 409;
    return isSessionNotFoundError(error) ? 404 : 400;
}
function notificationErrorStatus(error) {
    return isSessionNotFoundError(error) ? 404 : 400;
}
function isSessionNotFoundError(error) {
    const message = errorMessage(error);
    return message === "Session not found" || message === "Archived session not found";
}
function isRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
//# sourceMappingURL=sessionRoutes.js.map