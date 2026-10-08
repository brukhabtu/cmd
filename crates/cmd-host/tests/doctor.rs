//! Proves `cmd plugin doctor` against the real calculator and against a plugin that
//! misbehaves, through the `cmd-plugin` binary that `cmd plugin` shares its code with.

mod common;

use std::path::{Path, PathBuf};
use std::process::Command;

fn doctor(dir: &Path, extra: &[&str]) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_cmd-plugin"))
        .arg("doctor")
        .arg(dir)
        .args(extra)
        .output()
        .expect("cmd-plugin runs")
}

fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}

#[test]
fn the_calculator_is_examined_end_to_end() {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../plugins/calculator");
    let output = doctor(&dir, &["--query", "6 * 7", "--run", "42"]);
    let stdout = text(&output.stdout);
    assert!(
        output.status.success(),
        "{stdout}\n{}",
        text(&output.stderr)
    );
    assert!(stdout.contains("\"name\": \"calculator\""), "{stdout}");
    assert!(stdout.contains("\"title\": \"42\""), "{stdout}");
    assert!(stdout.contains("\"kind\": \"symbol\""), "{stdout}");
    assert!(stdout.contains("\"kind\": \"copy\""), "{stdout}");
}

#[test]
fn a_plugin_that_chatters_on_stdout_is_diagnosed_with_the_line() {
    let dir = std::env::temp_dir().join(format!("cmd-doctor-chatter-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::write(
        dir.join("fake.py"),
        format!("NAME = \"chatty\"\n{}", common::FAKE),
    )
    .unwrap();
    std::fs::write(
        dir.join("cmd-plugin.toml"),
        "name = \"chatty\"\ncommand = [\"python3\", \"fake.py\"]\n",
    )
    .unwrap();
    let output = doctor(&dir, &["--query", "chatter"]);
    let stderr = text(&output.stderr);
    assert_eq!(output.status.code(), Some(1), "{stderr}");
    assert!(stderr.contains("stdout is reserved"), "{stderr}");
    assert!(stderr.contains("debugging..."), "{stderr}");
}

#[test]
fn a_missing_manifest_is_a_plugin_problem_and_bad_arguments_are_a_usage_problem() {
    let empty = std::env::temp_dir().join(format!("cmd-doctor-empty-{}", std::process::id()));
    std::fs::create_dir_all(&empty).unwrap();
    assert_eq!(doctor(&empty, &[]).status.code(), Some(1));
    assert_eq!(doctor(&empty, &["--query"]).status.code(), Some(2));
}

#[test]
fn a_plugin_is_started_with_its_data_and_config_directories() {
    let root = std::env::temp_dir().join(format!("cmd-doctor-env-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    let dir = root.join("envy");
    let home = root.join("home");
    std::fs::create_dir_all(&dir).unwrap();
    std::fs::create_dir_all(&home).unwrap();
    std::fs::write(
        dir.join("plugin.py"),
        r#"import json, os, sys
for line in sys.stdin:
    request = json.loads(line)
    if request["method"] == "describe":
        result = {"name": "envy", "version": "1", "protocol": 1}
    else:
        result = {"items": [{"id": "d", "title": os.environ.get("CMD_PLUGIN_DATA", "unset")}]}
    print(json.dumps({"id": request["id"], "result": result}), flush=True)
"#,
    )
    .unwrap();
    std::fs::write(
        dir.join("cmd-plugin.toml"),
        "name = \"envy\"\ncommand = [\"python3\", \"plugin.py\"]\n",
    )
    .unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_cmd-plugin"))
        .arg("doctor")
        .arg(&dir)
        .args(["--query", "x"])
        .env("HOME", &home)
        .output()
        .expect("cmd-plugin runs");
    let stdout = text(&output.stdout);
    assert!(
        output.status.success(),
        "{stdout}\n{}",
        text(&output.stderr)
    );
    let data = home.join(if cfg!(target_os = "macos") {
        "Library/Application Support/cmd/plugin-data/envy"
    } else {
        ".config/cmd/plugin-data/envy"
    });
    assert!(
        data.is_dir(),
        "the data directory is made: {}",
        data.display()
    );
    assert!(
        stdout.contains(&format!("\"title\": \"{}\"", data.display())),
        "{stdout}"
    );
    assert!(stdout.contains("CMD_PLUGIN_CONFIG="), "{stdout}");
}
