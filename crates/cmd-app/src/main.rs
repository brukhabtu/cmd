//! The launcher window.
//!
//! Every key the launcher owns becomes a [`cmd_core::state::Event`]; the state machine
//! answers with a [`cmd_core::state::Step`]; this file performs it. Text does not come
//! from the key handler: typing, dead keys and input-method composition reach the state
//! machine through GPUI's input handler, installed by the query line in `input.rs`. The
//! global chord shows the window, Escape and losing focus hide it. That is the whole shell.
//! The window is opened again on the display under the pointer when that has changed; the
//! view, with the host and the state, outlives it.

mod displays;
mod icons;
mod input;

use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

use cmd_core::input::Motion;
use cmd_core::placement::{self, Placement};
use cmd_core::query::Hit;
use cmd_core::state::{Event, Launcher, Step};
use cmd_host::{Bundle, Host, HostEvent, Located, Startup, Timeouts, bundle, manifest};
use global_hotkey::hotkey::HotKey;
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
use gpui::prelude::*;
use gpui::{
    App, Application, AsyncApp, Bounds, ClipboardItem, Context, DisplayId, Div, Entity,
    FocusHandle, Global, KeyDownEvent, Keystroke, Pixels, Render, RenderImage, Rgba, ShapedLine,
    Window, WindowAppearance, WindowBackgroundAppearance, WindowBounds, WindowHandle, WindowKind,
    WindowOptions, div, img, point, px, rgb, rgba, size,
};
use input::InputElement;

const WIDTH: f32 = 680.0;
const HEIGHT: f32 = 420.0;
const INPUT_HEIGHT: f32 = 56.0;
/// The status line keeps its height whether or not it has anything to say, so the number
/// of rows under it never changes.
const STATUS_HEIGHT: f32 = 24.0;
const ROW_HEIGHT: f32 = 48.0;
/// How many result rows fit under the input and the status line. The state machine keeps
/// the selection inside this window onto the list, so no scroll container is needed.
const VISIBLE_ROWS: usize = 7;
// The window is a fixed size, so the compiler, not the eye, checks that the rows fit.
// The cast is of a one-digit constant; nothing is lost.
#[allow(clippy::cast_precision_loss)]
const _: () = assert!(INPUT_HEIGHT + STATUS_HEIGHT + VISIBLE_ROWS as f32 * ROW_HEIGHT <= HEIGHT);
const PLACEHOLDER: &str = "Search, or type a keyword";
/// Option-Space. Spotlight holds Cmd-Space; `CMD_HOTKEY=super+Space` takes it once Spotlight lets go.
const DEFAULT_HOTKEY: &str = "alt+Space";
/// How long a plugin may keep the person waiting before the window says so.
const PATIENCE: Duration = Duration::from_millis(300);
/// Stands first in the starting list while uv fetches the plugins' Python, so the line needs
/// no state of its own. Only a manifest that spelt out a NUL in its name could clash.
const FETCHING_PYTHON: &str = "\0python";

/// The colours for one appearance. The tints are translucent so the blur behind the
/// window shows through them.
struct Palette {
    tint: Rgba,
    text: Rgba,
    muted: Rgba,
    selected: Rgba,
    warning: Rgba,
}

/// The palette that suits the system appearance; the vibrant variants read the same way.
fn palette(appearance: WindowAppearance) -> Palette {
    match appearance {
        WindowAppearance::Dark | WindowAppearance::VibrantDark => Palette {
            tint: rgba(0x1c_1c_1e_d9),
            text: rgb(0xf2_f2_f7),
            muted: rgb(0x8e_8e_93),
            selected: rgba(0xff_ff_ff_1f),
            warning: rgb(0xff_9f_0a),
        },
        WindowAppearance::Light | WindowAppearance::VibrantLight => Palette {
            tint: rgba(0xf5_f5_f7_d9),
            text: rgb(0x1d_1d_1f),
            muted: rgb(0x6e_6e_73),
            selected: rgba(0x00_00_00_14),
            warning: rgb(0xc9_3c_00),
        },
    }
}

/// What the start-up thread tells the window: a report as each plugin comes up or fails,
/// then the host itself, last.
enum Starting {
    Report(Startup),
    Ready(Host),
}

