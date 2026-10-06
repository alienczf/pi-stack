---
name: stream
description: Start, check or close a pi-streams stream. Close gets a handover from every open thread and copies lasting knowledge into the project's context before it runs pi-streams close. Use only for /skill:stream or /stream with new, status or close.
disable-model-invocation: true
---

# Stream

The arguments are `new <id>`, `status [<id>]` or `close <id>`. Pass any extra flags ZF gives to every `pi-streams` call.

## New and status

Run `pi-streams new <id>`. Report the pi-web URL and the coordinator's session id it prints. The kickoff interview waits for ZF in that session.

Run `pi-streams status [<id>]` and report its output unchanged.

## Close

Paths here are relative to the stream folder. Prompt threads only with `pi-web-cli prompt --steer <session> TEXT`. Then poll `pi-web-cli status <session>` in one shell loop. Stop when `isStreaming` is false, `pendingMessageCount` is 0 and `messageCount` has grown since the prompt, or when a `pendingAsk` appears. Answer a pending ask from STREAM.md and DECISIONS.md with `pi-web-cli answer <session> <askId> <questionId> TEXT`, or pass it to ZF. Never open or resume a thread's session to check on it.

1. Run `pi-streams status <id> --json` to find the stream folder and its threads.
2. Prompt each thread that is not archived and has no `handover/<role>.md` with this text, then wait until the file exists:
   `Write <stream folder>/handover/<role>.md and leave it uncommitted. Follow pstack's poteto-mode/playbooks/pause-safely.md: your intent, what you did with proof, what is left, and what the next agent should know. Then stop.`
   Never write a thread's handover yourself.
3. Read every handover. Copy only lasting knowledge into the project's `../context/` files: how to test a repo, gotchas, and ZF's preferences. Keep each entry short. Update an existing entry instead of adding a duplicate, and list any new file in `../context/README.md`.
4. For a mistake that repeated across threads, start a thread in that repo with `pi-streams thread spawn <id> --repo NAME --role correct-NAME --note TEXT`, where TEXT names the mistake and the handovers that show it. Prompt it with pstack's `/skill:correct`, wait, then get its handover as in step 2.
5. For a thread that fought one problem repeatedly, prompt it with pstack's `/skill:reflect` and wait. Reflect stops for approval, so read its last reply with `pi-web-cli messages <session>`, show it to ZF, and send ZF's choice back.
6. Run `pi-streams close <id>`. It archives the threads, marks you, the coordinator, done, and commits, so commit nothing yourself. If it refuses or stops on a busy thread, fix what it names and run it again.
7. Report each context entry you added or changed with its file, the reflect and correct results with any PR links, and the close output.
