//! `cmd plugin install`, `update`, `remove` and `list` (decision 8).
//!
//! A plugin is installed into the plugin root as a plain directory named after its
//! manifest, beside a hidden `.cmd-install.toml` that says where it came from, so that
//! `update` knows what to move it to and `list` can say so. Index plugins are fetched at
//! the index's pinned commit and keep no `.git`; URL plugins are shallow clones and keep
//! theirs, which is what `update` fast-forwards; path plugins are copies.
//!
//! Everything is staged under a hidden directory in the root and only renamed into place
//! once the manifest has been read and the name checked, so a refused install leaves
//! nothing behind.

use std::fmt::Write as _;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::git::{self, GitError};
use crate::index::{self, Entry, IndexError};
use crate::manifest::{self, LoadError, Located};

/// The file an install writes beside the plugin, and `update` and `list` read.
pub const RECORD_FILE: &str = ".cmd-install.toml";

/// The marker that decision 8's warning has been shown once.
const WARNING_SHOWN: &str = ".install-warning-shown";

/// Where the SDK lives inside this repository, for the rewrite below.
const SDK_SUBDIRECTORY: &str = "python/cmd-sdk";

/// Decision 8's one-time warning before the first install from outside the index.
const WARNING: &str = "cmd plugin: installing a plugin runs someone's code with your rights. \
The index is a recommendation with a reviewed ref, not a sandbox; a URL is not even that. \
This is said once.";

/// What `cmd plugin install <what>` was given, read from the word alone.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Source {
    Index { name: String },
    Git { url: String },
    Path(PathBuf),
}

impl Source {
    /// A URL or `git@` is git; an existing directory or anything spelt as a path is a
    /// path; `owner/name` is a GitHub repository; a bare word is an index name. The
    /// order matters: `plugins/calculator` is a path when that directory exists and a
    /// GitHub repository when it does not, which the usage text warns about.
    pub fn classify(what: &str, is_dir: bool) -> Source {
        if what.contains("://") || what.starts_with("git@") {
            return Source::Git {
                url: what.to_string(),
            };
        }
        if is_dir || ["/", "./", "../", "~/"].iter().any(|p| what.starts_with(p)) {
            return Source::Path(PathBuf::from(what));
        }
        if let Some((owner, name)) = what.split_once('/')
            && is_repository_word(owner)
            && is_repository_word(name)
        {
            return Source::Git {
                url: format!("https://github.com/{owner}/{name}"),
            };
        }
        Source::Index {
            name: what.to_string(),
        }
    }
}

fn is_repository_word(word: &str) -> bool {
    !word.is_empty()
        && word
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
}

/// The kind of source a plugin was installed from.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Kind {
    Index,
    Git,
    Path,
}

/// The git source the plugin's `cmd-sdk` dependency was rewritten to, when it was.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SdkSource {
    pub git: String,
    pub subdirectory: String,
    pub rev: String,
}

/// What `.cmd-install.toml` holds.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Record {
    pub kind: Kind,
    /// The index name, for the `index` kind.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    /// The git URL, or the path a copy was made from.
    pub source: String,
    /// The index entry's ref, or the clone's branch.
    #[serde(default, rename = "ref", skip_serializing_if = "Option::is_none")]
    pub reference: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub commit: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subdirectory: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cmd_sdk: Option<SdkSource>,
}

impl Record {
    /// The record in `dir`, `None` when there is none: the directory was copied by hand.
    pub fn load(dir: &Path) -> Result<Option<Record>, InstallError> {
        let path = dir.join(RECORD_FILE);
        let text = match std::fs::read_to_string(&path) {
            Ok(text) => text,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(source) => {
                return Err(InstallError::io(
                    format!("reading {}", path.display()),
                    source,
                ));
            }
        };
        toml::from_str(&text)
            .map(Some)
            .map_err(|source| InstallError::BadRecord { path, source })
    }

    pub fn write(&self, dir: &Path) -> Result<(), InstallError> {
        let path = dir.join(RECORD_FILE);
        let body = toml::to_string(self).map_err(|error| {
            InstallError::io(
                format!("writing {}", path.display()),
                io::Error::other(error),
            )
        })?;
        let text = format!(
            "# Written by `cmd plugin install`; read by `cmd plugin update` and `list`.\n{body}"
        );
        std::fs::write(&path, text)
            .map_err(|source| InstallError::io(format!("writing {}", path.display()), source))
    }

