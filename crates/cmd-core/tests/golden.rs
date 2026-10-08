//! The host's side of the golden exchanges in `docs/plugin-protocol.golden.json`, which
//! `python/cmd-sdk/tests/unit/test_golden.py` checks the SDK against too: the host sends
//! the requests as written, and reads each answer as the fixture says it does.

use cmd_core::protocol::{
    ACCEPTED, DecodeError, Description, Items, Method, Ran, Request, decode_response,
    encode_request, result,
};
use cmd_core::query;
use serde_json::{Value, json};

const GOLDEN: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../docs/plugin-protocol.golden.json"
));

fn exchanges() -> Vec<Value> {
    let golden: Value = serde_json::from_str(GOLDEN).expect("the fixture is JSON");
    golden["exchanges"]
        .as_array()
        .expect("the fixture has a list of exchanges")
        .clone()
}

fn as_json<T: serde::Serialize>(value: &T) -> Value {
    serde_json::to_value(value).expect("protocol types serialise")
}

#[test]
fn the_fixture_holds_every_kind_of_exchange_the_document_promises() {
    let names: Vec<String> = exchanges()
        .iter()
        .map(|exchange| exchange["request"]["method"].as_str().unwrap().to_string())
        .collect();
    assert_eq!(names, ["describe", "describe", "query", "run", "query"]);
}

#[test]
fn every_request_is_one_the_host_reads_and_writes_back_as_it_is() {
    for exchange in exchanges() {
        let wire = &exchange["request"];
        let request: Request = serde_json::from_value(wire.clone()).expect("a request");
        let mut written = as_json(&request);
        // The host always writes its list of capabilities, so an older host's describe,
        // which has none, comes back with an empty one.
        if wire["method"] == "describe"
            && wire["params"].get("capabilities").is_none()
            && let Some(params) = written["params"].as_object_mut()
        {
            assert_eq!(params.remove("capabilities"), Some(json!([])));
        }
        assert_eq!(&written, wire, "{}", exchange["name"]);
    }
}

#[test]
fn the_describe_this_host_sends_is_the_golden_one() {
    let golden = exchanges()
        .into_iter()
        .find(|exchange| exchange["request"]["params"]["protocol"] == json!(1))
        .expect("a describe from a version 1 host");
    let line = encode_request(&Request {
        id: 1,
        method: Method::describe(),
    });
    let sent: Value = serde_json::from_str(&line).unwrap();
    assert_eq!(sent, golden["request"]);
}

#[test]
fn every_answer_reads_as_the_fixture_says() {
    for exchange in exchanges() {
        let name = &exchange["name"];
        let reads = &exchange["host_reads"];
        let line = exchange["answer"].to_string();
        let response = decode_response(&line).expect("an answer is a protocol message");
        assert_eq!(json!(response.id), exchange["request"]["id"], "{name}");
        if let Some(error) = reads.get("error") {
            match result::<Items>(response) {
                Err(DecodeError::Plugin(got)) => assert_eq!(&as_json(&got), error, "{name}"),
                other => panic!("{name}: expected the plugin's error, got {other:?}"),
            }
            continue;
        }
        match exchange["request"]["method"].as_str().unwrap() {
            "describe" => {
                let description: Description = result(response).expect("a description");
                assert!(ACCEPTED.contains(&description.protocol), "{name}");
                assert_eq!(&as_json(&description), &reads["description"], "{name}");
            }
            "query" => {
                let items: Items = result(response).expect("the answer as a whole decodes");
                assert_eq!(&as_json(&items.items), &reads["items"], "{name}");
                let dropped = reads["dropped"].as_array().unwrap();
                assert_eq!(items.dropped.len(), dropped.len(), "{name}");
                for (got, want) in items.dropped.iter().zip(dropped) {
                    assert!(got.starts_with(want.as_str().unwrap()), "{name}: {got}");
                }
                let ranked: Vec<Value> = query::merge([(0, items.items)])
                    .into_iter()
                    .map(|hit| json!(hit.item.id))
                    .collect();
                assert_eq!(&json!(ranked), &reads["ranked"], "{name}");
            }
            "run" => {
                let ran: Ran = result(response).expect("an effect");
                assert_eq!(&as_json(&ran.effect), &reads["effect"], "{name}");
            }
            other => panic!("{name}: no expectation for {other}"),
        }
    }
}
