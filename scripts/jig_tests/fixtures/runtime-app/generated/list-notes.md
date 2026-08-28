# List notes

Feature ID: `list-notes`
Owner: `app.py`
Public entry point: `client.py list`
Allowed dependencies: Python standard library and the public loopback protocol.
Evidence: Public JSON list output.
Last result: Runtime self-test receipt at the current source revision.

## Sub-features

- `list-empty` returns an empty list.
- `list-saved` returns persisted notes.

## How to get to it (user POV)

- Run the public `client.py list` command.

## Driving it with fixture-control

- Doctor the endpoint, then list and parse the public JSON output.

## Gotchas

- Reading the storage file alone does not prove the public list path.
