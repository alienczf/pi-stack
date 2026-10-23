#!/usr/bin/env bash
# Pull track artifacts from options-01, mirror them to /workspace/harness-program, and commit+push the docs branch.
# Box-only. Uses options-01-ssh without --ensure-tg (G15). It never prints tokens and never merges.
set -euo pipefail
M=/workspace/harness-program; R=/workspace/audit-pi-stack; H=/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program
for f in 10-pi-streams-fix-catalog.md 11-artifact-map.md 12-track-1-progress.md 20-prime-cli-design.md 30-research-designs.md 30a-external-corpus.md 31-design-a-detailed.md 40-b-over-prime.md 41-design-b-prime-detailed.md 42-design-b-prime-unchanged.md 50-a-vs-b.md 51-design-merged.md; do
  if options-01-ssh "test -f $H/$f"; then options-01-ssh --scp-from "$H/$f" "$M/$f" >/dev/null; fi
done
cd "$R"; git checkout -q docs/harness-program; git pull -q --ff-only origin docs/harness-program || true
mkdir -p docs/harness-program/briefs
cp "$M"/[0-9]*.md "$M"/STATUS.md "$M"/collect.sh docs/harness-program/; cp "$M"/briefs/*.md docs/harness-program/briefs/; rm -f docs/harness-program/briefs/_common.md
git add docs/harness-program
if ! git diff --cached --quiet; then
  git -c user.name="Grok Bot (pi-bot)" -c user.email="alienczf@users.noreply.github.com" commit -qm "${1:-docs(harness-program): collect track artifacts}"
  git -c credential.helper= -c credential.helper=/home/box/.config/pi-bot/git-credential-pi-bot push -q origin docs/harness-program
  git log --oneline -1
else echo "no changes"; fi
