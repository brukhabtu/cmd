//! The status line's share for plugin tasks (decision 12, TASK-8), and who wins the line.
//!
//! Plugins report tasks; the host keeps the latest per task and tells the window. This is
//! the window's own copy: what to show, for how long, and what a restart takes away. It
//! is a state machine like [`crate::state`]: events in, a line out, and time is an input
//! too (every event and query carries `now`, a [`Duration`] from any fixed origin), so
//! nothing here reads a clock.

use std::collections::BTreeMap;
use std::time::Duration;

use crate::task::{Task, TaskState};

/// How long a `done` task stays on the line before it drops.
pub const DONE_FOR: Duration = Duration::from_secs(5);

/// Something that happened to the tasks.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TaskEvent {
    /// The plugin at this index, called `name`, reported `task` at time `at`. It replaces
    /// the plugin's earlier line for the same task id.
    Reported {
        plugin: usize,
        name: String,
        task: Task,
        at: Duration,
    },
    /// The plugin restarted or reloaded: its tasks are gone and it reports again.
    /// `HostEvent::Task` carries no "cleared" signal, so the window clears its copy on
    /// `Restarted` and `Reloaded` (decision 12).
    Cleared { plugin: usize },
    /// The window came up.
    Shown,
    /// The window was put away. A failed task that stood on the line while the window was
    /// up is dismissed: the first slice of dismissal, because decision 4 owns every key.
    Hidden,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct Entry {
    name: String,
    task: Task,
    at: Duration,
    /// The window was up while this failed task stood on the line, so hiding the window
    /// dismisses it. A failure that arrives while the window is hidden waits for a show.
    seen: bool,
}

/// The latest line per (plugin, task id), as the window shows them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Tasks {
    entries: BTreeMap<(usize, String), Entry>,
    shown: bool,
}

impl Default for Tasks {
    /// The window starts shown, as the view does.
    fn default() -> Self {
        Tasks {
            entries: BTreeMap::new(),
            shown: true,
        }
    }
}

/// What the tasks say, as one line.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskLine {
    /// The most important task, then `+N` for the others, then its detail. The view
    /// truncates it, so the detail goes last and is what is lost first.
    pub text: String,
    /// The line is about a failure, which is shown as a warning.
    pub failed: bool,
}

impl Tasks {
    pub fn apply(&mut self, event: TaskEvent) {
        match event {
            TaskEvent::Reported {
                plugin,
                name,
                task,
                at,
            } => {
                self.prune(at);
                let seen = self.shown && task.state == TaskState::Failed;
                self.entries.insert(
                    (plugin, task.id.clone()),
                    Entry {
                        name,
                        task,
                        at,
                        seen,
                    },
                );
            }
            TaskEvent::Cleared { plugin } => {
                self.entries.retain(|(owner, _), _| *owner != plugin);
            }
            TaskEvent::Shown => {
                self.shown = true;
                for entry in self.entries.values_mut() {
                    entry.seen |= entry.task.state == TaskState::Failed;
                }
            }
            TaskEvent::Hidden => {
                self.shown = false;
                self.entries.retain(|_, entry| !entry.seen);
            }
        }
    }

    /// Forget the `done` tasks that have been shown for [`DONE_FOR`].
    pub fn prune(&mut self, now: Duration) {
        self.entries.retain(|_, entry| entry.is_live(now));
    }

    /// The line to show at `now`: failed tasks first, then running, then done; within a
    /// kind the order is plugin, then task id, so the line does not jump between
    /// equals. The others are counted as `+N`. `None` when nothing is on show.
    pub fn line(&self, now: Duration) -> Option<TaskLine> {
        let live = || self.entries.iter().filter(|(_, entry)| entry.is_live(now));
        // `min_by_key` keeps the first of equals, and the map is in (plugin, id) order.
        let (_, entry) = live().min_by_key(|(_, entry)| entry.rank())?;
        let task = &entry.task;
        let progress = match (task.state, task.done, task.total) {
            (TaskState::Failed, ..) => " failed".to_string(),
            (_, Some(done), Some(total)) => format!(" {done}/{total}"),
            _ => String::new(),
        };
        let others = match live().count() - 1 {
            0 => String::new(),
            others => format!(" +{others}"),
        };
        let detail = task
            .detail
            .as_ref()
            .map_or_else(String::new, |detail| format!(" \u{b7} {detail}"));
        let text = format!("{}: {}{progress}{others}{detail}", entry.name, task.label);
        Some(TaskLine {
            text,
            failed: task.state == TaskState::Failed,
        })
    }

