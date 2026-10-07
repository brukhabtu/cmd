//! The imperative shell around plugins.
//!
//! [`manifest`] finds plugin directories and reads their `cmd-plugin.toml`.
//! [`process`] runs one plugin and exchanges protocol lines with it.
//! [`Host`] owns every running plugin and answers the launcher's queries.

pub mod host;
pub mod manifest;
pub mod process;

pub use host::{Host, QueryError, RunError, StartError, Timeouts};
pub use manifest::{Located, Manifest};
pub use process::{CallError, PluginProcess};
