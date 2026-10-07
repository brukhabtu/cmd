//! Fake plugins for the host's functional tests: a few lines of Python that speak the
//! protocol and misbehave on request. Each test binary includes this module.

#![allow(dead_code)]

use cmd_core::protocol::{Effect, Item};
use cmd_host::{HostEvent, Located, Manifest};

/// Answers describe, echoes queries as one item, copies the item on run. Special texts:
/// "stall" never answers, "late" answers after 300 ms, "chatter" writes a stray line,
/// "quit" exits, "fail" answers with an error, "unreadable" answers with an id-0 error.
pub const FAKE: &str = r#"
import json, sys, time
for line in sys.stdin:
    request = json.loads(line)
    reply = lambda result: print(json.dumps({"id": request["id"], "result": result}), flush=True)
    if request["method"] == "describe":
        reply({"name": NAME, "version": "0", "protocol": 0})
    elif request["method"] == "run":
        reply({"effect": {"kind": "copy", "text": request["params"]["item"]}})
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
        reply({"items": [{"id": "echo", "title": NAME + ":" + request["params"]["text"]}]})
"#;

/// The command for a fake named `name`; `slow` makes every query take 300 ms.
pub fn command(name: &str, slow: bool) -> Vec<String> {
    let body = if slow {
        FAKE.replace(
            "    request = json.loads(line)\n",
            "    request = json.loads(line)\n    if request[\"method\"] == \"query\":\n        time.sleep(0.3)\n",
        )
    } else {
        FAKE.to_string()
    };
    vec![
        "python3".to_string(),
        "-c".to_string(),
        format!("NAME = {name:?}\n{body}"),
    ]
}

/// A plugin directory the host can start, pointing at a fake.
pub fn located(name: &str, slow: bool) -> Located {
    Located {
        dir: ".".into(),
        manifest: Manifest {
            name: name.to_string(),
            command: command(name, slow),
        },
    }
}

/// A fake that claims to speak protocol `protocol`, for the host's version check.
pub fn speaking(name: &str, protocol: u32) -> Located {
    let mut located = located(name, false);
    let script = &mut located.manifest.command[2];
    assert!(
        script.contains("\"protocol\": 0"),
        "the fake answers describe with protocol 0"
    );
    *script = script.replace("\"protocol\": 0", &format!("\"protocol\": {protocol}"));
    located
}

/// The items `plugin` answered for `generation`. A query without a keyword reaches
/// every keywordless plugin, so the other plugins' answers to the same query arrive in
/// any order around this one and are skipped.
pub fn answer_from(
    events: &async_channel::Receiver<HostEvent>,
    plugin: usize,
    generation: u64,
) -> Vec<Item> {
    loop {
        match events.recv_blocking().unwrap() {
            HostEvent::Answered {
                generation: answered,
                plugin: from,
                result: Ok(items),
            } if answered == generation && from == plugin => return items,
            HostEvent::Answered { plugin: other, .. } if other != plugin => {}
            other => panic!("unexpected {other:?}"),
        }
    }
}

/// The effect of `plugin`'s run in `generation`, skipping other plugins' answers to
/// earlier queries that were still on their way.
pub fn effect_from(
    events: &async_channel::Receiver<HostEvent>,
    plugin: usize,
    generation: u64,
) -> Effect {
    loop {
        match events.recv_blocking().unwrap() {
            HostEvent::Ran {
                generation: ran,
                plugin: from,
                result: Ok(effect),
            } if ran == generation && from == plugin => return effect,
            HostEvent::Answered { plugin: other, .. } if other != plugin => {}
            other => panic!("unexpected {other:?}"),
        }
    }
}
