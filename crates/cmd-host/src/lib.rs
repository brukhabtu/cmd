//! The imperative shell around plugins.
//!
//! [`manifest`] finds plugin directories and reads their `cmd-plugin.toml`.
//! [`process`] runs one plugin and exchanges protocol lines with it.
//! [`Host`] owns every running plugin and answers the launcher's queries.
//! [`bundle`] points plugins at cmd.app's own uv and Python when the app runs from one.
//! [`cli`] is `cmd plugin ...`: [`install`] fetches, updates, removes and lists plugins
//! through [`git`] and the [`index`], and [`doctor`] runs one directory for its author.

pub mod bundle;
pub mod cli;
pub mod doctor;
pub mod git;
pub mod host;
pub mod index;
pub mod install;
pub mod manifest;
pub mod process;

pub use bundle::Bundle;
pub use cli::Env;
pub use host::{Host, HostEvent, RunError, StartError, Startup, Timeouts};
pub use manifest::{Located, Manifest};
pub use process::{CallError, PluginProcess};