struct LauncherView {
    state: Launcher,
    /// `None` until the start-up thread hands the host over; the window is up long before.
    host: Option<Host>,
    /// The plugins found but not yet up or refused, by manifest name, for the line under
    /// the input on a first launch, when uv may still be fetching Python.
    starting: Vec<String>,
    focus: FocusHandle,
    /// Whether the window is meant to be on screen. Losing focus while shown hides it.
    shown: bool,
    /// When the current query was asked, for the waiting line.
    asked_at: Instant,
    /// What went wrong finding and starting plugins, shown under the input on every show
    /// until the person has pressed a key at the window.
    start_trouble: Option<String>,
    /// The query line as last drawn and where, for the input method to place its
    /// candidates. The text itself is the state machine's.
    last_line: Option<ShapedLine>,
    last_bounds: Option<Bounds<Pixels>>,
}

impl LauncherView {
    /// `starting` names the plugins found, which come up later on the start-up thread.
    /// `trouble` is what went wrong while finding them. It is shown under the input until
    /// the person has pressed a key here, so a plugin that is missing is not simply
    /// silent, even when a focus loss at launch hid the window before anyone looked.
    /// The view belongs to no window: [`LauncherView::attach`] joins it to each one.
    fn new(starting: Vec<String>, trouble: &[String], cx: &mut Context<Self>) -> Self {
        let start_trouble = (!trouble.is_empty()).then(|| trouble.join("; "));
        let mut state = Launcher::new(VISIBLE_ROWS);
        if let Some(message) = &start_trouble {
            state.apply(Event::Noted(message.clone()));
        }
        Self {
            state,
            host: None,
            starting,
            focus: cx.focus_handle(),
            shown: true,
            asked_at: Instant::now(),
            start_trouble,
            last_line: None,
            last_bounds: None,
        }
    }

    /// Join the view to a newly opened window. The observers live in the window and go
    /// with it, so a window opened again on another display gets its own.
    fn attach(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        cx.observe_window_activation(window, |view, window, cx| {
            if view.shown && !window.is_window_active() {
                view.hide(cx);
            }
        })
        .detach();
        // The palette is read on every draw, so a switch between light and dark only
        // needs a redraw.
        cx.observe_window_appearance(window, |_, _, cx| cx.notify())
            .detach();
        window.focus(&self.focus);
    }

    /// The start-up thread said something. A plugin that could not be started joins the
    /// start trouble, so it is shown at once and again on every show until a key is
    /// pressed, as one missing at discovery is. Text typed while the plugins were starting
    /// is asked once the host is here, so nobody has to type it again.
    fn on_startup(&mut self, starting: Starting, cx: &mut Context<Self>) {
        match starting {
            Starting::Report(Startup::Up { name, .. }) => self.started(&name),
            Starting::Report(Startup::FetchingPython) => {
                self.starting.insert(0, FETCHING_PYTHON.to_string());
            }
            Starting::Report(Startup::FetchedPython(fetched)) => {
                self.started(FETCHING_PYTHON);
                if let Err(message) = fetched {
                    self.note_trouble(message);
                }
            }
            Starting::Report(Startup::Failed(error)) => {
                self.started(error.name());
                self.note_trouble(error.to_string());
            }
            Starting::Ready(host) => {
                self.host = Some(host);
                // Every plugin has been reported by now; nothing is left starting.
                self.starting.clear();
                if !self.state.text().trim().is_empty() {
                    let text = self.state.text().to_string();
                    self.ask(self.state.generation, &text, cx);
                }
            }
        }
        cx.notify();
    }

    /// Strike one plugin off the starting line. Only the first entry goes, so a second
    /// directory declaring the same name stays listed until its own report.
    fn started(&mut self, name: &str) {
        if let Some(position) = self.starting.iter().position(|starting| starting == name) {
            self.starting.remove(position);
        }
    }

    fn note_trouble(&mut self, message: String) {
        let trouble = match self.start_trouble.take() {
            Some(earlier) => format!("{earlier}; {message}"),
            None => message,
        };
        self.state.apply(Event::Noted(trouble.clone()));
        self.start_trouble = Some(trouble);
    }

    /// Hand the text to the plugins it reaches, and redraw once they have had their
    /// chance, so the waiting line can appear.
    fn ask(&mut self, generation: u64, text: &str, cx: &mut Context<Self>) {
        let plugins = self
            .host
            .as_ref()
            .map(|host| host.query(generation, text))
            .unwrap_or_default();
        self.asked_at = Instant::now();
        self.state.apply(Event::Asked {
            generation,
            plugins,
        });
        cx.spawn(async move |view, cx| {
            cx.background_executor().timer(PATIENCE).await;
            let _ = view.update(cx, |_, cx| cx.notify());
        })
        .detach();
    }

