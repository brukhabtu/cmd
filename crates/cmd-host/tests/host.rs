//! Proves the host against fake plugins: answers arrive as events, a slow plugin
//! delays only itself, stale queries are skipped, and runs come back as effects.

mod common;

use std::time::{Duration, Instant};

use cmd_core::protocol::Effect;
use cmd_host::{Host, HostEvent, Timeouts};

fn host(plugins: &[(&str, bool)]) -> Host {
    host_with(plugins, Timeouts::default())
}

fn host_with(plugins: &[(&str, bool)], timeouts: Timeouts) -> Host {
    let located = plugins
        .iter()
        .map(|(name, slow)| common::located(name, *slow))
        .collect();
    let (host, errors) = Host::start(located, timeouts);
    assert!(errors.is_empty(), "{errors:?}");
    host
}

/// A plugin directory of its own, holding `fake.py` with the given NAME and no manifest.
fn editable(tag: &str, name: &str) -> (std::path::PathBuf, cmd_host::Located) {
    let dir = std::env::temp_dir().join(format!("cmd-host-{tag}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(
        dir.join("fake.py"),
        format!("NAME = {name:?}\n{}", common::FAKE),
    )
    .unwrap();
    let located = cmd_host::Located {
        dir: dir.clone(),
        manifest: cmd_host::Manifest {
            name: "editable".into(),
            command: vec!["python3".into(), "fake.py".into()],
        },
    };
    (dir, located)
}

/// The first title the plugin answers for `text`, so a test can see which code answered.
fn ask(host: &Host, generation: u64, text: &str) -> String {
    host.query(generation, text);
    match next_within(host, Duration::from_secs(10)) {
        HostEvent::Answered {
            result: Ok(items), ..
        } => items[0].title.clone(),
        other => panic!("unexpected {other:?}"),
    }
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
fn a_plugin_that_keeps_timing_out_counts_as_hung_and_is_started_again() {
    let host = host_with(
        &[("a", false)],
        Timeouts {
            query: Duration::from_millis(100),
            hung_after: 2,
            ..Timeouts::default()
        },
    );
    host.query(1, "stall");
    match next(&host) {
        HostEvent::Answered {
            generation: 1,
            result: Err(error),
            ..
        } => assert!(
            error.contains("no answer") && !error.contains("starting it again"),
            "one timeout is not yet a hang: {error}"
        ),
        other => panic!("unexpected {other:?}"),
    }
    host.query(2, "stall");
    match next(&host) {
        HostEvent::Answered {
            generation: 2,
            result: Err(error),
            ..
        } => assert!(
            error.contains("2 times in a row") && error.contains("starting it again"),
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
    assert_eq!(ask(&host, 3, "hello"), "a:hello");
}

/// Two stalled queries on a host whose plugin counts as hung after two timeouts, with
/// their two answers taken, so the restart is the next event.
fn hang_twice(host: &Host, first_generation: u64) {
    for generation in [first_generation, first_generation + 1] {
        host.query(generation, "stall");
        match next(host) {
            HostEvent::Answered { result: Err(_), .. } => {}
            other => panic!("unexpected {other:?}"),
        }
    }
}

#[test]
fn a_plugin_that_hangs_again_waits_longer_before_its_second_restart() {
    let host = host_with(
        &[("a", false)],
        Timeouts {
            query: Duration::from_millis(100),
            hung_after: 2,
            ..Timeouts::default()
        },
    );
    hang_twice(&host, 1);
    assert_eq!(
        next(&host),
        HostEvent::Restarted {
            plugin: 0,
            attempt: 1
        }
    );
    let restarted = Instant::now();
    hang_twice(&host, 3);
    // The timeouts in between did not count as healthy calls, so this is restart two,
    // and it waited the first back-off step (2 s) from the last one.
    assert_eq!(
        next_within(&host, Duration::from_secs(10)),
        HostEvent::Restarted {
            plugin: 0,
            attempt: 2
        }
    );
    assert!(
        restarted.elapsed() >= Duration::from_millis(1500),
        "the second restart came after {:?}",
        restarted.elapsed()
    );
}

#[test]
fn a_changed_file_reloads_the_plugin_onto_the_new_code_and_manifest() {
    let (dir, located) = editable("reload", "before");
    let (host, errors) = Host::start(vec![located], Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    assert_eq!(ask(&host, 1, "hello"), "before:hello");

    // The script changes: the plugin comes back on the new code.
    std::fs::write(
        dir.join("fake.py"),
        format!("NAME = \"after\"\n{}", common::FAKE),
    )
    .unwrap();
    assert_eq!(
        next_within(&host, Duration::from_secs(10)),
        HostEvent::Reloaded { plugin: 0 }
    );
    assert_eq!(host.name(0).as_deref(), Some("after"));
    assert_eq!(ask(&host, 2, "hello"), "after:hello");

    // A manifest appears, naming another script: the reload reads it and runs that.
    std::fs::write(
        dir.join("other.py"),
        format!("NAME = \"other\"\n{}", common::FAKE),
    )
    .unwrap();
    std::fs::write(
        dir.join("cmd-plugin.toml"),
        "name = \"editable\"\ncommand = [\"python3\", \"other.py\"]\n",
    )
    .unwrap();
    // Two files, so one reload or two, depending on how the writes fell around the settle.
    let started = Instant::now();
    while host.name(0).as_deref() != Some("other") {
        assert_eq!(
            next_within(&host, Duration::from_secs(10)),
            HostEvent::Reloaded { plugin: 0 }
        );
        assert!(started.elapsed() < Duration::from_secs(10));
    }
    assert_eq!(ask(&host, 3, "hello"), "other:hello");
}

#[test]
fn a_broken_manifest_is_reported_and_the_old_code_keeps_answering() {
    let (dir, located) = editable("broken", "before");
    let (host, errors) = Host::start(vec![located], Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");

    std::fs::write(
        dir.join("cmd-plugin.toml"),
        "name = \"editable\"\ncommand = []\n",
    )
    .unwrap();
    match next_within(&host, Duration::from_secs(10)) {
        HostEvent::Trouble { plugin: 0, message } => assert!(
            message.contains("did not come back after a change")
                && message.contains("not a valid manifest"),
            "{message}"
        ),
        other => panic!("unexpected {other:?}"),
    }
    assert_eq!(ask(&host, 1, "hello"), "before:hello");
}

#[test]
fn blank_input_asks_nobody_and_the_plugin_is_still_described() {
    let host = host(&[("a", false)]);
    assert_eq!(host.descriptions().count(), 1);
    assert_eq!(host.name(0).as_deref(), Some("a"));
    assert_eq!(host.query(1, "   "), Vec::<usize>::new());
}
