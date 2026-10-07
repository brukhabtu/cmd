---
name: python-idioms
description: Bruk's Python dialect dictionary - what each construct declares to the reader, and the Python version that gates it. Use when writing, refactoring, or reviewing Python in a repository Bruk owns; when choosing between a frozen dataclass, NamedTuple, TypedDict, Enum, or a bare class, between list and tuple, comprehension and generator, match and if, or f-string and t-string; when separating logic from I/O, such as a retry loop or any function that mixes decisions with network, database, or clock calls; when deciding how to raise and document an exception; when adopting a feature from Python 3.11 through 3.15; and when asked whether code is idiomatic or says what it means.
---

# Python idioms

Read `references/idioms.md` in this skill's directory before making or reviewing the
choice in front of you. It is the whole dictionary: each construct in the house style,
what choosing it declares, and the minimum Python version it needs.

`references/yielded-effects.md` is a worked example for one entry: the dictionary's
retry handler rewritten as a generator that yields its effects. Read it only when logic
and I/O alternate too many times for a function to return one step at a time.

## Applying it

Every idiom is a claim about the code, and the claim has to be true. When choosing a
construct, ask what a reader will conclude from it and whether that conclusion holds. A
`list` that nothing mutates and a public name with no outside caller are both false
signals, and the fix is to choose the construct that tells the truth.

The dictionary is the standard for repositories I own. In a repository someone else
owns, the local dialect governs.

Check the project's `requires-python` before reaching for a version-tagged idiom. Where
an entry has a form for earlier versions, the dictionary gives it.

When an idiom makes the code harder to read, harder to change, or harder to ship, drop
the idiom.

The plugin's Python rule is the always-on subset of this dictionary. It arrives the
first time a Python file is touched in a repository I own.
