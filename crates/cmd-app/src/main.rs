//! The launcher window.
//!
//! Every key becomes a [`cmd_core::state::Event`]; the state machine answers with a
//! [`cmd_core::state::Step`]; this file performs it. The global chord shows the window,
//! Escape and losing focus hide it. That is the whole shell.

use std::path::PathBuf;
use std::time::{Duration, Instant};

use cmd_core::state::{Event, Launcher, Step};
use cmd_host::{Host, HostEvent, Timeouts, manifest};
use global_hotkey::hotkey::HotKey;
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
use gpui::prelude::*;
use gpui::{
    App, Application, AsyncApp, Bounds, ClipboardItem, Context, FocusHandle, KeyDownEvent, Pixels,
    Render, SharedString, Window, WindowBounds, WindowHandle, WindowKind, WindowOptions, div,
    point, px, rgb, size,
};

const WIDTH: f32 = 680.0;
const HEIGHT: f32 = 420.0;
const PLACEHOLDER: &str = "Search, or type a keyword";
/// Option-Space. Spotlight holds Cmd-Space; `CMD_HOTKEY=super+Space` takes it once Spotlight lets go.
const DEFAULT_HOTKEY: &str = "alt+Space";
/// How long a plugin may keep the person waiting before the window says so.
const PATIENCE: Duration = Duration::from_millis(300);

struct LauncherView {
    state: Launcher,
    host: Host,
    focus: FocusHandle,
    /// Whether the window is meant to be on screen. Losing focus while shown hides it.
    shown: bool,
    /// When the current query was asked, for the waiting line.
    asked_at: Instant,
    /// What went wrong finding and starting plugins, shown under the input on every show
    /// until the person has pressed a key at the window.
    start_trouble: Option<String>,
}

impl LauncherView {
    /// `trouble` is what went wrong while finding and starting plugins. It is shown under
    /// the input until the person has pressed a key here, so a plugin that is missing is
    /// not simply silent, even when a focus loss at launch hid the window before anyone
    /// looked.
    fn new(host: Host, trouble: &[String], window: &mut Window, cx: &mut Context<Self>) -> Self {
        cx.observe_window_activation(window, |view, window, cx| {
            if view.shown && !window.is_window_active() {
                view.hide(cx);
            }
        })
        .detach();
        let start_trouble = (!trouble.is_empty()).then(|| trouble.join("; "));
        let mut state = Launcher::default();
        if let Some(message) = &start_trouble {
            state.apply(Event::Noted(message.clone()));
        }
        Self {
            state,
            host,
            focus: cx.focus_handle(),
            shown: true,
            asked_at: Instant::now(),
            start_trouble,
        }
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
            .name(plugin)
            .unwrap_or_else(|| "a plugin".to_string())
    }

