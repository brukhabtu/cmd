//! Every running plugin, behind one door, each on its own thread.
//!
//! The window never waits on a plugin. [`Host::query`] routes the text, hands each
//! plugin it reaches a command, and returns at once with the list of plugins asked.
//! Answers arrive later as [`HostEvent`]s on a channel the window's executor awaits.
//! One worker per plugin means a slow plugin delays only its own answers, and the
//! one-request-in-flight rule the process layer relies on still holds.

use std::io;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

use cmd_core::protocol::{Description, Effect, Item, Items, Method, Ran, VERSION};
use cmd_core::query::{self, Scope};
use thiserror::Error;

use crate::manifest::Located;
use crate::process::PluginProcess;

/// How long a worker waits on each kind of call.
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
        source: crate::process::CallError,
    },
    #[error("{name} speaks protocol {theirs}, this host speaks {ours}")]
    Protocol {
        name: String,
        theirs: u32,
        ours: u32,
    },
}

/// Why an action could not even be asked for.
#[derive(Debug, Error)]
pub enum RunError {
    #[error("no plugin at index {0}")]
    NoSuchPlugin(usize),
}

/// What a plugin's worker reports back. `plugin` is the plugin's index in the host.
#[derive(Debug, Clone, PartialEq)]
pub enum HostEvent {
    /// The answer to the query of this generation, or why there is none.
    Answered {
        generation: u64,
        plugin: usize,
        result: Result<Vec<Item>, String>,
    },
    /// The effect of a run, or why it did not run.
    Ran {
        plugin: usize,
        result: Result<Effect, String>,
    },
}

enum Command {
    Query { generation: u64, text: String },
    Run { item: String, action: String },
}

struct Plugin {
    located: Located,
    description: Description,
    commands: mpsc::Sender<Command>,
}

/// The plugins that started, in the order they were given, each behind a worker thread.
pub struct Host {
    plugins: Vec<Plugin>,
    events: async_channel::Sender<HostEvent>,
    inbox: async_channel::Receiver<HostEvent>,
}

impl Host {
    /// Start every plugin, shake hands with it, and give it a worker.
    ///
    /// Failures come back beside the host, so one broken plugin does not take
    /// the rest down. Plugin indices in events refer to the plugins that started.
    pub fn start(plugins: Vec<Located>, timeouts: Timeouts) -> (Host, Vec<StartError>) {
        let (events, inbox) = async_channel::unbounded();
        let mut started = Vec::new();
        let mut errors = Vec::new();
        for located in plugins {
            match handshake(located, timeouts.describe) {
                Ok((located, description, process)) => {
                    let (commands, work) = mpsc::channel();
                    let index = started.len();
                    let reports = events.clone();
                    let name = format!("plugin:{}", description.name);
                    let spawned = thread::Builder::new()
                        .name(name.clone())
                        .spawn(move || serve(index, process, &work, &reports, timeouts));
                    match spawned {
                        Ok(_handle) => started.push(Plugin {
                            located,
                            description,
                            commands,
                        }),
                        Err(source) => errors.push(StartError::Spawn { name, source }),
                    }
                }
                Err(error) => errors.push(error),
            }
        }
        (
            Host {
                plugins: started,
                events,
                inbox,
            },
            errors,
        )
    }

    /// The channel every worker reports on. Clone it and await it on the window's executor.
    pub fn events(&self) -> async_channel::Receiver<HostEvent> {
        self.inbox.clone()
    }

    /// What each running plugin said about itself.
    pub fn descriptions(&self) -> impl Iterator<Item = &Description> {
        self.plugins.iter().map(|plugin| &plugin.description)
    }

    /// The name of a plugin by index, for messages.
    pub fn name(&self, plugin: usize) -> Option<&str> {
        self.plugins
            .get(plugin)
            .map(|plugin| plugin.description.name.as_str())
    }

    /// The directories of the running plugins, for diagnostics.
    pub fn located(&self) -> impl Iterator<Item = &Located> {
        self.plugins.iter().map(|plugin| &plugin.located)
    }

    /// Route the input and ask the plugins it reaches. Returns their indices at once;
    /// each answers later with a [`HostEvent::Answered`] carrying this generation.
    pub fn query(&self, generation: u64, input: &str) -> Vec<usize> {
        let scopes: Vec<Scope> = self
            .plugins
            .iter()
            .map(|plugin| Scope::from_keyword(plugin.description.keyword.clone()))
            .collect();
        let routes = query::route(input, &scopes);
        let asked: Vec<usize> = routes.iter().map(|route| route.plugin).collect();
        for route in routes {
            let command = Command::Query {
                generation,
                text: route.text,
            };
            if self.plugins[route.plugin].commands.send(command).is_err() {
                // The worker is gone; answer for it so the window stops waiting.
                let _ = self.events.send_blocking(HostEvent::Answered {
                    generation,
                    plugin: route.plugin,
                    result: Err(format!(
                        "{}: its worker has stopped",
                        self.plugins[route.plugin].description.name
                    )),
                });
            }
        }
        asked
    }

    /// Ask a plugin to run an action. The effect arrives as a [`HostEvent::Ran`].
    pub fn run(&self, plugin: usize, item: &str, action: &str) -> Result<(), RunError> {
        let running = self
            .plugins
            .get(plugin)
            .ok_or(RunError::NoSuchPlugin(plugin))?;
        let command = Command::Run {
            item: item.to_string(),
            action: action.to_string(),
        };
        if running.commands.send(command).is_err() {
            let _ = self.events.send_blocking(HostEvent::Ran {
                plugin,
                result: Err(format!(
                    "{}: its worker has stopped",
                    running.description.name
                )),
            });
        }
        Ok(())
    }
}

fn handshake(
    located: Located,
    timeout: Duration,
) -> Result<(Located, Description, PluginProcess), StartError> {
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
    Ok((located, description, process))
}

/// A plugin's worker: take commands until the host goes away, answer each on the event channel.
///
/// Commands that piled up while a call was in flight are taken together, and only the
/// newest query among them is asked: the window has already moved past the others.
/// A run is never skipped.
fn serve(
    plugin: usize,
    mut process: PluginProcess,
    work: &mpsc::Receiver<Command>,
    reports: &async_channel::Sender<HostEvent>,
    timeouts: Timeouts,
) {
    while let Ok(first) = work.recv() {
        let mut batch = vec![first];
        while let Ok(more) = work.try_recv() {
            batch.push(more);
        }
        let newest_query = batch
            .iter()
            .rposition(|command| matches!(command, Command::Query { .. }));
        for (position, command) in batch.into_iter().enumerate() {
            let event = match command {
                Command::Query { .. } if Some(position) != newest_query => continue,
                Command::Query { generation, text } => HostEvent::Answered {
                    generation,
                    plugin,
                    result: process
                        .call::<Items>(Method::Query { text }, timeouts.query)
                        .map(|items| items.items)
                        .map_err(|error| error.to_string()),
                },
                Command::Run { item, action } => HostEvent::Ran {
                    plugin,
                    result: process
                        .call::<Ran>(Method::Run { item, action }, timeouts.run)
                        .map(|ran| ran.effect)
                        .map_err(|error| error.to_string()),
                },
            };
            if reports.send_blocking(event).is_err() {
                return;
            }
        }
    }
}