    /// A worker answered or ran something; the state machine decides what it means.
    /// Errors get the plugin's name here, and only here.
    fn on_host_event(&mut self, event: HostEvent, cx: &mut Context<Self>) {
        let event = match event {
            HostEvent::Answered {
                generation,
                plugin,
                result: Ok(items),
            } => Event::Answered {
                generation,
                plugin,
                items,
            },
            HostEvent::Answered {
                generation,
                plugin,
                result: Err(error),
            } => Event::Unanswered {
                generation,
                plugin,
                error: format!("{}: {error}", self.plugin_name(plugin)),
            },
            HostEvent::Ran {
                generation,
                result: Ok(effect),
                ..
            } => Event::Ran { generation, effect },
            HostEvent::Ran {
                generation,
                plugin,
                result: Err(error),
            } => Event::Failed {
                generation,
                message: format!("{}: {error}", self.plugin_name(plugin)),
            },
            HostEvent::Restarted { plugin, attempt } => Event::Noted(format!(
                "{} started again (restart {attempt})",
                self.plugin_name(plugin)
            )),
            HostEvent::Trouble { plugin, message } => {
                Event::Noted(format!("{}: {message}", self.plugin_name(plugin)))
            }
            HostEvent::Reloaded { plugin } => {
                Event::Noted(format!("{} reloaded", self.plugin_name(plugin)))
            }
        };
        self.handle(event, cx);
    }

    fn plugin_name(&self, plugin: usize) -> String {
        self.host
            .as_ref()
            .and_then(|host| host.name(plugin))
            .unwrap_or_else(|| "a plugin".to_string())
    }

    /// The plugins still starting, or else those still owed an answer once they have kept
    /// the person waiting, by name.
    fn waiting_on(&self) -> Option<String> {
        if !self.starting.is_empty() {
            return Some(starting_line(&self.starting));
        }
        if self.state.pending.is_empty() || self.asked_at.elapsed() < PATIENCE {
            return None;
        }
        let names: Vec<String> = self
            .state
            .pending
            .iter()
            .map(|plugin| self.plugin_name(*plugin))
            .collect();
        Some(format!("waiting on {}", names.join(", ")))
    }

    /// Bring the window up with an empty, focused input, and the start trouble under it
    /// while that is still unseen.
    fn show(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.shown = true;
        if let Some(message) = &self.start_trouble {
            self.state.apply(Event::Noted(message.clone()));
        }
        cx.activate(true);
        window.activate_window();
        window.focus(&self.focus);
        cx.notify();
    }

    /// Put the window away. The state resets, so the next show starts empty.
    fn hide(&mut self, cx: &mut Context<Self>) {
        self.shown = false;
        let step = self.state.apply(Event::Escape);
        debug_assert_eq!(step, Step::Hide);
        cx.hide();
        cx.notify();
    }

    /// The keyboard model (decision 4), as [`key`] reads it. Text is not read here: a key
    /// left alone goes on to the input method, which delivers its character through the
    /// input handler. Every key taken here stops propagation, or macOS would hand it to
    /// the input method as well.
    fn on_key(&mut self, event: &KeyDownEvent, _window: &mut Window, cx: &mut Context<Self>) {
        let event = match key(&event.keystroke) {
            Key::Text => return,
            Key::Dropped => None,
            // A pasteboard without text (an image, say) pastes nothing.
            Key::Paste => cx
                .read_from_clipboard()
                .and_then(|item| item.text())
                .map(Event::Paste),
            Key::Owned(event) => Some(event),
        };
        cx.stop_propagation();
        if let Some(event) = event {
            // A key pressed here means the person has seen what was under the input.
            self.start_trouble = None;
            self.handle(event, cx);
        }
    }

    fn handle(&mut self, event: Event, cx: &mut Context<Self>) {
        let step = self.state.apply(event);
        self.perform(step, cx);
        cx.notify();
    }

    fn perform(&mut self, step: Step, cx: &mut Context<Self>) {
        match step {
            // Before the host is here nobody is asked, and the text is asked again when it
            // arrives (see `on_startup`).
            Step::Query { generation, text } => self.ask(generation, &text, cx),
            Step::Run {
                generation,
                plugin,
                item,
                action,
            } => {
                // Without a host there are no hits to run, so this keeps the match total.
                let ran = match &self.host {
                    Some(host) => host
                        .run(generation, plugin, &item, &action)
                        .map_err(|error| error.to_string()),
                    None => Err("the plugins are still starting".to_string()),
                };
                if let Err(message) = ran {
                    self.state.apply(Event::Failed {
                        generation,
                        message,
                    });
                }
            }
            Step::Hide => self.put_away(cx),
            Step::Copy(text) => cx.write_to_clipboard(ClipboardItem::new_string(text)),
            Step::CopyAndHide(text) => {
                cx.write_to_clipboard(ClipboardItem::new_string(text));
                self.put_away(cx);
            }
            Step::OpenAndHide(target) => {
                cx.open_url(&target);
                self.put_away(cx);
            }
            Step::Nothing => {}
        }
    }

