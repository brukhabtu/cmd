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
use std::time::{Duration, Instant};

use cmd_core::protocol::{Description, Effect, Item, Items, Method, Ran, VERSION};
use cmd_core::query::{self, Scope};
use thiserror::Error;

use crate::manifest::Located;
use crate::process::{CallError, PluginProcess};

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
    /// The effect of the run issued in this generation, or why it did not run.
    Ran {
        generation: u64,
        plugin: usize,
        result: Result<Effect, String>,
    },
    /// The plugin's process had gone and a fresh one is up; `attempt` counts restarts
    /// since the last healthy call.
    Restarted { plugin: usize, attempt: u32 },
}

enum Command {
    Query {
        generation: u64,
        text: String,
    },
    Run {
        generation: u64,
        item: String,
        action: String,
    },
}

struct Plugin {
    located: Located,
    description: Description,
    commands: mpsc::Sender<Command>,
}

/// The shortest and longest waits before a plugin is started again after it died.
const FIRST_RESTART_DELAY: Duration = Duration::from_secs(2);
const LONGEST_RESTART_DELAY: Duration = Duration::from_secs(30);

/// How often a plugin has died lately, so restarts slow down instead of spinning.
#[derive(Debug, Default)]
struct Restarts {
    attempt: u32,
    last: Option<Instant>,
}

impl Restarts {
    /// How long to wait before the next restart: nothing the first time, then doubling.
    fn delay(&self) -> Duration {
        let Some(last) = self.last else {
            return Duration::ZERO;
        };
        let wanted = FIRST_RESTART_DELAY
            .saturating_mul(2u32.saturating_pow(self.attempt.saturating_sub(1)))
            .min(LONGEST_RESTART_DELAY);
        wanted.saturating_sub(last.elapsed())
    }

    fn record(&mut self) -> u32 {
        self.attempt += 1;
        self.last = Some(Instant::now());
        self.attempt
    }

    fn healthy(&mut self) {
        self.attempt = 0;
    }
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
                    let home = located.clone();
                    let spawned = thread::Builder::new()
                        .name(name.clone())
                        .spawn(move || serve(index, &home, process, &work, &reports, timeouts));
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
                    result: Err("its worker has stopped".to_string()),
                });
            }
        }
        asked
    }

    /// Ask a plugin to run an action. The effect arrives as a [`HostEvent::Ran`] tagged
    /// with `generation`, so the window can drop one that belongs to an earlier state.
    pub fn run(
        &self,
        generation: u64,
        plugin: usize,
        item: &str,
        action: &str,
    ) -> Result<(), RunError> {
        let running = self
            .plugins
            .get(plugin)
            .ok_or(RunError::NoSuchPlugin(plugin))?;
        let command = Command::Run {
            generation,
            item: item.to_string(),
            action: action.to_string(),
        };
        if running.commands.send(command).is_err() {
            let _ = self.events.send_blocking(HostEvent::Ran {
                generation,
                plugin,
                result: Err("its worker has stopped".to_string()),
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
/// A run is never skipped. When the process has died, the command in hand is answered
/// with that fact, the plugin is started again with back-off, and the next command runs
/// on the fresh process.
fn serve(
    plugin: usize,
    home: &Located,
    mut process: PluginProcess,
    work: &mpsc::Receiver<Command>,
    reports: &async_channel::Sender<HostEvent>,
    timeouts: Timeouts,
) {
    let mut restarts = Restarts::default();
    while let Ok(first) = work.recv() {
        let mut batch = vec![first];
        while let Ok(more) = work.try_recv() {
            batch.push(more);
        }
        let newest_query = batch
            .iter()
            .rposition(|command| matches!(command, Command::Query { .. }));
        for (position, command) in batch.into_iter().enumerate() {
            if matches!(command, Command::Query { .. }) && Some(position) != newest_query {
                continue;
            }
            let (event, gone) = answer(plugin, &mut process, command, timeouts);
            if !gone {
                restarts.healthy();
            }
            if reports.send_blocking(event).is_err() {
                return;
            }
            if gone {
                thread::sleep(restarts.delay());
                let attempt = restarts.record();
                match start_again(home, timeouts.describe) {
                    Ok(fresh) => {
                        process = fresh;
                        if reports
                            .send_blocking(HostEvent::Restarted { plugin, attempt })
                            .is_err()
                        {
                            return;
                        }
                    }
                    Err(error) => eprintln!(
                        "cmd-host: {} did not come back: {error}",
                        home.manifest.name
                    ),
                }
            }
        }
    }
}

/// Run one command and say whether the process turned out to be gone.
fn answer(
    plugin: usize,
    process: &mut PluginProcess,
    command: Command,
    timeouts: Timeouts,
) -> (HostEvent, bool) {
    match command {
        Command::Query { generation, text } => {
            let result = process.call::<Items>(Method::Query { text }, timeouts.query);
            let gone = is_gone(&result);
            let result = result.map(|items| items.items).map_err(describe_failure);
            (
                HostEvent::Answered {
                    generation,
                    plugin,
                    result,
                },
                gone,
            )
        }
        Command::Run {
            generation,
            item,
            action,
        } => {
            let result = process.call::<Ran>(Method::Run { item, action }, timeouts.run);
            let gone = is_gone(&result);
            let result = result.map(|ran| ran.effect).map_err(describe_failure);
            (
                HostEvent::Ran {
                    generation,
                    plugin,
                    result,
                },
                gone,
            )
        }
    }
}

fn is_gone<T>(result: &Result<T, CallError>) -> bool {
    matches!(
        result,
        Err(CallError::Exited | CallError::Write(_) | CallError::Read(_))
    )
}

fn describe_failure(error: CallError) -> String {
    match error {
        CallError::Exited | CallError::Write(_) | CallError::Read(_) => {
            format!("{error}; starting it again")
        }
        other => other.to_string(),
    }
}

fn start_again(home: &Located, timeout: Duration) -> Result<PluginProcess, StartError> {
    handshake(home.clone(), timeout).map(|(_, _, process)| process)
}
