import { AutomaticAdmissionRejected, parseAutomaticAdmission, validControlGoalInvocation } from "./automaticAdmissionStore.js";
function ref(session) { return { id: session.sessionId, cwd: session.sessionManager.getCwd() }; }
function record(value) { return typeof value === "object" && value !== null && !Array.isArray(value); }
export class SessionControlGoalController {
    constructor(controls, host) {
        this.controls = controls;
        this.host = host;
        this.running = new Map();
        this.scheduled = new Set();
        this.abandoned = new WeakMap();
        this.unavailable = new WeakSet();
        this.fallback = new WeakMap();
    }
    goal(session) {
        return this.fallback.get(session) ?? this.controls.controlGoal(ref(session));
    }
    pending(session) {
        return this.running.has(session);
    }
    async submit(session, value) {
        if (!record(value))
            throw new AutomaticAdmissionRejected("Control goal must be an object");
        const body = value;
        if (body["attachments"] !== undefined || body["images"] !== undefined)
            throw new AutomaticAdmissionRejected("Current-goal control accepts only its exact automatic text, not human attachments");
        const automatic = parseAutomaticAdmission(body["automaticAdmission"]);
        if (automatic === undefined || typeof body["id"] !== "string" || body["id"].trim() === "" || typeof body["runId"] !== "string" || body["runId"].trim() === "" || !Number.isSafeInteger(body["sequence"]) || Number(body["sequence"]) < 1 || typeof body["potetoGoal"] !== "string" || body["potetoGoal"].trim() === "" || typeof body["text"] !== "string" || !validControlGoalInvocation(body["text"], body["potetoGoal"], automatic.kind))
            throw new AutomaticAdmissionRejected("Control goal requires its exact identity, transport sequence, invocation and saved generation");
        this.controls.assertCurrent(ref(session), automatic);
        if (!this.host.current(session) || this.host.maintenanceOwns(session))
            throw new AutomaticAdmissionRejected("Maintenance or another runtime owns admission; retain the current goal intent");
        if (this.abandoned.get(session)?.has(body.id))
            throw new AutomaticAdmissionRejected("Abandoned control goal cannot be replayed");
        let goal = { version: 1, id: body.id, runId: body.runId, sequence: Number(body.sequence), sessionId: session.sessionId, cwd: session.sessionManager.getCwd(), text: body.text, potetoGoal: body.potetoGoal, automaticAdmission: automatic, state: "queued" };
        if (!this.unavailable.has(session)) {
            try { goal = await this.controls.saveControlGoal(ref(session), goal); }
            catch (error) {
                if (error instanceof AutomaticAdmissionRejected) throw error;
                this.unavailable.add(session);
            }
        }
        if (this.unavailable.has(session)) {
            const previous = this.fallback.get(session);
            if (previous?.id === goal.id) {
                if (JSON.stringify([previous.text, previous.potetoGoal, previous.automaticAdmission, previous.runId, previous.sequence]) !== JSON.stringify([goal.text, goal.potetoGoal, goal.automaticAdmission, goal.runId, goal.sequence]))
                    throw new AutomaticAdmissionRejected("Control goal identity changed intent");
                return previous;
            }
        }
        this.fallback.set(session, goal);
        this.notify(session);
        return goal;
    }
    async status(session, id) {
        let goal = this.goal(session);
        if (goal?.id !== id)
            throw new AutomaticAdmissionRejected("Control goal is absent or superseded");
        if (goal.state === "queued") {
            try { this.controls.assertCurrent(ref(session), goal.automaticAdmission); }
            catch (error) { await this.abandon(session, goal, String(error)); goal = this.goal(session); }
        }
        if ((goal.state === "sending" || goal.state === "uncertain") && this.running.get(session) !== id) {
            await this.abandon(session, goal, "Lost sender abandoned without replay");
            goal = this.goal(session) ?? { ...goal, state: "superseded" };
        }
        return goal;
    }
    async change(session, goal, change) {
        if (!this.unavailable.has(session)) {
            try {
                const updated = await this.controls.updateControlGoal(ref(session), goal.id, change);
                if (updated !== undefined && this.fallback.get(session)?.id === goal.id) this.fallback.set(session, updated);
                return updated;
            }
            catch (error) {
                if (error instanceof AutomaticAdmissionRejected) throw error;
                this.unavailable.add(session);
            }
        }
        const saved = this.fallback.get(session) ?? goal;
        if (saved.id !== goal.id) return undefined;
        const current = structuredClone(saved);
        change(current);
        this.fallback.set(session, current);
        return current;
    }
    async abandon(session, goal, detail) {
        const failed = this.abandoned.get(session) ?? new Set();
        failed.add(goal.id);
        this.abandoned.set(session, failed);
        if (this.fallback.get(session)?.id === goal.id || !this.fallback.has(session))
            this.fallback.set(session, { ...goal, state: "superseded", detail });
        try { await this.controls.updateControlGoal(ref(session), goal.id, current => { current.state = "superseded"; current.detail = detail; }); }
        catch { this.unavailable.add(session); }
    }
    notify(session) {
        if (this.scheduled.has(session) || this.running.has(session)) return;
        let goal;
        try { goal = this.goal(session); }
        catch { this.unavailable.add(session); return; }
        if (goal?.state !== "queued" || this.abandoned.get(session)?.has(goal.id)) return;
        this.scheduled.add(session);
        setImmediate(() => {
            this.scheduled.delete(session);
            void this.drain(session).catch(async error => {
                await this.abandon(session, goal, String(error));
                try { this.host.failure(session, String(error)); } catch {}
            });
        });
    }
    async drain(session) {
        const goal = this.goal(session);
        if (goal?.state !== "queued" || this.running.has(session)) return;
        if (!this.host.current(session) || this.host.busy(session) || this.host.humanInputPending(session) || this.host.maintenanceOwns(session)) return;
        this.running.set(session, goal.id);
        try {
            this.controls.assertCurrent(ref(session), goal.automaticAdmission);
            const sending = await this.change(session, goal, current => { current.state = "sending"; });
            if (sending === undefined) return;
            this.controls.assertCurrent(ref(session), sending.automaticAdmission);
            await this.host.send(session, sending.text, sending.potetoGoal);
            await this.change(session, sending, current => { if (current.state === "sending") current.state = "ended"; });
        }
        catch (error) {
            await this.abandon(session, goal, error instanceof Error ? error.message : String(error));
            try { this.host.failure(session, String(error)); } catch {}
        }
        finally {
            this.running.delete(session);
            try { this.host.publish(session); } catch {}
            this.notify(session);
        }
    }
}
