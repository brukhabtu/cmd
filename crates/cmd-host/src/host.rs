//! Every running plugin, behind one door, each on its own thread.
//!
//! The window never waits on a plugin. [`Host::query`] routes the text, hands each
//! plugin it reaches a command, and returns at once with the list of plugins asked.
//! Answers arrive later as [`HostEvent`]s on a channel the window's executor awaits.
//! One worker per plugin means a slow plugin delays only its own answers, and the
//! one-request-in-flight rule the process layer relies on still holds.

use std::ffi::OsString;
use std::io;
use std::path::{Path, PathBuf};
use std::sync::{Arc, PoisonError, RwLock, mpsc};
use std::thread;
use std::time::{Duration, Instant};

use cmd_core::protocol::{ACCEPTED, Description, Effect, Item, Items, Method, Ran};
use cmd_core::query::{self, Scope};
use notify::{RecursiveMode, Watcher};
use thiserror::Error;

use crate::manifest::{self, LoadError, Located};
use crate::process::{CallError, PluginProcess};

/// How long a worker waits on each kind of call.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Timeouts {
    /// Generous: the first `uv run` of a plugin may have to build its environment.
    pub describe: Duration,
    pub query: Duration,
    pub run: Duration,
    /// This many timeouts in a row and the plugin counts as hung: it is killed and
    /// started again like one that died. Zero never counts a plugin as hung.
    pub hung_after: u32,
}

impl Default for Timeouts {
    fn default() -> Self {
        Self {
            describe: Duration::from_secs(60),
            query: Duration::from_secs(3),
            run: Duration::from_secs(10),
            hung_after: 3,
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
    #[error("{name} speaks protocol {theirs}, this host accepts {oldest} to {newest}")]
    Protocol {
        name: String,
        theirs: u32,
        oldest: u32,
        newest: u32,
    },
    /// A later plugin directory declared a name that is already running: the first in the
    /// order of the plugin directories wins, and this one is not started.
    #[error("{name} is already running from {}; not starting the copy in {}", first.display(), second.display())]
    Duplicate {
        name: String,
        first: PathBuf,
        second: PathBuf,
    },
}

impl StartError {
    /// The plugin this is about, as its manifest names it, so a caller can strike it off a
    /// list of plugins still starting without reading the message.
    pub fn name(&self) -> &str {
        match self {
            StartError::Spawn { name, .. }
            | StartError::Describe { name, .. }
            | StartError::Protocol { name, .. }
            | StartError::Duplicate { name, .. } => name,
        }
    }
}

/// What [`Host::start_reporting`] says about each plugin, in the order the plugins were
/// given, each before the next handshake begins.
#[derive(Debug)]
pub enum Startup {
    /// The plugin described itself and has a worker; `plugin` is its index in the host
    /// and `name` is what its manifest calls it, as in [`StartError::name`].
    Up { plugin: usize, name: String },
    /// The plugin was not started.
    Failed(StartError),
    /// Inside cmd.app, before any plugin starts: uv is fetching the Python they run on,
    /// which on a first launch takes a while (decision 7).
    FetchingPython,
    /// The fetch is over; an error says why there is no Python. Plugins are started
    /// anyway, so each says for itself what it lacks.
    FetchedPython(Result<(), String>),
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
    /// A file in the plugin's directory changed and a fresh process runs the new code.
    Reloaded { plugin: usize },
    /// Something the window should say about the plugin: it could not be started again,
    /// or its answer had items the host could not read, which are left out.
    Trouble { plugin: usize, message: String },
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
    /// A file under the plugin's directory changed: start it again on the new code.
    Reload,
}

struct Plugin {
    /// The directory the plugin runs from, with the manifest it was started on.
    located: Located,
    /// Shared with the worker, which replaces it when the plugin starts again.
    description: Arc<RwLock<Description>>,
    commands: mpsc::Sender<Command>,
}

/// How long to wait after a file changed before starting the plugin on the new code.
const RELOAD_SETTLE: Duration = Duration::from_millis(200);

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
    /// Watches every plugin directory for the life of the host. `None` when watching failed.
    _watcher: Option<notify::RecommendedWatcher>,
}

impl Host {
    /// Start every plugin, shake hands with it, and give it a worker.
    ///
    /// Failures come back beside the host, so one broken plugin does not take
    /// the rest down. Plugin indices in events refer to the plugins that started.
    pub fn start(plugins: Vec<Located>, timeouts: Timeouts) -> (Host, Vec<StartError>) {
        Self::start_in(plugins, timeouts, &[])
    }

