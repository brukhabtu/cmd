//! Proves `cmd plugin install`, `update`, `remove` and `list` through the real
//! `cmd-plugin` binary, with every git source a local repository: the index is read from
//! one (`CMD_INDEX`), plugins are fetched from others, and the real calculator is
//! installed from this repository's own checkout and driven through uv. No network.

mod common;

use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

/// A manifest and a fake plugin named `name`, as files.
fn plugin_files(name: &str) -> Vec<(String, String)> {
    vec![
        (
            "cmd-plugin.toml".into(),
            format!("name = \"{name}\"\ncommand = [\"python3\", \"fake.py\"]\n"),
        ),
        (
            "fake.py".into(),
            format!("NAME = \"{name}\"\n{}", common::FAKE),
        ),
    ]
}

/// A fresh directory under the system temp directory, named for the test.
fn scratch(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("cmd-plugin-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}

/// Run git in `dir` with a fixed identity, so a commit needs no configuration.
fn git(dir: &Path, args: &[&str]) -> String {
    let output = Command::new("git")
        .arg("-C")
        .arg(dir)
        .args([
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-c",
            "commit.gpgsign=false",
        ])
        .args(args)
        .output()
        .expect("git runs");
    assert!(
        output.status.success(),
        "git {args:?} in {}: {}",
        dir.display(),
        text(&output.stderr)
    );
    text(&output.stdout).trim().to_string()
}

fn write_files(dir: &Path, files: &[(String, String)]) {
    for (path, content) in files {
        let path = dir.join(path);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, content).unwrap();
    }
}

/// Commit `files` on top of whatever `dir` holds and return the new commit.
fn commit(dir: &Path, files: &[(String, String)], message: &str) -> String {
    write_files(dir, files);
    git(dir, &["add", "-A"]);
    git(dir, &["commit", "-q", "-m", message]);
    git(dir, &["rev-parse", "HEAD"])
}

/// A repository at `dir` holding `files`: its file URL and its one commit.
fn repository(dir: &Path, files: &[(String, String)]) -> (String, String) {
    std::fs::create_dir_all(dir).unwrap();
    git(dir, &["init", "-q", "-b", "main"]);
    let commit = commit(dir, files, "first");
    (url(dir), commit)
}

fn url(dir: &Path) -> String {
    format!("file://{}", dir.display())
}

fn entry(name: &str, source: &str, reference: &str, subdirectory: Option<&str>) -> String {
    let mut entry = format!(
        "[[plugin]]\nname = \"{name}\"\nsummary = \"The {name} plugin.\"\nsource = \"{source}\"\nref = \"{reference}\"\n"
    );
    if let Some(subdirectory) = subdirectory {
        let _ = writeln!(entry, "subdirectory = \"{subdirectory}\"");
    }
    entry
}

/// An index repository listing `entries`: its file URL.
fn index_repository(dir: &Path, entries: &str) -> String {
    let (url, _) = repository(dir, &[("plugins/index.toml".into(), entries.into())]);
    url
}

fn reindex(dir: &Path, entries: &str) {
    commit(
        dir,
        &[("plugins/index.toml".into(), entries.into())],
        "move the index",
    );
}

/// `cmd-plugin` with the plugin root and the index of one test.
fn cli(root: &Path, index: &str, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_cmd-plugin"))
        .env("CMD_PLUGINS", root)
        .env("CMD_INDEX", index)
        .args(args)
        .output()
        .expect("cmd-plugin runs")
}

fn ok(output: &Output) -> String {
    assert!(
        output.status.success(),
        "exit {:?}\n{}\n{}",
        output.status.code(),
        text(&output.stdout),
        text(&output.stderr)
    );
    text(&output.stdout)
}

fn failed(output: &Output) -> String {
    assert_eq!(
        output.status.code(),
        Some(1),
        "{}\n{}",
        text(&output.stdout),
        text(&output.stderr)
    );
    text(&output.stderr)
}

/// Every file under `dir` with its content, for before-and-after comparisons.
fn snapshot(dir: &Path) -> BTreeMap<PathBuf, Vec<u8>> {
    let mut files = BTreeMap::new();
    for entry in std::fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            files.extend(snapshot(&path));
        } else {
            files.insert(path.clone(), std::fs::read(&path).unwrap());
        }
    }
    files
}

