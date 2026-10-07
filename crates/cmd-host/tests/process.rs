//! Proves the process discipline against a fake plugin: a few lines of Python
//! that answer the protocol, stall, answer late, or misbehave on request.

use std::path::Path;
use std::time::Duration;

use cmd_core::protocol::{Description, Items, Method, VERSION};
use cmd_host::{CallError, PluginProcess};

const FAKE: &str = r#"
import json, sys, time
for line in sys.stdin:
    request = json.loads(line)
    reply = lambda result: print(json.dumps({"id": request["id"], "result": result}), flush=True)
    if request["method"] == "describe":
        reply({"name": "fake", "version": "0", "protocol": 0})
    elif request["params"]["text"] == "stall":
        pass
    elif request["params"]["text"] == "late":
        time.sleep(0.3)
        reply({"items": [{"id": "late", "title": "late"}]})
    elif request["params"]["text"] == "unreadable":
        print(json.dumps({"id": 0, "error": {"code": "bad_request", "message": "params.text must be a str"}}), flush=True)
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
    query_within(process, text, Duration::from_secs(5))
}

fn query_within(
    process: &mut PluginProcess,
    text: &str,
    timeout: Duration,
) -> Result<Items, CallError> {
    process.call(Method::Query { text: text.into() }, timeout)
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
    let error = query_within(&mut process, "stall", Duration::from_millis(200)).unwrap_err();
    assert!(matches!(error, CallError::Timeout(_)), "{error}");
}

#[test]
fn a_late_answer_is_dropped_and_the_next_call_still_works() {
    let mut process = fake();
    let timed_out = query_within(&mut process, "late", Duration::from_millis(50));
    assert!(matches!(timed_out, Err(CallError::Timeout(_))));
    // The answer to "late" arrives first, under the old id, and is skipped.
    assert_eq!(
        query(&mut process, "after").unwrap().items[0].title,
        "after"
    );
}

#[test]
fn an_error_with_id_zero_answers_the_request_in_flight() {
    let mut process = fake();
    let error = query(&mut process, "unreadable").unwrap_err();
    assert!(
        error
            .to_string()
            .contains("bad_request: params.text must be a str"),
        "{error}"
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
fn a_plugin_error_reaches_the_caller_with_its_message() {
    let mut process = fake();
    let error = query(&mut process, "fail").unwrap_err();
    assert!(
        error
            .to_string()
            .contains("the plugin reported an error: boom: no"),
        "{error}"
    );
}

#[test]
fn an_exited_plugin_is_reported_as_exited() {
    let mut process = fake();
    let error = query(&mut process, "quit").unwrap_err();
    assert!(matches!(error, CallError::Exited), "{error}");
}