    /// The record as `list` shows it: where the plugin came from and at what.
    pub fn describe(&self) -> String {
        match self.kind {
            Kind::Index => format!(
                "index {} {}@{}",
                self.source,
                self.reference.as_deref().unwrap_or("?"),
                short(self.commit.as_deref().unwrap_or("?"))
            ),
            Kind::Git => format!(
                "git {} {}@{}",
                self.source,
                self.reference.as_deref().unwrap_or("?"),
                short(self.commit.as_deref().unwrap_or("?"))
            ),
            Kind::Path => format!("path {}", self.source),
        }
    }
}

/// Replace `cmd-sdk = { workspace = true }` under `[tool.uv.sources]` with the git source
/// `sdk`, which is the form the tutorial teaches, pinned to a commit.
///
/// A plugin from inside this repository depends on the SDK as a workspace member, which
/// cannot resolve once the plugin stands alone (task 1.35). The one place that SDK can be
/// is the repository the plugin came from, at the commit it came from. `None` when there
/// is no such line, and also when the rewrite does not parse back, so a malformed file is
/// never written.
pub fn rewrite_sdk_source(pyproject: &str, sdk: &SdkSource) -> Option<String> {
    let mut rewritten = String::with_capacity(pyproject.len() + 80);
    let mut in_sources = false;
    let mut replaced = false;
    for line in pyproject.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') {
            in_sources = trimmed == "[tool.uv.sources]";
        }
        if in_sources && !replaced && is_workspace_sdk_line(trimmed) {
            let _ = writeln!(
                rewritten,
                "cmd-sdk = {{ git = {}, subdirectory = {}, rev = {} }}",
                toml_string(&sdk.git),
                toml_string(&sdk.subdirectory),
                toml_string(&sdk.rev)
            );
            replaced = true;
            continue;
        }
        rewritten.push_str(line);
        rewritten.push('\n');
    }
    if !replaced || rewritten.parse::<toml::Table>().is_err() {
        return None;
    }
    Some(rewritten)
}

fn is_workspace_sdk_line(line: &str) -> bool {
    line.split_once('=').is_some_and(|(key, value)| {
        key.trim() == "cmd-sdk"
            && value.split_whitespace().collect::<String>() == "{workspace=true}"
    })
}

fn toml_string(text: &str) -> String {
    toml::Value::String(text.to_string()).to_string()
}

/// Whether a pyproject still names the SDK as a workspace member.
pub fn has_workspace_sdk(pyproject: &str) -> bool {
    let mut in_sources = false;
    pyproject.lines().map(str::trim).any(|line| {
        if line.starts_with('[') {
            in_sources = line == "[tool.uv.sources]";
        }
        in_sources && is_workspace_sdk_line(line)
    })
}

/// Where installs go: the first `CMD_PLUGINS` entry, else the per-user directory.
/// `./plugins` is for development and is never written to.
pub fn install_root(env: Option<&str>, home: Option<&Path>) -> Option<PathBuf> {
    if let Some(first) = env.and_then(|list| list.split(':').find(|entry| !entry.is_empty())) {
        return Some(PathBuf::from(first));
    }
    home.map(manifest::user_plugin_dir)
}

/// A name that can be a directory of its own inside the root.
pub fn plain_name(name: &str) -> Result<(), InstallError> {
    let reason = if name.is_empty() {
        "it is empty"
    } else if name.contains('/') || name.contains('\\') {
        "it contains a path separator"
    } else if name.starts_with('.') {
        "it starts with a dot"
    } else {
        return Ok(());
    };
    Err(InstallError::BadName {
        name: name.to_string(),
        reason,
    })
}

