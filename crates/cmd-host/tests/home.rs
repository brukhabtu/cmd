//! The home query (decision 13): blank input reaches the plugins that declared `home` and
//! nobody else, as an ordinary query with a generation, carrying `home: true`.

use std::time::Duration;

use cmd_core::protocol::Item;
use cmd_host::{Host, HostEvent, Located, Manifest, Timeouts};

/// A plugin that echoes the query params it was sent as its one item's title, so a test
/// sees exactly what crossed the wire. `HOME` decides whether its description says so.
const FAKE: &str = r#"
import json, sys
for line in sys.stdin:
    request = json.loads(line)
    if request["method"] == "describe":
        description = {"name": NAME, "version": "0", "protocol": 1}
        if HOME:
            description["home"] = True
        result = description
    else:
        result = {"items": [{"id": "echo", "title": json.dumps(request["params"], sort_keys=True)}]}
    print(json.dumps({"id": request["id"], "result": result}), flush=True)
"#;

fn plugin(name: &str, home: bool) -> Located {
    let flag = if home { "True" } else { "False" };
    Located {
        dir: ".".into(),
        manifest: Manifest {
            name: name.to_string(),
            command: vec![
                "python3".into(),
                "-c".into(),
                format!("NAME = {name:?}\nHOME = {flag}\n{FAKE}"),
            ],
        },
    }
}

fn started(plugins: Vec<Located>) -> Host {
    let (host, errors) = Host::start(plugins, Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    host
}

/// The answers to `generation` from `count` plugins, as (plugin, generation, items).
fn answers(host: &Host, count: usize) -> Vec<(usize, u64, Vec<Item>)> {
    let events = host.events();
    let mut got = Vec::new();
    while got.len() < count {
        let event = events.recv_blocking().expect("the host is alive");
        match event {
            HostEvent::Answered {
                generation,
                plugin,
                result: Ok(items),
            } => got.push((plugin, generation, items)),
            other => panic!("unexpected {other:?}"),
        }
    }
    got.sort_by_key(|(plugin, ..)| *plugin);
    got
}

#[test]
fn home_asks_only_the_plugins_that_declared_it_and_says_so_in_the_query() {
    let host = started(vec![
        plugin("quiet", false),
        plugin("homebody", true),
        plugin("also", true),
    ]);
    assert_eq!(host.home(5), vec![1, 2]);
    let got = answers(&host, 2);
    assert_eq!(
        got.iter().map(|(plugin, ..)| *plugin).collect::<Vec<_>>(),
        vec![1, 2]
    );
    for (_, generation, items) in &got {
        assert_eq!(*generation, 5);
        assert_eq!(items[0].title, r#"{"home": true, "text": ""}"#);
    }
    // Nothing else is on its way: the plugin that did not declare it was not asked.
    std::thread::sleep(Duration::from_millis(200));
    assert!(host.events().try_recv().is_err());
}

#[test]
fn blank_typed_input_still_reaches_nobody_and_typed_text_carries_no_home_flag() {
    let host = started(vec![plugin("quiet", false), plugin("homebody", true)]);
    assert_eq!(host.query(1, "   "), Vec::<usize>::new());
    assert_eq!(host.query(2, "hello"), vec![0, 1]);
    for (_, generation, items) in answers(&host, 2) {
        assert_eq!(generation, 2);
        assert_eq!(items[0].title, r#"{"text": "hello"}"#);
    }
}

#[test]
fn with_no_home_plugin_the_home_query_asks_nobody() {
    let host = started(vec![plugin("quiet", false)]);
    assert_eq!(host.home(1), Vec::<usize>::new());
}
