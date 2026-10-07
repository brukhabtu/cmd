//! Icons beside result rows.
//!
//! A plugin names an icon (protocol version 1); this module turns it into a bitmap the
//! window can draw. The system does the resolving: on macOS, `NSWorkspace` knows the icon
//! for a path and `NSImage` knows the symbols, so no bundle or icns is read here. GPUI's
//! asset cache keeps each resolved icon for the app's lifetime, keyed by the request, so
//! `AppKit` is asked once per distinct icon, and only the PNG decode runs off the main
//! thread, because `AppKit` objects must not cross threads.

use std::sync::Arc;

use cmd_core::protocol::Icon;
use gpui::{App, Asset, RenderImage, Rgba};
use image::{Frame, ImageFormat};

/// The slot an icon takes in a row, in points.
pub const SIZE: f32 = 24.0;
/// Bitmaps are fetched at twice the slot so they stay sharp on a Retina display.
const PIXELS: u32 = 48;

/// What the cache keys on: the icon and the colour a symbol is drawn in, so a change of
/// appearance draws the symbol again instead of showing the old tint.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Request {
    pub icon: Icon,
    pub tint: [u8; 3],
}

impl Request {
    /// A request for `icon` with symbols drawn in `text`, the row's text colour.
    pub fn new(icon: &Icon, text: Rgba) -> Self {
        Self {
            icon: icon.clone(),
            tint: tint_of(text),
        }
    }
}

/// The loader GPUI's asset cache runs once per distinct [`Request`].
pub struct IconAsset;

impl Asset for IconAsset {
    type Source = Request;
    type Output = Option<Arc<RenderImage>>;

    fn load(
        source: Request,
        _cx: &mut App,
    ) -> impl std::future::Future<Output = Self::Output> + Send + 'static {
        // The cache calls this on the main thread, which is where `AppKit` is asked; the
        // future that goes to the background carries only bytes.
        let png = platform::png(&source.icon, PIXELS);
        let tint = matches!(source.icon, Icon::Symbol { .. }).then_some(source.tint);
        async move { png.and_then(|bytes| render_image(&bytes, tint)) }
    }
}

/// The colour's channels as bytes. The clamp makes the casts exact.
#[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
fn tint_of(colour: Rgba) -> [u8; 3] {
    let channel = |value: f32| (value.clamp(0.0, 1.0) * 255.0).round() as u8;
    [channel(colour.r), channel(colour.g), channel(colour.b)]
}

/// A PNG as the image GPUI draws: straight-alpha BGRA, which is what its own loader
/// produces, with the symbol tint applied first when there is one.
fn render_image(png: &[u8], tint: Option<[u8; 3]>) -> Option<Arc<RenderImage>> {
    let mut pixels = image::load_from_memory_with_format(png, ImageFormat::Png)
        .ok()?
        .into_rgba8();
    if let Some(rgb) = tint {
        tint_rgba(&mut pixels, rgb);
    }
    for pixel in pixels.as_chunks_mut::<4>().0 {
        pixel.swap(0, 2);
    }
    Some(Arc::new(RenderImage::new(vec![Frame::new(pixels)])))
}

/// Paint every pixel `rgb`, keeping its alpha: a symbol is a shape, and its colour is the
/// row's to choose.
fn tint_rgba(pixels: &mut [u8], rgb: [u8; 3]) {
    for pixel in pixels.as_chunks_mut::<4>().0 {
        pixel[..3].copy_from_slice(&rgb);
    }
}

/// Which of several bitmap widths to draw at `wanted`: the smallest that is at least as
/// wide, so the icon is only ever scaled down, or the widest there is when none is.
/// Only the macOS resolver has several widths to choose from.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn nearest(widths: &[u32], wanted: u32) -> Option<usize> {
    let at_least = widths
        .iter()
        .enumerate()
        .filter(|(_, width)| **width >= wanted)
        .min_by_key(|(_, width)| **width);
    at_least
        .or_else(|| widths.iter().enumerate().max_by_key(|(_, width)| **width))
        .map(|(index, _)| index)
}