    /// [`Host::start`] with `env` set for every plugin process, now and on every restart.
    pub fn start_in(
        plugins: Vec<Located>,
        timeouts: Timeouts,
        env: &[(OsString, OsString)],
    ) -> (Host, Vec<StartError>) {
        let mut errors = Vec::new();
        let host = Self::start_reporting_in(plugins, timeouts, env, |report| {
            if let Startup::Failed(error) = report {
                errors.push(error);
            }
        });
        (host, errors)
    }

    /// [`Host::start`], telling `report` about each plugin as its handshake ends, so a
    /// caller that cannot wait for the slowest plugin (the window, on a first launch
    /// where uv may be fetching Python) can say which ones are still starting.
    ///
    /// Handshakes stay one after another: the first directory to declare a name wins,
    /// and indices follow the order given, so both must be decided in sequence.
    pub fn start_reporting(
        plugins: Vec<Located>,
        timeouts: Timeouts,
        report: impl FnMut(Startup),
    ) -> Host {
        Self::start_reporting_in(plugins, timeouts, &[], report)
    }

    /// [`Host::start_reporting`] with `env` set for every plugin process, now and on
    /// every restart: inside cmd.app it points them at the bundle's uv and its Python.
    pub fn start_reporting_in(
        plugins: Vec<Located>,
        timeouts: Timeouts,
        env: &[(OsString, OsString)],
        report: impl FnMut(Startup),
    ) -> Host {
        Self::start_reporting_with(plugins, timeouts, env, None, report)
    }

    /// [`Host::start_reporting_in`] that also gives each plugin a data and a config
    /// directory under `user_dir`, the per-user cmd directory (`manifest::user_cmd_dir`;
    /// tests pass a scratch directory, as they pass a scratch home elsewhere). Each
    /// plugin process gets `CMD_PLUGIN_DATA` and `CMD_PLUGIN_CONFIG`, now and on every
    /// restart. The data directory is created and left unwatched; the config directory
    /// is not created, and a change in it, or its appearing, reloads the plugin. With
    /// `None` the plugins get neither variable and nothing more is watched.
    pub fn start_reporting_with(
        plugins: Vec<Located>,
        timeouts: Timeouts,
        env: &[(OsString, OsString)],
        user_dir: Option<&Path>,
        mut report: impl FnMut(Startup),
    ) -> Host {
        let (events, inbox) = async_channel::unbounded();
        let mut started: Vec<Plugin> = Vec::new();
        for located in plugins {
            let same_name =
                |plugin: &&Plugin| plugin.located.manifest.name == located.manifest.name;
            if let Some(first) = started.iter().find(same_name) {
                report(Startup::Failed(StartError::Duplicate {
                    name: located.manifest.name,
                    first: first.located.dir.clone(),
                    second: located.dir,
                }));
                continue;
            }
            let env = match plugin_env(&located.manifest.name, user_dir, env) {
                Ok(env) => env,
                Err(source) => {
                    let name = located.manifest.name;
                    report(Startup::Failed(StartError::Spawn { name, source }));
                    continue;
                }
            };
            match handshake(located, &env, timeouts.describe) {
                Ok((located, description, process)) => {
                    let (commands, work) = mpsc::channel();
                    let reports = events.clone();
                    let plugin = started.len();
                    let name = located.manifest.name.clone();
                    let description = Arc::new(RwLock::new(description));
                    let worker = Worker {
                        plugin,
                        home: located.clone(),
                        description: Arc::clone(&description),
                        process,
                        env,
                        timeouts,
                        restarts: Restarts::default(),
                        timeouts_in_a_row: 0,
                    };
                    let spawned = thread::Builder::new()
                        .name(format!("plugin:{name}"))
                        .spawn(move || worker.serve(&work, &reports));
                    match spawned {
                        Ok(_handle) => {
                            started.push(Plugin {
                                located,
                                description,
                                commands,
                            });
                            report(Startup::Up { plugin, name });
                        }
                        Err(source) => report(Startup::Failed(StartError::Spawn { name, source })),
                    }
                }
                Err(error) => report(Startup::Failed(error)),
            }
        }
        let watcher = watch_plugins(&started, user_dir);
        Host {
            plugins: started,
            events,
            inbox,
            _watcher: watcher,
        }
    }

