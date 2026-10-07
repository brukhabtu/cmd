//! Proves the host against the real calculator plugin, run through uv exactly
//! as the app runs it. Needs `uv` on PATH; CI runs `uv sync` first so the
//! handshake does not pay for building the environment.

use std::path::PathBuf;

use cmd_core::protocol::Effect;
use cmd_core::state::DEFAULT_ACTION;
use cmd_host::{Host, HostEvent, Timeouts, manifest};

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
    let items = match events.recv_blocking().unwrap() {
        HostEvent::Answered {
            generation: 1,
            plugin,
            result: Ok(items),
        } if plugin == calculator => items,
        other => panic!("unexpected {other:?}"),
    };
    assert_eq!(items[0].title, "8");

    host.run(1, calculator, &items[0].id, DEFAULT_ACTION)
        .unwrap();
    assert_eq!(
        events.recv_blocking().unwrap(),
        HostEvent::Ran {
            generation: 1,
            plugin: calculator,
            result: Ok(Effect::Copy { text: "8".into() })
        }
    );

    host.query(2, "not arithmetic");
    match events.recv_blocking().unwrap() {
        HostEvent::Answered {
            generation: 2,
            result: Ok(items),
            ..
        } => assert_eq!(items, []),
        other => panic!("unexpected {other:?}"),
    }
}
