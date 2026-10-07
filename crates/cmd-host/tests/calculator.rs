//! Proves the host against the real calculator plugin, run through uv exactly
//! as the app runs it. Needs `uv` on PATH; CI runs `uv sync` first so the
//! handshake does not pay for building the environment.

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
    let events = host.events();

    assert!(host.query(1, "2 + 2 * 3").contains(&calculator));
    let items = answer_from(&events, calculator, 1);
    assert_eq!(items[0].title, "8");

    host.run(1, calculator, &items[0].id, DEFAULT_ACTION)
        .unwrap();
    assert_eq!(
        effect_from(&events, calculator, 1),
        Effect::Copy { text: "8".into() }
    );

    host.query(2, "not arithmetic");
    assert_eq!(answer_from(&events, calculator, 2), []);
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
