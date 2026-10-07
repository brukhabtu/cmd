//! What the shell sees of the displays and the pointer, in one coordinate space, for
//! `cmd_core::placement` to decide from.
//!
//! GPUI 0.2.2 on macOS reports every display with its origin at zero and keeps window
//! bounds relative to the window's own screen, and it has no pointer position outside its
//! windows. So on macOS the displays' arrangement and the pointer come from CoreGraphics,
//! which shares one global space (the main display's top-left at the origin, y down, in
//! points). Reading the pointer this way needs no permission. If GPUI later reports real
//! display origins, this is the one place to change.

use cmd_core::placement::{Display, Point, Rect, Size};
use gpui::App;

/// The displays, the pointer when it could be read, and the primary display's id.
pub struct Seen {
    pub displays: Vec<Display>,
    pub pointer: Option<Point>,
    pub primary: Option<u32>,
}

/// Look now: the arrangement may have changed since the last show.
#[cfg(target_os = "macos")]
pub fn look(cx: &App) -> Seen {
    use core_graphics::display::CGDisplay;
    use core_graphics::event::CGEvent;
    use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};

    let displays = cx
        .displays()
        .iter()
        .map(|display| {
            let id = u32::from(display.id());
            let bounds = CGDisplay::new(id).bounds();
            Display {
                id,
                bounds: rect(
                    bounds.origin.x,
                    bounds.origin.y,
                    bounds.size.width,
                    bounds.size.height,
                ),
            }
        })
        .collect();
    // A null event carries the pointer's current location; a failure means the
    // placement falls back to the primary display, never a panic.
    let pointer = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
        .ok()
        .and_then(|source| CGEvent::new(source).ok())
        .map(|event| {
            let location = event.location();
            point(location.x, location.y)
        });
    Seen {
        displays,
        pointer,
        primary: cx.primary_display().map(|display| u32::from(display.id())),
    }
}

/// Elsewhere GPUI's own display bounds are all there is, and no pointer, so the primary
/// display wins. This keeps the whole show path compiling and linted off macOS.
#[cfg(not(target_os = "macos"))]
pub fn look(cx: &App) -> Seen {
    let displays = cx
        .displays()
        .iter()
        .map(|display| {
            let bounds = display.bounds();
            Display {
                id: u32::from(display.id()),
                bounds: rect(
                    f64::from(bounds.origin.x),
                    f64::from(bounds.origin.y),
                    f64::from(bounds.size.width),
                    f64::from(bounds.size.height),
                ),
            }
        })
        .collect();
    Seen {
        displays,
        pointer: None,
        primary: cx.primary_display().map(|display| u32::from(display.id())),
    }
}

/// The one narrowing from the system's f64 to the core's f32, compiled on every platform
/// so the pedantic cast lints are met on Linux too, not first on macOS CI.
#[expect(
    clippy::cast_possible_truncation,
    reason = "display coordinates in points are far inside f32's exact range"
)]
fn rect(x: f64, y: f64, width: f64, height: f64) -> Rect {
    Rect {
        origin: point(x, y),
        size: Size {
            width: width as f32,
            height: height as f32,
        },
    }
}

#[expect(
    clippy::cast_possible_truncation,
    reason = "display coordinates in points are far inside f32's exact range"
)]
fn point(x: f64, y: f64) -> Point {
    Point {
        x: x as f32,
        y: y as f32,
    }
}
