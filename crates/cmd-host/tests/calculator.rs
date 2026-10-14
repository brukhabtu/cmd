//! Proves the host against the real calculator and websearch plugins, run through uv
//! exactly as the app runs them, so the Python wire shape and the Rust types are seen
//! to agree through a real process. Needs `uv` on PATH; CI runs `uv sync` first so the
//! handshake does not pay for building the environment.

mod common;

use std::path::PathBuf;

use cmd_core::protocol::{Description, Effect, Icon, Items, Method, VERSION};
use cmd_core::state::DEFAULT_ACTION;
use cmd_core::task::TaskState;
use cmd_host::{Host, HostEvent, PluginProcess, Timeouts, manifest};
use common::{answer_from, effect_from};

fn plugins_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../plugins")
}

#[test]
fn the_real_sdk_answers_a_version_0_host_at_version_0_and_sends_it_no_icon() {
    let located = manifest::load(&plugins_dir().join("calculator")).expect("the calculator");
    let mut process =
        PluginProcess::spawn(&located.manifest.command, &located.dir).expect("it starts");
    let timeouts = Timeouts::default();
    let older = Method::Describe {
        protocol: 0,
        capabilities: vec![],
    };
    let description: Description = process.call(older, timeouts.describe).unwrap();
    assert_eq!(description.protocol, 0);
    let items: Items = process
        .call(
            Method::Query {
                text: "2 + 2".into(),
                home: false,
            },
            timeouts.query,
        )
        .unwrap();
    assert_eq!(items.items[0].title, "4");
    assert_eq!(items.items[0].icon, None, "version 0 has no icon field");
}