    /// The plugins still owed an answer, by name, once they have kept the person waiting.
    fn waiting_on(&self) -> Option<String> {
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

    /// The chord: bring the window up, or put it away if it is already up.
    fn toggle(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.shown {
            self.hide(cx);
        } else {
            self.show(window, cx);
        }
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

    /// The keyboard model (decision 4): a few keys are the launcher's, the rest is text.
    fn on_key(&mut self, event: &KeyDownEvent, _window: &mut Window, cx: &mut Context<Self>) {
        let keystroke = &event.keystroke;
        let command = keystroke.modifiers.platform;
        let event = match keystroke.key.as_str() {
            "backspace" if command => Some(Event::Clear),
            "backspace" => Some(Event::Backspace),
            "up" => Some(Event::Up),
            "down" => Some(Event::Down),
            "enter" => Some(Event::Submit),
            "escape" => Some(Event::Escape),
            digit @ ("1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9") if command => {
                digit.parse::<usize>().ok().map(|n| Event::Pick(n - 1))
            }
            _ if command || keystroke.modifiers.control => None,
            _ => keystroke.key_char.clone().map(Event::Typed),
        };
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
            Step::Query { generation, text } => {
                let plugins = self.host.query(generation, &text);
                self.asked_at = Instant::now();
                self.state.apply(Event::Asked {
                    generation,
                    plugins,
                });
                // Redraw once the plugins have had their chance, so the waiting line can appear.
                cx.spawn(async move |view, cx| {
                    cx.background_executor().timer(PATIENCE).await;
                    let _ = view.update(cx, |_, cx| cx.notify());
                })
                .detach();
            }
            Step::Run {
                generation,
                plugin,
                item,
                action,
            } => {
                if let Err(error) = self.host.run(generation, plugin, &item, &action) {
                    self.state.apply(Event::Failed {
                        generation,
                        message: error.to_string(),
                    });
                }
            }
            Step::Hide => self.put_away(cx),
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

impl Render for LauncherView {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let empty = self.state.text.is_empty();
        let input: SharedString = if empty {
            PLACEHOLDER.into()
        } else {
            self.state.text.clone().into()
        };
        let selected = self.state.selected;
        div()
            .id("launcher")
            .track_focus(&self.focus)
            .on_key_down(cx.listener(Self::on_key))
            .flex()
            .flex_col()
            .size_full()
            .bg(rgb(0x1c_1c_1e))
            .text_color(rgb(0xf2_f2_f7))
            .rounded_xl()
            .overflow_hidden()
            .child(
                div()
                    .h(px(56.0))
                    .px(px(18.0))
                    .flex()
                    .items_center()
                    .text_xl()
                    .when(empty, |input| input.text_color(rgb(0x8e_8e_93)))
                    .child(input),
            )
            .children(self.state.message.clone().map(|message| {
                div()
                    .px(px(18.0))
                    .pb(px(8.0))
                    .text_sm()
                    .text_color(rgb(0xff_9f_0a))
                    .child(message)
            }))
            .children(self.waiting_on().map(|waiting| {
                div()
                    .px(px(18.0))
                    .pb(px(8.0))
                    .text_sm()
                    .text_color(rgb(0x8e_8e_93))
                    .child(waiting)
            }))
            .children(self.state.hits.iter().enumerate().map(|(index, hit)| {
                div()
                    .px(px(18.0))
                    .py(px(10.0))
                    .flex()
                    .flex_col()
                    .when(index == selected, |row| row.bg(rgb(0x2c_2c_2e)))
                    .child(div().text_base().child(hit.item.title.clone()))
                    .children(hit.item.subtitle.clone().map(|subtitle| {
                        div().text_sm().text_color(rgb(0x8e_8e_93)).child(subtitle)
                    }))
            }))
    }
}

/// Find and start the plugins. Where to look is `manifest::plugin_dirs`'s decision; this
/// only reads the environment. What went wrong comes back beside the host, for the
/// window to show, and goes to stderr for whoever started the app from a terminal.
fn start_host() -> (Host, Vec<String>) {
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
    let (host, start_errors) = Host::start(located, Timeouts::default());
    trouble.extend(start_errors.iter().map(ToString::to_string));
    for message in &trouble {
        eprintln!("cmd: {message}");
    }
    (host, trouble)
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

/// Hand every worker report to the view until the host or the window goes away.
async fn relay_host_events(
    events: async_channel::Receiver<HostEvent>,
    window: WindowHandle<LauncherView>,
    cx: &mut AsyncApp,
) {
    while let Ok(event) = events.recv().await {
        if window
            .update(cx, |view, _, cx| view.on_host_event(event, cx))
            .is_err()
        {
            break;
        }
    }
}

/// Toggle the window on every press until the channel or the window goes away.
async fn show_on_press(
    presses: async_channel::Receiver<()>,
    window: WindowHandle<LauncherView>,
    cx: &mut AsyncApp,
) {
    while presses.recv().await.is_ok() {
        let shown = window.update(cx, LauncherView::toggle);
        if shown.is_err() {
            break;
        }
    }
}

/// Where the launcher sits: centred across the primary display, a third of the way down.
/// Falls back to the centre of the screen when no display is reported.
fn launcher_bounds(cx: &App) -> Bounds<Pixels> {
    let size = size(px(WIDTH), px(HEIGHT));
    match cx.primary_display() {
        Some(display) => {
            let screen = display.bounds();
            Bounds {
                origin: point(
                    screen.origin.x + (screen.size.width - size.width) / 2.0,
                    screen.origin.y + screen.size.height / 3.0 - size.height / 2.0,
                ),
                size,
            }
        }
        None => Bounds::centered(None, size, cx),
    }
}

fn main() {
    let (host, trouble) = start_host();
    let events = host.events();
    let (notify, presses) = async_channel::bounded(1);
    let _hotkey = register_hotkey(notify);
    Application::new().run(move |cx: &mut App| {
        let bounds = launcher_bounds(cx);
        let options = WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(bounds)),
            titlebar: None,
            kind: WindowKind::PopUp,
            is_movable: false,
            is_resizable: false,
            is_minimizable: false,
            ..Default::default()
        };
        let window = cx
            .open_window(options, |window, cx| {
                let view = cx.new(|cx| LauncherView::new(host, &trouble, window, cx));
                let focus = view.read(cx).focus.clone();
                window.focus(&focus);
                view
            })
            .expect("the launcher window opens");
        cx.spawn(async move |cx| show_on_press(presses, window, cx).await)
            .detach();
        cx.spawn(async move |cx| relay_host_events(events, window, cx).await)
            .detach();
        cx.activate(true);
    });
}