/// Why a command could not do what it was asked. Each message is the sentence the
/// person reads after `cmd plugin <command>: `.
#[derive(Debug, Error)]
pub enum InstallError {
    #[error(transparent)]
    Git(#[from] GitError),
    #[error(transparent)]
    Index(#[from] IndexError),
    #[error("{name} is not in the index, which lists {}", listed.join(", "))]
    NotInIndex { name: String, listed: Vec<String> },
    #[error("{from} has no {} so it is not a plugin", manifest::FILE_NAME)]
    NoManifest { from: String },
    #[error(transparent)]
    Manifest(LoadError),
    #[error("{name:?} cannot be a plugin name: {reason}")]
    BadName { name: String, reason: &'static str },
    #[error("the manifest is named {manifest:?} but the index entry is {entry:?}")]
    NameMismatch { manifest: String, entry: String },
    #[error("{} already exists; `cmd plugin remove {name}` first", dir.display())]
    AlreadyInstalled { name: String, dir: PathBuf },
    #[error("{name} is not installed in {}", root.display())]
    NotInstalled { name: String, root: PathBuf },
    #[error("{name} was not installed by cmd plugin, so there is nothing to update it from")]
    NoRecord { name: String },
    #[error("{name} is no longer in the index; nothing changed")]
    NoLongerListed { name: String },
    #[error(
        "{name} was installed from {was} but the index now lists it at {now}; nothing changed: remove and install again, deliberately"
    )]
    SourceChanged {
        name: String,
        was: String,
        now: String,
    },
    #[error("{name} could not be fast-forwarded, nothing changed: {stderr}")]
    FastForwardFailed { name: String, stderr: String },
    #[error("{count} of the plugins could not be updated")]
    SomeFailed { count: usize },
    #[error("{} is not a directory", path.display())]
    NotADirectory { path: PathBuf },
    #[error("{} is not a valid install record: {source}", path.display())]
    BadRecord {
        path: PathBuf,
        #[source]
        source: toml::de::Error,
    },
    #[error("{what}: {source}")]
    Io {
        what: String,
        #[source]
        source: io::Error,
    },
}

impl InstallError {
    fn io(what: String, source: io::Error) -> Self {
        InstallError::Io { what, source }
    }
}

/// Install one plugin into `root`.
pub fn install(
    root: &Path,
    source: &Source,
    index_repository: &str,
    out: &mut dyn Write,
) -> Result<(), InstallError> {
    std::fs::create_dir_all(root)
        .map_err(|e| InstallError::io(format!("creating {}", root.display()), e))?;
    let staging = Staging::new(root, "staging");
    let fetched = match source {
        Source::Index { name } => {
            plain_name(name)?;
            refuse_existing(root, name)?;
            let index = index::fetch(index_repository)?;
            let entry = index
                .entry(name)
                .ok_or_else(|| InstallError::NotInIndex {
                    name: name.clone(),
                    listed: index.names(),
                })?
                .clone();
            let tree = fetch_index_entry(&entry, &staging.dir)?;
            Fetched {
                tree,
                record: Record {
                    kind: Kind::Index,
                    name: Some(entry.name.clone()),
                    source: entry.source.clone(),
                    reference: Some(entry.reference.clone()),
                    commit: Some(entry.commit().to_string()),
                    subdirectory: entry.subdirectory.clone(),
                    cmd_sdk: None,
                },
                entry: Some(entry),
            }
        }
        Source::Git { url } => {
            warn_once(root)?;
            git::clone_shallow(url, &staging.dir)?;
            Fetched {
                tree: staging.dir.clone(),
                record: Record {
                    kind: Kind::Git,
                    name: None,
                    source: url.clone(),
                    reference: Some(git::branch(&staging.dir)?),
                    commit: Some(git::head(&staging.dir)?),
                    subdirectory: None,
                    cmd_sdk: None,
                },
                entry: None,
            }
        }
        Source::Path(path) => {
            if !path.is_dir() {
                return Err(InstallError::NotADirectory { path: path.clone() });
            }
            warn_once(root)?;
            copy_tree(path, &staging.dir)?;
            let from = path.canonicalize().unwrap_or_else(|_| path.clone());
            Fetched {
                tree: staging.dir.clone(),
                record: Record {
                    kind: Kind::Path,
                    name: None,
                    source: from.display().to_string(),
                    reference: None,
                    commit: None,
                    subdirectory: None,
                    cmd_sdk: None,
                },
                entry: None,
            }
        }
    };
    let located = load_manifest(&fetched.tree, &describe_source(source))?;
    let name = located.manifest.name.clone();
    plain_name(&name)?;
    if let Some(entry) = &fetched.entry
        && entry.name != name
    {
        return Err(InstallError::NameMismatch {
            manifest: name,
            entry: entry.name.clone(),
        });
    }
    refuse_existing(root, &name)?;
    let dir = root.join(&name);
    std::fs::rename(&fetched.tree, &dir)
        .map_err(|e| InstallError::io(format!("moving the plugin into {}", dir.display()), e))?;
    let mut record = fetched.record;
    record.cmd_sdk = pin_sdk(&dir, &record)?;
    record.write(&dir)?;
    let at = record
        .commit
        .as_deref()
        .map(|commit| format!(" at {}", short(commit)))
        .unwrap_or_default();
    let _ = writeln!(
        out,
        "installed {name} from {}{at} into {}",
        record.source,
        dir.display()
    );
    // Until task 1.31 lands, a running launcher does not look for new directories.
    let _ = writeln!(out, "cmd starts it the next time it opens");
    Ok(())
}

/// What one source fetched: where its tree is, and the record it will be installed with.
struct Fetched {
    tree: PathBuf,
    record: Record,
    entry: Option<Entry>,
}

fn describe_source(source: &Source) -> String {
    match source {
        Source::Index { name } => format!("the index entry {name}"),
        Source::Git { url } => url.clone(),
        Source::Path(path) => path.display().to_string(),
    }
}

/// Fetch an index entry's commit into `staging` and return the directory that holds the
/// plugin: the subdirectory when the entry has one. The `.git` goes, so what is kept is
/// a plain directory at the pinned commit and nothing more.
fn fetch_index_entry(entry: &Entry, staging: &Path) -> Result<PathBuf, InstallError> {
    git::fetch_commit(&entry.source, entry.commit(), staging)?;
    std::fs::remove_dir_all(staging.join(".git"))
        .map_err(|e| InstallError::io("removing the fetched repository's .git".into(), e))?;
    Ok(match &entry.subdirectory {
        Some(subdirectory) => staging.join(subdirectory),
        None => staging.to_path_buf(),
    })
}

fn load_manifest(tree: &Path, source: &str) -> Result<Located, InstallError> {
    manifest::load(tree).map_err(|error| match error {
        LoadError::Io { source: ref io, .. } if io.kind() == io::ErrorKind::NotFound => {
            InstallError::NoManifest {
                from: source.to_string(),
            }
        }
        other => InstallError::Manifest(other),
    })
}

fn refuse_existing(root: &Path, name: &str) -> Result<(), InstallError> {
    let dir = root.join(name);
    if dir.exists() {
        return Err(InstallError::AlreadyInstalled {
            name: name.to_string(),
            dir,
        });
    }
    Ok(())
}

/// Rewrite a workspace SDK source to the git source at the plugin's own commit, for the
/// kinds that have one. A copy from a path keeps its file and is warned about: the path
/// it came from may well be this repository's checkout, where the workspace resolves.
fn pin_sdk(dir: &Path, record: &Record) -> Result<Option<SdkSource>, InstallError> {
    let path = dir.join("pyproject.toml");
    let text = match std::fs::read_to_string(&path) {
        Ok(text) => text,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(InstallError::io(format!("reading {}", path.display()), e)),
    };
    if !has_workspace_sdk(&text) {
        return Ok(None);
    }
    let Some(commit) = &record.commit else {
        eprintln!(
            "cmd plugin: {} names cmd-sdk as a workspace member, which only resolves inside this repository's checkout",
            path.display()
        );
        return Ok(None);
    };
    let sdk = SdkSource {
        git: record.source.clone(),
        subdirectory: SDK_SUBDIRECTORY.to_string(),
        rev: commit.clone(),
    };
    let Some(rewritten) = rewrite_sdk_source(&text, &sdk) else {
        return Ok(None);
    };
    std::fs::write(&path, rewritten)
        .map_err(|e| InstallError::io(format!("writing {}", path.display()), e))?;
    Ok(Some(sdk))
}

/// Decision 8's warning, printed before the first install from outside the index and
/// then never again: a marker in the root remembers.
fn warn_once(root: &Path) -> Result<(), InstallError> {
    let marker = root.join(WARNING_SHOWN);
    if marker.exists() {
        return Ok(());
    }
    eprintln!("{WARNING}");
    std::fs::write(&marker, "")
        .map_err(|e| InstallError::io(format!("writing {}", marker.display()), e))
}

/// Copy a plugin directory, leaving behind what uv builds on the machine it came from.
fn copy_tree(from: &Path, to: &Path) -> Result<(), InstallError> {
    let describe = |e| InstallError::io(format!("copying {}", from.display()), e);
    std::fs::create_dir_all(to).map_err(describe)?;
    for entry in std::fs::read_dir(from).map_err(describe)? {
        let entry = entry.map_err(describe)?;
        let name = entry.file_name();
        if name == ".venv" || name == "__pycache__" {
            continue;
        }
        let target = to.join(&name);
        if entry.file_type().map_err(describe)?.is_dir() {
            copy_tree(&entry.path(), &target)?;
        } else {
            std::fs::copy(entry.path(), &target).map_err(describe)?;
        }
    }
    Ok(())
}

/// Move one plugin, or every plugin with a record, to what its source now has.
pub fn update(
    root: &Path,
    name: Option<&str>,
    index_repository: &str,
    out: &mut dyn Write,
) -> Result<(), InstallError> {
    if let Some(name) = name {
        plain_name(name)?;
        let dir = root.join(name);
        if !dir.is_dir() {
            return Err(InstallError::NotInstalled {
                name: name.to_string(),
                root: root.to_path_buf(),
            });
        }
        let record = Record::load(&dir)?.ok_or_else(|| InstallError::NoRecord {
            name: name.to_string(),
        })?;
        return update_one(root, name, &record, index_repository, out);
    }
    let mut failed = 0;
    let mut seen = 0;
    for dir in installed_dirs(root)? {
        let Some(record) = Record::load(&dir)? else {
            continue;
        };
        seen += 1;
        let name = dir
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_default();
        if let Err(error) = update_one(root, &name, &record, index_repository, out) {
            eprintln!("cmd plugin update: {name}: {error}");
            failed += 1;
        }
    }
    if seen == 0 {
        let _ = writeln!(out, "nothing installed by cmd plugin in {}", root.display());
    }
    if failed > 0 {
        return Err(InstallError::SomeFailed { count: failed });
    }
    Ok(())
}

fn installed_dirs(root: &Path) -> Result<Vec<PathBuf>, InstallError> {
    let entries = match std::fs::read_dir(root) {
        Ok(entries) => entries,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(InstallError::io(format!("reading {}", root.display()), e)),
    };
    let mut dirs: Vec<PathBuf> = entries
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.is_dir()
                && !path
                    .file_name()
                    .is_some_and(|n| n.to_string_lossy().starts_with('.'))
        })
        .collect();
    dirs.sort();
    Ok(dirs)
}

