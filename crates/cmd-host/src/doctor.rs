//! `cmd plugin doctor`: run a plugin directory the way the launcher does, and show what
//! comes back.
//!
//! ```text
//! cmd plugin doctor <plugin-dir> [--query TEXT] [--run ITEM [--action ACTION]]
//! ```
//!
//! Prints the manifest, the description from the handshake, then the items for the query
//! and the effect for the run, as JSON. A protocol problem prints the host's own message,
//! the one the launcher would show, and exits 1. A usage mistake exits 2.

use std::path::PathBuf;
use std::process::ExitCode;
use std::time::Duration;

use cmd_core::protocol::{ACCEPTED, Description, Items, Method, Ran, VERSION};
use cmd_core::state::DEFAULT_ACTION;

use crate::{PluginProcess, Timeouts, manifest};

const USAGE: &str = "usage: cmd plugin doctor <plugin-dir> [--query TEXT] [--run ITEM [--action ACTION]]\n\
  The query text is sent as given: the launcher would first strip the plugin's keyword.";

/// What the person asked for, read from the arguments. Pure: a list of strings in, this out.
#[derive(Debug, PartialEq, Eq)]
pub struct Request {
    pub dir: PathBuf,
    pub query: Option<String>,
    pub run: Option<String>,
    pub action: String,
}

pub fn parse_args(args: &[String]) -> Result<Request, String> {
    let mut words = args.iter();
    let dir = words.next().ok_or_else(|| USAGE.to_string())?;
    let mut request = Request {
        dir: PathBuf::from(dir),
        query: None,
        run: None,
        action: DEFAULT_ACTION.to_string(),
    };
    while let Some(flag) = words.next() {
        let value = words
            .next()
            .ok_or_else(|| format!("{flag} needs a value\n{USAGE}"))?;
        match flag.as_str() {
            "--query" => request.query = Some(value.clone()),
            "--run" => request.run = Some(value.clone()),
            "--action" => request.action.clone_from(value),
            other => return Err(format!("unknown option {other}\n{USAGE}")),
        }
    }
    Ok(request)
}

pub fn examine(request: &Request, timeouts: Timeouts) -> Result<(), String> {
    let located = manifest::load(&request.dir).map_err(|error| error.to_string())?;
    println!(
        "manifest: {} runs {:?}",
        located.manifest.name, located.manifest.command
    );
    let mut process = PluginProcess::spawn(&located.manifest.command, &located.dir)
        .map_err(|error| format!("could not start the plugin: {error}"))?;
    let description: Description = process
        .call(Method::Describe { protocol: VERSION }, timeouts.describe)
        .map_err(|error| format!("describe: {error}"))?;
    println!("description: {}", pretty(&description));
    if !ACCEPTED.contains(&description.protocol) {
        return Err(format!(
            "the plugin speaks protocol {}, this host accepts {} to {}",
            description.protocol,
            ACCEPTED.start(),
            ACCEPTED.end()
        ));
    }
    if let Some(text) = &request.query {
        let items: Items = process
            .call(Method::Query { text: text.clone() }, timeouts.query)
            .map_err(|error| format!("query {text:?}: {error}"))?;
        println!("items for {text:?}: {}", pretty(&items.items));
    }
    if let Some(item) = &request.run {
        let ran: Ran = process
            .call(
                Method::Run {
                    item: item.clone(),
                    action: request.action.clone(),
                },
                timeouts.run,
            )
            .map_err(|error| format!("run {item:?} with action {:?}: {error}", request.action))?;
        println!("effect: {}", pretty(&ran.effect));
    }
    Ok(())
}

fn pretty<T: serde::Serialize>(value: &T) -> String {
    serde_json::to_string_pretty(value).unwrap_or_else(|error| format!("<unprintable: {error}>"))
}

/// The whole command: the words after `doctor` in, the exit code out.
pub fn run(args: &[String]) -> ExitCode {
    let request = match parse_args(args) {
        Ok(request) => request,
        Err(message) => {
            eprintln!("{message}");
            return ExitCode::from(2);
        }
    };
    // The first run of a plugin builds its environment through uv, which takes longer
    // than a handshake the launcher would wait for.
    let timeouts = Timeouts {
        describe: Duration::from_secs(60),
        ..Timeouts::default()
    };
    match examine(&request, timeouts) {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("cmd plugin doctor: {message}");
            ExitCode::from(1)
        }
    }
}

#[cfg(test)]
mod tests {
    use std::path::Path;

    use super::*;

    fn args(words: &[&str]) -> Vec<String> {
        words.iter().map(ToString::to_string).collect()
    }

    #[test]
    fn a_directory_alone_is_a_handshake_check() {
        let request = parse_args(&args(&["plugins/calculator"])).unwrap();
        assert_eq!(request.dir, Path::new("plugins/calculator"));
        assert_eq!(request.query, None);
        assert_eq!(request.run, None);
        assert_eq!(request.action, DEFAULT_ACTION);
    }

    #[test]
    fn query_run_and_action_are_read_in_any_order() {
        let request = parse_args(&args(&[
            "d", "--run", "4", "--action", "copy", "--query", "2+2",
        ]))
        .unwrap();
        assert_eq!(request.query.as_deref(), Some("2+2"));
        assert_eq!(request.run.as_deref(), Some("4"));
        assert_eq!(request.action, "copy");
    }

    #[test]
    fn mistakes_are_usage_errors() {
        assert!(parse_args(&args(&[])).unwrap_err().contains("usage"));
        assert!(
            parse_args(&args(&["d", "--query"]))
                .unwrap_err()
                .contains("needs a value")
        );
        assert!(
            parse_args(&args(&["d", "--bogus", "x"]))
                .unwrap_err()
                .contains("unknown option")
        );
    }
}
