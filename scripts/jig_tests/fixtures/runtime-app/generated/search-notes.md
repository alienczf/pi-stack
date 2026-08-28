# Search notes

Feature ID: `search-notes`
Owner: `app.py`
Public entry point: `client.py search`
Allowed dependencies: Python standard library and the public loopback protocol.
Evidence: Public JSON search output.
Last result: Runtime self-test receipt at the current source revision.

## Sub-features

- `search-title` finds a title.
- `search-miss` returns an empty list.

## How to get to it (user POV)

- Run the public `client.py search <query>` command.

## Driving it with fixture-control

- Add a note, search for its title, and inspect the public JSON output.

## Gotchas

- Search must not mutate the persisted note list.