    /// The channel every worker reports on. Clone it and await it on the window's executor.
    pub fn events(&self) -> async_channel::Receiver<HostEvent> {
        self.inbox.clone()
    }

    /// What each running plugin says about itself, as of now: a reload can change it.
    pub fn descriptions(&self) -> impl Iterator<Item = Description> + '_ {
        self.plugins.iter().map(|plugin| {
            plugin
                .description
                .read()
                .unwrap_or_else(PoisonError::into_inner)
                .clone()
        })
    }

    /// The name of a plugin by index, for messages.
    pub fn name(&self, plugin: usize) -> Option<String> {
        self.descriptions()
            .nth(plugin)
            .map(|description| description.name)
    }

    /// The directories of the running plugins, for diagnostics.
    pub fn located(&self) -> impl Iterator<Item = &Located> {
        self.plugins.iter().map(|plugin| &plugin.located)
    }

    /// Route the input and ask the plugins it reaches. Returns their indices at once;
    /// each answers later with a [`HostEvent::Answered`] carrying this generation.
    pub fn query(&self, generation: u64, input: &str) -> Vec<usize> {
        let scopes: Vec<Scope> = self
            .descriptions()
            .map(|description| Scope::from_keyword(description.keyword))
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

/// The environment for one plugin: `base`, and with a `user_dir` the two variables naming
/// its data directory, which is created here, and its config directory, which is not.
pub(crate) fn plugin_env(
    name: &str,
    user_dir: Option<&Path>,
    base: &[(OsString, OsString)],
) -> io::Result<Vec<(OsString, OsString)>> {
    let mut env = base.to_vec();
    let Some(user_dir) = user_dir else {
        return Ok(env);
    };
    if !manifest::is_directory_name(name) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("{name:?} cannot name a data directory"),
        ));
    }
    let user_dir = std::path::absolute(user_dir)?;
    let data = manifest::plugin_data_root(&user_dir).join(name);
    std::fs::create_dir_all(&data).map_err(|source| {
        io::Error::new(
            source.kind(),
            format!(
                "cannot make the data directory {}: {source}",
                data.display()
            ),
        )
    })?;
    let config = manifest::plugin_config_root(&user_dir).join(name);
    env.push(("CMD_PLUGIN_DATA".into(), data.into_os_string()));
    env.push(("CMD_PLUGIN_CONFIG".into(), config.into_os_string()));
    Ok(env)
}

fn handshake(
    located: Located,
    env: &[(OsString, OsString)],
    timeout: Duration,
) -> Result<(Located, Description, PluginProcess), StartError> {
    let name = located.manifest.name.clone();
    let mut process = PluginProcess::spawn_in(&located.manifest.command, &located.dir, env)
        .map_err(|source| StartError::Spawn {
            name: name.clone(),
            source,
        })?;
    let description: Description = process
        .call(Method::describe(), timeout)
        .map_err(|source| StartError::Describe {
            name: name.clone(),
            source,
        })?;
    if !ACCEPTED.contains(&description.protocol) {
        return Err(StartError::Protocol {
            name,
            theirs: description.protocol,
            oldest: *ACCEPTED.start(),
            newest: *ACCEPTED.end(),
        });
    }
    Ok((located, description, process))
}

/// What a call said about the process behind it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Health {
    Fine,
    TimedOut,
    /// The process has exited or its pipes are broken; the next call cannot reach it.
    Gone,
}

fn health_of<T>(result: &Result<T, CallError>) -> Health {
    match result {
        Err(CallError::Exited | CallError::Write(_) | CallError::Read(_)) => Health::Gone,
        Err(CallError::Timeout(_)) => Health::TimedOut,
        Ok(_) | Err(_) => Health::Fine,
    }
}

/// A plugin's worker: owns the process and answers commands on the event channel until
/// the host goes away. Starts the plugin again when it dies, hangs, or its code changes.
struct Worker {
    plugin: usize,
    /// The directory and the manifest the process was last started on.
    home: Located,
    description: Arc<RwLock<Description>>,
    process: PluginProcess,
    /// Set on every start of the process, so a restart runs on the same uv and Python.
    env: Vec<(OsString, OsString)>,
    timeouts: Timeouts,
    restarts: Restarts,
    timeouts_in_a_row: u32,
}

