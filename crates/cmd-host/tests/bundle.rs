//! Proves the bundle's wiring through real processes: a fake cmd.app under a temporary
//! directory, a fake plugin that answers with its own environment, and a fake uv that
//! records how it was called.

use std::ffi::{OsStr, OsString};
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::Duration;

use cmd_host::{Bundle, Host, HostEvent, Located, Manifest, Startup, Timeouts, bundle};

/// Answers describe, answers every query with one item per variable the bundle sets,
/// titled `NAME=value`, and exits on "quit" so the host has to start it again.
const ECHO_ENV: &str = r#"
import json, os, sys
for line in sys.stdin:
    request = json.loads(line)
    reply = lambda result: print(json.dumps({"id": request["id"], "result": result}), flush=True)
    if request["method"] == "describe":
        reply({"name": "echo-env", "version": "0", "protocol": 1})
    elif request["params"]["text"] == "quit":
        sys.exit(0)
    else:
        names = ["PATH", "UV_PYTHON_INSTALL_DIR", "UV_CACHE_DIR", "UV_PYTHON_PREFERENCE"]
        reply({"items": [{"id": name, "title": name + "=" + os.environ.get(name, "")} for name in names]})
"#;

/// A fake cmd.app, its home directory, and the fake plugin's script beside them.
struct Fake {
    root: PathBuf,
    macos: PathBuf,
    home: PathBuf,
}

