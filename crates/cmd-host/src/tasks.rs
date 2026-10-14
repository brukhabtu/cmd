//! What the host remembers of the tasks a plugin reports, and how they reach the window.
//!
//! The plugin's reader thread offers each event to a [`TaskBoard`] as it arrives. The
//! board keeps the latest state per task id and a flusher thread turns what changed into
//! [`HostEvent`]s at most every [`FLUSH_GAP`], so a plugin that reports a thousand times a
//! second costs the host the reading of those lines and one event per task per gap, and
//! nothing ever waits on the window (decision 12).

use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Condvar, Mutex, MutexGuard, PoisonError};
use std::time::Duration;

use cmd_core::task::{Event, Task, TaskState};

use crate::host::HostEvent;

/// How many tasks the host keeps per plugin. A new id over this drops a finished task to
/// make room, and with none finished is itself ignored.
pub const MAX_TASKS: usize = 64;

/// How many problems with a plugin's task lines the host reports for one run of the
/// plugin, so a plugin writing bad lines in a loop cannot fill the window with notes.
const TROUBLE_BUDGET: usize = 10;

/// The least time between two flushes of a plugin's changes to the window.
pub const FLUSH_GAP: Duration = Duration::from_millis(50);

/// The tasks of one run of one plugin.
#[derive(Debug, Default)]
struct Book {
    latest: BTreeMap<String, Task>,
    /// Ids whose latest state has not gone to the window yet.
    pending: BTreeSet<String>,
    troubles: Vec<String>,
    troubles_left: Option<usize>,
}

impl Book {
    fn offer(&mut self, event: Event) {
        match event {
            Event::Invalid(why) => self.trouble(format!("ignored a task report: {why}")),
            Event::Task(task) => {
                if !self.latest.contains_key(&task.id) && self.latest.len() >= MAX_TASKS {
                    let finished = self
                        .latest
                        .iter()
                        .find(|(_, held)| held.state == TaskState::Done)
                        .map(|(id, _)| id.clone());
                    let Some(finished) = finished else {
                        self.trouble(format!(
                            "ignored a task report: it already has {MAX_TASKS} tasks"
                        ));
                        return;
                    };
                    self.latest.remove(&finished);
                    self.pending.remove(&finished);
                }
                self.pending.insert(task.id.clone());
                self.latest.insert(task.id.clone(), task);
            }
        }
    }

    fn trouble(&mut self, message: String) {
        let left = self.troubles_left.get_or_insert(TROUBLE_BUDGET);
        match *left {
            0 => {}
            1 => {
                *left = 0;
                self.troubles
                    .push("no more problems with its task reports will be shown".to_string());
            }
            _ => {
                *left -= 1;
                self.troubles.push(message);
            }
        }
    }

    fn has_news(&self) -> bool {
        !self.pending.is_empty() || !self.troubles.is_empty()
    }
}

#[derive(Debug, Default)]
struct Inner {
    /// The process whose reports count. 0 before any process has been activated.
    current: u64,
    book: Book,
    /// A process that has been started but not yet taken over from the old one: its
    /// reports wait here, so one sent right after its `describe` is not lost, and so a
    /// process that fails its handshake leaves the old one's tasks alone.
    staged: Option<(u64, Book)>,
    last_token: u64,
    closed: bool,
}

/// The latest state of each task a plugin reports, across the plugin's restarts.
#[derive(Debug)]
pub struct TaskBoard {
    plugin: usize,
    events: async_channel::Sender<HostEvent>,
    inner: Mutex<Inner>,
    wake: Condvar,
}

impl TaskBoard {
    /// A board for the plugin at this index, reporting on `events`. Start its flusher
    /// with [`TaskBoard::spawn_flusher`].
    pub fn new(plugin: usize, events: async_channel::Sender<HostEvent>) -> Arc<Self> {
        Arc::new(Self {
            plugin,
            events,
            inner: Mutex::new(Inner::default()),
            wake: Condvar::new(),
        })
    }

