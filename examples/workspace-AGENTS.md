# Workspace router

This folder holds more than one git repo. It is not a product. Do not put domain rules here.

Pi still loads ancestor `AGENTS.md` files into a child cwd. Keep this file small. A fat parent poisons every child.

## Where work goes

- One git repo, one jig. `cd` into that repo and run `/skill:jig` or `jig.sh`.
- Two git repos, or two jigs. Read the cross-repo skill. Start one `pi -p` per repo with `cd "$repo"`. Do not use `playbooks/investigation.md`.
- Process and Cursor-verb mapping live in `~/.pi/agent/AGENTS.md`.

## Do not

- Do not add language or framework rules to this file.
- Do not share a lexicon across children.
- Do not edit a child tree from the parent cwd.