#[cfg(target_os = "macos")]
mod platform {
    use std::path::Path;

    use cmd_core::protocol::Icon;
    use objc2_app_kit::{
        NSBitmapImageFileType, NSBitmapImageRep, NSFontWeightRegular, NSImage,
        NSImageSymbolConfiguration, NSImageSymbolScale, NSWorkspace,
    };
    use objc2_foundation::{NSDictionary, NSString};

    use super::nearest;

    /// The icon as PNG bytes, from the bitmap nearest `pixels` wide, or nothing when the
    /// system has no icon for it: a path that is not there, a symbol name it does not know.
    pub fn png(icon: &Icon, pixels: u32) -> Option<Vec<u8>> {
        let image = match icon {
            Icon::Path { path } => {
                let location = Path::new(path);
                if !location.is_absolute() || !location.exists() {
                    return None;
                }
                NSWorkspace::sharedWorkspace().iconForFile(&NSString::from_str(path))
            }
            Icon::Symbol { name } => {
                let symbol = NSImage::imageWithSystemSymbolName_accessibilityDescription(
                    &NSString::from_str(name),
                    None,
                )?;
                // SAFETY: reading a constant AppKit exports; it is never written.
                let weight = unsafe { NSFontWeightRegular };
                let configuration =
                    NSImageSymbolConfiguration::configurationWithPointSize_weight_scale(
                        f64::from(pixels),
                        weight,
                        NSImageSymbolScale::Medium,
                    );
                symbol.imageWithSymbolConfiguration(&configuration)?
            }
        };
        // A TIFF carries one page per representation, so an application icon offers
        // every size it ships with and the one nearest the slot is picked.
        let tiff = image.TIFFRepresentation()?;
        let pages = NSBitmapImageRep::imageRepsWithData(&tiff);
        let bitmaps: Vec<_> = pages
            .iter()
            .filter_map(|page| page.downcast::<NSBitmapImageRep>().ok())
            .collect();
        let widths: Vec<u32> = bitmaps
            .iter()
            .map(|bitmap| u32::try_from(bitmap.pixelsWide()).unwrap_or(0))
            .collect();
        let chosen = &bitmaps[nearest(&widths, pixels)?];
        // SAFETY: the properties dictionary is untyped in `AppKit`; an empty one asks for
        // the defaults, which is all a PNG needs.
        let png = unsafe {
            chosen.representationUsingType_properties(
                NSBitmapImageFileType::PNG,
                &NSDictionary::new(),
            )
        }?;
        Some(png.to_vec())
    }
}

#[cfg(not(target_os = "macos"))]
mod platform {
    use cmd_core::protocol::Icon;

    /// Only macOS knows how to draw an icon; elsewhere every row is text alone.
    pub fn png(_icon: &Icon, _pixels: u32) -> Option<Vec<u8>> {
        None
    }
}

#[cfg(test)]
mod tests {
    use std::io::Cursor;

    use gpui::rgb;
    use image::RgbaImage;

    use super::*;

    #[test]
    fn the_nearest_width_is_the_smallest_at_least_as_wide_or_else_the_widest() {
        assert_eq!(nearest(&[16, 32, 128, 512], 48), Some(2));
        assert_eq!(nearest(&[512, 128, 32, 16], 32), Some(2));
        assert_eq!(nearest(&[16, 32], 48), Some(1));
        assert_eq!(nearest(&[], 48), None);
    }

    #[test]
    fn a_tint_sets_the_colour_and_keeps_the_alpha() {
        let mut pixels = [0, 0, 0, 255, 9, 9, 9, 0];
        tint_rgba(&mut pixels, [1, 2, 3]);
        assert_eq!(pixels, [1, 2, 3, 255, 1, 2, 3, 0]);
    }