impl Worker {
    /// Commands that piled up while a call was in flight are taken together, and only the
    /// newest query among them is asked: the window has already moved past the others.
    /// A run is never skipped. Reloads among them become one restart, done first.
    fn serve(mut self, work: &mpsc::Receiver<Command>, reports: &async_channel::Sender<HostEvent>) {
        while let Ok(first) = work.recv() {
            let mut batch = vec![first];
            batch.extend(work.try_iter());
            if batch
                .iter()
                .any(|command| matches!(command, Command::Reload))
            {
                match self.reload(work, reports) {
                    Some(later) => batch.extend(later),
                    None => return,
                }
            }
            let newest_query = batch
                .iter()
                .rposition(|command| matches!(command, Command::Query { .. }));
            for (position, command) in batch.into_iter().enumerate() {
                let skip = match &command {
                    Command::Reload => true,
                    Command::Query { .. } => Some(position) != newest_query,
                    Command::Run { .. } => false,
                };
                if !skip && !self.answer_and_recover(command, reports) {
                    return;
                }
            }
        }
    }

    /// Start the plugin again on what its directory holds now, once the editor has had
    /// a moment to finish writing. Commands that arrived meanwhile come back to be
    /// answered on the fresh process; further reloads among them are covered by this
    /// one. `None` once the host has gone.
    fn reload(
        &mut self,
        work: &mpsc::Receiver<Command>,
        reports: &async_channel::Sender<HostEvent>,
    ) -> Option<Vec<Command>> {
        thread::sleep(RELOAD_SETTLE);
        let later: Vec<Command> = work
            .try_iter()
            .filter(|command| !matches!(command, Command::Reload))
            .collect();
        let plugin = self.plugin;
        let event = self.start_again("after a change", HostEvent::Reloaded { plugin });
        if matches!(event, HostEvent::Reloaded { .. }) {
            self.restarts.healthy();
        }
        reports.send_blocking(event).ok().map(|()| later)
    }

    /// Answer one command and, when the process turned out to be gone or hung, start it
    /// again with back-off. Only an answered call counts as healthy and forgets the
    /// back-off: a plugin that hangs every time waits longer each restart, like one that
    /// dies every time. Whether the host is still listening.
    fn answer_and_recover(
        &mut self,
        command: Command,
        reports: &async_channel::Sender<HostEvent>,
    ) -> bool {
        let (event, health, aside) = self.answer(command);
        let (event, gone) = self.hung_or_gone(event, health);
        if health == Health::Fine {
            self.restarts.healthy();
        }
        if reports.send_blocking(event).is_err() {
            return false;
        }
        if let Some(aside) = aside
            && reports.send_blocking(aside).is_err()
        {
            return false;
        }
        if !gone {
            return true;
        }
        thread::sleep(self.restarts.delay());
        let attempt = self.restarts.record();
        let plugin = self.plugin;
        let event = self.start_again("after it died", HostEvent::Restarted { plugin, attempt });
        reports.send_blocking(event).is_ok()
    }

    /// Run one command and say how the process behind it fared. The third value is an
    /// event to send after the answer: a note that items the host could not read were
    /// left out of it, which the window shows as it shows any trouble.
    fn answer(&mut self, command: Command) -> (HostEvent, Health, Option<HostEvent>) {
        let plugin = self.plugin;
        match command {
            Command::Reload => unreachable!("reloads are handled before answering"),
            Command::Query { generation, text } => {
                let result = self
                    .process
                    .call::<Items>(Method::Query { text }, self.timeouts.query);
                let health = health_of(&result);
                let aside = result
                    .as_ref()
                    .ok()
                    .and_then(Items::dropped_note)
                    .map(|message| HostEvent::Trouble { plugin, message });
                let result = result.map(|items| items.items).map_err(describe_failure);
                (
                    HostEvent::Answered {
                        generation,
                        plugin,
                        result,
                    },
                    health,
                    aside,
                )
            }
            Command::Run {
                generation,
                item,
                action,
            } => {
                let result = self
                    .process
                    .call::<Ran>(Method::Run { item, action }, self.timeouts.run);
                let health = health_of(&result);
                let result = result.map(|ran| ran.effect).map_err(describe_failure);
                (
                    HostEvent::Ran {
                        generation,
                        plugin,
                        result,
                    },
                    health,
                    None,
                )
            }
        }
    }

