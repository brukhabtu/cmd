# Everyday use

![The launcher answering a question for the web](../assets/screenshots/websearch.png){ width="640" }

## Keys

| Keys | What they do |
|---|---|
| ++option+space++ | Show the launcher, or hide it if it is showing |
| Typing | Asks every plugin that answers the text, as you type |
| ++up++ / ++down++ | Move the selection; the list scrolls past seven rows |
| ++enter++ | Run the selected row; on a suggestion row, fill it into the input |
| ++tab++ | Complete the selected row: put its completion in the input and keep going. Rows with no completion ignore it |
| ++cmd+1++ to ++cmd+9++ | Run the first to ninth row on screen |
| ++escape++ | Hide the launcher (or cancel what an input method is composing) |
| ++cmd+backspace++ | Delete everything before the cursor |
| ++option+backspace++ | Delete the word before the cursor |
| ++left++ / ++right++ | Move the cursor; with ++option++ a word at a time, with ++cmd++ to the start or end |
| ++shift++ with any of those | Select as the cursor moves |
| ++cmd+a++, ++cmd+c++, ++cmd+v++ | Select all, copy, paste |

The launcher hides itself when you click elsewhere.

## Keywords

Some plugins answer only when the text starts with their keyword, so they stay out of the
way otherwise: `web` searches the web, `f` finds files. Others answer anything they
understand: the applications plugin answers part of an app's name, the calculator answers
arithmetic, and the system plugin answers `sleep`, `lock`, `trash` and `dark`.

![The system plugin's answer to dark](../assets/screenshots/system.png){ width="640" }

## The line under the input

A single line under the input says what is going on: a plugin's error, the background work
plugins report, which plugins are still answering, or which are still starting. When
several have something to say, the line shows the first of these:

1. A message: a plugin's error, or trouble starting plugins (in the warning colour).
2. A failed task, such as `vault: Saving capture failed`, also in the warning colour.
3. A running task, such as `search: Indexing notes 120/900`, with a detail after it when
   the plugin gives one and it fits. A task that finished shows for five seconds, then goes.
4. The plugins you are waiting on, or that are still starting.

With more than one task the line shows the most important and counts the rest: `+2`.
The line updates at most four times a second.

A failed task stays until you have seen it: it goes the next time the launcher is hidden
after it was on the line. There is no key for it, since the keys the launcher owns are
fixed (decision 4). A plugin that restarts or reloads takes its tasks off the line; it
reports them again if it still has them.

![The line under the input while the plugins start](../assets/screenshots/launcher-starting.png){ width="640" }

!!! abstract "To be written"
    Every key, mouse use, and what each message means. Tracked by the documentation epic
    (TASK-1.43).