impl Fake {
    fn new(tag: &str) -> Fake {
        let root = std::env::temp_dir().join(format!("cmd-bundle-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        let macos = root.join("cmd.app/Contents/MacOS");
        let home = root.join("home");
        std::fs::create_dir_all(&macos).unwrap();
        std::fs::create_dir_all(&home).unwrap();
        std::fs::write(root.join("echo_env.py"), ECHO_ENV).unwrap();
        Fake { root, macos, home }
    }

    fn bundle(&self) -> Bundle {
        Bundle::detect(&self.macos.join("cmd"), &self.home).expect("the fake is a bundle")
    }

    /// An executable shell script in the bundle's `Contents/MacOS` directory.
    fn carry(&self, name: &str, body: &str) {
        let path = self.macos.join(name);
        std::fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
    }

    /// The plugin as a manifest inside the bundle names it: a bare command that only the
    /// bundle's PATH can find.
    fn bundled_plugin(&self) -> Located {
        let script = self.root.join("echo_env.py");
        self.carry("echo-env", &format!("exec python3 '{}'", script.display()));
        Located {
            dir: self.root.clone(),
            manifest: Manifest {
                name: "echo-env".into(),
                command: vec!["echo-env".into()],
            },
        }
    }

    /// The same plugin started by path, for a host outside any bundle.
    fn plain_plugin(&self) -> Located {
        Located {
            dir: self.root.clone(),
            manifest: Manifest {
                name: "echo-env".into(),
                command: vec![
                    "python3".into(),
                    self.root.join("echo_env.py").display().to_string(),
                ],
            },
        }
    }

    fn support(&self) -> PathBuf {
        self.home.join("Library/Application Support/cmd")
    }
}

impl Drop for Fake {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

fn next(host: &Host) -> HostEvent {
    let events = host.events();
    let waited = std::thread::spawn(move || events.recv_blocking());
    let deadline = std::time::Instant::now() + Duration::from_secs(20);
    while !waited.is_finished() {
        assert!(
            std::time::Instant::now() < deadline,
            "no host event within 20 s"
        );
        std::thread::sleep(Duration::from_millis(10));
    }
    waited.join().unwrap().expect("the host is alive")
}

/// What the plugin says its environment is, by variable.
fn environment_of(host: &Host, generation: u64) -> Vec<(String, String)> {
    host.query(generation, "env");
    match next(host) {
        HostEvent::Answered {
            result: Ok(items), ..
        } => items
            .iter()
            .map(|item| {
                let (name, value) = item.title.split_once('=').unwrap();
                (name.to_string(), value.to_string())
            })
            .collect(),
        other => panic!("unexpected {other:?}"),
    }
}

fn get<'a>(env: &'a [(String, String)], name: &str) -> &'a str {
    &env.iter().find(|(key, _)| key == name).unwrap().1
}

fn assert_bundled(env: &[(String, String)], fake: &Fake) {
    let path = get(env, "PATH");
    let first = path.split(':').next().unwrap();
    assert_eq!(Path::new(first), fake.macos, "{path}");
    assert_eq!(
        Path::new(get(env, "UV_PYTHON_INSTALL_DIR")),
        fake.support().join("python")
    );
    assert_eq!(
        Path::new(get(env, "UV_CACHE_DIR")),
        fake.support().join("uv-cache")
    );
    assert_eq!(get(env, "UV_PYTHON_PREFERENCE"), "only-managed");
}

#[test]
fn inside_a_bundle_plugins_run_on_its_path_and_uv_s_managed_python_even_after_a_restart() {
    let fake = Fake::new("env");
    let inherited = std::env::var_os("PATH");
    let env = fake.bundle().environment(inherited.as_deref());
    let (host, errors) = Host::start_in(vec![fake.bundled_plugin()], Timeouts::default(), &env);
    assert!(errors.is_empty(), "{errors:?}");
    assert_bundled(&environment_of(&host, 1), &fake);

    host.query(2, "quit");
    assert!(matches!(next(&host), HostEvent::Answered { .. }));
    assert!(
        matches!(next(&host), HostEvent::Restarted { .. }),
        "the plugin is started again"
    );
    assert_bundled(&environment_of(&host, 3), &fake);
}

#[test]
fn outside_a_bundle_plugins_get_the_app_s_own_environment() {
    let fake = Fake::new("plain");
    let (host, errors) = Host::start(vec![fake.plain_plugin()], Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    let env = environment_of(&host, 1);
    for name in [
        "PATH",
        "UV_PYTHON_INSTALL_DIR",
        "UV_CACHE_DIR",
        "UV_PYTHON_PREFERENCE",
    ] {
        let own = std::env::var_os(name).unwrap_or_default();
        assert_eq!(OsStr::new(get(&env, name)), own, "{name}");
    }
}

/// Start the bundled plugin through the app's path and keep every report.
fn start_bundled(fake: &Fake, bundle: Option<&Bundle>) -> (Host, Vec<Startup>) {
    let mut reports = Vec::new();
    let inherited = std::env::var_os("PATH");
    let host = bundle::start_reporting(
        bundle,
        inherited.as_deref(),
        None,
        vec![fake.bundled_plugin()],
        Timeouts::default(),
        |report| reports.push(report),
    );
    (host, reports)
}

#[test]
fn the_bundled_uv_fetches_python_with_the_bundle_s_environment_before_the_first_plugin() {
    let fake = Fake::new("fetch");
    let record = fake.root.join("uv-called");
    fake.carry(
        "uv",
        &format!(
            "printf '%s\\n' \"$@\" \"$UV_PYTHON_INSTALL_DIR\" \"$UV_PYTHON_PREFERENCE\" > '{}'",
            record.display()
        ),
    );
    let (_host, reports) = start_bundled(&fake, Some(&fake.bundle()));
    match reports.as_slice() {
        [
            Startup::FetchingPython,
            Startup::FetchedPython(Ok(())),
            Startup::Up { name, .. },
        ] => assert_eq!(name, "echo-env"),
        other => panic!("unexpected {other:?}"),
    }
    let called = std::fs::read_to_string(&record).expect("the bundled uv ran");
    let python = fake.support().join("python");
    assert_eq!(
        called.lines().collect::<Vec<_>>(),
        [
            "python",
            "install",
            "3.15",
            "--no-bin",
            &python.display().to_string(),
            "only-managed"
        ]
    );
}

#[test]
fn a_failed_fetch_says_what_uv_said_and_the_plugins_still_start() {
    let fake = Fake::new("fetch-fails");
    fake.carry("uv", "echo 'error: no network to fetch 3.15' >&2\nexit 2");
    let (_host, reports) = start_bundled(&fake, Some(&fake.bundle()));
    match reports.as_slice() {
        [
            Startup::FetchingPython,
            Startup::FetchedPython(Err(message)),
            Startup::Up { .. },
        ] => assert!(
            message.contains("Python 3.15") && message.contains("no network"),
            "{message}"
        ),
        other => panic!("unexpected {other:?}"),
    }
}

#[test]
fn a_bundle_without_uv_says_so() {
    let fake = Fake::new("no-uv");
    let env: Vec<(OsString, OsString)> = fake.bundle().environment(None);
    let error = fake.bundle().install_python(&env).unwrap_err();
    assert!(error.contains("could not run"), "{error}");
    assert!(error.contains("uv"), "{error}");
}

#[test]
fn outside_a_bundle_nothing_is_fetched() {
    let fake = Fake::new("no-bundle");
    let plugin = fake.plain_plugin();
    let mut reports = Vec::new();
    let _host = bundle::start_reporting(
        None,
        None,
        None,
        vec![plugin],
        Timeouts::default(),
        |report| {
            reports.push(report);
        },
    );
    assert!(
        matches!(reports.as_slice(), [Startup::Up { .. }]),
        "{reports:?}"
    );
}
