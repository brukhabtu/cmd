//! Proves the host reads the lines a plugin starts (decision 12): a task reported between
//! calls arrives, one reported during a call does not fail it, an unreadable one is
//! trouble, only the latest state per task is kept, and a restart clears the plugin's
//! tasks. The fake plugin writes the lines on request (see `common::FAKE`).
//! The same reader takes the `notify` lines of decision 13, tested at the end.

mod common;

use std::time::{Duration, Instant};

use cmd_core::notice::Notice;
use cmd_core::task::{Task, TaskState};
use cmd_host::{Host, HostEvent, Timeouts};

type Want = fn(&HostEvent) -> bool;

fn host(names: &[&str]) -> Host {
    let located = names
        .iter()
        .map(|name| common::located(name, false))
        .collect();
    let (host, errors) = Host::start(located, Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    host
}

/// Every event that arrives until each of `wants` has been satisfied by one of them. The
/// answer to a query and the tasks a plugin reports around it arrive in either order, so a
/// test names what it needs and not the order.
fn gather(host: &Host, wants: &[Want]) -> Vec<HostEvent> {
    let events = host.events();
    let started = Instant::now();
    let mut seen: Vec<HostEvent> = Vec::new();
    while !wants.iter().all(|want| seen.iter().any(want)) {
        if let Ok(event) = events.try_recv() {
            seen.push(event);
        } else {
            assert!(
                started.elapsed() < Duration::from_secs(10),
                "not every wanted event came in time; saw {seen:?}"
            );
            std::thread::sleep(Duration::from_millis(10));
        }
    }
    seen
}

fn is_task(event: &HostEvent) -> bool {
    matches!(event, HostEvent::Task { .. })
}

fn is_answer(event: &HostEvent) -> bool {
    matches!(event, HostEvent::Answered { .. })
}

fn is_trouble(event: &HostEvent) -> bool {
    matches!(event, HostEvent::Trouble { .. })
}

fn is_done(event: &HostEvent) -> bool {
    matches!(event, HostEvent::Task { task, .. } if task.state == TaskState::Done)
}

fn is_restart(event: &HostEvent) -> bool {
    matches!(event, HostEvent::Restarted { .. })
}

fn tasks_in(events: &[HostEvent]) -> Vec<&Task> {
    events
        .iter()
        .filter_map(|event| match event {
            HostEvent::Task { task, .. } => Some(task),
            _ => None,
        })
        .collect()
}

/// Whether the fake's good answer is among the events: the call was not failed.
fn answered_ok(events: &[HostEvent]) -> bool {
    events.iter().any(|event| {
        matches!(
            event,
            HostEvent::Answered {
                result: Ok(items), ..
            } if items[0].title == "after" || items[0].title == "later"
        )
    })
}

const INDEX: &str = r#"{"id": "index", "label": "Indexing notes", "state": "running", "done": 120, "total": 900, "detail": "meetings/2026"}"#;

#[test]
fn a_task_reported_between_calls_is_received() {
    let host = host(&["a"]);
    host.query(1, &format!("later {INDEX}"));
    let answer = gather(&host, &[is_answer]);
    assert!(answered_ok(&answer));
    assert!(
        tasks_in(&answer).is_empty(),
        "the plugin has not reported yet"
    );
    // The call is over; 200 ms later the plugin reports with nobody asking.
    let seen = gather(&host, &[is_task]);
    let HostEvent::Task { plugin, task } = seen.last().unwrap() else {
        unreachable!()
    };
    assert_eq!(*plugin, 0);
    assert_eq!(task.id, "index");
    assert_eq!(task.label, "Indexing notes");
    assert_eq!(task.state, TaskState::Running);
    assert_eq!((task.done, task.total), (Some(120), Some(900)));
    assert_eq!(task.detail.as_deref(), Some("meetings/2026"));
    assert_eq!(host.tasks(0), vec![task.clone()]);
}

#[test]
fn a_task_reported_during_a_call_does_not_fail_it() {
    let host = host(&["a"]);
    host.query(1, &format!("task {INDEX}"));
    let seen = gather(&host, &[is_answer, is_task]);
    assert!(
        answered_ok(&seen),
        "the call is answered, not failed by the line: {seen:?}"
    );
    assert_eq!(tasks_in(&seen)[0].id, "index");
}

#[test]
fn an_invalid_task_line_is_trouble_for_that_plugin_and_never_a_failed_call() {
    let host = host(&["a"]);
    host.query(1, "badtask");
    let seen = gather(&host, &[is_answer, is_trouble]);
    assert!(answered_ok(&seen), "{seen:?}");
    assert!(
        seen.iter().any(|event| matches!(
            event,
            HostEvent::Trouble { plugin: 0, message } if message.contains("label is required")
        )),
        "{seen:?}"
    );
    assert_eq!(tasks_in(&seen), Vec::<&Task>::new());
    assert_eq!(host.tasks(0), vec![]);
}

#[test]
fn an_event_the_host_has_no_name_for_is_trouble_too() {
    let host = host(&["a"]);
    host.query(1, "unknown");
    let seen = gather(&host, &[is_answer, is_trouble]);
    assert!(answered_ok(&seen), "{seen:?}");
    assert!(seen.iter().any(|event| matches!(
        event,
        HostEvent::Trouble { message, .. } if message.contains("unknown event")
    )));
}

#[test]
fn a_flood_of_updates_leaves_the_latest_state_and_costs_the_call_nothing() {
    let host = host(&["a"]);
    let started = Instant::now();
    host.query(1, "flood 3000");
    let seen = gather(&host, &[is_answer, is_done]);
    assert!(started.elapsed() < Duration::from_secs(5));
    assert!(answered_ok(&seen), "{seen:?}");
    let reports = tasks_in(&seen);
    assert!(
        reports.len() < 100,
        "3001 lines became {} events",
        reports.len()
    );
    assert_eq!(reports.last().unwrap().state, TaskState::Done);
    let held = host.tasks(0);
    assert_eq!(held.len(), 1);
    assert_eq!(held[0].state, TaskState::Done, "the latest state per id");
    assert_eq!(held[0].done, None);
}

#[test]
fn a_later_report_replaces_the_earlier_one_for_the_same_id_only() {
    let host = host(&["a"]);
    for (generation, params) in [
        (
            1,
            r#"{"id": "one", "label": "One", "state": "running", "done": 1, "total": 2}"#,
        ),
        (2, r#"{"id": "two", "label": "Two", "state": "running"}"#),
        (
            3,
            r#"{"id": "one", "label": "One", "state": "failed", "detail": "disk full"}"#,
        ),
    ] {
        host.query(generation, &format!("task {params}"));
        gather(&host, &[is_answer, is_task]);
    }
    let held = host.tasks(0);
    let summary: Vec<(&str, TaskState)> = held
        .iter()
        .map(|task| (task.id.as_str(), task.state))
        .collect();
    assert_eq!(
        summary,
        [("one", TaskState::Failed), ("two", TaskState::Running)]
    );
    assert_eq!(held[0].detail.as_deref(), Some("disk full"));
    assert_eq!(held[0].done, None, "the whole task is replaced, not merged");
}

#[test]
fn each_plugin_has_its_own_tasks() {
    let host = host(&["a", "b"]);
    host.query(1, &format!("task {INDEX}"));
    let seen = gather(
        &host,
        &[
            |event| matches!(event, HostEvent::Task { plugin: 0, .. }),
            |event| matches!(event, HostEvent::Task { plugin: 1, .. }),
        ],
    );
    assert_eq!(tasks_in(&seen).len(), 2);
    assert_eq!(host.tasks(0).len(), 1);
    assert_eq!(host.tasks(1).len(), 1);
    assert_eq!(host.tasks(7), vec![]);
}

#[test]
fn a_restart_clears_the_plugin_s_tasks_and_the_new_process_reports_again() {
    let host = host(&["a"]);
    host.query(1, &format!("task {INDEX}"));
    gather(&host, &[is_answer, is_task]);
    assert_eq!(host.tasks(0).len(), 1);

    host.query(2, "quit");
    gather(&host, &[is_restart]);
    assert_eq!(host.tasks(0), vec![], "the old process's tasks are gone");
    std::thread::sleep(Duration::from_millis(300));
    assert!(
        host.events().try_recv().is_err(),
        "no task event follows the restart"
    );

    host.query(3, &format!("task {INDEX}"));
    let seen = gather(&host, &[is_answer, is_task]);
    assert_eq!(tasks_in(&seen)[0].id, "index");
    assert_eq!(host.tasks(0).len(), 1);
}

// Notices (decision 13): the same reader, a second event name.

fn notices_in(events: &[HostEvent]) -> Vec<&Notice> {
    events
        .iter()
        .filter_map(|event| match event {
            HostEvent::Notice { notice, .. } => Some(notice),
            _ => None,
        })
        .collect()
}

fn is_notice(event: &HostEvent) -> bool {
    matches!(event, HostEvent::Notice { .. })
}

/// Whatever else has arrived once the flusher has had time to send it.
fn settle(host: &Host, seen: &mut Vec<HostEvent>) {
    std::thread::sleep(Duration::from_millis(300));
    while let Ok(event) = host.events().try_recv() {
        seen.push(event);
    }
}

const MOVED: &str = r#"{"id": "PROJ-12", "title": "PROJ-12 moved", "body": "In Review", "open": "https://example.test/PROJ-12"}"#;

#[test]
fn a_notice_sent_between_calls_is_received_cleaned() {
    let host = host(&["a"]);
    host.query(1, r#"laternotice {"id": "i", "title": "Moved\u0007\nnow"}"#);
    let answer = gather(&host, &[is_answer]);
    assert!(
        notices_in(&answer).is_empty(),
        "the plugin has not sent yet"
    );
    let seen = gather(&host, &[is_notice]);
    let HostEvent::Notice { plugin, notice } = seen.last().unwrap() else {
        unreachable!()
    };
    assert_eq!(*plugin, 0);
    assert_eq!(
        (notice.id.as_str(), notice.title.as_str()),
        ("i", "Moved now")
    );
    assert_eq!(
        (notice.body.as_deref(), notice.open.as_deref()),
        (None, None)
    );
}

#[test]
fn a_notice_sent_during_a_call_does_not_fail_it() {
    let host = host(&["a"]);
    host.query(1, &format!("notice {MOVED}"));
    let seen = gather(&host, &[is_answer, is_notice]);
    assert!(answered_ok(&seen), "{seen:?}");
    let notice = notices_in(&seen)[0];
    assert_eq!(notice.title, "PROJ-12 moved");
    assert_eq!(notice.body.as_deref(), Some("In Review"));
    assert_eq!(notice.open.as_deref(), Some("https://example.test/PROJ-12"));
}

#[test]
fn an_invalid_notice_is_trouble_for_that_plugin_and_never_a_failed_call() {
    let host = host(&["a"]);
    host.query(1, "badnotice");
    let seen = gather(&host, &[is_answer, is_trouble]);
    assert!(answered_ok(&seen), "{seen:?}");
    assert!(
        seen.iter().any(|event| matches!(
            event,
            HostEvent::Trouble { plugin: 0, message } if message.contains("title is required")
        )),
        "{seen:?}"
    );
    assert_eq!(notices_in(&seen), Vec::<&Notice>::new());
}

#[test]
fn notices_above_five_in_ten_seconds_are_dropped_with_one_note() {
    let host = host(&["a"]);
    let started = Instant::now();
    host.query(1, "notices 300");
    let mut seen = gather(&host, &[is_answer, is_trouble]);
    settle(&host, &mut seen);
    assert!(started.elapsed() < Duration::from_secs(5));
    assert!(
        answered_ok(&seen),
        "a flood does not fail the call: {seen:?}"
    );
    let ids: Vec<&str> = notices_in(&seen).iter().map(|n| n.id.as_str()).collect();
    assert_eq!(ids, ["n0", "n1", "n2", "n3", "n4"]);
    let notes: Vec<&HostEvent> = seen.iter().filter(|e| is_trouble(e)).collect();
    assert_eq!(notes.len(), 1, "one note for the window: {seen:?}");
    assert!(matches!(
        notes[0],
        HostEvent::Trouble { plugin: 0, message } if message.contains("more than 5 notices")
    ));
}

#[test]
fn the_rate_is_per_plugin() {
    let host = host(&["a", "b"]);
    host.query(1, "notices 8");
    let mut seen = gather(
        &host,
        &[
            |event| matches!(event, HostEvent::Trouble { plugin: 0, .. }),
            |event| matches!(event, HostEvent::Trouble { plugin: 1, .. }),
        ],
    );
    settle(&host, &mut seen);
    for plugin in [0, 1] {
        let count = seen
            .iter()
            .filter(|event| matches!(event, HostEvent::Notice { plugin: p, .. } if *p == plugin))
            .count();
        assert_eq!(count, 5, "plugin {plugin}");
    }
}

#[test]
fn a_restart_does_not_stop_the_plugin_s_notices_arriving() {
    let host = host(&["a"]);
    host.query(1, &format!("notice {MOVED}"));
    gather(&host, &[is_answer, is_notice]);
    host.query(2, "quit");
    gather(&host, &[is_restart]);
    host.query(3, &format!("notice {MOVED}"));
    let seen = gather(&host, &[is_answer, is_notice]);
    assert_eq!(
        notices_in(&seen).len(),
        1,
        "the new process's notice arrives"
    );
}