/// The names of the directories in `root`, hidden ones included: what an install left.
fn directories(root: &Path) -> Vec<String> {
    let mut names: Vec<String> = std::fs::read_dir(root)
        .map(|entries| {
            entries
                .filter_map(Result::ok)
                .filter(|entry| entry.path().is_dir())
                .map(|entry| entry.file_name().to_string_lossy().into_owned())
                .collect()
        })
        .unwrap_or_default();
    names.sort();
    names
}

fn record(root: &Path, name: &str) -> toml::Table {
    std::fs::read_to_string(root.join(name).join(".cmd-install.toml"))
        .unwrap()
        .parse()
        .unwrap()
}

fn workspace() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap()
}

#[test]
fn the_real_calculator_installs_from_the_index_and_answers_through_uv() {
    let scratch = scratch("index-calculator");
    let root = scratch.join("plugins");
    let workspace = workspace();
    let head = git(&workspace, &["rev-parse", "HEAD"]);
    let source = url(&workspace);
    let index = index_repository(
        &scratch.join("index"),
        &format!(
            "{}{}",
            entry("calculator", &source, &head, Some("plugins/calculator")),
            entry("other", &source, &head, Some("plugins/websearch"))
        ),
    );

    let stdout = ok(&cli(&root, &index, &["install", "calculator"]));
    assert!(stdout.contains("installed calculator from"), "{stdout}");
    let dir = root.join("calculator");
    assert!(dir.join("cmd-plugin.toml").is_file());
    assert!(!dir.join(".git").exists(), "an index install keeps no .git");
    assert_eq!(
        directories(&root),
        vec!["calculator"],
        "nothing else is left"
    );

    let record = record(&root, "calculator");
    assert_eq!(record["kind"].as_str(), Some("index"));
    assert_eq!(record["name"].as_str(), Some("calculator"));
    assert_eq!(record["source"].as_str(), Some(source.as_str()));
    assert_eq!(record["ref"].as_str(), Some(head.as_str()));
    assert_eq!(record["commit"].as_str(), Some(head.as_str()));
    assert_eq!(record["subdirectory"].as_str(), Some("plugins/calculator"));
    assert_eq!(record["cmd_sdk"]["rev"].as_str(), Some(head.as_str()));

    let pyproject = std::fs::read_to_string(dir.join("pyproject.toml")).unwrap();
    assert!(
        pyproject.contains(&format!(
            "cmd-sdk = {{ git = \"{source}\", subdirectory = \"python/cmd-sdk\", rev = \"{head}\" }}"
        )),
        "{pyproject}"
    );

    // The installed copy stands alone: the SDK comes from the pinned commit, not the workspace.
    let output = cli(
        &root,
        &index,
        &["doctor", &dir.display().to_string(), "--query", "6 * 7"],
    );
    let stdout = ok(&output);
    assert!(stdout.contains("\"title\": \"42\""), "{stdout}");

    let stderr = failed(&cli(&root, &index, &["install", "calculator"]));
    assert!(stderr.contains(&dir.display().to_string()), "{stderr}");
    assert!(stderr.contains("cmd plugin remove calculator"), "{stderr}");

    let stderr = failed(&cli(&root, &index, &["install", "nothing"]));
    assert!(stderr.contains("nothing is not in the index"), "{stderr}");
    assert!(stderr.contains("calculator, other"), "{stderr}");

    let stderr = failed(&cli(&root, &index, &["install", "other"]));
    assert!(stderr.contains("named \"websearch\""), "{stderr}");
    assert!(stderr.contains("index entry is \"other\""), "{stderr}");
    assert_eq!(
        directories(&root),
        vec!["calculator"],
        "a refused install leaves nothing"
    );
}

