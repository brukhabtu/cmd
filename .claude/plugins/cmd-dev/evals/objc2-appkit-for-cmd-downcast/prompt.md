---
plugins: ["../.."]
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
tags: [appkit]
---

In the cmd launcher's macOS-only Rust code (objc2 0.6, objc2-foundation 0.3, objc2-app-kit 0.3), I have `let pages = NSBitmapImageRep::imageRepsWithData(&tiff);`, an `NSArray<NSImageRep>`. I want a Vec of only the pages that are `NSBitmapImageRep`, to read `pixelsWide()` from each. Write the Rust.
