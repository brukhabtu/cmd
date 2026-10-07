# cmd-dev

The Claude Code skills for working on this repository, and their evals.

A skill is added after the model has demonstrably got something wrong, never in
anticipation. Candidates are proposed at milestone boundaries and sit on the board as
drafts until the evidence exists; `docs/skills.md` has the process and the gate.

Two skills are written and not yet accepted; their board drafts are promoted only when the
gate passes on a pull request that touches this plugin (`.github/workflows/skills.yml`):

- `gpui-for-cmd`, from milestone 1's demonstrated miss in the GPUI window and the Linux
  check recipe, updated at milestone 2 with the facts the builders verified (the input
  handler's key routing, displays, the window look, assets) and a corrected display claim.
  Three cases: `evals/gpui-for-cmd-*`.
- `objc2-appkit-for-cmd`, from milestone 2's three macOS-only misses that only CI's macOS job
  could catch. Three cases: `evals/objc2-appkit-for-cmd-*`.

Each case is a question answered from an empty directory (each run starts in one), graded by
regex on the answer, with a `Skill` grader as the plugin-fired indicator.

## Layout

```
skills/<name>/SKILL.md          the skill
evals/<name>-<case>/prompt.md   one eval case: frontmatter and the prompt
evals/<name>-<case>/graders/    one grader per file: regex, tool_used, file_exists, llm
evals/results/                  written by `claude plugin eval`; ignored by git
```

## Running

```sh
claude plugin validate --strict .claude/plugins/cmd-dev
claude plugin eval .claude/plugins/cmd-dev --trust-plugin --threshold 1.0 --no-publish
```

The eval runs real agent sessions on your credential. `--ablation with-without` (the default
when the plugin resolves) also runs each case without the plugin and reports the delta, which
is the number that says whether the skill earns its place.
