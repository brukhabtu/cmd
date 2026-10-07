//! `git` as a subprocess, for `cmd plugin`.
//!
//! Decision 8 says plugins are installed by cloning, and the person's own git is the one
//! tool that already knows their credentials, proxies and ssh keys; driving it as a
//! process keeps all of that theirs. Every call runs with terminal prompts disabled, so
//! a repository that does not exist fails in well under a second instead of asking for a
//! username inside a command that cannot answer.

use std::io;
use std::path::{Path, PathBuf};
use std::process::Command;

use thiserror::Error;

/// What went wrong running git.
#[derive(Debug, Error)]
pub enum GitError {
    #[error("git is not installed; on macOS `xcode-select --install` provides it")]
    NotInstalled,
    #[error("git {command} failed: {stderr}")]
    Failed { command: String, stderr: String },
}

/// Run `git` with `args`, in `cwd` when given, and return what it printed to stdout.
pub fn run(args: &[&str], cwd: Option<&Path>) -> Result<String, GitError> {
    let mut command = Command::new("git");
    command
        .env("GIT_TERMINAL_PROMPT", "0")
        .args(["-c", "advice.detachedHead=false"])
        .args(args);
    if let Some(cwd) = cwd {
        command.current_dir(cwd);
    }
    let output = command.output().map_err(|error| {
        if error.kind() == io::ErrorKind::NotFound {
            GitError::NotInstalled
        } else {
            GitError::Failed {
                command: args.join(" "),
                stderr: error.to_string(),
            }
        }
    })?;
    if output.status.success() {
        return Ok(String::from_utf8_lossy(&output.stdout).into_owned());
    }
    Err(GitError::Failed {
        command: args.join(" "),
        stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
    })
}

/// Fetch one commit of `url` into a fresh repository at `into` and check it out.
///
/// `git clone --branch` takes only tags and branches, and an index entry pins a commit,
/// so this is the shallow fetch decision 8 describes.
pub fn fetch_commit(url: &str, commit: &str, into: &Path) -> Result<(), GitError> {
    let into_text = into.display().to_string();
    run(&["init", "-q", &into_text], None)?;
    run(&["fetch", "-q", "--depth", "1", url, commit], Some(into)).map_err(|e| blame(url, e))?;
    run(&["checkout", "-q", "FETCH_HEAD"], Some(into))?;
    Ok(())
}

/// Clone the default branch of `url` into `into`, one commit deep.
pub fn clone_shallow(url: &str, into: &Path) -> Result<(), GitError> {
    let into_text = into.display().to_string();
    run(&["clone", "-q", "--depth", "1", url, &into_text], None).map_err(|e| blame(url, e))?;
    Ok(())
}

/// Move `dir` to the tip of its upstream, only when that is a fast-forward. A shallow
/// clone deepens as far as it needs to. A dirty tree or a diverged commit makes git
/// abort before it touches anything.
pub fn pull_ff_only(dir: &Path) -> Result<(), GitError> {
    run(&["pull", "-q", "--ff-only"], Some(dir))?;
    Ok(())
}

/// The commit `dir` is at.
pub fn head(dir: &Path) -> Result<String, GitError> {
    Ok(run(&["rev-parse", "HEAD"], Some(dir))?.trim().to_string())
}

/// The branch `dir` is on, or `HEAD` when it is detached.
pub fn branch(dir: &Path) -> Result<String, GitError> {
    Ok(run(&["rev-parse", "--abbrev-ref", "HEAD"], Some(dir))?
        .trim()
        .to_string())
}

/// The text of `path` at the tip of the default branch of `url`, read from a shallow
/// fetch into a scratch repository that is removed afterwards.
pub fn file_at_head(url: &str, path: &str) -> Result<String, GitError> {
    let scratch = Scratch::new();
    let dir = scratch.0.display().to_string();
    run(&["init", "-q", &dir], None)?;
    run(
        &["fetch", "-q", "--depth", "1", url, "HEAD"],
        Some(&scratch.0),
    )
    .map_err(|e| blame(url, e))?;
    run(
        &["cat-file", "-p", &format!("FETCH_HEAD:{path}")],
        Some(&scratch.0),
    )
}

/// Git's message for a missing HTTPS repository is about the username prompt it could
/// not show; the person needs to hear about the repository instead.
fn blame(url: &str, error: GitError) -> GitError {
    match error {
        GitError::Failed { command, stderr } if stderr.contains("could not read Username") => {
            GitError::Failed {
                command,
                stderr: format!(
                    "no repository at {url}, or it is private (an ssh URL uses your keys)"
                ),
            }
        }
        other => other,
    }
}

/// A directory under the system temp directory that goes away with this value.
struct Scratch(PathBuf);

impl Scratch {
    fn new() -> Self {
        let dir = std::env::temp_dir().join(format!(
            "cmd-git-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_or(0, |since| since.as_nanos())
        ));
        Self(dir)
    }
}

impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_missing_https_repository_is_reported_as_such_not_as_a_prompt() {
        let error = blame(
            "https://github.com/nobody/nothing",
            GitError::Failed {
                command: "fetch".into(),
                stderr: "fatal: could not read Username for 'https://github.com': terminal prompts disabled".into(),
            },
        );
        let message = error.to_string();
        assert!(
            message.contains("no repository at https://github.com/nobody/nothing"),
            "{message}"
        );
        assert!(message.contains("ssh URL"), "{message}");
    }

    #[test]
    fn other_failures_keep_gits_own_words() {
        let error = blame(
            "file:///x",
            GitError::Failed {
                command: "fetch".into(),
                stderr: "fatal: '/x' does not appear to be a git repository".into(),
            },
        );
        assert!(
            error
                .to_string()
                .contains("does not appear to be a git repository")
        );
    }
}
