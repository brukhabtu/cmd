//! Proves the host against the real files plugin, run through uv exactly as the app
//! runs it, with fake `mdfind` and `open` programs ahead of the real ones on PATH so
//! the test is the same on Linux and on a Mac. Needs `uv` on PATH; CI runs `uv sync`
//! first so the handshake does not pay for building the environment.

use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use cmd_core::protocol::Effect;
use cmd_core::state::DEFAULT_ACTION;
use cmd_host::{Host, HostEvent, Timeouts, manifest};

fn plugins_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../plugins")
}

/// The fakes directory holds `mdfind` and `open` alone, so `uv` is still found further
/// along PATH. `mdfind` answers with two paths under the directory; `open` logs its
/// arguments.
fn install_fakes() -> (PathBuf, Vec<PathBuf>) {
    let dir = std::env::temp_dir().join(format!("cmd-files-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let found = vec![dir.join("Projects/cmd/README.md"), dir.join("readme.txt")];
    let mdfind = format!(
        "#!/bin/sh\nprintf '%s\\0' '{}' '{}'\n",
        found[0].display(),
        found[1].display()
    );
    let open = format!(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" >> '{}'\n",
        dir.join("open.log").display()
    );
    for (name, body) in [("mdfind", mdfind), ("open", open)] {
        let path = dir.join(name);
        std::fs::write(&path, body).unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
    }
    (dir, found)
}

/// The folder as the plugin shows it: the home directory shortened to `~`.
fn folder_as_shown(path: &Path) -> String {
    let parent = path.parent().unwrap();
    match std::env::var_os("HOME").map(PathBuf::from) {
        Some(home) if parent == home => "~".to_string(),
        Some(home) => match parent.strip_prefix(&home) {
            Ok(rest) => format!("~/{}", rest.display()),
            Err(_) => parent.display().to_string(),
        },
        None => parent.display().to_string(),
    }
}

#[test]
fn files_lists_names_with_their_folders_and_enter_reveals_while_the_second_action_opens() {
    let (fakes, found) = install_fakes();
    let mut located = manifest::load(&plugins_dir().join("files")).expect("the manifest loads");
    let path = format!(
        "PATH={}:{}",
        fakes.display(),
        std::env::var("PATH").unwrap_or_default()
    );
    located
        .manifest
        .command
        .splice(0..0, ["env".to_string(), path]);

    let (host, errors) = Host::start(vec![located], Timeouts::default());
    assert!(errors.is_empty(), "{errors:?}");
    let files = host
        .descriptions()
        .position(|description| description.name == "files")
        .expect("files started");
    assert_eq!(
        host.descriptions().nth(files).unwrap().keyword.as_deref(),
        Some("f")
    );
    let events = host.events();

    // The keyword routes to files alone; the rows are names with their folders.
    assert_eq!(host.query(1, "f readme"), vec![files]);
    let items = match events.recv_blocking().unwrap() {
        HostEvent::Answered {
            generation: 1,
            plugin,
            result: Ok(items),
        } if plugin == files => items,
        other => panic!("unexpected {other:?}"),
    };
    let titles: Vec<&str> = items.iter().map(|item| item.title.as_str()).collect();
    assert_eq!(titles, ["readme.txt", "README.md"]);
    assert_eq!(items[0].id, found[1].display().to_string());
    assert_eq!(
        items[0].subtitle.as_deref(),
        Some(folder_as_shown(&found[1]).as_str())
    );
    assert_eq!(
        items[1].subtitle.as_deref(),
        Some(folder_as_shown(&found[0]).as_str())
    );
    for item in &items {
        let actions: Vec<&str> = item
            .actions
            .iter()
            .map(|action| action.id.as_str())
            .collect();
        assert_eq!(actions, ["reveal", "open"]);
    }

    // Enter reveals: the plugin runs `open -R` itself and asks the host only to close.
    host.run(1, files, &items[0].id, DEFAULT_ACTION).unwrap();
    assert_eq!(
        events.recv_blocking().unwrap(),
        HostEvent::Ran {
            generation: 1,
            plugin: files,
            result: Ok(Effect::Close)
        }
    );
    let log = std::fs::read_to_string(fakes.join("open.log")).expect("open was run");
    assert_eq!(log, format!("-R\n{}\n", found[1].display()));

    // The second action hands the host a file URL to open.
    host.run(1, files, &items[0].id, &items[0].actions[1].id)
        .unwrap();
    assert_eq!(
        events.recv_blocking().unwrap(),
        HostEvent::Ran {
            generation: 1,
            plugin: files,
            result: Ok(Effect::Open {
                target: format!("file://{}", found[1].display())
            })
        }
    );

    // Without the keyword the plugin is never asked.
    assert!(!host.query(2, "readme").contains(&files));
}
