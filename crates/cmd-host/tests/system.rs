//! Proves the host against the real system plugin, run through uv exactly as
//! the app runs it. The run names an item the plugin never issues: this test
//! also runs under `cargo test` on a developer's Mac and must never put it to
//! sleep, lock it or empty its Trash.

mod common;

use std::path::PathBuf;

use cmd_core::protocol::Effect;
use cmd_core::state::DEFAULT_ACTION;
use cmd_host::{Host, Timeouts, manifest};
use common::{answer_from, effect_from};

fn plugins_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../plugins")
}

#[test]
fn a_command_is_a_definite_answer_and_an_unknown_item_is_shown_not_run() {
    let found = manifest::discover(&plugins_dir()).expect("plugins directory exists");
    let located: Vec<_> = found
        .into_iter()
        .map(|entry| entry.expect("every manifest is valid"))
        .collect();
    assert!(
        located
            .iter()
            .any(|plugin| plugin.manifest.name == "system")
    );

    let (host, errors) = Host::start(located, Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    let system = host
        .descriptions()
        .position(|description| description.name == "system")
        .expect("the system plugin started");
    let events = host.events();

    // No keyword: the plugin sees every query, and a command is one scoreless item.
    assert!(host.query(1, "lock").contains(&system));
    let items = answer_from(&events, system, 1);
    assert_eq!(items.len(), 1);
    assert_eq!(items[0].id, "lock");
    assert_eq!(items[0].score, None);
    assert_eq!(items[0].actions, []);

    host.query(2, "safari");
    assert_eq!(answer_from(&events, system, 2), []);

    host.run(2, system, "nothing", DEFAULT_ACTION).unwrap();
    match effect_from(&events, system, 2) {
        Effect::Show { text } => assert!(text.contains("nothing"), "{text}"),
        other => panic!("unexpected {other:?}"),
    }
}
