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

#[test]
fn answers_arrive_as_events_with_their_generation_and_plugin() {
    let host = host(&[("a", false), ("b", false)]);
    assert_eq!(host.query(7, "hello"), vec![0, 1]);
    let mut answers = vec![next(&host), next(&host)];
    answers.sort_by_key(|event| match event {
        HostEvent::Answered { plugin, .. } | HostEvent::Ran { plugin, .. } => *plugin,
    });
    let titles: Vec<String> = answers
        .into_iter()
        .map(|event| match event {
            HostEvent::Answered {
                generation: 7,
                result: Ok(items),
                ..
            } => items[0].title.clone(),
            other => panic!("unexpected {other:?}"),
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
        match next(&host) {
            HostEvent::Answered { generation, .. } => {
                generations.push(generation);
                if generation == 3 {
                    break;
                }
            }
            HostEvent::Ran { .. } => panic!("a run was never asked for"),
        }
    }
    assert!(
        generations == [1, 3] || generations == [3],
        "{generations:?}"
    );
    host.query(4, "d");
    assert!(matches!(
        next(&host),
        HostEvent::Answered { generation: 4, .. }
    ));
}

#[test]
fn a_run_comes_back_as_an_effect() {
    let host = host(&[("a", false)]);
    host.run(0, "the item", "default").unwrap();
    assert_eq!(
        next(&host),
        HostEvent::Ran {
            plugin: 0,
            result: Ok(Effect::Copy {
                text: "the item".into()
            })
        }
    );
    assert!(host.run(3, "x", "default").is_err());
}

#[test]
fn a_plugin_that_fails_to_answer_says_so_in_the_event() {
    let host = host(&[("a", false)]);
    host.query(1, "fail");
    match next(&host) {
        HostEvent::Answered {
            result: Err(error), ..
        } => assert!(error.contains("boom: no"), "{error}"),
        other => panic!("unexpected {other:?}"),
    }
}

#[test]
fn a_keyword_plugin_is_asked_only_for_its_keyword() {
    let host = host(&[("a", false)]);
    assert_eq!(host.descriptions().count(), 1);
    assert_eq!(host.name(0), Some("a"));
    assert_eq!(host.query(1, "   "), Vec::<usize>::new());
}
