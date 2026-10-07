//! Proves the host against fake plugins: answers arrive as events, a slow plugin
//! delays only itself, stale queries are skipped, and runs come back as effects.

mod common;

use std::time::{Duration, Instant};

use cmd_core::protocol::Effect;
use cmd_host::{Host, HostEvent, Timeouts};

fn host(plugins: &[(&str, bool)]) -> Host {
    let located = plugins
        .iter()
        .map(|(name, slow)| common::located(name, *slow))
        .collect();
    let (host, errors) = Host::start(located, Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    host
}

fn next(host: &Host) -> HostEvent {
    host.events().recv_blocking().expect("the host is alive")
}

/// The next event, or a panic naming the wait: a test must never hang on a silent host.
fn next_within(host: &Host, limit: Duration) -> HostEvent {
    let events = host.events();
    let started = Instant::now();
    loop {
        if let Ok(event) = events.try_recv() {
            return event;
        }
        assert!(started.elapsed() < limit, "no event within {limit:?}");
        std::thread::sleep(Duration::from_millis(20));
    }
}

fn generation_of(event: &HostEvent) -> u64 {
    match event {
        HostEvent::Answered { generation, .. } | HostEvent::Ran { generation, .. } => *generation,
        HostEvent::Restarted { .. } | HostEvent::Reloaded { .. } | HostEvent::Trouble { .. } => {
            panic!("no restart was expected")
        }
    }
}

#[test]
fn answers_arrive_as_events_with_their_generation_and_plugin() {
    let host = host(&[("a", false), ("b", false)]);
    assert_eq!(host.query(7, "hello"), vec![0, 1]);
    let mut answers = vec![next(&host), next(&host)];
    answers.sort_by_key(|event| match event {
        HostEvent::Answered { plugin, .. }
        | HostEvent::Ran { plugin, .. }
        | HostEvent::Restarted { plugin, .. }
        | HostEvent::Reloaded { plugin, .. }
        | HostEvent::Trouble { plugin, .. } => *plugin,
    });
    let titles: Vec<String> = answers
        .into_iter()
        .map(|event| match event {
            HostEvent::Answered {
                generation: 7,
                result: Ok(items),
                ..
            } => items[0].title.clone(),
            other => {
                panic!("unexpected {other:?}")
            }
        })
        .collect();
    assert_eq!(titles, vec!["a:hello", "b:hello"]);
}

#[test]
fn a_slow_plugin_delays_only_its_own_answer() {
    let host = host(&[("slow", true), ("fast", false)]);
    let started = Instant::now();
    host.query(1, "x");
    let first = next(&host);
    assert!(
        matches!(first, HostEvent::Answered { plugin: 1, .. }),
        "{first:?}"
    );
    assert!(
        started.elapsed() < Duration::from_millis(250),
        "the fast answer waited for the slow one"
    );
    let second = next(&host);
    assert!(
        matches!(second, HostEvent::Answered { plugin: 0, .. }),
        "{second:?}"
    );
}

#[test]
fn queries_that_piled_up_behind_a_slow_call_collapse_to_the_newest() {
    let host = host(&[("slow", true)]);
    host.query(1, "a");
    host.query(2, "b");
    host.query(3, "c");
    // Generation 1 is answered only if the worker had already picked it up; 2 never is.
    let mut generations = Vec::new();
    loop {
        let generation = generation_of(&next(&host));
        generations.push(generation);
        if generation == 3 {
            break;
        }
    }
    assert!(
        generations == [1, 3] || generations == [3],
        "{generations:?}"
    );
    host.query(4, "d");
    assert_eq!(generation_of(&next(&host)), 4);
}

#[test]
fn an_answer_can_arrive_after_a_newer_query_was_sent_and_names_its_generation() {
    let host = host(&[("slow", true)]);
    host.query(1, "a");
    // The worker is inside the 300 ms call for generation 1 when generation 2 is sent.
    std::thread::sleep(Duration::from_millis(100));
    host.query(2, "b");
    assert_eq!(
        generation_of(&next(&host)),
        1,
        "the stale answer still arrives, tagged"
    );
    assert_eq!(generation_of(&next(&host)), 2);
}

#[test]
fn a_run_comes_back_as_an_effect_tagged_with_its_generation() {
    let host = host(&[("a", false)]);
    host.run(9, 0, "the item", "default").unwrap();
    assert_eq!(
        next(&host),
        HostEvent::Ran {
            generation: 9,
            plugin: 0,
            result: Ok(Effect::Copy {
                text: "the item".into()
            })
        }
    );
    assert!(host.run(9, 3, "x", "default").is_err());
}

#[test]
fn a_plugin_that_fails_to_answer_says_so_in_the_event() {
    let host = host(&[("a", false)]);
    host.query(1, "fail");
    match next(&host) {
        HostEvent::Answered {
            result: Err(error), ..
        } => assert!(error.contains("boom: no"), "{error}"),
        other => {
            panic!("unexpected {other:?}")
        }
    }
}

#[test]
fn a_plugin_that_exits_is_started_again_for_the_next_query() {
    let host = host(&[("a", false)]);
    host.query(1, "quit");
    match next(&host) {
        HostEvent::Answered {
            generation: 1,
            result: Err(error),
            ..
        } => assert!(
            error.contains("exited") && error.contains("starting it again"),
            "{error}"
        ),
        other => panic!("unexpected {other:?}"),
    }
    assert_eq!(
        next(&host),
        HostEvent::Restarted {
            plugin: 0,
            attempt: 1
        }
    );
    host.query(2, "hello");
    match next(&host) {
        HostEvent::Answered {
            generation: 2,
            result: Ok(items),
            ..
        } => assert_eq!(items[0].title, "a:hello"),
        other => panic!("unexpected {other:?}"),
    }
}

#[test]
fn a_changed_file_reloads_the_plugin_onto_the_new_code() {
    let dir = std::env::temp_dir().join(format!("cmd-host-reload-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let script = dir.join("fake.py");
    std::fs::write(&script, format!("NAME = \"before\"\n{}", common::FAKE)).unwrap();
    let located = cmd_host::Located {
        dir: dir.clone(),
        manifest: cmd_host::Manifest {
            name: "editable".into(),
            command: vec!["python3".into(), "fake.py".into()],
        },
    };
    let (host, errors) = Host::start(vec![located], Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");

    std::fs::write(&script, format!("NAME = \"after\"\n{}", common::FAKE)).unwrap();
    assert_eq!(
        next_within(&host, Duration::from_secs(10)),
        HostEvent::Reloaded { plugin: 0 }
    );
    host.query(1, "hello");
    match next_within(&host, Duration::from_secs(10)) {
        HostEvent::Answered {
            result: Ok(items), ..
        } => assert_eq!(items[0].title, "after:hello"),
        other => panic!("unexpected {other:?}"),
    }
}

#[test]
fn blank_input_asks_nobody_and_the_plugin_is_still_described() {
    let host = host(&[("a", false)]);
    assert_eq!(host.descriptions().count(), 1);
    assert_eq!(host.name(0), Some("a"));
    assert_eq!(host.query(1, "   "), Vec::<usize>::new());
}