fn update_one(
    root: &Path,
    name: &str,
    record: &Record,
    index_repository: &str,
    out: &mut dyn Write,
) -> Result<(), InstallError> {
    let dir = root.join(name);
    match record.kind {
        Kind::Path => {
            let _ = writeln!(
                out,
                "{name}: installed from {}; nothing to update",
                record.source
            );
            Ok(())
        }
        Kind::Index => update_index_plugin(root, name, record, index_repository, out),
        Kind::Git => update_git_plugin(&dir, name, record, out),
    }
}

/// An index plugin moves to the index's current commit only, through the same fetch an
/// install does, and the directories are swapped once the new tree has been checked.
fn update_index_plugin(
    root: &Path,
    name: &str,
    record: &Record,
    index_repository: &str,
    out: &mut dyn Write,
) -> Result<(), InstallError> {
    let dir = root.join(name);
    let index = index::fetch(index_repository)?;
    let listed = record.name.as_deref().unwrap_or(name);
    let entry = index
        .entry(listed)
        .ok_or_else(|| InstallError::NoLongerListed {
            name: name.to_string(),
        })?;
    if entry.source != record.source {
        return Err(InstallError::SourceChanged {
            name: name.to_string(),
            was: record.source.clone(),
            now: entry.source.clone(),
        });
    }
    let old = record.commit.clone().unwrap_or_default();
    if entry.commit() == old {
        let _ = writeln!(out, "{name}: up to date at {}", short(&old));
        return Ok(());
    }
    let staging = Staging::new(root, &format!("update-{name}"));
    let tree = fetch_index_entry(entry, &staging.dir)?;
    let located = load_manifest(&tree, &format!("the index entry {listed}"))?;
    if located.manifest.name != entry.name {
        return Err(InstallError::NameMismatch {
            manifest: located.manifest.name,
            entry: entry.name.clone(),
        });
    }
    let retired = Staging::new(root, &format!("old-{name}"));
    std::fs::rename(&dir, &retired.dir)
        .map_err(|e| InstallError::io(format!("setting aside {}", dir.display()), e))?;
    if let Err(error) = std::fs::rename(&tree, &dir) {
        // The old tree is still whole; put it back before saying what went wrong.
        let _ = std::fs::rename(&retired.dir, &dir);
        return Err(InstallError::io(
            format!("moving the new tree into {}", dir.display()),
            error,
        ));
    }
    let mut record = Record {
        kind: Kind::Index,
        name: Some(entry.name.clone()),
        source: entry.source.clone(),
        reference: Some(entry.reference.clone()),
        commit: Some(entry.commit().to_string()),
        subdirectory: entry.subdirectory.clone(),
        cmd_sdk: None,
    };
    record.cmd_sdk = pin_sdk(&dir, &record)?;
    record.write(&dir)?;
    let _ = writeln!(out, "{name}: {} -> {}", short(&old), short(entry.commit()));
    Ok(())
}

