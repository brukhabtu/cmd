//! Every running plugin, behind one door.

use std::io;
use std::time::Duration;

use cmd_core::protocol::{Description, Effect, Items, Method, Ran, VERSION};
use cmd_core::query::{self, Hit, Scope};
use thiserror::Error;

use crate::manifest::Located;
use crate::process::{CallError, PluginProcess};

/// How long the host waits on each kind of call.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Timeouts {
    /// Generous: the first `uv run` of a plugin may have to build its environment.
    pub describe: Duration,
    pub query: Duration,
    pub run: Duration,
}

impl Default for Timeouts {
    fn default() -> Self {
        Self {
            describe: Duration::from_secs(60),
            query: Duration::from_secs(3),
            run: Duration::from_secs(10),
        }
    }
}

/// Why a plugin could not be started.
#[derive(Debug, Error)]
pub enum StartError {
    #[error("could not start {name}: {source}")]
    Spawn {
        name: String,
        #[source]
        source: io::Error,
    },
    #[error("{name} did not describe itself: {source}")]
    Describe {
        name: String,
        #[source]
        source: CallError,
    },
    #[error("{name} speaks protocol {theirs}, this host speaks {ours}")]
    Protocol {
        name: String,
        theirs: u32,
        ours: u32,
    },
}

/// A plugin that did not answer a query.
#[derive(Debug, Error)]
#[error("{plugin}: {source}")]
pub struct QueryError {
    pub plugin: String,
    #[source]
    pub source: CallError,
}

/// Why an action did not run.
#[derive(Debug, Error)]
pub enum RunError {
    #[error("no plugin at index {0}")]
    NoSuchPlugin(usize),
    #[error("{plugin}: {source}")]
    Call {
        plugin: String,
        #[source]
        source: CallError,
    },
}

struct Running {
    located: Located,
    description: Description,
    process: PluginProcess,
}

/// The plugins that started, in the order they were given.
pub struct Host {
    plugins: Vec<Running>,
    timeouts: Timeouts,
}

impl Host {
    /// Start every plugin and shake hands with it.
    ///
    /// Failures come back beside the host, so one broken plugin does not take
    /// the rest down. Plugin indices in [`Hit`] refer to the plugins that started.
    pub fn start(plugins: Vec<Located>, timeouts: Timeouts) -> (Host, Vec<StartError>) {
        let mut running = Vec::new();
        let mut errors = Vec::new();
        for located in plugins {
            match start_one(located, timeouts.describe) {
                Ok(plugin) => running.push(plugin),
                Err(error) => errors.push(error),
            }
        }
        (
            Host {
                plugins: running,
                timeouts,
            },
            errors,
        )
    }

    /// What each running plugin said about itself.
    pub fn descriptions(&self) -> impl Iterator<Item = &Description> {
        self.plugins.iter().map(|plugin| &plugin.description)
    }

    /// Ask the plugins the input routes to, and merge their answers.
    pub fn query(&mut self, input: &str) -> (Vec<Hit>, Vec<QueryError>) {
        let scopes: Vec<Scope> = self
            .plugins
            .iter()
            .map(|plugin| Scope::from_keyword(plugin.description.keyword.clone()))
            .collect();
        let mut batches = Vec::new();
        let mut errors = Vec::new();
        for route in query::route(input, &scopes) {
            let plugin = &mut self.plugins[route.plugin];
            let method = Method::Query { text: route.text };
            match plugin.process.call::<Items>(method, self.timeouts.query) {
                Ok(items) => batches.push((route.plugin, items.items)),
                Err(source) => errors.push(QueryError {
                    plugin: plugin.description.name.clone(),
                    source,
                }),
            }
        }
        (query::merge(batches), errors)
    }

    /// Run one action on one item and return the effect the plugin asks for.
    pub fn run(&mut self, plugin: usize, item: &str, action: &str) -> Result<Effect, RunError> {
        let running = self
            .plugins
            .get_mut(plugin)
            .ok_or(RunError::NoSuchPlugin(plugin))?;
        let method = Method::Run {
            item: item.to_string(),
            action: action.to_string(),
        };
        let ran: Ran = running
            .process
            .call(method, self.timeouts.run)
            .map_err(|source| RunError::Call {
                plugin: running.description.name.clone(),
                source,
            })?;
        Ok(ran.effect)
    }

    /// The directories of the running plugins, for diagnostics.
    pub fn located(&self) -> impl Iterator<Item = &Located> {
        self.plugins.iter().map(|plugin| &plugin.located)
    }
}

fn start_one(located: Located, timeout: Duration) -> Result<Running, StartError> {
    let name = located.manifest.name.clone();
    let mut process =
        PluginProcess::spawn(&located.manifest.command, &located.dir).map_err(|source| {
            StartError::Spawn {
                name: name.clone(),
                source,
            }
        })?;
    let description: Description = process
        .call(Method::Describe { protocol: VERSION }, timeout)
        .map_err(|source| StartError::Describe {
            name: name.clone(),
            source,
        })?;
    if description.protocol != VERSION {
        return Err(StartError::Protocol {
            name,
            theirs: description.protocol,
            ours: VERSION,
        });
    }
    Ok(Running {
        located,
        description,
        process,
    })
}
