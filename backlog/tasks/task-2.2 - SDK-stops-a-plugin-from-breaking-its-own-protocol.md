---
id: TASK-2.2
title: SDK stops a plugin from breaking its own protocol
status: Done
assignee: []
created_date: '2026-10-08 13:47'
updated_date: '2026-10-08 18:38'
labels:
  - size-2
dependencies: []
modified_files:
  - python/cmd-sdk/src/cmd_sdk/serve.py
  - python/cmd-sdk/src/cmd_sdk/protocol.py
parent_task_id: TASK-2
type: task
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the contract review: a stray print, a PathIcon, a NaN score and an unknown method each break a call or the next one.

- `serve` keeps the real stdout for the protocol and points sys.stdout at stderr.
- The encoder checks types and finiteness, serialises inside the guarded block with allow_nan=False, and a bad item becomes a plugin_error naming it, not a dead process.
- An unknown method is answered with the request id and a new `unknown_method` code, never id 0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A plugin that prints, returns a Path icon, a NaN or infinite score, or is sent an unknown method keeps serving, and the host gets an answer with the right id
- [x] #2 Each case has an SDK test and the adapter test still passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-08. Done in python/cmd-sdk (serve.py, protocol.py), docs/plugin-protocol.md (stdout, score, error table) and the SDK README.
- serve keeps the real stdout for the protocol and points sys.stdout at stderr while it serves (contextlib.redirect_stdout), when the sink is stdout.
- Answers are built and encoded inside the guarded block, so nothing a plugin returns can end the loop. The encoder checks types and finiteness field by field (id, title, subtitle, score, actions, icon, effects, description) and refuses NaN with allow_nan=False. A bad item becomes a plugin_error naming it: "InvalidAnswerError: item 2 ('odd'): score is nan, and must be a finite number". Text that is not valid Unicode (a file name read from bytes that were not UTF-8) is refused the same way, and an exception message holding one is escaped, since either would have raised on the write.
- An unknown method is answered with the request's id and a new unknown_method code. Beyond the task: bad_request now carries the request's id when the line had one, as docs/plugin-protocol.md already said it did (the code always sent 0, so a late error for a request the host had given up on could have been taken for the next one's).
- The Rust side needed no change: error codes are free strings (PluginError.code). The host test fixtures that send id 0 still apply, for lines with no id.
Evidence: 17 of the new functional tests fail against the SDK at HEAD (a TypeError ending the loop, a NaN on the wire, id 0 on an unknown method); all 55 SDK tests pass now; scripts/check.sh passes, including the adapter test; a real plugin process over pipes (print, a PathIcon holding a Path, a NaN score, an unknown method, then a good query) wrote strict JSON with the right ids and kept serving.
Not covered, noted on TASK-2.6: a child process a plugin starts inherits the real stdout.
Review at close, 2026-10-08: a read-only reviewer who did not do the work said close, both criteria met (55 tests pass, cargo test -p cmd-host passes, 17 new tests fail on the old SDK for the right reasons, the Rust host skips a late error with another id and still matches id 0). Its findings: sys.exit() in a plugin ended the session, and a single Action as actions or an int too large for a float escaped without naming the item. Both fixed, with tests (58 pass). Left as they are: a KeyboardInterrupt or a sink whose write raises still ends the loop, since the host has gone; the range of score is documented and not checked.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
SDK serve keeps stdout for the protocol and points print at stderr; answers are checked and encoded inside the guard, so a bad item, a NaN or infinite score, a Path icon or a plugin that exits becomes a plugin_error naming it; an unknown method is answered with its own id and the new unknown_method code, and bad_request carries the id when the line had one. Closed on review.
<!-- SECTION:FINAL_SUMMARY:END -->