/// A URL plugin is fast-forwarded in place; git refuses to touch an edited clone.
fn update_git_plugin(
    dir: &Path,
    name: &str,
    record: &Record,
    out: &mut dyn Write,
) -> Result<(), InstallError> {
    match git::pull_ff_only(dir) {
        Ok(()) => {}
        Err(GitError::Failed { stderr, .. }) => {
            return Err(InstallError::FastForwardFailed {
                name: name.to_string(),
                stderr,
            });
        }
        Err(error) => return Err(error.into()),
    }
    let new = git::head(dir)?;
    let old = record.commit.clone().unwrap_or_default();
    if new == old {
        let _ = writeln!(out, "{name}: up to date at {}", short(&old));
        return Ok(());
    }
    let mut record = record.clone();
    record.reference = Some(git::branch(dir)?);
    record.commit = Some(new.clone());
    // A pyproject that upstream has turned back into the workspace form is pinned again;
    // one rewritten at install stays as it is, since that commit still exists.
    if let Some(sdk) = pin_sdk(dir, &record)? {
        record.cmd_sdk = Some(sdk);
    }
    record.write(dir)?;
    let _ = writeln!(out, "{name}: {} -> {}", short(&old), short(&new));
    Ok(())
}

/// Delete one plugin directory, whether or not `cmd plugin` put it there.
pub fn remove(root: &Path, name: &str, out: &mut dyn Write) -> Result<(), InstallError> {
    plain_name(name)?;
    let dir = root.join(name);
    if !dir.is_dir() {
        return Err(InstallError::NotInstalled {
            name: name.to_string(),
            root: root.to_path_buf(),
        });
    }
    let had_record = dir.join(RECORD_FILE).is_file();
    std::fs::remove_dir_all(&dir)
        .map_err(|e| InstallError::io(format!("removing {}", dir.display()), e))?;
    let _ = writeln!(
        out,
        "removed {name} ({}){}",
        dir.display(),
        if had_record {
            ""
        } else {
            ", which was not installed by cmd plugin"
        }
    );
    Ok(())
}

