//! The query line, drawn from the state machine's [`cmd_core::input::Input`], and the
//! platform's text input wired back into it.
//!
//! On macOS a key that carries a character goes to the window's key listeners first and,
//! when none of them consumes it, on to the input method, which answers through the
//! [`EntityInputHandler`] below: plain typing, dead keys and composition (IME) all arrive
//! there. Every method that writes turns into an [`Event`] for the state machine, so the
//! view keeps no text of its own, only the line it last drew and where it drew it, which
//! the input method needs to place its candidate window.

use std::ops::Range;

use cmd_core::input::utf16_to_byte;
use cmd_core::state::Event;
use gpui::{
    App, Bounds, Context, Element, ElementId, ElementInputHandler, Entity, EntityInputHandler,
    GlobalElementId, Hsla, InspectorElementId, IntoElement, LayoutId, PaintQuad, Pixels, Point,
    ShapedLine, SharedString, Style, TextRun, UTF16Selection, UnderlineStyle, Window, fill, point,
    px, relative, size,
};

use crate::{LauncherView, PLACEHOLDER};

/// The width of the cursor.
const CURSOR_WIDTH: f32 = 2.0;
/// How strongly the selection is tinted with the text colour.
const SELECTION_ALPHA: f32 = 0.25;

/// The query line: the text with the cursor, the selection and the composition
/// underline, or the placeholder in `muted` while there is no text.
pub(crate) struct InputElement {
    pub(crate) view: Entity<LauncherView>,
    pub(crate) muted: Hsla,
}

pub(crate) struct Prepainted {
    line: Option<ShapedLine>,
    cursor: Option<PaintQuad>,
    selection: Option<PaintQuad>,
}

impl IntoElement for InputElement {
    type Element = Self;

    fn into_element(self) -> Self::Element {
        self
    }
}

impl Element for InputElement {
    type RequestLayoutState = ();
    type PrepaintState = Prepainted;

    fn id(&self) -> Option<ElementId> {
        None
    }

    fn source_location(&self) -> Option<&'static core::panic::Location<'static>> {
        None
    }

    fn request_layout(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&InspectorElementId>,
        window: &mut Window,
        cx: &mut App,
    ) -> (LayoutId, Self::RequestLayoutState) {
        let mut style = Style::default();
        style.size.width = relative(1.).into();
        style.size.height = window.line_height().into();
        (window.request_layout(style, [], cx), ())
    }

    fn prepaint(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>,
        _request_layout: &mut Self::RequestLayoutState,
        window: &mut Window,
        cx: &mut App,
    ) -> Self::PrepaintState {
        let input = self.view.read(cx).state.input.clone();
        let style = window.text_style();
        let (shown, colour): (SharedString, Hsla) = if input.is_empty() {
            (PLACEHOLDER.into(), self.muted)
        } else {
            (input.text().to_string().into(), style.color)
        };
        let run = TextRun {
            len: shown.len(),
            font: style.font(),
            color: colour,
            background_color: None,
            underline: None,
            strikethrough: None,
        };
        let runs = match input.marked() {
            Some(marked) if !input.is_empty() => vec![
                TextRun {
                    len: marked.start,
                    ..run.clone()
                },
                TextRun {
                    len: marked.end - marked.start,
                    underline: Some(UnderlineStyle {
                        color: Some(colour),
                        thickness: px(1.0),
                        wavy: false,
                    }),
                    ..run.clone()
                },
                TextRun {
                    len: shown.len() - marked.end,
                    ..run
                },
            ]
            .into_iter()
            .filter(|run| run.len > 0)
            .collect(),
            _ => vec![run],
        };
        let font_size = style.font_size.to_pixels(window.rem_size());
        let line = window
            .text_system()
            .shape_line(shown, font_size, &runs, None);
        let selection = input.selection();
        let (cursor, selection) = if selection.is_empty() {
            let x = if input.is_empty() {
                px(0.0)
            } else {
                line.x_for_index(input.cursor())
            };
            let cursor = fill(
                Bounds::new(
                    point(bounds.left() + x, bounds.top()),
                    size(px(CURSOR_WIDTH), bounds.bottom() - bounds.top()),
                ),
                style.color,
            );
            (Some(cursor), None)
        } else {
            let tint = fill(
                Bounds::from_corners(
                    point(
                        bounds.left() + line.x_for_index(selection.start),
                        bounds.top(),
                    ),
                    point(
                        bounds.left() + line.x_for_index(selection.end),
                        bounds.bottom(),
                    ),
                ),
                Hsla {
                    a: SELECTION_ALPHA,
                    ..style.color
                },
            );
            (None, Some(tint))
        };
        Prepainted {
            line: Some(line),
            cursor,
            selection,
        }
    }