    /// The state machine already reset itself; only the window is left to hide.
    fn put_away(&mut self, cx: &mut Context<Self>) {
        self.shown = false;
        cx.hide();
    }
}

/// What the launcher does with a key.
#[derive(Debug, PartialEq)]
enum Key {
    /// One of the launcher's own keys.
    Owned(Event),
    /// Cmd-V: the pasteboard's text, which only the caller can read.
    Paste,
    /// A Cmd or Control chord the launcher does not own: taken, and not typed.
    Dropped,
    /// Text, left for the input method to deliver through the input handler.
    Text,
}

/// The keyboard model (decision 4): a few keys are the launcher's, the rest is text.
/// Option is text except with Backspace and the arrows, where it means a word.
fn key(keystroke: &Keystroke) -> Key {
    let command = keystroke.modifiers.platform;
    let option = keystroke.modifiers.alt;
    let shift = keystroke.modifiers.shift;
    let event = match keystroke.key.as_str() {
        "backspace" if command => Event::Delete(Motion::LineStart),
        "backspace" if option => Event::Delete(Motion::PreviousWord),
        "backspace" => Event::Delete(Motion::PreviousGrapheme),
        "left" | "right" => {
            let motion = match (keystroke.key == "left", command, option) {
                (true, true, _) => Motion::LineStart,
                (false, true, _) => Motion::LineEnd,
                (true, false, true) => Motion::PreviousWord,
                (false, false, true) => Motion::NextWord,
                (true, false, false) => Motion::PreviousGrapheme,
                (false, false, false) => Motion::NextGrapheme,
            };
            Event::Move {
                motion,
                extend: shift,
            }
        }
        "a" if command => Event::SelectAll,
        "c" if command => Event::Copy,
        "v" if command => return Key::Paste,
        "up" => Event::Up,
        "down" => Event::Down,
        "enter" => Event::Submit,
        "escape" => Event::Escape,
        digit @ ("1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9") if command => {
            match digit.parse::<usize>() {
                Ok(n) => Event::Pick(n - 1),
                Err(_) => return Key::Dropped,
            }
        }
        _ if command || keystroke.modifiers.control => return Key::Dropped,
        _ => return Key::Text,
    };
    Key::Owned(event)
}

/// The query line. What it shows is the state machine's; see `input.rs`.
fn input_row(view: Entity<LauncherView>, palette: &Palette) -> Div {
    div()
        .h(px(INPUT_HEIGHT))
        .px(px(18.0))
        .flex()
        .items_center()
        .text_xl()
        .child(InputElement {
            view,
            muted: palette.muted.into(),
        })
}

/// A message from a plugin or the host wins over the waiting line; both are under the
/// input, and the strip stays the same height when there is nothing to say.
fn status_line(message: Option<String>, waiting: Option<String>, palette: &Palette) -> Div {
    let line = match (message, waiting) {
        (Some(message), _) => Some((message, palette.warning)),
        (None, Some(waiting)) => Some((waiting, palette.muted)),
        (None, None) => None,
    };
    div()
        .h(px(STATUS_HEIGHT))
        .px(px(18.0))
        .flex()
        .items_center()
        .text_sm()
        .children(line.map(|(text, colour)| div().truncate().text_color(colour).child(text)))
}