#[test]
fn a_repository_installs_from_its_url_with_one_warning_and_keeps_its_clone() {
    let scratch = scratch("url");
    let root = scratch.join("plugins");
    let index = index_repository(&scratch.join("index"), "");
    let (source, commit) = repository(&scratch.join("upstream"), &plugin_files("urlplug"));

    let output = cli(&root, &index, &["install", &source]);
    let stdout = ok(&output);
    let stderr = text(&output.stderr);
    assert!(
        stderr.contains("runs someone's code with your rights"),
        "{stderr}"
    );
    assert!(root.join(".install-warning-shown").is_file());
    assert!(stdout.contains("installed urlplug from"), "{stdout}");
    let dir = root.join("urlplug");
    assert!(dir.join(".git").is_dir(), "a URL install is a clone");
    let record = record(&root, "urlplug");
    assert_eq!(record["kind"].as_str(), Some("git"));
    assert_eq!(record["source"].as_str(), Some(source.as_str()));
    assert_eq!(record["ref"].as_str(), Some("main"));
    assert_eq!(record["commit"].as_str(), Some(commit.as_str()));
    assert!(record.get("name").is_none());

    // The warning was said once.
    let (bare, _) = repository(
        &scratch.join("bare"),
        &[("README".into(), "no manifest\n".into())],
    );
    let output = cli(&root, &index, &["install", &bare]);
    let stderr = failed(&output);
    assert!(!stderr.contains("someone's code"), "{stderr}");
    assert!(stderr.contains("has no cmd-plugin.toml"), "{stderr}");
    assert_eq!(
        directories(&root),
        vec!["urlplug"],
        "a refused clone leaves nothing"
    );
}

#[test]
fn a_github_name_that_does_not_exist_fails_naming_the_url_and_leaves_nothing() {
    let scratch = scratch("github");
    let root = scratch.join("plugins");
    let index = index_repository(&scratch.join("index"), "");
    let stderr = failed(&cli(&root, &index, &["install", "nobody/nothing"]));
    assert!(
        stderr.contains("https://github.com/nobody/nothing"),
        "{stderr}"
    );
    assert_eq!(directories(&root), Vec::<String>::new());
}

#[test]
fn a_directory_installs_as_a_copy_without_its_environment() {
    let scratch = scratch("path");
    let root = scratch.join("plugins");
    let index = index_repository(&scratch.join("index"), "");
    let source = scratch.join("mine");
    let mut files = plugin_files("mine");
    files.push((".venv/bin/python".into(), "not copied".into()));
    files.push(("src/__pycache__/x.pyc".into(), "not copied".into()));
    files.push(("src/mine.py".into(), "copied".into()));
    write_files(&source, &files);

    let stdout = ok(&cli(
        &root,
        &index,
        &["install", &source.display().to_string()],
    ));
    assert!(stdout.contains("installed mine from"), "{stdout}");
    let dir = root.join("mine");
    assert!(dir.join("fake.py").is_file());
    assert!(dir.join("src/mine.py").is_file());
    assert!(!dir.join(".venv").exists());
    assert!(!dir.join("src/__pycache__").exists());
    let record = record(&root, "mine");
    assert_eq!(record["kind"].as_str(), Some("path"));
    assert_eq!(
        record["source"].as_str(),
        Some(
            source
                .canonicalize()
                .unwrap()
                .display()
                .to_string()
                .as_str()
        )
    );
    assert!(record.get("commit").is_none());

    let stderr = failed(&cli(
        &root,
        &index,
        &["install", &source.display().to_string()],
    ));
    assert!(stderr.contains("already exists"), "{stderr}");

    let empty = scratch.join("empty");
    std::fs::create_dir_all(&empty).unwrap();
    let stderr = failed(&cli(
        &root,
        &index,
        &["install", &empty.display().to_string()],
    ));
    assert!(stderr.contains("has no cmd-plugin.toml"), "{stderr}");
    assert_eq!(directories(&root), vec!["mine"]);
}

/// A plugin repository shaped like this one: the plugin in a subdirectory and the SDK as
/// a workspace member, so the install has to pin it.
fn subdirectory_plugin(name: &str, body: &str) -> Vec<(String, String)> {
    let mut files: Vec<(String, String)> = plugin_files(name)
        .into_iter()
        .map(|(path, content)| (format!("plugins/{name}/{path}"), content))
        .collect();
    files.push((
        format!("plugins/{name}/pyproject.toml"),
        format!(
            "[project]\nname = \"{name}\"\nversion = \"0.1.0\"\ndependencies = [\"cmd-sdk\"]\n\n[tool.uv.sources]\ncmd-sdk = {{ workspace = true }}\n"
        ),
    ));
    files.push((format!("plugins/{name}/body.txt"), body.into()));
    files
}

