---
id: DRAFT-3
title: 'Skill: objc2 and AppKit from Rust in cmd'
status: Draft
assignee: []
created_date: '2026-10-07 10:53'
updated_date: '2026-10-07 12:04'
labels:
  - size-2
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Evidence from milestone 2
Two demonstrated misses, both caught only by CI's macOS job, since Linux cannot compile the macOS-only module: in crates/cmd-app/src/icons.rs (task 1.24), downcast_ref on an element of NSArray::iter() failed with E0515, because objc2-foundation 0.3's iter() yields owned Retained values, not references (fixed with Retained::downcast in bfb6a05); and the fix then named objc2::rc::Retained, which the app cannot import because objc2 is only a transitive dependency (fixed by inferring the type in 6b3f8e6). Each miss cost a CI round trip of about two minutes plus a push.

## What the skill would carry
objc2 0.6 and objc2-foundation/objc2-app-kit 0.3 facts as this repository uses them: NSArray iteration yields Retained, downcast versus downcast_ref, which crates are direct dependencies of cmd-app and how to add one target-specifically, unsafe constants such as NSFontWeightRegular, and that the only compile of this code is the macOS CI job, so every change goes up in its own small push and is checked there before anything stacks on it.

## Eval cases it must pass
1. 'Iterate an NSArray of NSImageRep and keep the NSBitmapImageRep ones' -> regex for downcast (not downcast_ref) on owned values.
2. 'Use Retained in crates/cmd-app' -> llm grader: the answer says objc2 must be added as a direct macOS-only dependency or the type inferred.
3. 'How do I check AppKit code in this repository from Linux?' -> regex for the macOS CI job.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Third demonstrated miss, 2026-10-07 11:19: the bundle task's macOS-only become_accessory (cfg target_os = macos) failed clippy's doc_markdown on CI (LSUIElement, PopUp, NSPanel unquoted in its doc comment), which the Linux scratch clippy cannot see because the item is compiled out there. Fixed in ea337f6. Pattern across all three: code under cfg(target_os = "macos") is never linted or compiled before CI, so the skill should carry the habit of quoting Apple type names in docs, the objc2 facts above, and pushing such code alone so CI's macOS job checks it before anything stacks on it.

Built on branch skills-milestone-2 as .claude/plugins/cmd-dev/skills/objc2-appkit-for-cmd/SKILL.md with three cases (downcast of owned NSArray elements, the target-specific dependency table, checking cfg(macos) code through CI's macOS job). Promote only when the eval gate passes on a pull request.

Merged into ccr-16512bde-x72oqp by pull request #1 (merge commit fa389ae) at the owner's request, before the eval gate could run: the repository has no Claude credential secret. Not accepted and not promoted: the gate is owed once the secret exists (re-run skills.yml by workflow_dispatch).
<!-- SECTION:NOTES:END -->