    fn lock(&self) -> MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(PoisonError::into_inner)
    }

    /// A process is about to start: its reports are kept aside under the token this
    /// returns, until [`TaskBoard::activate`] or [`TaskBoard::abandon`].
    pub fn begin(&self) -> u64 {
        let mut inner = self.lock();
        inner.last_token += 1;
        let token = inner.last_token;
        inner.staged = Some((token, Book::default()));
        token
    }

    /// The reader thread of the process with this token read an event. Reports from a
    /// process that is neither the current one nor the one starting are ignored.
    pub fn offer(&self, token: u64, event: Event) {
        let mut inner = self.lock();
        if inner.closed {
            return;
        }
        if token == inner.current {
            inner.book.offer(event);
            drop(inner);
            self.wake.notify_one();
        } else if let Some((staged, book)) = inner.staged.as_mut()
            && *staged == token
        {
            book.offer(event);
        }
    }

    /// The process with this token is up and takes over: the old process's tasks are
    /// gone, and what the new one has reported so far is now current.
    pub fn activate(&self, token: u64) {
        let mut inner = self.lock();
        let Some((staged, book)) = inner.staged.take() else {
            return;
        };
        if staged != token {
            inner.staged = Some((staged, book));
            return;
        }
        inner.current = token;
        inner.book = book;
        drop(inner);
        self.wake.notify_one();
    }

    /// The process with this token did not come up: whatever it reported is dropped.
    pub fn abandon(&self, token: u64) {
        let mut inner = self.lock();
        if matches!(inner.staged, Some((staged, _)) if staged == token) {
            inner.staged = None;
        }
    }

    /// The current process is gone: it has no tasks.
    pub fn clear(&self) {
        self.lock().book = Book::default();
    }

    /// The latest state of every task the plugin has reported, in id order.
    pub fn snapshot(&self) -> Vec<Task> {
        self.lock().book.latest.values().cloned().collect()
    }

    /// Stop the flusher.
    pub fn close(&self) {
        self.lock().closed = true;
        self.wake.notify_all();
    }

    /// Run the flusher on its own thread, until the board is closed or the window's
    /// channel is.
    pub fn spawn_flusher(self: &Arc<Self>) -> std::io::Result<()> {
        let board = Arc::clone(self);
        std::thread::Builder::new()
            .name(format!("tasks:{}", self.plugin))
            .spawn(move || board.flush_forever())
            .map(|_| ())
    }

    fn flush_forever(&self) {
        loop {
            let mut inner = self.lock();
            while !inner.closed && !inner.book.has_news() {
                inner = self
                    .wake
                    .wait(inner)
                    .unwrap_or_else(PoisonError::into_inner);
            }
            if inner.closed {
                return;
            }
            // The sends are inside the lock, and an unbounded channel never blocks, so a
            // restart (which takes this lock to swap books) cannot slip between the
            // taking and the sending and leave a stale task after its `Restarted`.
            let book = &mut inner.book;
            let changed = std::mem::take(&mut book.pending);
            let mut sent = Vec::new();
            for id in changed {
                if let Some(task) = book.latest.get(&id) {
                    sent.push(HostEvent::Task {
                        plugin: self.plugin,
                        task: task.clone(),
                    });
                }
            }
            for message in std::mem::take(&mut book.troubles) {
                sent.push(HostEvent::Trouble {
                    plugin: self.plugin,
                    message,
                });
            }
            for event in sent {
                if self.events.try_send(event).is_err() {
                    inner.closed = true;
                    return;
                }
            }
            drop(inner);
            std::thread::sleep(FLUSH_GAP);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn running(id: &str, done: u64) -> Event {
        Event::Task(Task {
            id: id.into(),
            label: "Indexing".into(),
            state: TaskState::Running,
            done: Some(done),
            total: Some(100),
            detail: None,
        })
    }

    fn finished(id: &str) -> Event {
        Event::Task(Task {
            id: id.into(),
            label: "Indexing".into(),
            state: TaskState::Done,
            done: None,
            total: None,
            detail: None,
        })
    }

    #[test]
    fn a_book_keeps_the_latest_state_per_id() {
        let mut book = Book::default();
        for done in 1..=1000 {
            book.offer(running("a", done));
        }
        book.offer(running("b", 5));
        assert_eq!(book.latest.len(), 2);
        assert_eq!(book.latest["a"].done, Some(1000));
        assert_eq!(book.pending.len(), 2, "one report per task, not per line");
    }

    #[test]
    fn a_book_over_its_limit_makes_room_by_dropping_a_finished_task_or_ignores_the_new_one() {
        let mut book = Book::default();
        for n in 0..MAX_TASKS {
            book.offer(running(&format!("t{n:03}"), 1));
        }
        book.offer(running("new", 1));
        assert!(!book.latest.contains_key("new"));
        assert_eq!(book.troubles.len(), 1);
        book.offer(finished("t007"));
        book.offer(running("new", 1));
        assert!(book.latest.contains_key("new"));
        assert!(!book.latest.contains_key("t007"));
        assert_eq!(book.latest.len(), MAX_TASKS);
    }

    #[test]
    fn a_book_reports_a_bounded_number_of_problems() {
        let mut book = Book::default();
        for n in 0..100 {
            book.offer(Event::Invalid(format!("bad {n}")));
        }
        assert_eq!(book.troubles.len(), TROUBLE_BUDGET);
        assert!(book.troubles.last().unwrap().contains("no more problems"));
    }

    fn board() -> (Arc<TaskBoard>, async_channel::Receiver<HostEvent>) {
        let (sender, receiver) = async_channel::unbounded();
        (TaskBoard::new(3, sender), receiver)
    }

    #[test]
    fn a_new_process_takes_over_and_the_old_ones_tasks_and_reports_are_gone() {
        let (board, _events) = board();
        let first = board.begin();
        board.activate(first);
        board.offer(first, running("old", 1));
        assert_eq!(board.snapshot().len(), 1);
        let second = board.begin();
        board.offer(second, running("early", 1));
        board.offer(first, running("late", 1));
        assert_eq!(
            board
                .snapshot()
                .iter()
                .map(|t| t.id.as_str())
                .collect::<Vec<_>>(),
            ["late", "old"],
            "until the new process is up, the old one still counts"
        );
        board.activate(second);
        board.offer(first, running("ghost", 1));
        let ids: Vec<String> = board.snapshot().into_iter().map(|t| t.id).collect();
        assert_eq!(ids, ["early"]);
    }

    #[test]
    fn a_process_that_never_came_up_leaves_the_old_tasks_alone() {
        let (board, _events) = board();
        let first = board.begin();
        board.activate(first);
        board.offer(first, running("kept", 1));
        let failed = board.begin();
        board.offer(failed, running("never", 1));
        board.abandon(failed);
        board.offer(failed, running("never", 2));
        let ids: Vec<String> = board.snapshot().into_iter().map(|t| t.id).collect();
        assert_eq!(ids, ["kept"]);
    }

    #[test]
    fn the_flusher_sends_each_changed_task_once_with_its_latest_state() {
        let (board, events) = board();
        let token = board.begin();
        board.activate(token);
        for done in 1..=500 {
            board.offer(token, running("a", done));
        }
        board.offer(token, Event::Invalid("nope".into()));
        board.spawn_flusher().unwrap();
        let first = events.recv_blocking().unwrap();
        let second = events.recv_blocking().unwrap();
        match (first, second) {
            (HostEvent::Task { plugin: 3, task }, HostEvent::Trouble { plugin: 3, message }) => {
                assert_eq!(task.done, Some(500));
                assert!(message.contains("nope"), "{message}");
            }
            other => panic!("unexpected {other:?}"),
        }
        assert!(events.try_recv().is_err(), "a flood is one report");
        board.close();
    }
}
