Steer 2 from Grok Bot, 2026-10-24 ~08:35 SGT. ZF has now done an interactive openai-codex login for Prime on options-01, but in the track 6 clean test home, not in your preserved runtime: HOME=/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home, Prime agent dir under that HOME at pi-stack-merged-poc-test/prime/agent (auth.json holds an openai-codex entry). Decision (G41): run your live checks against that authenticated runtime in place.

Do now, in /home/alphalab/Projects/worktrees/pi-stack-prime-cli:
1. Point your inference verification script from 20-prime-cli-design.md at that runtime by environment only (HOME and/or the Prime agent-dir variable). Never copy, move, print or edit auth.json or any credential, and never log in yourself. Use a fresh Prime session; do not reuse or touch track 6's sessions, streams or daemon. Start your own daemon if needed, on its own socket, and stop it when done.
2. Run real inference on openai-codex/gpt-6.1-sol at xhigh, then the off-host wrapper check from the design doc as far as it can run on the host (Grok Bot runs the box side; write the exact box command into 20).
3. Record the evidence (commands, outputs, pass or fail) in 20-prime-cli-design.md, and commit any code fix on feat/prime-cli with a regression test. No push.

On a usage limit, stop and report it; never switch provider or model. Keep context lean.

Finish with one line: TRACK 2 STATUS: <working|blocked|done> | artifact=<path> | next=<one line>.