/// One result: an icon slot, title over subtitle, highlighted when selected, with the
/// Cmd-number that runs it at the right. `position` counts from the first row on screen,
/// which is what Cmd-number counts (decision 4). The slot is laid out only when some row
/// on screen has an icon, so a list without icons looks as it did, and it stays empty
/// while an icon loads or when nothing resolved, so the titles line up.
fn result_row(
    hit: &Hit,
    selected: bool,
    position: usize,
    icon: Option<Arc<RenderImage>>,
    slot: bool,
    palette: &Palette,
) -> Div {
    let slot = slot.then(|| {
        div()
            .size(px(icons::SIZE))
            .flex_shrink_0()
            .mr(px(10.0))
            .children(icon.map(|image| img(image).size(px(icons::SIZE))))
    });
    let text = div()
        .flex_1()
        .flex()
        .flex_col()
        .overflow_hidden()
        .child(div().text_base().truncate().child(hit.item.title.clone()))
        .children(hit.item.subtitle.clone().map(|subtitle| {
            div()
                .text_sm()
                .truncate()
                .text_color(palette.muted)
                .child(subtitle)
        }));
    let shortcut = (position < 9).then(|| {
        div()
            .pl(px(12.0))
            .text_sm()
            .text_color(palette.muted)
            .child(format!("\u{2318}{}", position + 1))
    });
    div()
        .h(px(ROW_HEIGHT))
        .mx(px(8.0))
        .px(px(10.0))
        .flex()
        .items_center()
        .rounded_lg()
        .when(selected, |row| row.bg(palette.selected))
        .children(slot)
        .child(text)
        .children(shortcut)
}

impl Render for LauncherView {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let palette = palette(window.appearance());
        let selected = self.state.selected;
        let first_visible = self.state.first_visible;
        let visible = self.state.visible();
        let slot = visible.iter().any(|hit| hit.item.icon.is_some());
        div()
            .id("launcher")
            .track_focus(&self.focus)
            .on_key_down(cx.listener(Self::on_key))
            .flex()
            .flex_col()
            .size_full()
            .bg(palette.tint)
            .text_color(palette.text)
            .rounded_2xl()
            .overflow_hidden()
            .child(input_row(cx.entity(), &palette))
            .child(status_line(
                self.state.message.clone(),
                self.waiting_on(),
                &palette,
            ))
            .children(visible.iter().enumerate().map(|(position, hit)| {
                // The cache answers at once after the first draw; until then the slot is
                // empty and the view is redrawn when the icon is ready.
                let icon = hit.item.icon.as_ref().and_then(|icon| {
                    window
                        .use_asset::<icons::IconAsset>(&icons::Request::new(icon, palette.text), cx)
                        .flatten()
                });
                result_row(
                    hit,
                    first_visible + position == selected,
                    position,
                    icon,
                    slot,
                    &palette,
                )
            }))
    }
}

/// Find the plugins, which only reads directories and is quick enough for the main thread.
/// Where to look is `manifest::plugin_dirs`'s decision; this only reads the environment.
/// What went wrong comes back beside them, for the window to show, and goes to stderr for
/// whoever started the app from a terminal.
fn locate_plugins() -> (Vec<Located>, Vec<String>) {
    let env = std::env::var("CMD_PLUGINS").ok();
    let home = std::env::var_os("HOME").map(PathBuf::from);
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let dirs = manifest::plugin_dirs(env.as_deref(), home.as_deref(), &cwd);
    let (located, load_errors) = manifest::discover_all(&dirs);
    let mut trouble: Vec<String> = load_errors.iter().map(ToString::to_string).collect();
    if located.is_empty() {
        let looked = dirs
            .iter()
            .map(|dir| dir.display().to_string())
            .collect::<Vec<_>>()
            .join(", ");
        trouble.push(format!("no plugins found in {looked}"));
    }
    for message in &trouble {
        eprintln!("cmd: {message}");
    }
    (located, trouble)
}

/// The line under the input while the plugins start: uv fetching their Python comes first,
/// on a first launch inside cmd.app, and says so, since it is the long wait.
fn starting_line(starting: &[String]) -> String {
    match starting.split_first() {
        Some((first, [])) if first == FETCHING_PYTHON => {
            format!("fetching Python {}", bundle::PYTHON)
        }
        Some((first, rest)) if first == FETCHING_PYTHON => format!(
            "fetching Python {}, then starting {}",
            bundle::PYTHON,
            rest.join(", ")
        ),
        _ => format!("starting {}", starting.join(", ")),
    }
}

/// The cmd.app this binary runs from, if any. The path is made canonical first: the
/// cask links the binary from outside the bundle, and the link would hide it.
fn running_bundle() -> Option<Bundle> {
    let exe = std::env::current_exe()
        .and_then(|exe| exe.canonicalize())
        .ok()?;
    let home = std::env::var_os("HOME")?;
    Bundle::detect(&exe, Path::new(&home))
}