#[test]
fn an_index_plugin_updates_to_the_indexs_commit_and_refuses_a_changed_source() {
    let scratch = scratch("update-index");
    let root = scratch.join("plugins");
    let upstream = scratch.join("upstream");
    let (source, first) = repository(&upstream, &subdirectory_plugin("alpha", "one"));
    let index_dir = scratch.join("index");
    let index = index_repository(
        &index_dir,
        &entry("alpha", &source, &first, Some("plugins/alpha")),
    );
    ok(&cli(&root, &index, &["install", "alpha"]));
    let dir = root.join("alpha");
    assert_eq!(
        record(&root, "alpha")["cmd_sdk"]["rev"].as_str(),
        Some(first.as_str())
    );

    let stdout = ok(&cli(&root, &index, &["update", "alpha"]));
    assert!(stdout.contains("alpha: up to date"), "{stdout}");

    let second = commit(
        &upstream,
        &[("plugins/alpha/body.txt".into(), "two".into())],
        "second",
    );
    // The upstream moved but the index did not: nothing to move to.
    let stdout = ok(&cli(&root, &index, &["update", "alpha"]));
    assert!(stdout.contains("alpha: up to date"), "{stdout}");

    reindex(
        &index_dir,
        &entry("alpha", &source, &second, Some("plugins/alpha")),
    );
    let stdout = ok(&cli(&root, &index, &["update", "alpha"]));
    assert!(
        stdout.contains(&format!("alpha: {} -> {}", &first[..7], &second[..7])),
        "{stdout}"
    );
    assert_eq!(
        std::fs::read_to_string(dir.join("body.txt")).unwrap(),
        "two"
    );
    let record = record(&root, "alpha");
    assert_eq!(record["commit"].as_str(), Some(second.as_str()));
    assert_eq!(record["cmd_sdk"]["rev"].as_str(), Some(second.as_str()));
    let pyproject = std::fs::read_to_string(dir.join("pyproject.toml")).unwrap();
    assert!(
        pyproject.contains(&format!("rev = \"{second}\"")),
        "{pyproject}"
    );
    assert_eq!(
        directories(&root),
        vec!["alpha"],
        "the swap leaves no old copy"
    );

    let (elsewhere, moved) = repository(
        &scratch.join("elsewhere"),
        &subdirectory_plugin("alpha", "three"),
    );
    reindex(
        &index_dir,
        &entry("alpha", &elsewhere, &moved, Some("plugins/alpha")),
    );
    let before = snapshot(&dir);
    let stderr = failed(&cli(&root, &index, &["update", "alpha"]));
    assert!(stderr.contains("remove and install again"), "{stderr}");
    assert!(stderr.contains(&elsewhere), "{stderr}");
    assert_eq!(snapshot(&dir), before, "a refused update changes nothing");

    reindex(&index_dir, "");
    let stderr = failed(&cli(&root, &index, &["update", "alpha"]));
    assert!(stderr.contains("no longer in the index"), "{stderr}");
    assert_eq!(snapshot(&dir), before);
}

