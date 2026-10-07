//! Proves the host against the real applications plugin, run through uv exactly as the
//! app runs it, pointed with `--root` at a fake Applications folder so the test is the
//! same on Linux and on a Mac. The real calculator runs beside it: a query both answer
//! is the case that criterion #2 names, and `cmd_core::query::merge` must put the
//! calculator's definite answer above an application scored a full 1.0.

mod common;

use std::path::{Path, PathBuf};

use cmd_core::protocol::{Effect, Icon, Item};
use cmd_core::query::merge;
use cmd_core::state::DEFAULT_ACTION;
use cmd_host::{Host, HostEvent, Located, Timeouts, manifest};
use common::{answer_from, effect_from};

fn plugins_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../plugins")
}

/// A fake Applications folder: bundles at the top and one folder down, a bundle named
/// like an arithmetic expression, and a plain file in a bundle's clothing.
fn fake_root() -> PathBuf {
    let root = std::env::temp_dir().join(format!("cmd-applications-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    for bundle in [
        "Safari.app",
        "Visual Studio Code.app",
        "Utilities/Terminal.app",
        "1+1.app",
    ] {
        std::fs::create_dir_all(root.join(bundle)).unwrap();
    }
    std::fs::write(root.join("Notes.app"), "not a bundle").unwrap();
    root
}

/// The applications plugin as the manifest starts it, plus `--root` at the fake folder.
fn applications_at(root: &Path) -> Located {
    let mut located =
        manifest::load(&plugins_dir().join("applications")).expect("the manifest loads");
    assert_eq!(located.manifest.name, "applications");
    located
        .manifest
        .command
        .extend(["--root".to_string(), root.display().to_string()]);
    located
}

/// The answers of each of `plugins` to `generation`, in the order the plugins are named.
/// `answer_from` skips every other plugin's answer, so two calls in a row would drop
/// the second plugin's answer if it arrived first; this keeps every answer it is asked for.
fn answers_to(
    events: &async_channel::Receiver<HostEvent>,
    generation: u64,
    plugins: &[usize],
) -> Vec<Vec<Item>> {
    let mut answers: Vec<Option<Vec<Item>>> = vec![None; plugins.len()];
    while answers.iter().any(Option::is_none) {
        match events.recv_blocking().unwrap() {
            HostEvent::Answered {
                generation: answered,
                plugin,
                result: Ok(items),
            } if answered == generation => {
                if let Some(slot) = plugins.iter().position(|&wanted| wanted == plugin) {
                    answers[slot] = Some(items);
                }
            }
            HostEvent::Answered {
                generation: answered,
                ..
            } if answered < generation => {}
            other => panic!("unexpected {other:?}"),
        }
    }
    answers.into_iter().flatten().collect()
}

#[test]
fn applications_are_found_opened_as_file_urls_and_ranked_below_a_definite_answer() {
    let root = fake_root();
    let calculator = manifest::load(&plugins_dir().join("calculator")).expect("the manifest loads");
    let (host, errors) = Host::start(
        vec![applications_at(&root), calculator],
        Timeouts::default(),
    );
    assert!(errors.is_empty(), "{errors:?}");
    let descriptions: Vec<_> = host.descriptions().collect();
    let applications = descriptions
        .iter()
        .position(|description| description.name == "applications")
        .expect("the applications plugin started");
    let calculator = descriptions
        .iter()
        .position(|description| description.name == "calculator")
        .expect("the calculator started");
    assert_eq!(descriptions[applications].keyword, None);
    let events = host.events();

    // No keyword: part of a name reaches the plugin, and a bundle one folder down is found.
    assert!(host.query(1, "term").contains(&applications));
    let items = answer_from(&events, applications, 1);
    assert_eq!(items.len(), 1, "{items:?}");
    let terminal = &items[0];
    assert_eq!(terminal.title, "Terminal");
    assert_eq!(
        terminal.id,
        root.join("Utilities/Terminal.app").display().to_string()
    );
    assert!(
        terminal.subtitle.as_deref().unwrap().ends_with("Utilities"),
        "{terminal:?}"
    );
    let score = terminal.score.expect("a fuzzy match carries a score");
    assert!(score > 0.0 && score <= 1.0, "{score}");
    assert_eq!(
        terminal.icon,
        Some(Icon::Path {
            path: terminal.id.clone()
        })
    );

    // Enter opens the bundle: the host is handed a file URL, percent-encoded.
    host.query(2, "visual");
    let items = answer_from(&events, applications, 2);
    assert_eq!(items[0].title, "Visual Studio Code");
    host.run(2, applications, &items[0].id, DEFAULT_ACTION)
        .unwrap();
    assert_eq!(
        effect_from(&events, applications, 2),
        Effect::Open {
            target: format!("file://{}/Visual%20Studio%20Code.app", root.display())
        }
    );

    // Both plugins answer "1+1": the application is an exact match scored 1.0, and the
    // calculator's definite answer still comes first once the answers are merged.
    let asked = host.query(3, "1+1");
    assert!(asked.contains(&applications) && asked.contains(&calculator));
    let mut answers = answers_to(&events, 3, &[applications, calculator]).into_iter();
    let (app_items, calc_items) = (answers.next().unwrap(), answers.next().unwrap());
    assert_eq!(app_items.len(), 1);
    assert_eq!(app_items[0].score, Some(1.0));
    assert_eq!(calc_items[0].title, "2");
    assert_eq!(calc_items[0].score, None);
    let hits = merge(vec![(applications, app_items), (calculator, calc_items)]);
    let titles: Vec<&str> = hits.iter().map(|hit| hit.item.title.as_str()).collect();
    assert_eq!(titles, ["2", "1+1"]);
    assert_eq!(hits[0].plugin, calculator);

    // Nothing matches nonsense, and the plain file is never an application.
    host.query(4, "zzzz");
    assert_eq!(answer_from(&events, applications, 4), []);
    host.query(5, "notes");
    assert_eq!(answer_from(&events, applications, 5), []);
}
