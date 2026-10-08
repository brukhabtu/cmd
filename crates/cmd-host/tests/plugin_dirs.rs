//! The data and config directories the host gives each plugin: the two environment
//! variables, a data directory that can be written to without a restart, and a config
//! directory whose change, or appearing, restarts the plugin.

use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use cmd_host::{Host, HostEvent, Located, Manifest, Startup, Timeouts, manifest};

/// Speaks protocol 0. A query answers one item whose title depends on its text: "env"
/// gives the two variables, "write" writes a file in the data directory, "config" gives
/// the text of `config.toml` in the config directory, or "none".
const SCRIPT: &str = r#"
import json, os, sys
for line in sys.stdin:
    request = json.loads(line)
    def reply(result):
        print(json.dumps({"id": request["id"], "result": result}), flush=True)
    if request["method"] == "describe":
        reply({"name": "dirs", "version": "0", "protocol": 0})
        continue
    text = request["params"]["text"]
    data = os.environ.get("CMD_PLUGIN_DATA", "unset")
    config = os.environ.get("CMD_PLUGIN_CONFIG", "unset")
    if text == "env":
        title = data + "|" + config
    elif text == "write":
        with open(os.path.join(data, "state.json"), "w") as out:
            out.write("{}")
        title = "wrote"
    elif text == "write-here":
        with open("state.json", "w") as out:
            out.write("{}")
        title = "wrote"
    else:
        try:
            with open(os.path.join(config, "config.toml")) as source:
                title = source.read()
        except OSError:
            title = "none"
    reply({"items": [{"id": "x", "title": title}]})
"#;

/// A scratch tree: `user` stands for the per-user cmd directory, and the plugin runs from
/// `plugin`, a directory of its own, as a real one does.
struct Tree {
    user: PathBuf,
    plugin: PathBuf,
}

