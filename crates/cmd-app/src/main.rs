//! The launcher window.
//!
//! Every key becomes a [`cmd_core::state::Event`]; the state machine answers with a
//! [`cmd_core::state::Step`]; this file performs it. The global chord shows the window,
//! Escape and losing focus hide it. That is the whole shell.

use std::path::PathBuf;

use cmd_core::state::{Event, Launcher, Step};
use cmd_host::{Host, Timeouts, manifest};
use global_hotkey::hotkey::HotKey;
use global_hotkey::{GlobalHotKeyEvent, GlobalHotKeyManager, HotKeyState};
use gpui::prelude::*;
use gpui::{
    App, Application, AsyncApp, Bounds, ClipboardItem, Context, FocusHandle, KeyDownEvent, Render,
    SharedString, Window, WindowBounds, WindowHandle, WindowKind, WindowOptions, div, px, rgb,
    size,
};

const WIDTH: f32 = 680.0;
const HEIGHT: f32 = 420.0;
const PLACEHOLDER: &str = "Search, or type a keyword";
/// Option-Space. Spotlight holds Cmd-Space; `CMD_HOTKEY=super+Space` takes it once Spotlight lets go.
const DEFAULT_HOTKEY: &str = "alt+Space";

struct LauncherView {
    state: Launcher,
    host: Host,
    focus: FocusHandle,
    /// Whether the window is meant to be on screen. Losing focus while shown hides it.
    shown: bool,
}

impl LauncherView {
    fn new(host: Host, window: &mut Window, cx: &mut Context<Self>) -> Self {
        cx.observe_window_activation(window, |view, window, cx| {
            if view.shown && !window.is_window_active() {
                view.hide(cx);
            }
        })
        .detach();
        Self {
            state: Launcher::default(),
            host,
            focus: cx.focus_handle(),
            shown: true,
        }
    }

    /// Bring the window up with an empty, focused input.
    fn show(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.shown = true;
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
                let (hits, errors) = self.host.query(&text);
                self.state.apply(Event::Results { generation, hits });
                if let Some(error) = errors.first() {
                    self.state.apply(Event::Failed(error.to_string()));
                }
            }
            Step::Run {
                plugin,
                item,
                action,
            } => {
                let event = match self.host.run(plugin, &item, &action) {
                    Ok(effect) => Event::Ran(effect),
                    Err(error) => Event::Failed(error.to_string()),
                };
                let step = self.state.apply(event);
                self.perform(step, cx);
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

/// Where plugins live: `CMD_PLUGINS` if set, else `./plugins` for development.
fn plugins_dir() -> PathBuf {
    std::env::var_os("CMD_PLUGINS").map_or_else(|| PathBuf::from("plugins"), PathBuf::from)
}

fn start_host() -> Host {
    let mut located = Vec::new();
    match manifest::discover(&plugins_dir()) {
        Ok(found) => {
            for entry in found {
                match entry {
                    Ok(plugin) => located.push(plugin),
                    Err(error) => eprintln!("cmd: {error}"),
                }
            }
        }
        Err(error) => eprintln!("cmd: no plugins directory: {error}"),
    }
    let (host, errors) = Host::start(located, Timeouts::default());
    for error in &errors {
        eprintln!("cmd: {error}");
    }
    host
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

/// Show the window on every press until the channel or the window goes away.
async fn show_on_press(
    presses: async_channel::Receiver<()>,
    window: WindowHandle<LauncherView>,
    cx: &mut AsyncApp,
) {
    while presses.recv().await.is_ok() {
        let shown = window.update(cx, LauncherView::show);
        if shown.is_err() {
            break;
        }
    }
}

fn main() {
    let host = start_host();
    let (notify, presses) = async_channel::bounded(1);
    let _hotkey = register_hotkey(notify);
    Application::new().run(move |cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(WIDTH), px(HEIGHT)), cx);
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
                let view = cx.new(|cx| LauncherView::new(host, window, cx));
                let focus = view.read(cx).focus.clone();
                window.focus(&focus);
                view
            })
            .expect("the launcher window opens");
        cx.spawn(async move |cx| show_on_press(presses, window, cx).await)
            .detach();
        cx.activate(true);
    });
}
