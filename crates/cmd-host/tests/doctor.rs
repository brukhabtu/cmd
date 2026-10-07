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