/// Start the plugins on a thread of their own, beside the window: each handshake can
/// take up to the describe timeout, and on a first launch uv may be fetching Python
/// (decision 7). Each plugin is reported as it comes up or fails, and the host follows
/// last. A plain thread rather than the background executor, whose shared pool should
/// not be held for a minute by blocking calls.
fn start_host_beside(located: Vec<Located>, reports: async_channel::Sender<Starting>) {
    let started = thread::Builder::new()
        .name("cmd-startup".to_string())
        .spawn(move || {
            // Inside cmd.app the bundle's uv fetches Python here, before the first plugin.
            let app = running_bundle();
            let path = std::env::var_os("PATH");
            let user_dir =
                std::env::var_os("HOME").map(|home| manifest::user_cmd_dir(Path::new(&home)));
            let host = bundle::start_reporting(
                app.as_ref(),
                path.as_deref(),
                user_dir.as_deref(),
                located,
                Timeouts::default(),
                |report| {
                    match &report {
                        Startup::Failed(error) => eprintln!("cmd: {error}"),
                        Startup::FetchedPython(Err(message)) => eprintln!("cmd: {message}"),
                        Startup::Up { .. }
                        | Startup::FetchingPython
                        | Startup::FetchedPython(Ok(())) => {}
                    }
                    let _ = reports.send_blocking(Starting::Report(report));
                },
            );
            let _ = reports.send_blocking(Starting::Ready(host));
        });
    // Without this thread the window would say "starting" forever; like a window that
    // will not open, there is nothing to carry on with.
    started.expect("the start-up thread starts");
}

/// Register the chord and hand each press to `presses`. Returns the manager, which must
/// outlive the app: dropping it unregisters the chord.
fn register_hotkey(presses: async_channel::Sender<()>) -> Option<GlobalHotKeyManager> {
    let chord = std::env::var("CMD_HOTKEY").unwrap_or_else(|_| DEFAULT_HOTKEY.to_string());
    let hotkey: HotKey = match chord.parse() {
        Ok(hotkey) => hotkey,
        Err(error) => {
            eprintln!(
                "cmd: CMD_HOTKEY {chord:?} is not a chord ({error}); running without a hotkey"
            );
            return None;
        }
    };
    let manager = match GlobalHotKeyManager::new()
        .and_then(|manager| manager.register(hotkey).map(|()| manager))
    {
        Ok(manager) => manager,
        Err(error) => {
            eprintln!("cmd: could not register {chord}: {error}; running without a hotkey");
            return None;
        }
    };
    GlobalHotKeyEvent::set_event_handler(Some(move |event: GlobalHotKeyEvent| {
        if matches!(event.state(), HotKeyState::Pressed) {
            // A full channel means a press is already waiting; one show is enough.
            let _ = presses.try_send(());
        }
    }));
    Some(manager)
}

/// Hand every worker report to the view until the host or the app goes away. The view,
/// not a window, is the receiver, so a window opened again never cuts the host off.
async fn relay_host_events(
    events: async_channel::Receiver<HostEvent>,
    view: Entity<LauncherView>,
    cx: &mut AsyncApp,
) {
    while let Ok(event) = events.recv().await {
        if view
            .update(cx, |view, cx| view.on_host_event(event, cx))
            .is_err()
        {
            break;
        }
    }
}

/// Hand each start-up report to the view and, once the host arrives, relay its events
/// for as long as both last.
async fn bring_up_host(
    progress: async_channel::Receiver<Starting>,
    view: Entity<LauncherView>,
    cx: &mut AsyncApp,
) {
    while let Ok(starting) = progress.recv().await {
        // The receiver is taken before the host moves into the view; a clone of it
        // hears every worker.
        let events = match &starting {
            Starting::Ready(host) => Some(host.events()),
            Starting::Report(_) => None,
        };
        if view
            .update(cx, |view, cx| view.on_startup(starting, cx))
            .is_err()
        {
            return;
        }
        if let Some(events) = events {
            relay_host_events(events, view, cx).await;
            return;
        }
    }
}

/// Answer every press until the channel or the app goes away.
async fn show_on_press(presses: async_channel::Receiver<()>, cx: &mut AsyncApp) {
    while presses.recv().await.is_ok() {
        if cx.update(reveal).is_err() {
            break;
        }
    }
}

/// The view, which lives as long as the app, and the window it is in now, which is
/// replaced when the launcher moves to another display.
#[derive(Clone)]
struct Shell {
    view: Entity<LauncherView>,
    window: WindowHandle<LauncherView>,
}

impl Global for Shell {}

