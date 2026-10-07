//! `cmd plugin ...`: the subcommands the app binary answers before any window exists.
//!
//! The words after `plugin` come in, an exit code goes out. The same function backs the
//! `cmd-plugin` binary, so a clone without the app, and the tests on Linux, run exactly
//! what `cmd plugin` runs.

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use crate::install::{self, Source};
use crate::{doctor, index, manifest};

pub const USAGE: &str = "usage: cmd plugin <command>
  install <what>   a name from the index, a git URL, a GitHub owner/name, or a path
                   (write ./dir for a directory that is not there yet)
  update [name]    move an index plugin to the index's current ref, fast-forward a
                   cloned one; every installed plugin when no name is given
  remove <name>    delete the plugin directory
  list             what is installed, from where and at what; what the index lists
  doctor <dir> ... run a plugin directory the way the launcher does
Installs go to the first CMD_PLUGINS entry, or the per-user plugin directory.
CMD_INDEX names the git repository the index is read from.";

/// What the commands read from the process environment, gathered in one place so the
/// rest takes values.
#[derive(Debug, Clone)]
pub struct Env {
    /// `CMD_PLUGINS`, as the launcher reads it.
    pub plugins: Option<String>,
    pub home: Option<PathBuf>,
    pub cwd: PathBuf,
    /// The repository the index is read from.
    pub index: String,
}

impl Env {
    pub fn from_process() -> Self {
        Self {
            plugins: std::env::var("CMD_PLUGINS").ok(),
            home: std::env::var_os("HOME").map(PathBuf::from),
            cwd: std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
            index: std::env::var("CMD_INDEX").unwrap_or_else(|_| index::REPOSITORY.to_string()),
        }
    }

    fn install_root(&self) -> Result<PathBuf, String> {
        install::install_root(self.plugins.as_deref(), self.home.as_deref())
            .ok_or_else(|| "no plugin directory: HOME is unset and CMD_PLUGINS is empty".into())
    }

    /// A `~/` the shell did not expand, because the word was quoted.
    fn expand_home(&self, what: &str) -> String {
        match (what.strip_prefix("~/"), &self.home) {
            (Some(rest), Some(home)) => home.join(rest).display().to_string(),
            _ => what.to_string(),
        }
    }
}

/// Run one subcommand. Usage mistakes exit 2, failures 1.
pub fn run(args: &[String], env: &Env) -> ExitCode {
    let words: Vec<&str> = args.iter().map(String::as_str).collect();
    let result = match words.as_slice() {
        ["install", what] => install(env, what),
        ["update"] => update(env, None),
        ["update", name] => update(env, Some(name)),
        ["remove", name] => remove(env, name),
        ["list"] => {
            list(env);
            Ok(())
        }
        ["doctor", ..] => return doctor::run(&args[1..]),
        _ => {
            eprintln!("{USAGE}");
            return ExitCode::from(2);
        }
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("cmd plugin {}: {message}", words[0]);
            ExitCode::from(1)
        }
    }
}

fn install(env: &Env, what: &str) -> Result<(), String> {
    let what = env.expand_home(what);
    let source = Source::classify(&what, Path::new(&what).is_dir());
    let root = env.install_root()?;
    install::install(&root, &source, &env.index, &mut std::io::stdout()).map_err(|e| e.to_string())
}

fn update(env: &Env, name: Option<&str>) -> Result<(), String> {
    let root = env.install_root()?;
    install::update(&root, name, &env.index, &mut std::io::stdout()).map_err(|e| e.to_string())
}

fn remove(env: &Env, name: &str) -> Result<(), String> {
    let root = env.install_root()?;
    install::remove(&root, name, &mut std::io::stdout()).map_err(|e| e.to_string())
}

/// Every directory the launcher would look in, so a stale copy in `./plugins` is seen.
fn list(env: &Env) {
    let roots = manifest::plugin_dirs(env.plugins.as_deref(), env.home.as_deref(), &env.cwd);
    install::list(&roots, &env.index, &mut std::io::stdout());
}

#[cfg(test)]
mod tests {
    use super::*;

    fn env() -> Env {
        Env {
            plugins: Some("/nowhere/plugins".into()),
            home: Some(PathBuf::from("/nowhere/home")),
            cwd: PathBuf::from("/nowhere"),
            index: "file:///nowhere/index".into(),
        }
    }

    fn words(list: &[&str]) -> Vec<String> {
        list.iter().map(ToString::to_string).collect()
    }

    #[test]
    fn a_missing_or_unknown_word_is_a_usage_error() {
        for args in [
            &[][..],
            &["install"],
            &["install", "a", "b"],
            &["remove"],
            &["update", "a", "b"],
            &["list", "extra"],
            &["frobnicate"],
        ] {
            assert_eq!(run(&words(args), &env()), ExitCode::from(2), "{args:?}");
        }
    }

    #[test]
    fn a_quoted_tilde_is_expanded_against_home() {
        assert_eq!(env().expand_home("~/plugins/x"), "/nowhere/home/plugins/x");
        assert_eq!(env().expand_home("~x"), "~x");
        let homeless = Env {
            home: None,
            ..env()
        };
        assert_eq!(homeless.expand_home("~/x"), "~/x");
    }

    #[test]
    fn without_a_root_the_message_says_which_variables_to_set() {
        let homeless = Env {
            plugins: None,
            home: None,
            ..env()
        };
        assert!(homeless.install_root().unwrap_err().contains("CMD_PLUGINS"));
    }
}
