# Track 6 steer 1 (Grok Bot, 2026-10-24 08:05 SGT): model defaults (G40) + login done (G39)

Keep working on feat/merged-poc in your worktree. Two updates.

1. **ZF's Codex login is done (G39).** The clean test home `HOME=/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home` now has an `openai-codex` login (Prime said "Logged in to ChatGPT Plus/Pro (Codex Subscription)"; onboarding flags set in its settings.json). The live end-to-end check can run now. Don't print or copy the auth file.

2. **New model defaults (ZF t239u, verbatim): "default to sol xhigh 61 for streams and Luna xhigh 6 for all stream workers."**
   - Stream (coordinator) sessions default to `openai-codex/gpt-6.1-sol`, thinking `xhigh`.
   - All stream workers default to `openai-codex/gpt-6-luna`, thinking `xhigh` (id taken from `prime-agent model list` in the test home; its catalog entry maps xhigh).
   Make these the defaults in feat/merged-poc: the stream session spawn path, the worker handover/kickoff spawn path, the install/config defaults the installer writes, and the docs (README/install doc and anything stating the test model). Keep them overridable the way the current model setting is. Add a test that fails if either default changes (stream spawn gets Sol 6.1 xhigh; worker spawn gets Luna 6 xhigh). Commit it.
   Use these defaults in the upcoming live end-to-end check (stream on Sol 6.1 xhigh, workers on Luna 6 xhigh), and record the models used in 13-track-6-progress.md.

Everything else in briefs/track-6.md stands. Finish line unchanged: a `TRACK 6 STATUS:` line with branch@sha, suite, install and e2e results.
