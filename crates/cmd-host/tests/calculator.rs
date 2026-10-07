//! Proves the host against the real calculator plugin, run through uv exactly
//! as the app runs it. Needs `uv` on PATH; CI runs `uv sync` first so the
//! handshake does not pay for building the environment.

use std::path::PathBuf;

use cmd_core::protocol::Effect;
use cmd_core::state::DEFAULT_ACTION;
use cmd_host::{Host, Timeouts, manifest};

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

    let (mut host, errors) = Host::start(located, Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    assert!(
        host.descriptions()
            .any(|description| description.name == "calculator")
    );

    let (hits, errors) = host.query("2 + 2 * 3");
    assert!(errors.is_empty(), "{errors:?}");
    assert_eq!(hits[0].item.title, "8");

    let effect = host
        .run(hits[0].plugin, &hits[0].item.id, DEFAULT_ACTION)
        .unwrap();
    assert_eq!(effect, Effect::Copy { text: "8".into() });

    let (hits, errors) = host.query("not arithmetic");
    assert!(errors.is_empty(), "{errors:?}");
    assert_eq!(hits, []);
}