    #[test]
    fn the_tint_is_the_text_colour_in_bytes() {
        assert_eq!(tint_of(rgb(0xf2_f2_f7)), [0xf2, 0xf2, 0xf7]);
        assert_eq!(tint_of(rgb(0x1d_1d_1f)), [0x1d, 0x1d, 0x1f]);
    }

    /// A 2 by 2 PNG: one red pixel, one green, one blue, one transparent.
    fn png() -> Vec<u8> {
        let image = RgbaImage::from_raw(
            2,
            2,
            vec![255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 0, 0, 0, 0],
        )
        .unwrap();
        let mut bytes = Vec::new();
        image
            .write_to(&mut Cursor::new(&mut bytes), ImageFormat::Png)
            .unwrap();
        bytes
    }

    #[test]
    fn a_png_becomes_a_bgra_frame() {
        let image = render_image(&png(), None).unwrap();
        assert_eq!(
            image.as_bytes(0).unwrap(),
            [0, 0, 255, 255, 0, 255, 0, 255, 255, 0, 0, 255, 0, 0, 0, 0]
        );
    }

    #[test]
    fn a_tinted_png_keeps_only_its_alpha() {
        let image = render_image(&png(), Some([1, 2, 3])).unwrap();
        assert_eq!(
            image.as_bytes(0).unwrap(),
            [3, 2, 1, 255, 3, 2, 1, 255, 3, 2, 1, 255, 3, 2, 1, 0]
        );
    }

    #[test]
    fn bytes_that_are_not_a_png_resolve_to_nothing() {
        assert!(render_image(b"not a png", None).is_none());
    }

    #[test]
    fn a_request_keys_on_the_icon_and_the_tint() {
        let globe = Icon::Symbol {
            name: "globe".into(),
        };
        assert_ne!(
            Request::new(&globe, rgb(0xf2_f2_f7)),
            Request::new(&globe, rgb(0x1d_1d_1f))
        );
        assert_eq!(
            Request::new(&globe, rgb(0xf2_f2_f7)),
            Request::new(&globe, rgb(0xf2_f2_f7))
        );
    }
}

/// Run by `cargo test -p cmd-app` on macOS CI: the `AppKit` path against an application
/// that ships with the system and a symbol in every catalogue.
#[cfg(all(test, target_os = "macos"))]
mod macos_tests {
    use super::*;

    #[test]
    fn an_application_bundle_resolves_to_a_bitmap_at_least_the_wanted_size() {
        let png = platform::png(
            &Icon::Path {
                path: "/System/Applications/Calculator.app".into(),
            },
            PIXELS,
        )
        .expect("Calculator ships with macOS");
        let image = image::load_from_memory_with_format(&png, ImageFormat::Png).unwrap();
        assert!(image.width() >= PIXELS, "{} px wide", image.width());
        assert!(render_image(&png, None).is_some());
    }

    #[test]
    fn a_symbol_resolves_to_a_glyph_drawn_in_the_tint() {
        let png = platform::png(
            &Icon::Symbol {
                name: "magnifyingglass".into(),
            },
            PIXELS,
        )
        .expect("magnifyingglass is in every SF Symbols catalogue");
        let image = render_image(&png, Some([0xf2, 0xf2, 0xf7])).unwrap();
        let bytes = image.as_bytes(0).unwrap();
        let opaque = bytes
            .as_chunks::<4>()
            .0
            .iter()
            .find(|pixel| pixel[3] > 0)
            .expect("the glyph has an opaque pixel");
        assert_eq!(&opaque[..3], &[0xf7, 0xf2, 0xf2]);
    }

    #[test]
    fn an_unknown_symbol_and_a_missing_path_resolve_to_nothing() {
        assert!(
            platform::png(
                &Icon::Symbol {
                    name: "no.such.symbol.in.any.catalogue".into()
                },
                PIXELS
            )
            .is_none()
        );
        assert!(
            platform::png(
                &Icon::Path {
                    path: "/Applications/No Such App.app".into()
                },
                PIXELS
            )
            .is_none()
        );
    }
}
