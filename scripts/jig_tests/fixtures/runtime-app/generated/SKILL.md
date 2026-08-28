---
name: jig-verification
description: Drive the fixture notes process through its public client and preserve runtime evidence. Use before and after changes to the fixture.
---

# Fixture verification

## Launch

Run `python3 .pi/skills/jig-verification/helpers/fixture-control.py launch`. It starts one loopback process with disposable state.

## Doctor

Run `python3 .pi/skills/jig-verification/helpers/fixture-control.py doctor`. Require build `fixture-v1` and the run-owned data directory.

## Drive

Run `python3 .pi/skills/jig-verification/helpers/fixture-control.py drive`. It uses `client.py`, the public user surface.

## Evidence

Run `python3 .pi/skills/jig-verification/helpers/fixture-control.py evidence`. Preserve action and result JSON after cleanup.

## Cleanup

Run `python3 .pi/skills/jig-verification/helpers/fixture-control.py cleanup`. It checks the recorded PID and process start identity. It never kills by name.

## Helpers

Run `python3 .pi/skills/jig-verification/helpers/fixture-control.py self-test` for Launch, Doctor, Drive, Evidence, and Cleanup in one proof.
