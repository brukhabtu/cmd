//! `plugins/index.toml`: the plugins `cmd plugin install <name>` can fetch (decision 8).
//!
//! The index lives at the tip of this repository's default branch, so it is read with
//! one shallow fetch and never needs a clone. `CMD_INDEX` points the command at another
//! repository, which is how the tests use a local one.

use serde::Deserialize;
use thiserror::Error;

use crate::git::{self, GitError};

/// Where the index sits inside its repository.
pub const PATH: &str = "plugins/index.toml";

/// The repository the index is read from unless `CMD_INDEX` says otherwise: this one.
pub const REPOSITORY: &str = env!("CARGO_PKG_REPOSITORY");

/// The whole file.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Index {
    #[serde(default)]
    pub plugin: Vec<Entry>,
}

/// One listed plugin. The shape is the one `scripts/check_index.py` checks.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entry {
    pub name: String,
    pub summary: String,
    pub source: String,
    #[serde(rename = "ref")]
    pub reference: String,
    pub subdirectory: Option<String>,
    pub commit: Option<String>,
}

impl Entry {
    /// The commit an install fetches: `commit` when the ref is a tag that was pinned at
    /// review, otherwise the ref itself.
    pub fn commit(&self) -> &str {
        self.commit.as_deref().unwrap_or(&self.reference)
    }
}

impl Index {
    pub fn entry(&self, name: &str) -> Option<&Entry> {
        self.plugin.iter().find(|entry| entry.name == name)
    }

    /// Every listed name, for the message that says a name is not among them.
    pub fn names(&self) -> Vec<String> {
        self.plugin.iter().map(|entry| entry.name.clone()).collect()
    }
}

/// Why the index could not be read.
#[derive(Debug, Error)]
pub enum IndexError {
    #[error("could not fetch {PATH} from {repository}: {source}")]
    Git {
        repository: String,
        #[source]
        source: GitError,
    },
    #[error("{PATH} at {repository} is not a valid index: {source}")]
    Toml {
        repository: String,
        #[source]
        source: toml::de::Error,
    },
}

/// Parse index text.
pub fn parse(text: &str) -> Result<Index, toml::de::Error> {
    toml::from_str(text)
}

/// Read the index at the tip of `repository`'s default branch.
pub fn fetch(repository: &str) -> Result<Index, IndexError> {
    let text = git::file_at_head(repository, PATH).map_err(|source| IndexError::Git {
        repository: repository.to_string(),
        source,
    })?;
    parse(&text).map_err(|source| IndexError::Toml {
        repository: repository.to_string(),
        source,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const INDEX: &str = r#"
[[plugin]]
name = "calculator"
summary = "Arithmetic as you type."
source = "https://example.invalid/cmd"
ref = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
subdirectory = "plugins/calculator"

[[plugin]]
name = "tagged"
summary = "Pinned through a tag."
source = "https://example.invalid/tagged"
ref = "v1"
commit = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
"#;

    #[test]
    fn an_entry_is_found_by_name_and_its_commit_is_the_ref_unless_pinned() {
        let index = parse(INDEX).unwrap();
        let calculator = index.entry("calculator").unwrap();
        assert_eq!(
            calculator.commit(),
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        );
        assert_eq!(
            calculator.subdirectory.as_deref(),
            Some("plugins/calculator")
        );
        let tagged = index.entry("tagged").unwrap();
        assert_eq!(tagged.reference, "v1");
        assert_eq!(tagged.commit(), "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
        assert!(index.entry("nothing").is_none());
        assert_eq!(index.names(), vec!["calculator", "tagged"]);
    }

    #[test]
    fn an_unknown_field_is_rejected_so_the_shape_stays_the_one_the_check_script_knows() {
        let text = format!("{INDEX}\nkeyword = \"x\"\n");
        assert!(parse(&text).is_err());
    }

    #[test]
    fn an_empty_index_lists_nothing() {
        assert_eq!(
            parse("# nothing yet\n").unwrap().plugin,
            Vec::<Entry>::new()
        );
    }
}
