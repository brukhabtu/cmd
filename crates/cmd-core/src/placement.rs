//! Where the launcher window goes: on the display that holds the pointer, centred across
//! it and a third of the way down.
//!
//! The shell reports the displays and the pointer in one shared coordinate space (points,
//! y down) and asks nothing of the system here, so the choice is decided again from fresh
//! inputs on every show and follows a display arrangement changed while the app runs.

/// A position in the shell's shared display space.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Point {
    pub x: f32,
    pub y: f32,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Size {
    pub width: f32,
    pub height: f32,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect {
    pub origin: Point,
    pub size: Size,
}

impl Rect {
    /// Half-open on both axes, so a point on the edge two displays share belongs to one
    /// of them only.
    pub fn contains(&self, p: Point) -> bool {
        p.x >= self.origin.x
            && p.x < self.origin.x + self.size.width
            && p.y >= self.origin.y
            && p.y < self.origin.y + self.size.height
    }
}

/// One attached display: the system's id for it and where it sits in the shared space.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Display {
    pub id: u32,
    pub bounds: Rect,
}

/// The display to open on, and the window's top-left relative to that display's
/// top-left, which is what a window opened on a given display is positioned by.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Placement {
    pub display: u32,
    pub origin: Point,
}

impl Placement {
    /// Whether a window on `display` at `origin` is already where this placement puts it.
    /// Within a point, because the shell reads positions back through floating point; the
    /// shell reopens the window only when this says no.
    pub fn matches(&self, display: Option<u32>, origin: Point) -> bool {
        display == Some(self.display)
            && (origin.x - self.origin.x).abs() <= 1.0
            && (origin.y - self.origin.y).abs() <= 1.0
    }
}

/// The display under the pointer; else the primary, when the pointer is unknown or off
/// every display; else the first reported; else none.
pub fn display_under(
    displays: &[Display],
    pointer: Option<Point>,
    primary: Option<u32>,
) -> Option<&Display> {
    pointer
        .and_then(|p| displays.iter().find(|display| display.bounds.contains(p)))
        .or_else(|| primary.and_then(|id| displays.iter().find(|display| display.id == id)))
        .or_else(|| displays.first())
}

/// Centred across, a third of the way down, relative to the display's top-left. A display
/// smaller than the window pins it to the top-left rather than pushing it off screen.
pub fn launcher_origin(display: Size, window: Size) -> Point {
    Point {
        x: ((display.width - window.width) / 2.0).max(0.0),
        y: (display.height / 3.0 - window.height / 2.0).max(0.0),
    }
}