/// Where the launcher goes now (`cmd_core::placement` decides), with the display as GPUI
/// names it. `None` when no display is reported.
fn launcher_placement(cx: &App) -> Option<(DisplayId, Placement)> {
    let seen = displays::look(cx);
    let window = placement::Size {
        width: WIDTH,
        height: HEIGHT,
    };
    let placed = placement::place(&seen.displays, seen.pointer, seen.primary, window)?;
    let id = cx
        .displays()
        .iter()
        .map(|display| display.id())
        .find(|id| u32::from(*id) == placed.display)?;
    Some((id, placed))
}

/// Open the launcher's window on the given display, or centred on the screen when there
/// is none, and join the view to it. GPUI 0.2.2 cannot move an open window, so this is
/// also how the launcher changes display. `None` when the window would not open.
fn open_launcher(
    view: &Entity<LauncherView>,
    at: Option<(DisplayId, Placement)>,
    cx: &mut App,
) -> Option<WindowHandle<LauncherView>> {
    let size = size(px(WIDTH), px(HEIGHT));
    let (display_id, bounds) = match at {
        // The origin is relative to that display's top-left, as GPUI places it.
        Some((id, placed)) => (
            Some(id),
            Bounds {
                origin: point(px(placed.origin.x), px(placed.origin.y)),
                size,
            },
        ),
        None => (None, Bounds::centered(None, size, cx)),
    };
    // Blurred makes the NSWindow transparent with a vibrancy view beneath the content,
    // so the rounded, tinted root is the window's whole shape.
    let options = WindowOptions {
        window_bounds: Some(WindowBounds::Windowed(bounds)),
        display_id,
        titlebar: None,
        kind: WindowKind::PopUp,
        is_movable: false,
        is_resizable: false,
        is_minimizable: false,
        window_background: WindowBackgroundAppearance::Blurred,
        ..Default::default()
    };
    let view = view.clone();
    cx.open_window(options, move |window, cx| {
        view.update(cx, |view, cx| view.attach(window, cx));
        view
    })
    .map_err(|error| eprintln!("cmd: the launcher window would not open: {error}"))
    .ok()
}

/// The chord: put the launcher away if it is up; otherwise bring it up on the display
/// under the pointer, worked out afresh on every press so a moved pointer or a changed
/// arrangement is followed. The window is opened again only when it is not already there.
fn reveal(cx: &mut App) {
    let Some(shell) = cx.try_global::<Shell>().cloned() else {
        return;
    };
    if shell.view.read(cx).shown {
        shell.view.update(cx, LauncherView::hide);
        return;
    }
    let target = launcher_placement(cx);
    let here = shell.window.update(cx, |_, window, cx| {
        let origin = window.bounds().origin;
        (
            window.display(cx).map(|display| u32::from(display.id())),
            placement::Point {
                x: f32::from(origin.x),
                y: f32::from(origin.y),
            },
        )
    });
    let stays = match (here, &target) {
        (Ok((display, origin)), Some((_, placed))) => placed.matches(display, origin),
        // With no display to place on, the window stays where it is.
        (Ok(_), None) => true,
        (Err(_), _) => false,
    };
    let window = if stays {
        shell.window
    } else {
        let _ = shell
            .window
            .update(cx, |_, window, _| window.remove_window());
        let Some(window) = open_launcher(&shell.view, target, cx) else {
            return;
        };
        cx.set_global(Shell {
            view: shell.view.clone(),
            window,
        });
        window
    };
    let _ = window.update(cx, LauncherView::show);
}

/// Make the app an accessory: no Dock icon and no menu bar. The bundle's `LSUIElement` says
/// the same, but GPUI sets the regular policy as it finishes launching, just before it
/// calls the `run` closure, which overrides the plist; so this runs first in that closure.
/// The `PopUp` panel, a non-activating `NSPanel`, still takes the keyboard.
#[cfg(target_os = "macos")]
fn become_accessory() {
    use objc2::MainThreadMarker;
    use objc2_app_kit::{NSApplication, NSApplicationActivationPolicy};
    let Some(mtm) = MainThreadMarker::new() else {
        eprintln!("cmd: not on the main thread; the Dock icon stays");
        return;
    };
    let app = NSApplication::sharedApplication(mtm);
    if !app.setActivationPolicy(NSApplicationActivationPolicy::Accessory) {
        eprintln!("cmd: AppKit refused the accessory policy; the Dock icon stays");
    }
}

/// Elsewhere there is no Dock to leave.
#[cfg(not(target_os = "macos"))]
fn become_accessory() {}