impl Tree {
    fn new(tag: &str) -> Self {
        let root = std::env::temp_dir().join(format!("cmd-host-dirs-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let user = root.join("cmd");
        let plugin = user.join("plugins/dirs");
        std::fs::create_dir_all(&plugin).unwrap();
        Self { user, plugin }
    }

    fn located(&self) -> Located {
        Located {
            dir: self.plugin.clone(),
            manifest: Manifest {
                name: "dirs".to_string(),
                command: vec!["python3".into(), "-c".into(), SCRIPT.into()],
            },
        }
    }

    fn start(&self, user_dir: &Path) -> Host {
        let mut reports = Vec::new();
        let host = Host::start_reporting_with(
            vec![self.located()],
            Timeouts::default(),
            &[],
            Some(user_dir),
            |report| reports.push(report),
        );
        assert!(
            matches!(reports.as_slice(), [Startup::Up { .. }]),
            "{reports:?}"
        );
        host
    }
}

/// Ask `text`, passing over reloads that arrive first.
fn ask(host: &Host, generation: u64, text: &str) -> String {
    host.query(generation, text);
    let events = host.events();
    let started = Instant::now();
    loop {
        match events.try_recv() {
            Ok(HostEvent::Answered {
                result: Ok(items), ..
            }) => return items[0].title.clone(),
            Ok(HostEvent::Reloaded { .. }) => {}
            Ok(other) => panic!("unexpected {other:?}"),
            Err(_) => std::thread::sleep(Duration::from_millis(20)),
        }
        assert!(started.elapsed() < Duration::from_secs(10), "no answer");
    }
}

fn reloaded_within(host: &Host, limit: Duration) -> bool {
    let events = host.events();
    let started = Instant::now();
    while started.elapsed() < limit {
        match events.try_recv() {
            Ok(HostEvent::Reloaded { plugin: 0 }) => return true,
            Ok(other) => panic!("unexpected {other:?}"),
            Err(_) => std::thread::sleep(Duration::from_millis(20)),
        }
    }
    false
}

#[test]
fn both_directories_reach_the_plugin_as_environment_and_only_the_data_one_exists() {
    let tree = Tree::new("env");
    let host = tree.start(&tree.user);
    let data = tree.user.join("plugin-data/dirs");
    let config = tree.user.join("plugin-config/dirs");
    assert_eq!(
        ask(&host, 1, "env"),
        format!("{}|{}", data.display(), config.display())
    );
    assert!(data.is_dir(), "the host creates the data directory");
    assert!(!config.exists(), "the host leaves the config directory out");
    assert!(
        data.starts_with(manifest::plugin_data_root(&tree.user)) && data.is_absolute(),
        "{data:?}"
    );
}

#[test]
fn a_plugin_writing_in_its_data_directory_is_not_restarted() {
    let tree = Tree::new("write");
    let host = tree.start(&tree.user);
    for generation in 1..=3 {
        assert_eq!(ask(&host, generation, "write"), "wrote");
    }
    assert!(tree.user.join("plugin-data/dirs/state.json").is_file());
    assert!(
        !reloaded_within(&host, Duration::from_secs(1)),
        "writing to the data directory reloaded the plugin"
    );
}

#[test]
fn writing_next_to_the_plugin_reloads_it_which_is_why_the_data_directory_is_elsewhere() {
    let tree = Tree::new("control");
    let host = tree.start(&tree.user);
    assert_eq!(ask(&host, 1, "write-here"), "wrote");
    assert!(
        reloaded_within(&host, Duration::from_secs(10)),
        "a file in the plugin directory should reload it"
    );
}

#[test]
fn a_data_directory_inside_the_watched_one_would_reload_the_plugin() {
    // What the host did before it had a data directory, in effect: with the "per-user
    // directory" placed inside the plugin directory, the same write restarts the plugin.
    let tree = Tree::new("inside");
    let host = tree.start(&tree.plugin);
    assert_eq!(ask(&host, 1, "write"), "wrote");
    assert!(reloaded_within(&host, Duration::from_secs(10)));
}

#[test]
fn a_config_directory_that_appears_later_reloads_the_plugin_and_so_does_each_change() {
    let tree = Tree::new("config");
    let host = tree.start(&tree.user);
    assert_eq!(ask(&host, 1, "config"), "none");

    let config = tree.user.join("plugin-config/dirs");
    std::fs::create_dir_all(&config).unwrap();
    std::fs::write(config.join("config.toml"), "first").unwrap();
    assert!(
        reloaded_within(&host, Duration::from_secs(10)),
        "the config directory appearing should reload the plugin"
    );
    assert_eq!(ask(&host, 2, "config"), "first");

    std::fs::write(config.join("config.toml"), "second").unwrap();
    assert!(
        reloaded_within(&host, Duration::from_secs(10)),
        "a changed config file should reload the plugin"
    );
    assert_eq!(ask(&host, 3, "config"), "second");
}

#[test]
fn another_plugin_s_config_does_not_reload_this_one() {
    let tree = Tree::new("other");
    let host = tree.start(&tree.user);
    let other = tree.user.join("plugin-config/someone-else");
    std::fs::create_dir_all(&other).unwrap();
    std::fs::write(other.join("config.toml"), "x").unwrap();
    assert!(!reloaded_within(&host, Duration::from_secs(1)));
}

#[test]
fn a_name_that_cannot_be_a_directory_is_refused() {
    let tree = Tree::new("name");
    let mut located = tree.located();
    located.manifest.name = "../escape".to_string();
    let mut reports = Vec::new();
    let _host = Host::start_reporting_with(
        vec![located],
        Timeouts::default(),
        &[],
        Some(&tree.user),
        |report| reports.push(report),
    );
    assert!(
        matches!(reports.as_slice(), [Startup::Failed(_)]),
        "{reports:?}"
    );
    assert!(!tree.user.join("escape").exists());
}

#[test]
fn an_unwritable_user_directory_is_reported_naming_the_directory() {
    let tree = Tree::new("blocked");
    // A file where the plugin-data directory should be, so it cannot be made.
    std::fs::write(tree.user.join("plugin-data"), b"in the way").unwrap();
    let mut reports = Vec::new();
    let _host = Host::start_reporting_with(
        vec![tree.located()],
        Timeouts::default(),
        &[],
        Some(&tree.user),
        |report| reports.push(report),
    );
    let [Startup::Failed(error)] = reports.as_slice() else {
        panic!("{reports:?}");
    };
    let message = error.to_string();
    assert!(
        message.contains("cannot make the data directory"),
        "{message}"
    );
    assert!(message.contains("plugin-data"), "{message}");
}
