---
id: TASK-1.23
title: cmd.app bundle built by CI
status: In Progress
assignee: []
created_date: '2026-10-07 02:41'
updated_date: '2026-10-07 11:07'
labels:
  - size-5
milestone: m-3
dependencies:
  - TASK-1.22
parent_task_id: TASK-1
type: task
ordinal: 24000
---

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cargo-bundle or an equivalent produces cmd.app with an icon and an Info.plist that hides the Dock icon
- [ ] #2 The macOS CI job uploads the bundle as an artifact on every push to main
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. crates/cmd-app/Cargo.toml: [package.metadata.bundle] (name, identifier com.brukhabtu.cmd, SVG icon, Utility, osx minimum 12.0, info_plist_exts) and the NSApplication features on the existing objc2-app-kit entry. 2. assets/cmd.svg and assets/info-plist-extras.xml (LSUIElement). 3. main.rs: become_accessory() called first in the run closure, since GPUI sets the regular policy at launch. 4. scripts/check_bundle.py with scripts/tests/test_check_bundle.py. 5. scripts/bundle.sh: release build, cargo bundle, uv into Contents/MacOS, checks, ditto zip. 6. ci.yml app job: cached cargo-bundle, bundle.sh, upload-artifact. 7. README and docs/architecture.md. 8. File the runtime-wiring sibling task. Proof: check.sh, the scratch clippy, a debug bundle laid out on Linux and checked by check_bundle.py, and the first macOS CI run.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
From the review of decision 7: uv 0.11.32 knows no stable Python 3.15, so an automatic download during uv run fails and even the explicit install fetches a pre-release; the bundled uv must be a release that knows the 3.15 the plugins need, which means revisiting this when 3.15 is final. Also owed here, per decision 7: the arm64 uv binary size, the Python fetch time on a home connection, and the first launch of each bundled plugin.

Landed (worktree-wf_1ee14db4-a16-1): [package.metadata.bundle] in crates/cmd-app/Cargo.toml (identifier com.brukhabtu.cmd, which the owner confirms at acceptance; SVG icon; Utility; macOS 12.0 floor; info_plist_exts), assets/cmd.svg and assets/info-plist-extras.xml (LSUIElement), become_accessory() in main.rs called first in the run closure because GPUI 0.2.2 sets the regular activation policy in did_finish_launching and so overrides LSUIElement (objc2 0.6 made a direct dependency for MainThreadMarker; NSApplication, NSResponder and NSRunningApplication unioned into the existing objc2-app-kit features), scripts/check_bundle.py with scripts/tests/test_check_bundle.py (8 tests: plist values, the ICNS walk, a laid-out bundle; collection fails without the script), scripts/bundle.sh (release build, CARGO_BUNDLE_SKIP_BUILD=1 cargo bundle, uv $UV_VERSION 0.12.23 checked against its .sha256 into Contents/MacOS, plutil, PlistBuddy, uv --version, the 3.15 listing, du -sh, check_bundle.py, ditto zip), the ci.yml app job (cargo-bundle 0.12.0 cached by version, bundle.sh, upload-artifact cmd.app with if-no-files-found error; the old debug cargo build step is gone since bundle.sh builds release), README and docs/architecture.md.

Evidence on Linux: scripts/check.sh 'all checks passed'; scratch-workspace cargo clippy -p cmd-app --all-targets -D warnings exit 0 (the macOS function is cfg'd out there, so this proves only the Linux twin); in the scratch workspace, cargo build -p cmd-app (debug, not release, for disk) then CARGO_BUNDLE_SKIP_BUILD=1 cargo bundle --package cmd-app --format osx made target/debug/bundle/osx/cmd.app, and check_bundle.py --without-uv on it exits 0; its plist reads LSUIElement True, CFBundleExecutable cmd, CFBundleIconFile cmd.icns, CFBundleIdentifier com.brukhabtu.cmd, LSMinimumSystemVersion 12.0, LSApplicationCategoryType public.app-category.utilities; cmd.icns holds ic10 1024, ic09 512, ic08 256, ic11 to ic14. Without --without-uv it names the missing uv, as it should on Linux.

Owed: the first macOS CI run of this branch is the proof of both criteria and of become_accessory compiling (clippy and the release build there); then gh run download the cmd.app artifact and check file(1) reports Mach-O arm64 for cmd and uv, mode 755 on both, and check_bundle.py exits 0 on it. The .sha256 sidecar format is unverified from here; if the first run fails there, pin the hash in bundle.sh. On a Mac, a person: no Dock icon and no menu bar, the panel still taking the keyboard on Option-Space, the icon in Finder and the Dock at 16 and 32 px, opening after xattr -dr com.apple.quarantine (unsigned until 1.25), and 12.0 as a true floor. uv 0.12.23 knows only 3.15.0rc3 for darwin aarch64: re-pin UV_VERSION when a uv release lists 3.15.0. The bundle carries no plugins (decision 8: cmd plugin install), so a fresh bundle reports no plugins found; and until TASK-1.41 (the runtime wiring from decision 7, filed here) lands, an installed plugin resolves uv from launchd's PATH, not the bundle's. arm64 uv binary 35.5 MB; the bundle total comes from du -sh in the CI log. Intel Macs are not covered: the artifact is arm64 only.
<!-- SECTION:NOTES:END -->
