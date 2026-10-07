//! The launcher window.
//!
//! Every key becomes a [`cmd_core::state::Event`]; the state machine answers with a
//! [`cmd_core::state::Step`]; this file performs it. That is the whole shell.

use std::path::PathBuf;

use cmd_core::state::{Event, Launcher, Step};
use cmd_host::{Host, Timeouts, manifest};
use gpui::prelude::*;
use gpui::{
    App, Application, Bounds, ClipboardItem, Context, FocusHandle, KeyDownEvent, Render,
    SharedString, Window, WindowBounds, WindowKind, WindowOptions, div, px, rgb, size,
};

const WIDTH: f32 = 680.0;
const HEIGHT: f32 = 420.0;
const PLACEHOLDER: &str = "Search, or type a keyword";

struct LauncherView {
    state: Launcher,
    host: Host,
    focus: FocusHandle,
}

impl LauncherView {
    fn new(host: Host, cx: &mut Context<Self>) -> Self {
        Self {
            state: Launcher::default(),
            host,
            focus: cx.focus_handle(),
        }
    }

    fn on_key(&mut self, event: &KeyDownEvent, window: &mut Window, cx: &mut Context<Self>) {
        let keystroke = &event.keystroke;
        let event = match keystroke.key.as_str() {
            "backspace" => Some(Event::Backspace),
            "up" => Some(Event::Up),
            "down" => Some(Event::Down),
            "enter" => Some(Event::Submit),
            "escape" => Some(Event::Escape),
            _ if keystroke.modifiers.platform || keystroke.modifiers.control => None,
            _ => keystroke.key_char.clone().map(Event::Typed),
        };
        if let Some(event) = event {
            self.handle(event, window, cx);
        }
    }

    fn handle(&mut self, event: Event, window: &mut Window, cx: &mut Context<Self>) {
        let step = self.state.apply(event);
        self.perform(step, window, cx);
        cx.notify();
    }

    fn perform(&mut self, step: Step, window: &mut Window, cx: &mut Context<Self>) {
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
                self.perform(step, window, cx);
            }
            Step::Hide => cx.hide(),
            Step::CopyAndHide(text) => {
                cx.write_to_clipboard(ClipboardItem::new_string(text));
                cx.hide();
            }
            Step::OpenAndHide(target) => {
                cx.open_url(&target);
                cx.hide();
            }
            Step::Nothing => {}
        }
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
            .bg(rgb(0x1c1c1e))
            .text_color(rgb(0xf2f2f7))
            .rounded_xl()
            .overflow_hidden()
            .child(
                div()
                    .h(px(56.0))
                    .px(px(18.0))
                    .flex()
                    .items_center()
                    .text_xl()
                    .when(empty, |input| input.text_color(rgb(0x8e8e93)))
                    .child(input),
            )
            .children(self.state.message.clone().map(|message| {
                div()
                    .px(px(18.0))
                    .pb(px(8.0))
                    .text_sm()
                    .text_color(rgb(0xff9f0a))
                    .child(message)
            }))
            .children(self.state.hits.iter().enumerate().map(|(index, hit)| {
                div()
                    .px(px(18.0))
                    .py(px(10.0))
                    .flex()
                    .flex_col()
                    .when(index == selected, |row| row.bg(rgb(0x2c2c2e)))
                    .child(div().text_base().child(hit.item.title.clone()))
                    .children(
                        hit.item.subtitle.clone().map(|subtitle| {
                            div().text_sm().text_color(rgb(0x8e8e93)).child(subtitle)
                        }),
                    )
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

fn main() {
    let host = start_host();
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
        cx.open_window(options, |window, cx| {
            let view = cx.new(|cx| LauncherView::new(host, cx));
            let focus = view.read(cx).focus.clone();
            window.focus(&focus);
            view
        })
        .expect("the launcher window opens");
        cx.activate(true);
    });
}
