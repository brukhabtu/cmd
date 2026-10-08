//! `cmd-plugin.toml`: how a plugin directory says what to run.
//!
//! ```toml
//! name = "calculator"
//! command = ["uv", "run", "--quiet", "calculator"]
//! ```
//!
//! The command runs with the plugin directory as its working directory.
//!
//! Where plugin directories live is decided by [`plugin_dirs`]: the directories named in
//! `CMD_PLUGINS` when it is set, otherwise the per-user directory and, for development,
//! `./plugins` when it exists.

use std::io;
use std::path::{Path, PathBuf};

use serde::Deserialize;
use thiserror::Error;

/// The file a plugin directory must contain.
pub const FILE_NAME: &str = "cmd-plugin.toml";

/// What a plugin directory declares.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub name: String,
    /// The program and its arguments.
    pub command: Vec<String>,
}

/// A manifest together with the directory it came from.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Located {
    pub dir: PathBuf,
    pub manifest: Manifest,
}

/// Why manifest text was rejected.
#[derive(Debug, Error)]
pub enum ManifestError {
    #[error(transparent)]
    Toml(#[from] toml::de::Error),
    #[error("`command` must name a program")]
    EmptyCommand,
}

/// Why a manifest file could not be loaded.
#[derive(Debug, Error)]
pub enum LoadError {
    #[error("could not read {path}: {source}")]
    Io {
        path: PathBuf,
        #[source]
        source: io::Error,
    },
    #[error("{path} is not a valid manifest: {source}")]
    Manifest {
        path: PathBuf,
        #[source]
        source: ManifestError,
    },
}

/// Parse manifest text.
pub fn parse(text: &str) -> Result<Manifest, ManifestError> {
    let manifest: Manifest = toml::from_str(text)?;
    if manifest.command.is_empty() {
        return Err(ManifestError::EmptyCommand);
    }
    Ok(manifest)
}

/// Load the manifest in one plugin directory.
pub fn load(dir: &Path) -> Result<Located, LoadError> {
    let path = dir.join(FILE_NAME);
    let text = std::fs::read_to_string(&path).map_err(|source| LoadError::Io {
        path: path.clone(),
        source,
    })?;
    let manifest = parse(&text).map_err(|source| LoadError::Manifest { path, source })?;
    Ok(Located {
        dir: dir.to_path_buf(),
        manifest,
    })
}

/// Where to look for plugins.
///
/// `env` is the value of `CMD_PLUGINS`, a list of directories separated by `:`; when set
/// it is the whole answer. Otherwise the per-user directory under `home` (Application
/// Support on macOS, `.config` elsewhere) and `./plugins` under `cwd` when that exists.
pub fn plugin_dirs(env: Option<&str>, home: Option<&Path>, cwd: &Path) -> Vec<PathBuf> {
    if let Some(list) = env {
        return list
            .split(':')
            .filter(|entry| !entry.is_empty())
            .map(PathBuf::from)
            .collect();
    }
    let mut dirs = Vec::new();
    if let Some(home) = home {
        dirs.push(user_plugin_dir(home));
    }
    let development = cwd.join("plugins");
    if development.is_dir() {
        dirs.push(development);
    }
    dirs
}

/// The per-user cmd directory, which holds the plugins and what they keep:
/// `~/Library/Application Support/cmd` on macOS, `~/.config/cmd` elsewhere.
pub fn user_cmd_dir(home: &Path) -> PathBuf {
    if cfg!(target_os = "macos") {
        home.join("Library/Application Support/cmd")
    } else {
        home.join(".config/cmd")
    }
}

/// The per-user plugin directory: `plugins` under [`user_cmd_dir`].
pub fn user_plugin_dir(home: &Path) -> PathBuf {
    user_cmd_dir(home).join("plugins")
}

/// Where the host puts the data directories: `plugin-data` under the per-user cmd
/// directory `user_dir`. Nothing watches it.
pub fn plugin_data_root(user_dir: &Path) -> PathBuf {
    user_dir.join("plugin-data")
}

/// Where each plugin's config directory is: `plugin-config` under `user_dir`. The host
/// watches it.
pub fn plugin_config_root(user_dir: &Path) -> PathBuf {
    user_dir.join("plugin-config")
}

/// Whether `name` can be one directory name. A manifest name is the plugin's own to
/// choose, and it must not lead the host out of the directory it is a name in.
pub fn is_directory_name(name: &str) -> bool {
    !name.is_empty() && name != "." && name != ".." && !name.contains(['/', '\\', '\0'])
}

/// Load the plugins under every root, in root order then name order.
///
/// A root that does not exist is not an error: nothing has been installed there yet.
/// A bad manifest is reported beside the plugins that did load.
pub fn discover_all(roots: &[PathBuf]) -> (Vec<Located>, Vec<LoadError>) {
    let mut plugins = Vec::new();
    let mut errors = Vec::new();
    for root in roots {
        let found = match discover(root) {
            Ok(found) => found,
            Err(error) if error.kind() == io::ErrorKind::NotFound => continue,
            Err(source) => {
                errors.push(LoadError::Io {
                    path: root.clone(),
                    source,
                });
                continue;
            }
        };
        for entry in found {
            match entry {
                Ok(plugin) => plugins.push(plugin),
                Err(error) => errors.push(error),
            }
        }
    }
    (plugins, errors)
}

/// Load every subdirectory of `root` that holds a manifest, in name order.
///
/// A directory without a manifest is not a plugin and is skipped. A directory
/// with a bad manifest is reported, not skipped, so the person can fix it.
pub fn discover(root: &Path) -> io::Result<Vec<Result<Located, LoadError>>> {
    let mut dirs: Vec<PathBuf> = std::fs::read_dir(root)?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.join(FILE_NAME).is_file())
        .collect();
    dirs.sort();
    Ok(dirs.iter().map(|dir| load(dir)).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_manifest_names_the_plugin_and_its_command() {
        let manifest = parse("name = \"calc\"\ncommand = [\"uv\", \"run\", \"calc\"]\n").unwrap();
        assert_eq!(manifest.name, "calc");
        assert_eq!(manifest.command, vec!["uv", "run", "calc"]);
    }

    #[test]
    fn an_empty_command_is_rejected() {
        assert!(matches!(
            parse("name = \"calc\"\ncommand = []\n"),
            Err(ManifestError::EmptyCommand)
        ));
    }

    #[test]
    fn unknown_keys_are_rejected_so_typos_surface() {
        assert!(matches!(
            parse("name = \"calc\"\ncommand = [\"x\"]\nkeyword = \"c\"\n"),
            Err(ManifestError::Toml(_))
        ));
    }

    #[test]
    fn cmd_plugins_is_the_whole_answer_when_set() {
        let dirs = plugin_dirs(
            Some("/a:/b::"),
            Some(Path::new("/home/me")),
            Path::new("/work"),
        );
        assert_eq!(dirs, vec![PathBuf::from("/a"), PathBuf::from("/b")]);
    }

    #[test]
    fn otherwise_the_user_directory_comes_first_and_the_development_directory_only_if_present() {
        let scratch = scratch_dir("plugin-dirs");
        let dirs = plugin_dirs(None, Some(Path::new("/home/me")), &scratch);
        assert_eq!(dirs, vec![user_plugin_dir(Path::new("/home/me"))]);
        std::fs::create_dir_all(scratch.join("plugins")).unwrap();
        let dirs = plugin_dirs(None, Some(Path::new("/home/me")), &scratch);
        assert_eq!(dirs[1], scratch.join("plugins"));
        assert!(user_plugin_dir(Path::new("/home/me")).ends_with("cmd/plugins"));
    }

    #[test]
    fn the_data_and_config_directories_sit_beside_the_plugins() {
        let home = Path::new("/home/me");
        let user = user_cmd_dir(home);
        assert_eq!(user_plugin_dir(home), user.join("plugins"));
        assert_eq!(plugin_data_root(&user), user.join("plugin-data"));
        assert_eq!(plugin_config_root(&user), user.join("plugin-config"));
        assert!(is_directory_name("vault"));
        for bad in ["", ".", "..", "a/b", "../x", "a\\b"] {
            assert!(!is_directory_name(bad), "{bad:?}");
        }
    }

    #[test]
    fn discover_all_skips_a_missing_root_and_reports_a_bad_manifest_with_its_path() {
        let scratch = scratch_dir("discover-all");
        let good = scratch.join("good");
        let bad = scratch.join("bad");
        std::fs::create_dir_all(&good).unwrap();
        std::fs::create_dir_all(&bad).unwrap();
        std::fs::create_dir_all(scratch.join("not-a-plugin")).unwrap();
        std::fs::write(
            good.join(FILE_NAME),
            "name = \"good\"\ncommand = [\"true\"]\n",
        )
        .unwrap();
        std::fs::write(bad.join(FILE_NAME), "name = \"bad\"\ncommand = []\n").unwrap();
        let (plugins, errors) = discover_all(&[scratch.join("missing"), scratch.clone()]);
        assert_eq!(plugins.len(), 1);
        assert_eq!(plugins[0].manifest.name, "good");
        assert_eq!(errors.len(), 1);
        let message = errors[0].to_string();
        assert!(
            message.contains(&bad.join(FILE_NAME).display().to_string()),
            "{message}"
        );
        assert!(
            message.contains("`command` must name a program"),
            "{message}"
        );
    }

    fn scratch_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("cmd-host-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }
}
