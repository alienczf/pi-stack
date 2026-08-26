# Interview questions

Answer from the tree. Do not ask the user. Write the answers in `.pi/jig/interview.md`.

## Original nine

1. What do people add here. Binary, library, notebook, chart, terraform, strategy, other.
2. Name three existing features and the directories they live in.
3. What does CI already fail on. Quote the workflow or Makefile target.
4. What import, alloc, or API would be a domain crime in THIS repo even if another git repo wants it.
5. Who owns which tree. One writer per value.
6. Isolated new files. Where does new work go. What existing files must stay small.
7. Narrow exceptions. List them. If you cannot find any, write "none found".
8. How do you prove a change. Exact test command, replay, or dry-run already in the repo.
9. Colocation. Does a feature live in one directory.

## Extra five

10. List candidate nouns. Group synonyms. Pick 5 to 12 canonical words that already exist in this tree. Do not invent Dune's Feature/Host if this repo is a matching engine.
11. For each canonical noun, name the directory or type that owns it, and which other nouns it is allowed to import.
12. Find placement crimes. Callbacks, hooks, timers, or subroutines that sit outside the owning package.
13. Score every id in `references/failure-modes.md`. Each id is `absent`, `present-unencoded`, or `already-guarded`. Cite a `file:line` for every `present-*` row.
14. Find files near 1000 lines, `*util*` dumping grounds, `*legacy*` / `*compat*` dual APIs, inline imports, non-exhaustive switches, `as ` / `: any`.
15. Coordinator fence. If this repo has a registry of other git paths, or scripts that `cd` elsewhere then run `pi -p`, stop treating it as a product tree. Do not open those other trees for conventions. Score them as external systems.