    /// How long until the line changes by itself, when a `done` task drops: when to
    /// redraw with nobody typing. `None` when nothing is waiting to expire.
    pub fn next_expiry(&self, now: Duration) -> Option<Duration> {
        self.entries
            .values()
            .filter(|entry| entry.is_live(now) && entry.task.state == TaskState::Done)
            .map(|entry| (entry.at + DONE_FOR).saturating_sub(now))
            .min()
    }
}

impl Entry {
    fn is_live(&self, now: Duration) -> bool {
        self.task.state != TaskState::Done || now < self.at + DONE_FOR
    }

    fn rank(&self) -> u8 {
        match self.task.state {
            TaskState::Failed => 0,
            TaskState::Running => 1,
            TaskState::Done => 2,
        }
    }
}

/// How a status line is coloured.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tone {
    Warning,
    Muted,
}

/// Who gets the one line under the input, first to last:
///
/// 1. `message`: start trouble, a plugin's error, an effect's text. It is what the state
///    machine holds under the input until the text changes (and what TASK-1.39 folds the
///    starting names into).
/// 2. a failed task, which stays until dismissed and is the worst thing to miss.
/// 3. running tasks (and a `done` one for its few seconds).
/// 4. `waiting`: the plugins still starting, or still owed an answer. Its logic is not
///    this function's.
///
/// A line higher up hides the ones below it only while it stands; the lower ones come
/// back when it goes. Tasks are never dropped for want of room.
pub fn status_line(
    message: Option<String>,
    tasks: Option<TaskLine>,
    waiting: Option<String>,
) -> Option<(String, Tone)> {
    match (message, tasks, waiting) {
        (Some(message), ..) => Some((message, Tone::Warning)),
        (None, Some(tasks), _) => {
            let tone = if tasks.failed {
                Tone::Warning
            } else {
                Tone::Muted
            };
            Some((tasks.text, tone))
        }
        (None, None, Some(waiting)) => Some((waiting, Tone::Muted)),
        (None, None, None) => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const T0: Duration = Duration::from_secs(100);

    fn secs(n: u64) -> Duration {
        Duration::from_secs(n)
    }

    fn task(id: &str, state: TaskState, progress: Option<(u64, u64)>) -> Task {
        Task {
            id: id.into(),
            label: format!("label {id}"),
            state,
            done: progress.map(|(done, _)| done),
            total: progress.map(|(_, total)| total),
            detail: None,
        }
    }

    fn report(tasks: &mut Tasks, plugin: usize, task: Task, at: Duration) {
        tasks.apply(TaskEvent::Reported {
            plugin,
            name: format!("p{plugin}"),
            task,
            at,
        });
    }

    fn text(tasks: &Tasks, now: Duration) -> Option<String> {
        tasks.line(now).map(|line| line.text)
    }

    #[test]
    fn nothing_reported_shows_nothing() {
        assert_eq!(Tasks::default().line(T0), None);
    }

    #[test]
    fn a_running_task_shows_plugin_label_and_counts() {
        let mut tasks = Tasks::default();
        report(
            &mut tasks,
            0,
            task("a", TaskState::Running, Some((120, 900))),
            T0,
        );
        let line = tasks.line(T0).unwrap();
        assert_eq!(line.text, "p0: label a 120/900");
        assert!(!line.failed);
    }

    #[test]
    fn counts_need_both_numbers() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Running, None), T0);
        assert_eq!(text(&tasks, T0).unwrap(), "p0: label a");
        let mut only_done = task("a", TaskState::Running, None);
        only_done.done = Some(3);
        report(&mut tasks, 0, only_done, T0);
        assert_eq!(text(&tasks, T0).unwrap(), "p0: label a");
    }

    #[test]
    fn detail_goes_last() {
        let mut tasks = Tasks::default();
        let mut running = task("a", TaskState::Running, Some((1, 2)));
        running.detail = Some("meetings/2026".into());
        report(&mut tasks, 0, running, T0);
        report(&mut tasks, 1, task("b", TaskState::Running, None), T0);
        assert_eq!(
            text(&tasks, T0).unwrap(),
            "p0: label a 1/2 +1 \u{b7} meetings/2026"
        );
    }

    #[test]
    fn a_later_report_replaces_the_earlier_one() {
        let mut tasks = Tasks::default();
        report(
            &mut tasks,
            0,
            task("a", TaskState::Running, Some((1, 9))),
            T0,
        );
        report(
            &mut tasks,
            0,
            task("a", TaskState::Running, Some((2, 9))),
            T0 + secs(1),
        );
        assert_eq!(text(&tasks, T0 + secs(1)).unwrap(), "p0: label a 2/9");
    }

    #[test]
    fn the_same_task_id_in_two_plugins_is_two_tasks() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Running, None), T0);
        report(&mut tasks, 1, task("a", TaskState::Running, None), T0);
        assert_eq!(text(&tasks, T0).unwrap(), "p0: label a +1");
    }

    #[test]
    fn done_shows_for_five_seconds_then_drops() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Done, Some((9, 9))), T0);
        assert_eq!(text(&tasks, T0).unwrap(), "p0: label a 9/9");
        assert!(tasks.line(T0 + Duration::from_millis(4999)).is_some());
        assert_eq!(tasks.line(T0 + secs(5)), None);
        tasks.prune(T0 + secs(5));
        assert_eq!(tasks, Tasks::default());
    }

    #[test]
    fn a_report_forgets_the_done_tasks_that_have_expired() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Done, None), T0);
        report(
            &mut tasks,
            0,
            task("b", TaskState::Running, None),
            T0 + secs(6),
        );
        let mut fresh = Tasks::default();
        report(
            &mut fresh,
            0,
            task("b", TaskState::Running, None),
            T0 + secs(6),
        );
        assert_eq!(tasks, fresh);
    }

    #[test]
    fn next_expiry_counts_down_to_the_first_done_task_to_drop() {
        let mut tasks = Tasks::default();
        assert_eq!(tasks.next_expiry(T0), None);
        report(&mut tasks, 0, task("a", TaskState::Running, None), T0);
        assert_eq!(tasks.next_expiry(T0), None);
        report(
            &mut tasks,
            0,
            task("b", TaskState::Done, None),
            T0 + secs(1),
        );
        report(
            &mut tasks,
            0,
            task("c", TaskState::Done, None),
            T0 + secs(3),
        );
        assert_eq!(tasks.next_expiry(T0 + secs(2)), Some(secs(4)));
        assert_eq!(tasks.next_expiry(T0 + secs(7)), Some(secs(1)));
        assert_eq!(tasks.next_expiry(T0 + secs(9)), None);
    }

    #[test]
    fn a_done_task_that_runs_again_stays() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Done, None), T0);
        report(
            &mut tasks,
            0,
            task("a", TaskState::Running, None),
            T0 + secs(1),
        );
        assert!(tasks.line(T0 + secs(60)).is_some());
    }

    #[test]
    fn a_failed_task_stays_whatever_the_time() {
        let mut tasks = Tasks::default();
        let mut failed = task("a", TaskState::Failed, None);
        failed.detail = Some("disk full".into());
        report(&mut tasks, 0, failed, T0);
        let line = tasks.line(T0 + secs(3600)).unwrap();
        assert_eq!(line.text, "p0: label a failed \u{b7} disk full");
        assert!(line.failed);
    }

    #[test]
    fn a_restart_or_reload_clears_that_plugins_tasks_only() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Failed, None), T0);
        report(&mut tasks, 0, task("b", TaskState::Running, None), T0);
        report(&mut tasks, 1, task("c", TaskState::Running, None), T0);
        tasks.apply(TaskEvent::Cleared { plugin: 0 });
        assert_eq!(text(&tasks, T0).unwrap(), "p1: label c");
        tasks.apply(TaskEvent::Cleared { plugin: 1 });
        assert_eq!(tasks.line(T0), None);
    }

    #[test]
    fn failed_beats_running_beats_done() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Done, None), T0);
        assert!(text(&tasks, T0).unwrap().starts_with("p0: label a"));
        report(&mut tasks, 1, task("b", TaskState::Running, None), T0);
        assert!(text(&tasks, T0).unwrap().starts_with("p1: label b"));
        report(&mut tasks, 2, task("c", TaskState::Failed, None), T0);
        assert!(text(&tasks, T0).unwrap().starts_with("p2: label c failed"));
    }

    #[test]
    fn among_equals_the_order_is_plugin_then_id_and_does_not_depend_on_arrival() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 1, task("a", TaskState::Running, None), T0);
        report(&mut tasks, 0, task("z", TaskState::Running, None), T0);
        report(
            &mut tasks,
            0,
            task("m", TaskState::Running, None),
            T0 + secs(1),
        );
        assert_eq!(text(&tasks, T0 + secs(1)).unwrap(), "p0: label m +2");
    }

    #[test]
    fn the_count_of_the_rest_leaves_out_expired_done_tasks() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Running, None), T0);
        report(&mut tasks, 0, task("b", TaskState::Done, None), T0);
        report(&mut tasks, 0, task("c", TaskState::Running, None), T0);
        assert_eq!(text(&tasks, T0).unwrap(), "p0: label a +2");
        assert_eq!(text(&tasks, T0 + secs(5)).unwrap(), "p0: label a +1");
    }

    #[test]
    fn hiding_the_window_dismisses_a_failure_that_was_on_show() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Failed, None), T0);
        report(&mut tasks, 0, task("b", TaskState::Running, None), T0);
        tasks.apply(TaskEvent::Hidden);
        assert_eq!(text(&tasks, T0).unwrap(), "p0: label b");
        tasks.apply(TaskEvent::Shown);
        assert_eq!(text(&tasks, T0).unwrap(), "p0: label b");
    }

    #[test]
    fn a_failure_that_arrives_while_hidden_waits_for_a_show_and_the_hide_after_it() {
        let mut tasks = Tasks::default();
        tasks.apply(TaskEvent::Hidden);
        report(&mut tasks, 0, task("a", TaskState::Failed, None), T0);
        tasks.apply(TaskEvent::Hidden);
        assert!(tasks.line(T0).is_some());
        tasks.apply(TaskEvent::Shown);
        assert!(tasks.line(T0).is_some());
        tasks.apply(TaskEvent::Hidden);
        assert_eq!(tasks.line(T0), None);
    }

    #[test]
    fn hiding_leaves_running_tasks() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Running, None), T0);
        tasks.apply(TaskEvent::Hidden);
        tasks.apply(TaskEvent::Shown);
        assert!(tasks.line(T0).is_some());
    }

    #[test]
    fn a_failure_that_runs_again_is_no_longer_dismissed_by_a_hide() {
        let mut tasks = Tasks::default();
        report(&mut tasks, 0, task("a", TaskState::Failed, None), T0);
        report(&mut tasks, 0, task("a", TaskState::Running, None), T0);
        tasks.apply(TaskEvent::Hidden);
        assert!(tasks.line(T0).is_some());
    }

    fn line(text: &str, failed: bool) -> TaskLine {
        TaskLine {
            text: text.into(),
            failed,
        }
    }

    #[test]
    fn the_line_goes_to_message_then_failed_then_running_then_waiting() {
        let say = |message: Option<&str>, tasks, waiting: Option<&str>| {
            status_line(message.map(Into::into), tasks, waiting.map(Into::into))
        };
        assert_eq!(
            say(Some("trouble"), Some(line("t", true)), Some("w")),
            Some(("trouble".into(), Tone::Warning))
        );
        assert_eq!(
            say(None, Some(line("failed one", true)), Some("w")),
            Some(("failed one".into(), Tone::Warning))
        );
        assert_eq!(
            say(None, Some(line("running one", false)), Some("w")),
            Some(("running one".into(), Tone::Muted))
        );
        assert_eq!(say(None, None, Some("w")), Some(("w".into(), Tone::Muted)));
        assert_eq!(say(None, None, None), None);
    }
}
