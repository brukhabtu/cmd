//! `cmd-plugin.toml`: how a plugin directory says what to run.
//!
//! ```toml
//! name = "calculator"
//! command = ["uv", "run", "--quiet", "calculator"]
//! ```
//!
//! The command runs with the plugin directory as its working directory.

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
}