/// What is installed under `roots`, from where and at what, then what the index lists
/// that is not. The index being unreachable is said, not fatal: the installed lines are
/// the answer most of the time.
pub fn list(roots: &[PathBuf], index_repository: &str, out: &mut dyn Write) {
    let (plugins, errors) = manifest::discover_all(roots);
    if plugins.is_empty() {
        let looked = roots
            .iter()
            .map(|dir| dir.display().to_string())
            .collect::<Vec<_>>()
            .join(", ");
        let _ = writeln!(out, "no plugins in {looked}");
    }
    let mut installed = Vec::new();
    for plugin in &plugins {
        let origin = match Record::load(&plugin.dir) {
            Ok(Some(record)) => record.describe(),
            Ok(None) => "not installed by cmd plugin".to_string(),
            Err(error) => error.to_string(),
        };
        installed.push(plugin.manifest.name.clone());
        let _ = writeln!(
            out,
            "{}  {}  {origin}",
            plugin.manifest.name,
            plugin.dir.display()
        );
    }
    for error in &errors {
        let _ = writeln!(out, "{error}");
    }
    match index::fetch(index_repository) {
        Ok(index) => {
            for entry in index
                .plugin
                .iter()
                .filter(|entry| !installed.contains(&entry.name))
            {
                let _ = writeln!(out, "not installed: {} - {}", entry.name, entry.summary);
            }
        }
        Err(error) => {
            let _ = writeln!(
                out,
                "the index at {index_repository} could not be read: {error}"
            );
        }
    }
}