#[test]
fn a_cloned_plugin_fast_forwards_and_an_edited_or_diverged_clone_is_left_alone() {
    let scratch = scratch("update-git");
    let root = scratch.join("plugins");
    let index = index_repository(&scratch.join("index"), "");
    let upstream = scratch.join("upstream");
    let mut files = plugin_files("beta");
    files.push(("body.txt".into(), "one".into()));
    let (source, first) = repository(&upstream, &files);
    ok(&cli(&root, &index, &["install", &source]));
    let dir = root.join("beta");

    let second = commit(&upstream, &[("body.txt".into(), "two".into())], "second");
    let stdout = ok(&cli(&root, &index, &["update", "beta"]));
    assert!(
        stdout.contains(&format!("beta: {} -> {}", &first[..7], &second[..7])),
        "{stdout}"
    );
    assert_eq!(
        std::fs::read_to_string(dir.join("body.txt")).unwrap(),
        "two"
    );
    assert_eq!(
        record(&root, "beta")["commit"].as_str(),
        Some(second.as_str())
    );

    // An edit that upstream also touched: git refuses, the edit stays.
    std::fs::write(dir.join("body.txt"), "mine").unwrap();
    commit(&upstream, &[("body.txt".into(), "three".into())], "third");
    let stderr = failed(&cli(&root, &index, &["update", "beta"]));
    assert!(stderr.contains("nothing changed"), "{stderr}");
    assert!(stderr.contains("would be overwritten"), "{stderr}");
    assert_eq!(
        std::fs::read_to_string(dir.join("body.txt")).unwrap(),
        "mine"
    );
    assert_eq!(
        record(&root, "beta")["commit"].as_str(),
        Some(second.as_str())
    );

    // A local commit that diverged: likewise.
    commit(
        &dir,
        &[("body.txt".into(), "mine, committed".into())],
        "local",
    );
    let stderr = failed(&cli(&root, &index, &["update", "beta"]));
    assert!(stderr.contains("nothing changed"), "{stderr}");
    assert_eq!(
        std::fs::read_to_string(dir.join("body.txt")).unwrap(),
        "mine, committed"
    );
}

#[test]
fn update_without_a_name_walks_every_record_and_fails_if_any_did() {
    let scratch = scratch("update-all");
    let root = scratch.join("plugins");
    let index_dir = scratch.join("index");
    let (source, first) = repository(
        &scratch.join("upstream"),
        &subdirectory_plugin("gamma", "one"),
    );
    let index = index_repository(
        &index_dir,
        &entry("gamma", &source, &first, Some("plugins/gamma")),
    );
    ok(&cli(&root, &index, &["install", "gamma"]));
    let copied = scratch.join("delta");
    write_files(&copied, &plugin_files("delta"));
    ok(&cli(
        &root,
        &index,
        &["install", &copied.display().to_string()],
    ));
    let (cloned, _) = repository(&scratch.join("cloned"), &plugin_files("epsilon"));
    ok(&cli(&root, &index, &["install", &cloned]));
    // A hand-copied plugin has no record and is not touched.
    write_files(&root.join("zeta"), &plugin_files("zeta"));

    let output = cli(&root, &index, &["update"]);
    let stdout = ok(&output);
    assert!(stdout.contains("gamma: up to date"), "{stdout}");
    assert!(stdout.contains("delta: installed from"), "{stdout}");
    assert!(stdout.contains("nothing to update"), "{stdout}");
    assert!(stdout.contains("epsilon: up to date"), "{stdout}");
    assert!(!stdout.contains("zeta"), "{stdout}");

    // Break the clone's upstream: its update fails, the others still run, the exit says so.
    std::fs::remove_dir_all(scratch.join("cloned")).unwrap();
    let output = cli(&root, &index, &["update"]);
    let stdout = text(&output.stdout);
    let stderr = text(&output.stderr);
    assert_eq!(output.status.code(), Some(1), "{stdout}\n{stderr}");
    assert!(stdout.contains("gamma: up to date"), "{stdout}");
    assert!(stderr.contains("cmd plugin update: epsilon:"), "{stderr}");
    assert!(
        stderr.contains("1 of the plugins could not be updated"),
        "{stderr}"
    );

    let stderr = failed(&cli(&root, &index, &["update", "zeta"]));
    assert!(stderr.contains("not installed by cmd plugin"), "{stderr}");
    let stderr = failed(&cli(&root, &index, &["update", "nobody"]));
    assert!(stderr.contains("nobody is not installed"), "{stderr}");
}

#[test]
fn remove_deletes_whatever_is_there_and_names_what_is_not() {
    let scratch = scratch("remove");
    let root = scratch.join("plugins");
    let index = index_repository(&scratch.join("index"), "");
    let source = scratch.join("mine");
    write_files(&source, &plugin_files("mine"));
    ok(&cli(
        &root,
        &index,
        &["install", &source.display().to_string()],
    ));
    write_files(&root.join("copied"), &plugin_files("copied"));

    let stdout = ok(&cli(&root, &index, &["remove", "mine"]));
    assert!(stdout.contains("removed mine"), "{stdout}");
    assert!(!stdout.contains("not installed by cmd plugin"), "{stdout}");
    assert!(!root.join("mine").exists());

    let stdout = ok(&cli(&root, &index, &["remove", "copied"]));
    assert!(
        stdout.contains("which was not installed by cmd plugin"),
        "{stdout}"
    );
    assert!(!root.join("copied").exists());

    let stderr = failed(&cli(&root, &index, &["remove", "mine"]));
    assert!(stderr.contains("mine is not installed in"), "{stderr}");
    let stderr = failed(&cli(&root, &index, &["remove", "../mine"]));
    assert!(stderr.contains("cannot be a plugin name"), "{stderr}");
}

