//! `cmd-plugin`: the `cmd plugin ...` subcommands without the app, for a clone of this
//! repository and for the tests on a machine that cannot build the window.

use std::process::ExitCode;

use cmd_host::cli::{self, Env};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    cli::run(&args, &Env::from_process())
}