    fn paint(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>,
        _request_layout: &mut Self::RequestLayoutState,
        prepaint: &mut Self::PrepaintState,
        window: &mut Window,
        cx: &mut App,
    ) {
        let focus = self.view.read(cx).focus.clone();
        window.handle_input(
            &focus,
            ElementInputHandler::new(bounds, self.view.clone()),
            cx,
        );
        if let Some(selection) = prepaint.selection.take() {
            window.paint_quad(selection);
        }
        let Some(line) = prepaint.line.take() else {
            return;
        };
        // A line that fails to paint leaves the row empty for one frame; nothing to report.
        let _ = line.paint(bounds.origin, window.line_height(), window, cx);
        if focus.is_focused(window)
            && let Some(cursor) = prepaint.cursor.take()
        {
            window.paint_quad(cursor);
        }
        self.view.update(cx, |view, _| {
            view.last_line = Some(line);
            view.last_bounds = Some(bounds);
        });
    }
}

impl LauncherView {
    /// Text from the input method is a key pressed at the window, as far as the start
    /// trouble is concerned.
    fn edit(&mut self, event: Event, cx: &mut Context<Self>) {
        self.start_trouble = None;
        self.handle(event, cx);
    }
}

/// Offsets here are the platform's UTF-16 units; the state machine counts bytes, and the
/// bridge is [`cmd_core::input::Input`]'s.
impl EntityInputHandler for LauncherView {
    fn text_for_range(
        &mut self,
        range: Range<usize>,
        adjusted_range: &mut Option<Range<usize>>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<String> {
        let input = &self.state.input;
        let range = input.range_from_utf16(&range);
        adjusted_range.replace(input.range_to_utf16(&range));
        input.text().get(range).map(str::to_string)
    }

    fn selected_text_range(
        &mut self,
        _ignore_disabled_input: bool,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<UTF16Selection> {
        let input = &self.state.input;
        Some(UTF16Selection {
            range: input.range_to_utf16(&input.selection()),
            reversed: input.reversed(),
        })
    }

    fn marked_text_range(
        &self,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<Range<usize>> {
        let input = &self.state.input;
        input.marked().map(|marked| input.range_to_utf16(&marked))
    }

    fn unmark_text(&mut self, _window: &mut Window, cx: &mut Context<Self>) {
        self.edit(Event::Unmark, cx);
    }

    fn replace_text_in_range(
        &mut self,
        range: Option<Range<usize>>,
        text: &str,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let event = match range {
            Some(range) => Event::Replace {
                range: self.state.input.range_from_utf16(&range),
                text: text.to_string(),
            },
            None => Event::Typed(text.to_string()),
        };
        self.edit(event, cx);
    }

    fn replace_and_mark_text_in_range(
        &mut self,
        range: Option<Range<usize>>,
        new_text: &str,
        new_selected_range: Option<Range<usize>>,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        // The input method's selection is within the composed text, not the whole input.
        let selection = new_selected_range.map(|selection| {
            utf16_to_byte(new_text, selection.start)..utf16_to_byte(new_text, selection.end)
        });
        let event = Event::Compose {
            range: range.map(|range| self.state.input.range_from_utf16(&range)),
            text: new_text.to_string(),
            selection,
        };
        self.edit(event, cx);
    }

    fn bounds_for_range(
        &mut self,
        range_utf16: Range<usize>,
        element_bounds: Bounds<Pixels>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<Bounds<Pixels>> {
        let line = self.last_line.as_ref()?;
        let range = self.state.input.range_from_utf16(&range_utf16);
        Some(Bounds::from_corners(
            point(
                element_bounds.left() + line.x_for_index(range.start),
                element_bounds.top(),
            ),
            point(
                element_bounds.left() + line.x_for_index(range.end),
                element_bounds.bottom(),
            ),
        ))
    }

    fn character_index_for_point(
        &mut self,
        point: Point<Pixels>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<usize> {
        let local = self.last_bounds?.localize(&point)?;
        let index = self.last_line.as_ref()?.index_for_x(local.x)?;
        // While the input is empty the line is the placeholder; offsets clamp to the text.
        Some(self.state.input.offset_to_utf16(index))
    }
}