#[test]
fn the_calculator_answers_through_the_real_process() {
    let found = manifest::discover(&plugins_dir()).expect("plugins directory exists");
    let located: Vec<_> = found
        .into_iter()
        .map(|entry| entry.expect("every manifest is valid"))
        .collect();
    assert!(
        located
            .iter()
            .any(|plugin| plugin.manifest.name == "calculator")
    );

    let (host, errors) = Host::start(located, Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    let calculator = host
        .descriptions()
        .position(|description| description.name == "calculator")
        .expect("the calculator started");
    assert!(
        host.descriptions()
            .all(|description| description.protocol == VERSION),
        "every plugin agrees this host's version"
    );
    let events = host.events();

    assert!(host.query(1, "2 + 2 * 3").contains(&calculator));
    let items = answer_from(&events, calculator, 1);
    assert_eq!(items[0].title, "8");
    assert_eq!(
        items[0].icon,
        Some(Icon::Symbol {
            name: "equal".into()
        })
    );

    host.run(1, calculator, &items[0].id, DEFAULT_ACTION)
        .unwrap();
    assert_eq!(
        effect_from(&events, calculator, 1),
        Effect::Copy { text: "8".into() }
    );

    host.query(2, "not arithmetic");
    assert_eq!(answer_from(&events, calculator, 2), []);
}

/// A plugin written against the real SDK that reports a task from inside a query and, from
/// a thread of its own, after the query has been answered.
const REPORTER: &str = r#"
import threading
from cmd_sdk import Close, Description, Item, Plugin, Task, report, serve

def query(text):
    report(Task("index", "Indexing notes", "running", 1, 3))
    threading.Timer(0.2, report, [Task("index", "Indexing notes", "done")]).start()
    return (Item("a", "a"),)

serve(Plugin(Description("reporter", "1"), query, lambda item, action: Close()))
"#;

/// A plugin whose code is `code`, run by the real SDK from this repository's workspace.
fn sdk_plugin(name: &str, code: &str) -> cmd_host::Located {
    cmd_host::Located {
        dir: plugins_dir().join(".."),
        manifest: cmd_host::Manifest {
            name: name.into(),
            command: [
                "uv",
                "run",
                "--quiet",
                "--project",
                "python/cmd-sdk",
                "python",
                "-c",
                code,
            ]
            .map(String::from)
            .to_vec(),
        },
    }
}

#[test]
fn a_task_the_real_sdk_reports_reaches_the_host_during_and_between_calls() {
    let located = sdk_plugin("reporter", REPORTER);
    let (host, errors) = Host::start(vec![located], Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    host.query(1, "go");
    let events = host.events();
    let (mut answered, mut running, mut finished) = (false, false, false);
    while !(answered && running && finished) {
        match events.recv_blocking().unwrap() {
            HostEvent::Answered { result: Ok(_), .. } => answered = true,
            HostEvent::Task { task, .. } if task.state == TaskState::Running => {
                assert_eq!((task.done, task.total), (Some(1), Some(3)));
                running = true;
            }
            HostEvent::Task { task, .. } if task.state == TaskState::Done => {
                assert_eq!(task.label, "Indexing notes");
                finished = true;
            }
            other => panic!("unexpected {other:?}"),
        }
    }
}

/// A plugin written against the real SDK that sends a notice from inside a query and, from a
/// thread of its own, after the query has been answered.
const NOTIFIER: &str = r#"
import threading
from cmd_sdk import Close, Description, Item, Plugin, notify, serve

def query(text):
    notify("PROJ-12", "PROJ-12 moved", "In Review", "https://example.test/PROJ-12")
    threading.Timer(0.2, notify, ["PROJ-13", "PROJ-13 moved"]).start()
    return (Item("a", "a"),)

serve(Plugin(Description("notifier", "1"), query, lambda item, action: Close()))
"#;

#[test]
fn a_notice_the_real_sdk_sends_reaches_the_host_during_and_between_calls() {
    let (host, errors) = Host::start(vec![sdk_plugin("notifier", NOTIFIER)], Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    host.query(1, "go");
    let events = host.events();
    let (mut answered, mut notices) = (false, Vec::new());
    while !(answered && notices.len() == 2) {
        match events.recv_blocking().unwrap() {
            HostEvent::Answered { result: Ok(_), .. } => answered = true,
            HostEvent::Notice { notice, .. } => notices.push(notice),
            other => panic!("unexpected {other:?}"),
        }
    }
    assert_eq!(notices[0].id, "PROJ-12");
    assert_eq!(notices[0].body.as_deref(), Some("In Review"));
    assert_eq!(
        notices[0].open.as_deref(),
        Some("https://example.test/PROJ-12")
    );
    assert_eq!(notices[1].title, "PROJ-13 moved");
    assert_eq!(
        (notices[1].body.as_deref(), notices[1].open.as_deref()),
        (None, None)
    );
}

#[test]
fn a_keyword_plugin_sees_only_its_keyword_and_can_ask_the_host_to_open_something() {
    let found = manifest::discover(&plugins_dir()).expect("plugins directory exists");
    let located: Vec<_> = found
        .into_iter()
        .map(|entry| entry.expect("every manifest is valid"))
        .collect();
    let (host, errors) = Host::start(located, Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    let websearch = host
        .descriptions()
        .position(|description| description.name == "websearch")
        .expect("websearch started");
    let events = host.events();

    // The keyword routes to websearch alone, with the keyword stripped.
    assert_eq!(host.query(1, "web rust gpui"), vec![websearch]);
    let items = answer_from(&events, websearch, 1);
    assert_eq!(items[0].id, "https://duckduckgo.com/?q=rust+gpui");
    assert_eq!(items[0].actions.len(), 2);
    assert_eq!(
        items[0].icon,
        Some(Icon::Symbol {
            name: "globe".into()
        })
    );

    // The second action copies; the first (Enter) opens.
    host.run(1, websearch, &items[0].id, &items[0].actions[1].id)
        .unwrap();
    assert_eq!(
        effect_from(&events, websearch, 1),
        Effect::Copy {
            text: items[0].id.clone()
        }
    );
    host.run(1, websearch, &items[0].id, DEFAULT_ACTION)
        .unwrap();
    assert_eq!(
        effect_from(&events, websearch, 1),
        Effect::Open {
            target: items[0].id.clone()
        }
    );

    // A query without the keyword never reaches a keyword plugin.
    assert!(!host.query(2, "rust gpui").contains(&websearch));
}