    /// Whether the process is to be started again: it has gone, or it has now timed out
    /// `hung_after` times in a row, in which case the answer says so.
    fn hung_or_gone(&mut self, event: HostEvent, health: Health) -> (HostEvent, bool) {
        self.timeouts_in_a_row = match health {
            Health::TimedOut => self.timeouts_in_a_row + 1,
            Health::Fine | Health::Gone => 0,
        };
        let limit = self.timeouts.hung_after;
        if limit == 0 || self.timeouts_in_a_row < limit {
            return (event, health == Health::Gone);
        }
        self.timeouts_in_a_row = 0;
        let hung = |error: String| format!("{error}, {limit} times in a row; starting it again");
        let event = match event {
            HostEvent::Answered {
                generation,
                plugin,
                result: Err(error),
            } => HostEvent::Answered {
                generation,
                plugin,
                result: Err(hung(error)),
            },
            HostEvent::Ran {
                generation,
                plugin,
                result: Err(error),
            } => HostEvent::Ran {
                generation,
                plugin,
                result: Err(hung(error)),
            },
            other => other,
        };
        (event, true)
    }

    /// Start the process again on what the directory holds now. The manifest is read
    /// afresh, so a changed command takes effect, and the new description replaces the
    /// old one in the host. Returns the event to report: `success` when the plugin is
    /// up, or [`HostEvent::Trouble`] saying it did not come back `when`. On trouble the
    /// old process, if any, keeps serving.
    fn start_again(&mut self, when: &str, success: HostEvent) -> HostEvent {
        let plugin = self.plugin;
        let started = self
            .manifest_now()
            .map_err(|error| error.to_string())
            .and_then(|located| {
                handshake(located, &self.env, self.timeouts.describe)
                    .map_err(|error| error.to_string())
            });
        match started {
            Ok((located, description, process)) => {
                self.home = located;
                *self
                    .description
                    .write()
                    .unwrap_or_else(PoisonError::into_inner) = description;
                self.process = process;
                self.timeouts_in_a_row = 0;
                success
            }
            Err(error) => HostEvent::Trouble {
                plugin,
                message: format!("did not come back {when}: {error}"),
            },
        }
    }

    /// The manifest as the directory holds it now. A directory without one keeps the
    /// manifest the plugin was started on: the host was handed it directly, as tests do.
    fn manifest_now(&self) -> Result<Located, LoadError> {
        match manifest::load(&self.home.dir) {
            Err(LoadError::Io { source, .. }) if source.kind() == io::ErrorKind::NotFound => {
                Ok(self.home.clone())
            }
            loaded => loaded,
        }
    }
}

fn describe_failure(error: CallError) -> String {
    match error {
        CallError::Exited | CallError::Write(_) | CallError::Read(_) => {
            format!("{error}; starting it again")
        }
        other => other.to_string(),
    }
}

/// Watch every plugin directory, and with a `user_dir` every plugin's config directory,
/// and tell the owning worker when a file changes.
///
/// A config directory may not exist yet, and is not the host's to create. So the watch is
/// on `plugin-config`, which holds them all and which the host makes if it is missing:
/// a config directory appearing in it, or a file in one, arrives as an event whose path
/// is under that plugin's directory. The data directories are under `plugin-data`, which
/// is never watched.
fn watch_plugins(
    plugins: &[Plugin],
    user_dir: Option<&Path>,
) -> Option<notify::RecommendedWatcher> {
    let mut homes: Vec<(PathBuf, mpsc::Sender<Command>)> = plugins
        .iter()
        .map(|plugin| {
            let dir = plugin
                .located
                .dir
                .canonicalize()
                .unwrap_or_else(|_| plugin.located.dir.clone());
            (dir, plugin.commands.clone())
        })
        .collect();
    let mut roots: Vec<PathBuf> = homes.iter().map(|(dir, _)| dir.clone()).collect();
    let config_root = user_dir.and_then(|user_dir| {
        let root = manifest::plugin_config_root(&std::path::absolute(user_dir).ok()?);
        std::fs::create_dir_all(&root).ok()?;
        root.canonicalize().ok()
    });
    if let Some(root) = &config_root {
        for plugin in plugins {
            let name = &plugin.located.manifest.name;
            if manifest::is_directory_name(name) {
                homes.push((root.join(name), plugin.commands.clone()));
            }
        }
        roots.push(root.clone());
    }
    let mut watcher = notify::recommended_watcher(move |event: notify::Result<notify::Event>| {
        let Ok(event) = event else { return };
        if !event.kind.is_modify() && !event.kind.is_create() && !event.kind.is_remove() {
            return;
        }
        for path in &event.paths {
            for (dir, commands) in &homes {
                if is_source_under(path, dir) {
                    let _ = commands.send(Command::Reload);
                }
            }
        }
    })
    .ok()?;
    for dir in &roots {
        if let Err(error) = watcher.watch(dir, RecursiveMode::Recursive) {
            eprintln!("cmd-host: not watching {}: {error}", dir.display());
        }
    }
    Some(watcher)
}