/// Where a window of `window`'s size goes, given what the shell sees now.
pub fn place(
    displays: &[Display],
    pointer: Option<Point>,
    primary: Option<u32>,
    window: Size,
) -> Option<Placement> {
    display_under(displays, pointer, primary).map(|display| Placement {
        display: display.id,
        origin: launcher_origin(display.bounds.size, window),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const WINDOW: Size = Size {
        width: 680.0,
        height: 420.0,
    };

    fn display(id: u32, x: f32, y: f32, width: f32, height: f32) -> Display {
        Display {
            id,
            bounds: Rect {
                origin: Point { x, y },
                size: Size { width, height },
            },
        }
    }

    fn at(x: f32, y: f32) -> Point {
        Point { x, y }
    }

    /// The primary at the origin and a second display to its right.
    fn side_by_side() -> Vec<Display> {
        vec![
            display(1, 0.0, 0.0, 1920.0, 1080.0),
            display(2, 1920.0, 0.0, 2560.0, 1440.0),
        ]
    }

    fn chosen(displays: &[Display], pointer: Option<Point>, primary: Option<u32>) -> Option<u32> {
        display_under(displays, pointer, primary).map(|display| display.id)
    }

    #[test]
    fn the_pointer_picks_its_display() {
        assert_eq!(
            chosen(&side_by_side(), Some(at(2500.0, 300.0)), Some(1)),
            Some(2)
        );
        assert_eq!(
            chosen(&side_by_side(), Some(at(100.0, 300.0)), Some(1)),
            Some(1)
        );
    }

    #[test]
    fn a_display_left_of_the_primary_has_negative_coordinates_and_is_still_found() {
        let displays = vec![
            display(1, 0.0, 0.0, 1920.0, 1080.0),
            display(3, -1440.0, -200.0, 1440.0, 900.0),
        ];
        assert_eq!(chosen(&displays, Some(at(-10.0, -100.0)), Some(1)), Some(3));
    }

    #[test]
    fn a_shared_edge_belongs_to_one_display() {
        let displays = side_by_side();
        let edge = Point {
            x: 1920.0,
            y: 500.0,
        };
        assert!(!displays[0].bounds.contains(edge));
        assert!(displays[1].bounds.contains(edge));
        assert_eq!(chosen(&displays, Some(edge), Some(1)), Some(2));
    }

    #[test]
    fn no_pointer_means_the_primary() {
        assert_eq!(chosen(&side_by_side(), None, Some(2)), Some(2));
    }

    #[test]
    fn a_pointer_off_every_display_means_the_primary() {
        assert_eq!(
            chosen(&side_by_side(), Some(at(9000.0, 9000.0)), Some(2)),
            Some(2)
        );
    }

    #[test]
    fn no_primary_means_the_first() {
        assert_eq!(chosen(&side_by_side(), None, None), Some(1));
        assert_eq!(chosen(&side_by_side(), None, Some(42)), Some(1));
    }

    #[test]
    fn no_displays_means_nothing() {
        assert_eq!(chosen(&[], Some(at(0.0, 0.0)), Some(1)), None);
        assert_eq!(place(&[], Some(at(0.0, 0.0)), Some(1), WINDOW), None);
    }

    #[test]
    fn the_window_sits_centred_a_third_down() {
        let screen = Size {
            width: 1920.0,
            height: 1080.0,
        };
        assert_eq!(
            launcher_origin(screen, WINDOW),
            Point { x: 620.0, y: 150.0 }
        );
    }

    #[test]
    fn the_origin_is_relative_to_the_chosen_display() {
        let placed = place(&side_by_side(), Some(at(2500.0, 300.0)), Some(1), WINDOW);
        assert_eq!(
            placed,
            Some(Placement {
                display: 2,
                origin: Point { x: 940.0, y: 270.0 },
            })
        );
    }

    #[test]
    fn a_display_smaller_than_the_window_pins_it_to_the_top_left() {
        let tiny = Size {
            width: 600.0,
            height: 400.0,
        };
        assert_eq!(launcher_origin(tiny, WINDOW), Point { x: 0.0, y: 0.0 });
    }

    #[test]
    fn a_rearranged_display_moves_the_placement_with_it() {
        let pointer = Some(at(2500.0, 300.0));
        let before = place(&side_by_side(), pointer, Some(1), WINDOW).map(|p| p.display);
        // The second display moved to the left of the primary, and the primary's resolution
        // changed: the same pointer is now on the primary, at its new size.
        let swapped = vec![
            display(1, 0.0, 0.0, 3008.0, 1692.0),
            display(2, -2560.0, 0.0, 2560.0, 1440.0),
        ];
        let after = place(&swapped, pointer, Some(1), WINDOW);
        assert_eq!(before, Some(2));
        assert_eq!(
            after,
            Some(Placement {
                display: 1,
                origin: Point {
                    x: 1164.0,
                    y: 354.0
                },
            })
        );
    }

    #[test]
    fn matches_within_a_point_and_not_beyond() {
        let placed = Placement {
            display: 2,
            origin: Point { x: 940.0, y: 270.0 },
        };
        assert!(placed.matches(Some(2), Point { x: 940.5, y: 269.2 }));
        assert!(!placed.matches(Some(2), Point { x: 942.0, y: 270.0 }));
        assert!(!placed.matches(Some(2), Point { x: 940.0, y: 268.5 }));
        assert!(!placed.matches(Some(1), Point { x: 940.0, y: 270.0 }));
        assert!(!placed.matches(None, Point { x: 940.0, y: 270.0 }));
    }
}
