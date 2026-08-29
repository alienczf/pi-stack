# Create note

Feature ID: `create-note`
Owner: `app.py`
Public entry point: `client.py add`
Allowed dependencies: Python standard library and the public loopback protocol.
Evidence: Action, public list output, and persisted notes JSON.
Last result: Runtime self-test receipt at the current source revision.

Run python3 client.py add --title "Release" --body "Ship it" using the launched fixture.
The public list command returns the saved Release note.
Capture the add command, list output, and persisted notes.json bytes.
Stop only the exact process recorded by the verification run and remove its disposable data.
Complete within five seconds.

## Sub-features

- `create-save` stores a title and body.
- `create-persist` survives a second public read.

## How to get to it (user POV)

- Run the public `client.py add` command against the launched endpoint.

## Driving it with fixture-control

- Launch, doctor, add `Release`, list notes, and inspect persisted JSON.

## Gotchas

- An HTTP success without the public list and persisted file is incomplete proof.
