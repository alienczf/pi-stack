# Lexicon style

`lexicon.md` is explanation, not a glossary. A tired agent should learn the nouns by reading one page of running prose.

Write 5 to 12 nouns that already exist in THIS tree. Each noun is defined by its relation to the others. Include one negative. You import X from Y. You do not import Z.

Dune's public fragment has this shape. Copy the shape, not the nouns.

A Feature is one user-visible capability and its code lives in one directory. A Feature talks to the Host only through an Entrypoint. The Client renders TranscriptCards. The Host owns the thread. Nothing in a Feature imports Host internals. You import `thread` from the Host barrel. You do not reach into `host/src/thread/callbacks.ts`.

A bullet list of names with no relationships fails this file. Synonyms are the bug. Pick one noun and plan the rename.

Do not invent Feature, Client, Host, Entrypoint, or TranscriptCard unless those words already name things in this repo.