/// `cmd plugin ...` is answered here, before the host, the hotkey or the GPUI
/// application exist, so a subcommand never opens the launcher (decision 8).
fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.first().map(String::as_str) == Some("plugin") {
        return cmd_host::cli::run(&args[1..], &cmd_host::cli::Env::from_process());
    }
    let (located, trouble) = locate_plugins();
    let names: Vec<String> = located
        .iter()
        .map(|located| located.manifest.name.clone())
        .collect();
    let (notify, presses) = async_channel::bounded(1);
    let _hotkey = register_hotkey(notify);
    Application::new().run(move |cx: &mut App| {
        become_accessory();
        let view = cx.new(|cx| LauncherView::new(names, &trouble, cx));
        let at = launcher_placement(cx);
        let window = open_launcher(&view, at, cx).expect("the launcher window opens");
        cx.set_global(Shell {
            view: view.clone(),
            window,
        });
        // Only now, with the window open, does the first handshake begin.
        let (reports, progress) = async_channel::unbounded();
        start_host_beside(located, reports);
        cx.spawn(async move |cx| show_on_press(presses, cx).await)
            .detach();
        cx.spawn(async move |cx| bring_up_host(progress, view, cx).await)
            .detach();
        cx.activate(true);
    });
    ExitCode::SUCCESS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_starting_line_says_python_is_being_fetched_before_the_plugins() {
        let names = |names: &[&str]| names.iter().map(ToString::to_string).collect::<Vec<_>>();
        assert_eq!(
            starting_line(&names(&[FETCHING_PYTHON, "applications", "calculator"])),
            "fetching Python 3.15, then starting applications, calculator"
        );
        assert_eq!(
            starting_line(&names(&[FETCHING_PYTHON])),
            "fetching Python 3.15"
        );
        assert_eq!(
            starting_line(&names(&["applications", "calculator"])),
            "starting applications, calculator"
        );
    }

    fn pressed(source: &str) -> Key {
        key(&Keystroke::parse(source).expect("a keystroke"))
    }

    fn moved(motion: Motion, extend: bool) -> Key {
        Key::Owned(Event::Move { motion, extend })
    }

    #[test]
    fn backspace_deletes_a_grapheme_a_word_or_to_the_start() {
        assert_eq!(
            pressed("backspace"),
            Key::Owned(Event::Delete(Motion::PreviousGrapheme))
        );
        assert_eq!(
            pressed("alt-backspace"),
            Key::Owned(Event::Delete(Motion::PreviousWord))
        );
        assert_eq!(
            pressed("cmd-backspace"),
            Key::Owned(Event::Delete(Motion::LineStart))
        );
    }

    #[test]
    fn the_arrows_move_by_grapheme_word_or_line_and_shift_extends() {
        assert_eq!(pressed("left"), moved(Motion::PreviousGrapheme, false));
        assert_eq!(pressed("right"), moved(Motion::NextGrapheme, false));
        assert_eq!(pressed("shift-left"), moved(Motion::PreviousGrapheme, true));
        assert_eq!(pressed("alt-left"), moved(Motion::PreviousWord, false));
        assert_eq!(pressed("alt-shift-right"), moved(Motion::NextWord, true));
        assert_eq!(pressed("cmd-left"), moved(Motion::LineStart, false));
        assert_eq!(pressed("cmd-shift-right"), moved(Motion::LineEnd, true));
    }

    #[test]
    fn the_editing_chords_select_copy_and_paste() {
        assert_eq!(pressed("cmd-a"), Key::Owned(Event::SelectAll));
        assert_eq!(pressed("cmd-c"), Key::Owned(Event::Copy));
        assert_eq!(pressed("cmd-v"), Key::Paste);
    }

    #[test]
    fn the_launcher_keys_are_unchanged() {
        assert_eq!(pressed("up"), Key::Owned(Event::Up));
        assert_eq!(pressed("cmd-down"), Key::Owned(Event::Down));
        assert_eq!(pressed("enter"), Key::Owned(Event::Submit));
        assert_eq!(pressed("escape"), Key::Owned(Event::Escape));
        assert_eq!(pressed("cmd-3"), Key::Owned(Event::Pick(2)));
    }

    #[test]
    fn characters_are_left_for_the_input_method_and_other_chords_are_dropped() {
        assert_eq!(pressed("a"), Key::Text);
        assert_eq!(pressed("shift-a"), Key::Text);
        assert_eq!(pressed("alt-e"), Key::Text, "Option-E starts a dead key");
        assert_eq!(pressed("3"), Key::Text);
        assert_eq!(pressed("cmd-k"), Key::Dropped);
        assert_eq!(pressed("ctrl-a"), Key::Dropped);
    }
}
