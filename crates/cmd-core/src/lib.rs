//! The functional core of cmd.
//!
//! Everything here takes data and returns data. Spawning processes, reading
//! lines, drawing windows, and touching the clipboard happen in `cmd-host` and
//! `cmd-app`, which call into this crate and act on what comes back.

pub mod input;
pub mod placement;
pub mod protocol;
pub mod query;
pub mod state;
