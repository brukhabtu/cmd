---
name: work-loop
description: Use whenever a task is too big for a handful of tool calls. How Bruk sizes, splits, delegates, and closes development work - one loop of understand, size, do or split, then check and learn, on a Backlog.md board. Use when writing down an intent for a piece of work, accepting a draft, planning or sequencing multi-step work, writing a task's plan, before spawning subagents or picking a model or effort level for one, when work turns out bigger than expected, when deciding whether a task can close, and when driving a long run with /goal.
---

# How we work

A way of thinking about development work, not a checklist. Use judgment about how much
of it a given task needs. If the whole thing fits in a handful of tool calls, do it
yourself: no board, no delegation, no separate verifier. The shape that scales is one
loop applied at every level: understand, size, then do or split, then check and learn.
Split work re-enters the same loop.

## Principles

**Understand before doing.** Work is easier when we can say what finished looks like.
If that's hard to write down, that's a signal to investigate first, and the investigation
is worthwhile work in its own right. At the top of a piece of work, the person who has
the problem writes it down in their own terms: the problem, the outcome they want, what
must not break, and the questions still open. That is the intent, and it is the root
task on the board. The same things get answered again at each level below it, down to
the plan for a single change.

**Size is about predictability.** Think in complexity, unknowns, and risk rather than time.
Large work tends to get split not because small pieces are faster but because they land
where we expect. When unknowns dominate, spiking first usually pays for itself. Open
questions are unknowns, so they count in the size. A question that blocks the work is
usually a task of its own, a spike or a design, and what it delivers is the answer
written down.

**Keep the plan visible.** Prefer a board over memory. Tasks with acceptance criteria and
stated blockers make the work reviewable while it's still cheap to change course, and the
board is what survives a compacted context. A task with no blockers is implicitly saying
it can start now and won't collide with anything.

**Accepting is a separate decision from starting.** Before work is split or begun,
someone checks that it's understood well enough: the finish line is something a reviewer
could check, and each open question is either answered or carried forward on purpose.
The size can pick who that is, the same way it picks model and effort: the person doing
the work when it's small, a lead when the risk is higher. This is the cheapest review
there is, because changing course here is editing a sentence.

**Delegate for scale, not for company.** Subagents earn their cost on sizeable,
independent tracks of work. One agent is better than several when one will do, and work
you can finish yourself isn't worth handing off.

**Decide the order.** Let dependencies drive sequencing. Parallelism is a choice worth
making deliberately, and isolation is what that choice costs.

**Closing is a separate decision from doing.** The person who did the work checks it as
they go; that's expected and doesn't need to be asked for. Whether the task closes is a
different question, answered once by someone who didn't do the work, from the acceptance
criteria and the evidence. Ask that reviewer to report everything and filter afterwards.
A parent stays open while its children are. When they're done, the parent closes against
its own finish line, so the root closes on the outcome its author asked for and not on
the list of things that got built.

**The scope is the deliverable.** Deliver what the task asks for, completely, and leave
the rest alone. Something else worth doing that turns up along the way is a new task on
the board, not a change to make now.

**Treat stuck as information.** Work that turns out bigger than expected is worth
stopping on, with a proposed split, rather than pushing through. That's a good moment for
a human to look. A plan that no longer matches the work is the same signal: note a small
drift on the task, and stop on a large one.

**Let learning outlive the task.** Discoveries are more useful as tests, rules, or docs
than as chat, and they go on the board as follow-ups rather than into the current change.
Unknowns that surfaced are worth writing back to the task so the next sizing is better.
A finish line that changes after the work under it has started is worth counting,
because it says the understanding was thinner than it looked.

**Run long work against a stated finish, with a ceiling.** One end condition per piece of
work, judged on what's actually visible, and a budget so it can't run forever. Say what
you're doing as you go; a quiet run is an unverifiable one.

## Tools that fit this

- Backlog.md for the board: `--type` for the kind of node, a draft for work nobody has
  accepted yet, `--ac` for the finish line, `--dep` with a reason, labels for size,
  `--plan` and `--append-notes` for the record, new tasks for follow-ups. What each key
  means is in `references/board-frontmatter.md`. Read it before creating or editing a
  task.
- Markdown in the repo for all of it: intents, tasks, and plans. A person and an agent
  read the same file, and git keeps the history. Anything that has to appear in another
  system is written out from the markdown by a tool, and the markdown stays the source.
- A leaf's plan: the files that change go in `modified_files`, and `--plan` holds the
  order of work, the risks, and the proof. Plan mode is a good way to write one before
  any edit.
- A Claude interview to draft an intent with someone who isn't an engineer. They correct
  it before anyone accepts it.
- Subagents as workers, and one read-only reviewer per task at close. Handing a worker a
  task ID and letting it read the task is usually the cleanest handoff; its report
  belongs in the task notes.
- `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` and `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` for
  the budget, so depth and fan-out are enforced rather than remembered.
- Worktrees when running work in parallel; the working tree when running sequentially.
- `/goal` to drive long runs, phrased on the board's printed state, with a turn cap.
- Effort before model: the size label can pick both. Starting points below; adjust from
  evals, not from taste.

## Model and effort by task

| Task | Model | Effort | Reason |
|---|---|---|---|
| Orchestrating, spikes, design, and leaves of size 3-5 | Opus 5.5 | high | Sizing, splitting, investigating, and multi-file work that has to land whole |
| Leaf, size 1-2 | Sonnet 5.5 | medium | Everyday coding; fast and cheap |
| Review at close | Opus 5.5 | low | Ask for everything, filter after |
| Mechanical sweeps: inventories, grep, file lists | Qwen 27B, local | - | Sub-agent tasks; runs on the machine, so no per-call price |

There is no model above Opus to step up to. A leaf that Opus at high still gets wrong is
stuck, and stuck is a reason to stop and split.

## Sizing

Sizing follows the same thinking as `references/story-points.md`: complexity, unknowns,
and risk, and never time. In that document, the default for a story that lands at 8 or
above is to split it before committing to it.