/// The first characters of a commit, as git shows them.
fn short(commit: &str) -> &str {
    let end = commit
        .char_indices()
        .nth(7)
        .map_or(commit.len(), |(i, _)| i);
    &commit[..end]
}

/// A hidden directory in the root that goes away with this value, so an install that
/// is refused half way leaves nothing to find. Hidden, so discovery never mistakes it
/// for a plugin and the file watcher's new-plugin scan can skip it by its dot.
struct Staging {
    dir: PathBuf,
}

impl Staging {
    fn new(root: &Path, purpose: &str) -> Self {
        let dir = root.join(format!(".{purpose}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        Self { dir }
    }
}

impl Drop for Staging {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const CALCULATOR_PYPROJECT: &str = include_str!("../../../plugins/calculator/pyproject.toml");

    fn sdk() -> SdkSource {
        SdkSource {
            git: "https://github.com/brukhabtu/cmd".into(),
            subdirectory: "python/cmd-sdk".into(),
            rev: "1159f73f7c9cc1248abe259a3a2de8592cfa7a67".into(),
        }
    }

    #[test]
    fn a_bare_word_is_an_index_name_and_urls_are_git() {
        assert_eq!(
            Source::classify("calculator", false),
            Source::Index {
                name: "calculator".into()
            }
        );
        assert_eq!(
            Source::classify("https://github.com/o/n", false),
            Source::Git {
                url: "https://github.com/o/n".into()
            }
        );
        assert_eq!(
            Source::classify("git@github.com:o/n.git", false),
            Source::Git {
                url: "git@github.com:o/n.git".into()
            }
        );
    }

    #[test]
    fn owner_slash_name_is_a_github_repository_unless_it_is_a_directory() {
        assert_eq!(
            Source::classify("o/n", false),
            Source::Git {
                url: "https://github.com/o/n".into()
            }
        );
        assert_eq!(Source::classify("o/n", true), Source::Path("o/n".into()));
        // The usage text says to write ./ for a path that does not exist yet.
        assert_eq!(
            Source::classify("plugins/calculator", false),
            Source::Git {
                url: "https://github.com/plugins/calculator".into()
            }
        );
        assert_eq!(
            Source::classify("o/n/deeper", false),
            Source::Index {
                name: "o/n/deeper".into()
            }
        );
    }

    #[test]
    fn anything_spelt_as_a_path_is_a_path() {
        for what in ["./x", "/x", "../x", "~/x"] {
            assert_eq!(
                Source::classify(what, false),
                Source::Path(what.into()),
                "{what}"
            );
        }
    }

    #[test]
    fn a_record_of_each_kind_round_trips_through_toml() {
        let records = [
            Record {
                kind: Kind::Index,
                name: Some("calculator".into()),
                source: "https://github.com/brukhabtu/cmd".into(),
                reference: Some("v1".into()),
                commit: Some("abc".into()),
                subdirectory: Some("plugins/calculator".into()),
                cmd_sdk: Some(sdk()),
            },
            Record {
                kind: Kind::Git,
                name: None,
                source: "https://github.com/o/n".into(),
                reference: Some("main".into()),
                commit: Some("def".into()),
                subdirectory: None,
                cmd_sdk: None,
            },
            Record {
                kind: Kind::Path,
                name: None,
                source: "/home/me/plugin".into(),
                reference: None,
                commit: None,
                subdirectory: None,
                cmd_sdk: None,
            },
        ];
        for record in records {
            let text = toml::to_string(&record).unwrap();
            let back: Record = toml::from_str(&text).unwrap();
            assert_eq!(back, record, "{text}");
        }
        let text = toml::to_string(&Record {
            kind: Kind::Path,
            name: None,
            source: "/p".into(),
            reference: None,
            commit: None,
            subdirectory: None,
            cmd_sdk: None,
        })
        .unwrap();
        assert!(text.contains("kind = \"path\""), "{text}");
        assert!(!text.contains("commit"), "{text}");
    }

    #[test]
    fn the_calculators_workspace_sdk_becomes_the_tutorials_git_source_with_a_rev() {
        assert!(has_workspace_sdk(CALCULATOR_PYPROJECT));
        let rewritten = rewrite_sdk_source(CALCULATOR_PYPROJECT, &sdk()).unwrap();
        assert!(
            rewritten.contains(
                "cmd-sdk = { git = \"https://github.com/brukhabtu/cmd\", subdirectory = \"python/cmd-sdk\", rev = \"1159f73f7c9cc1248abe259a3a2de8592cfa7a67\" }\n"
            ),
            "{rewritten}"
        );
        assert!(!has_workspace_sdk(&rewritten));
        let table: toml::Table = rewritten.parse().unwrap();
        let source = &table["tool"]["uv"]["sources"]["cmd-sdk"];
        assert_eq!(
            source["git"].as_str(),
            Some("https://github.com/brukhabtu/cmd")
        );
        assert_eq!(source["subdirectory"].as_str(), Some("python/cmd-sdk"));
        assert_eq!(source["rev"].as_str(), Some(sdk().rev.as_str()));
        // Everything else is untouched.
        assert_eq!(table["project"]["name"].as_str(), Some("calculator"));
        assert!(rewritten.contains("[build-system]"));
    }

    #[test]
    fn a_pyproject_without_a_workspace_sdk_is_left_alone() {
        let already_git = CALCULATOR_PYPROJECT.replace(
            "cmd-sdk = { workspace = true }",
            "cmd-sdk = { git = \"https://example.invalid/cmd\", subdirectory = \"python/cmd-sdk\" }",
        );
        assert_eq!(rewrite_sdk_source(&already_git, &sdk()), None);
        assert_eq!(
            rewrite_sdk_source("[project]\nname = \"x\"\n", &sdk()),
            None
        );
        // The same line outside the sources table is somebody else's.
        assert_eq!(
            rewrite_sdk_source("[other]\ncmd-sdk = { workspace = true }\n", &sdk()),
            None
        );
    }

    #[test]
    fn installs_go_to_the_first_cmd_plugins_entry_else_the_user_directory() {
        assert_eq!(
            install_root(Some(":/a:/b"), Some(Path::new("/home/me"))),
            Some(PathBuf::from("/a"))
        );
        assert_eq!(
            install_root(None, Some(Path::new("/home/me"))),
            Some(manifest::user_plugin_dir(Path::new("/home/me")))
        );
        assert_eq!(
            install_root(Some(""), Some(Path::new("/home/me"))),
            Some(manifest::user_plugin_dir(Path::new("/home/me")))
        );
        assert_eq!(install_root(None, None), None);
    }

    #[test]
    fn a_plugin_name_must_be_able_to_be_a_directory_of_its_own() {
        assert!(plain_name("calculator").is_ok());
        assert!(plain_name("my-plugin_2").is_ok());
        for bad in ["", "a/b", "..", ".hidden", "a\\b"] {
            let error = plain_name(bad).unwrap_err().to_string();
            assert!(error.contains("cannot be a plugin name"), "{bad}: {error}");
        }
    }

    #[test]
    fn a_commit_is_shown_short() {
        assert_eq!(short("1159f73f7c9cc1248abe259a3a2de8592cfa7a67"), "1159f73");
        assert_eq!(short("abc"), "abc");
    }
}