#[test]
fn list_shows_each_plugin_with_its_origin_and_what_the_index_has_that_is_not_installed() {
    let scratch = scratch("list");
    let root = scratch.join("plugins");
    let index_dir = scratch.join("index");
    let (source, first) = repository(
        &scratch.join("upstream"),
        &subdirectory_plugin("alpha", "one"),
    );
    let index = index_repository(
        &index_dir,
        &format!(
            "{}{}",
            entry("alpha", &source, &first, Some("plugins/alpha")),
            entry("omega", &source, &first, Some("plugins/omega"))
        ),
    );
    ok(&cli(&root, &index, &["install", "alpha"]));
    let (cloned, clone_commit) = repository(&scratch.join("cloned"), &plugin_files("beta"));
    ok(&cli(&root, &index, &["install", &cloned]));
    let copied = scratch.join("gamma");
    write_files(&copied, &plugin_files("gamma"));
    ok(&cli(
        &root,
        &index,
        &["install", &copied.display().to_string()],
    ));
    write_files(&root.join("delta"), &plugin_files("delta"));

    let stdout = ok(&cli(&root, &index, &["list"]));
    let line = |name: &str| {
        stdout
            .lines()
            .find(|line| line.starts_with(&format!("{name}  ")))
            .unwrap_or_else(|| panic!("no line for {name} in {stdout}"))
            .to_string()
    };
    assert!(line("alpha").contains(&format!("index {source} {first}@{}", &first[..7])));
    assert!(line("beta").contains(&format!("git {cloned} main@{}", &clone_commit[..7])));
    assert!(line("gamma").contains(&format!(
        "path {}",
        copied.canonicalize().unwrap().display()
    )));
    assert!(line("delta").contains("not installed by cmd plugin"));
    assert!(
        stdout.contains("not installed: omega - The omega plugin."),
        "{stdout}"
    );
    assert!(!stdout.contains("not installed: alpha"), "{stdout}");

    let unreachable = url(&scratch.join("no-such-repository"));
    let stdout = ok(&cli(&root, &unreachable, &["list"]));
    assert!(stdout.contains("alpha  "), "{stdout}");
    assert!(stdout.contains("could not be read"), "{stdout}");
    assert!(stdout.contains("no-such-repository"), "{stdout}");
}

#[test]
fn without_git_every_fetching_command_says_how_to_get_it() {
    let scratch = scratch("no-git");
    let root = scratch.join("plugins");
    let index = index_repository(&scratch.join("index"), "");
    let (source, _) = repository(&scratch.join("upstream"), &plugin_files("beta"));
    ok(&cli(&root, &index, &["install", &source]));
    let empty_path = scratch.join("empty-path");
    std::fs::create_dir_all(&empty_path).unwrap();

    let without_git = |args: &[&str]| {
        Command::new(env!("CARGO_BIN_EXE_cmd-plugin"))
            .env("CMD_PLUGINS", &root)
            .env("CMD_INDEX", &index)
            .env("PATH", &empty_path)
            .args(args)
            .output()
            .expect("cmd-plugin runs")
    };
    for args in [
        &["install", "anything"][..],
        &["install", "https://example.invalid/x"],
        &["update", "beta"],
    ] {
        let stderr = failed(&without_git(args));
        assert!(
            stderr.contains("git is not installed"),
            "{args:?}: {stderr}"
        );
        assert!(stderr.contains("xcode-select"), "{args:?}: {stderr}");
    }
    let stdout = ok(&without_git(&["list"]));
    assert!(stdout.contains("beta  "), "{stdout}");
    assert!(stdout.contains("git is not installed"), "{stdout}");
}