/// Whether `path` is a file under the plugin directory `dir` that its author would edit,
/// as opposed to one Python or uv writes while the plugin runs: anything hidden, under
/// `__pycache__` or named `uv.lock` below `dir` does not count. `dir` itself may sit
/// under a hidden directory, as the per-user plugin directory does on Linux.
fn is_source_under(path: &Path, dir: &Path) -> bool {
    let Ok(below) = path.strip_prefix(dir) else {
        return false;
    };
    !below.components().any(|component| {
        let name = component.as_os_str().to_string_lossy();
        name == "__pycache__" || name == "uv.lock" || name.starts_with('.')
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restarts_wait_longer_each_time_and_forget_after_a_healthy_call() {
        let mut restarts = Restarts::default();
        assert_eq!(restarts.delay(), Duration::ZERO);
        assert_eq!(restarts.record(), 1);
        let first = restarts.delay();
        assert!(
            first > Duration::from_millis(1900) && first <= FIRST_RESTART_DELAY,
            "{first:?}"
        );
        restarts.record();
        assert!(
            restarts.delay() > Duration::from_millis(3900),
            "{:?}",
            restarts.delay()
        );
        for _ in 0..10 {
            restarts.record();
        }
        assert!(restarts.delay() <= LONGEST_RESTART_DELAY);
        restarts.healthy();
        restarts.record();
        assert!(
            restarts.delay() <= FIRST_RESTART_DELAY,
            "the count starts over after a healthy call"
        );
    }

    #[test]
    fn files_python_and_uv_write_while_running_are_not_source() {
        let dir = Path::new("/p");
        assert!(is_source_under(
            Path::new("/p/src/calculator/arithmetic.py"),
            dir
        ));
        assert!(is_source_under(Path::new("/p/cmd-plugin.toml"), dir));
        assert!(!is_source_under(
            Path::new("/p/src/calculator/__pycache__/arithmetic.cpython-315.pyc"),
            dir
        ));
        assert!(!is_source_under(
            Path::new("/p/.venv/lib/python3.15/site-packages/x.py"),
            dir
        ));
        assert!(!is_source_under(
            Path::new("/p/.pytest_cache/v/cache/nodeids"),
            dir
        ));
        assert!(!is_source_under(Path::new("/elsewhere/src/x.py"), dir));
        assert!(!is_source_under(Path::new("/p/uv.lock"), dir));
    }

    #[test]
    fn a_plugin_directory_under_a_hidden_one_is_still_watched() {
        let dir = Path::new("/home/me/.config/cmd/plugins/p");
        assert!(is_source_under(
            Path::new("/home/me/.config/cmd/plugins/p/src/p/__init__.py"),
            dir
        ));
        assert!(!is_source_under(
            Path::new("/home/me/.config/cmd/plugins/p/.venv/bin/python"),
            dir
        ));
    }

    #[test]
    fn a_call_that_hit_the_wire_is_the_process_s_health() {
        assert_eq!(health_of(&Ok(())), Health::Fine);
        assert_eq!(
            health_of::<()>(&Err(CallError::Timeout(Duration::from_secs(1)))),
            Health::TimedOut
        );
        assert_eq!(health_of::<()>(&Err(CallError::Exited)), Health::Gone);
    }
}
