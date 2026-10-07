//! The launcher window.
//!
//! Every key becomes a [`cmd_core::state::Event`]; the state machine answers with a
//! [`cmd_core::state::Step`]; this file performs it. The global chord shows the window,
//! Escape and losing focus hide it. That is the whole shell.

mod icons;

use std::path::PathBuf;
use std::process::ExitCode;
use std::sync::Arc;
use std::time::{Duration, Instant};

use cmd_core::query::Hit;
use cmd_core::state::{Event, Launcher, Step};
use cmd_host::{Host, HostEvent, Timeouts, manifest};
use global_hotkey::hotkey::HotKey;
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
use gpui::prelude::*;
use gpui::{
    App, Application, AsyncApp, Bounds, ClipboardItem, Context, Div, FocusHandle, KeyDownEvent,
    Pixels, Render, RenderImage, Rgba, SharedString, Window, WindowAppearance,
    WindowBackgroundAppearance, WindowBounds, WindowHandle, WindowKind, WindowOptions, div, img,
    point, px, rgb, rgba, size,
};

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
        // The palette is read on every draw, so a switch between light and dark only
        // needs a redraw.
        cx.observe_window_appearance(window, |_, _, cx| cx.notify())
            .detach();
        let start_trouble = (!trouble.is_empty()).then(|| trouble.join("; "));
        let mut state = Launcher::new(VISIBLE_ROWS);
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

/// The text typed so far, or the placeholder in the muted colour while there is none.
fn input_row(text: &str, palette: &Palette) -> Div {
    let empty = text.is_empty();
    let shown: SharedString = if empty {
        PLACEHOLDER.into()
    } else {
        text.to_string().into()
    };
    div()
        .h(px(INPUT_HEIGHT))
        .px(px(18.0))
        .flex()
        .items_center()
        .text_xl()
        .when(empty, |input| input.text_color(palette.muted))
        .child(shown)
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
            .child(input_row(&self.state.text, &palette))
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

/// Make the app an accessory: no Dock icon and no menu bar. The bundle's LSUIElement says
/// the same, but GPUI sets the regular policy as it finishes launching, just before it
/// calls the `run` closure, which overrides the plist; so this runs first in that closure.
/// The PopUp panel, a non-activating NSPanel, still takes the keyboard.
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
    let (host, trouble) = start_host();
    let events = host.events();
    let (notify, presses) = async_channel::bounded(1);
    let _hotkey = register_hotkey(notify);
    Application::new().run(move |cx: &mut App| {
        become_accessory();
        let bounds = launcher_bounds(cx);
        // Blurred makes the NSWindow transparent with a vibrancy view beneath the content,
        // so the rounded, tinted root is the window's whole shape.
        let options = WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(bounds)),
            titlebar: None,
            kind: WindowKind::PopUp,
            is_movable: false,
            is_resizable: false,
            is_minimizable: false,
            window_background: WindowBackgroundAppearance::Blurred,
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
    ExitCode::SUCCESS
}
