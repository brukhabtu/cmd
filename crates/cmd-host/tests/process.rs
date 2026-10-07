//! Proves the process discipline against a fake plugin: a few lines of Python
//! that answer the protocol, stall, or misbehave on request.

use std::path::Path;
use std::time::Duration;

use cmd_core::protocol::{Description, Items, Method, VERSION};
use cmd_host::{CallError, PluginProcess};

const FAKE: &str = r#"
import json, sys
for line in sys.stdin:
    request = json.loads(line)
    reply = lambda result: print(json.dumps({"id": request["id"], "result": result}), flush=True)
    if request["method"] == "describe":
        reply({"name": "fake", "version": "0", "protocol": 0})
    elif request["params"]["text"] == "stall":
        pass
    elif request["params"]["text"] == "chatter":
        print("debugging...", flush=True)
    elif request["params"]["text"] == "quit":
        sys.exit(0)
    elif request["params"]["text"] == "fail":
        print(json.dumps({"id": request["id"], "error": {"code": "boom", "message": "no"}}), flush=True)
    else:
        reply({"items": [{"id": "echo", "title": request["params"]["text"]}]})
"#;

fn fake() -> PluginProcess {
    let command = vec!["python3".to_string(), "-c".to_string(), FAKE.to_string()];
    PluginProcess::spawn(&command, Path::new(".")).expect("python3 is on PATH")
}

fn query(process: &mut PluginProcess, text: &str) -> Result<Items, CallError> {
    process.call(Method::Query { text: text.into() }, Duration::from_secs(5))
}

#[test]
fn a_plugin_answers_describe_and_query() {
    let mut process = fake();
    let description: Description = process
        .call(
            Method::Describe { protocol: VERSION },
            Duration::from_secs(5),
        )
        .unwrap();
    assert_eq!(description.name, "fake");
    assert_eq!(
        query(&mut process, "hello").unwrap().items[0].title,
        "hello"
    );
}

#[test]
fn a_silent_plugin_times_out() {
    let mut process = fake();
    let error = process
        .call::<Items>(
            Method::Query {
                text: "stall".into(),
            },
            Duration::from_millis(200),
        )
        .unwrap_err();
    assert!(matches!(error, CallError::Timeout(_)), "{error}");
}

#[test]
fn a_late_answer_is_dropped_and_the_next_call_still_works() {
    let mut process = fake();
    let _ = process.call::<Items>(
        Method::Query {
            text: "stall".into(),
        },
        Duration::from_millis(100),
    );
    assert_eq!(
        query(&mut process, "after").unwrap().items[0].title,
        "after"
    );
}

#[test]
fn stray_stdout_is_a_protocol_error_that_names_the_line() {
    let mut process = fake();
    let error = query(&mut process, "chatter").unwrap_err();
    assert!(
        matches!(&error, CallError::NotProtocol { line } if line == "debugging..."),
        "{error}"
    );
    assert!(error.to_string().contains("stderr"));
}

#[test]
fn a_plugin_error_is_reported_as_one() {
    let mut process = fake();
    let error = query(&mut process, "fail").unwrap_err();
    assert!(
        error.to_string().contains("plugin reported an error"),
        "{error}"
    );
}

#[test]
fn an_exited_plugin_is_reported_as_exited() {
    let mut process = fake();
    let error = query(&mut process, "quit").unwrap_err();
    assert!(matches!(error, CallError::Exited), "{error}");
}
