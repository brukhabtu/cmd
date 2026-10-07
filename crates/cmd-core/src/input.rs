//! The text of the query, with a cursor, a selection and an input method's composition.
//!
//! This is the one owner of the text. The window draws it and hands every edit here,
//! whether it came from a key, the pasteboard or an input method, so the state machine
//! sees one vocabulary of edits and the view holds no text of its own.
//!
//! Offsets are byte offsets into the text, always on a char boundary. The platform
//! speaks UTF-16, so the bridge at the bottom converts both ways.

use std::ops::Range;

use unicode_segmentation::UnicodeSegmentation;

/// Where a motion goes from the cursor.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Motion {
    PreviousGrapheme,
    NextGrapheme,
    PreviousWord,
    NextWord,
    LineStart,
    LineEnd,
}

/// The text and where the person is in it.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Input {
    text: String,
    cursor: usize,
    /// The fixed end of a selection. None means nothing is selected; the cursor is the
    /// moving end, so the selection is reversed when the cursor sits before the anchor.
    anchor: Option<usize>,
    /// The input method's uncommitted text, underlined by the view and replaced by the
    /// next composition or the commit.
    marked: Option<Range<usize>>,
}

impl Input {
    pub fn text(&self) -> &str {
        &self.text
    }

    pub fn is_empty(&self) -> bool {
        self.text.is_empty()
    }

    pub fn cursor(&self) -> usize {
        self.cursor
    }

    /// The selection in text order, empty at the cursor when there is none.
    pub fn selection(&self) -> Range<usize> {
        match self.anchor {
            Some(anchor) => anchor.min(self.cursor)..anchor.max(self.cursor),
            None => self.cursor..self.cursor,
        }
    }

    /// Whether the cursor is at the start of the selection rather than its end.
    pub fn reversed(&self) -> bool {
        self.anchor.is_some_and(|anchor| self.cursor < anchor)
    }

    pub fn selected_text(&self) -> Option<&str> {
        let selection = self.selection();
        (!selection.is_empty()).then(|| &self.text[selection])
    }

    pub fn marked(&self) -> Option<Range<usize>> {
        self.marked.clone()
    }

    /// Type `text` at the cursor: over the composition if one is open, else over the
    /// selection. Returns whether the text changed.
    pub fn insert(&mut self, text: &str) -> bool {
        let range = self.marked.clone().unwrap_or_else(|| self.selection());
        self.splice(range, text)
    }

    /// Put `text` in place of `range`, whatever the cursor and selection: the platform's
    /// explicit replacement range. Returns whether the text changed.
    pub fn replace(&mut self, range: Range<usize>, text: &str) -> bool {
        self.splice(self.clamped(range), text)
    }

    /// Insert pasted text as one line: a query has no lines, so each line break becomes
    /// a space. Returns whether the text changed.
    pub fn paste(&mut self, text: &str) -> bool {
        let flat = text.replace("\r\n", " ").replace(['\r', '\n'], " ");
        self.insert(&flat)
    }

    /// An input method's uncommitted text: `text` replaces `range`, or the composition
    /// so far, or the selection, and stays marked until the next composition or the
    /// commit. `selection` is the input method's selection within `text`, in bytes of
    /// `text`; without one the cursor sits after the text. Returns whether the text
    /// changed.
    pub fn compose(
        &mut self,
        range: Option<Range<usize>>,
        text: &str,
        selection: Option<Range<usize>>,
    ) -> bool {
        let range = range
            .map(|range| self.clamped(range))
            .or_else(|| self.marked.clone())
            .unwrap_or_else(|| self.selection());
        let start = range.start;
        let changed = self.splice(range, text);
        self.marked = (!text.is_empty()).then(|| start..start + text.len());
        if let Some(selection) = selection {
            let end = selection.end.min(text.len());
            let begin = selection.start.min(end);
            self.cursor = start + end;
            self.anchor = (begin != end).then_some(start + begin);
        }
        changed
    }

    /// The composition is over and its text stays as typed.
    pub fn unmark(&mut self) {
        self.marked = None;
    }

    /// Delete the selection, or from the cursor to where `motion` goes when nothing is
    /// selected. Returns whether the text changed.
    pub fn delete(&mut self, motion: Motion) -> bool {
        let selection = self.selection();
        let range = if selection.is_empty() {
            let target = self.target(motion);
            target.min(self.cursor)..target.max(self.cursor)
        } else {
            selection
        };
        self.splice(range, "")
    }

    /// Move the cursor where `motion` goes. With `extend` the selection grows from its
    /// anchor, set at the cursor when there is none. Without it a selection collapses to
    /// its start on a step left and its end on a step right, as a macOS field does, and
    /// any other motion simply moves the cursor.
    pub fn move_to(&mut self, motion: Motion, extend: bool) {
        if extend {
            self.anchor.get_or_insert(self.cursor);
            self.cursor = self.target(motion);
            return;
        }
        let selection = self.selection();
        self.cursor = match motion {
            Motion::PreviousGrapheme if !selection.is_empty() => selection.start,
            Motion::NextGrapheme if !selection.is_empty() => selection.end,
            _ => self.target(motion),
        };
        self.anchor = None;
    }

    pub fn select_all(&mut self) {
        self.anchor = Some(0);
        self.cursor = self.text.len();
    }

    /// Where `motion` lands from the cursor.
    fn target(&self, motion: Motion) -> usize {
        let cursor = self.cursor;
        match motion {
            Motion::PreviousGrapheme => self
                .text
                .grapheme_indices(true)
                .map(|(start, _)| start)
                .rfind(|start| *start < cursor)
                .unwrap_or(0),
            Motion::NextGrapheme => self
                .text
                .grapheme_indices(true)
                .map(|(start, _)| start)
                .find(|start| *start > cursor)
                .unwrap_or(self.text.len()),
            // The greatest word start before the cursor, so the spaces after a word go with
            // it, which is what Option-Backspace does in a Cocoa field.
            Motion::PreviousWord => self
                .text
                .unicode_word_indices()
                .map(|(start, _)| start)
                .rfind(|start| *start < cursor)
                .unwrap_or(0),
            Motion::NextWord => self
                .text
                .unicode_word_indices()
                .map(|(start, word)| start + word.len())
                .find(|end| *end > cursor)
                .unwrap_or(self.text.len()),
            Motion::LineStart => 0,
            Motion::LineEnd => self.text.len(),
        }
    }

    /// Put `text` in place of `range`, with the cursor after it and no selection or
    /// composition left. Returns whether the text changed.
    fn splice(&mut self, range: Range<usize>, text: &str) -> bool {
        let changed = self.text[range.clone()] != *text;
        self.text.replace_range(range.clone(), text);
        self.cursor = range.start + text.len();
        self.anchor = None;
        self.marked = None;
        changed
    }

    /// `range` pulled inside the text and onto char boundaries, so a range the platform
    /// computed from a stale view cannot split a char or run past the end.
    fn clamped(&self, range: Range<usize>) -> Range<usize> {
        let end = self.boundary_at_or_before(range.end);
        let start = self.boundary_at_or_before(range.start).min(end);
        start..end
    }

    fn boundary_at_or_before(&self, offset: usize) -> usize {
        let mut offset = offset.min(self.text.len());
        while !self.text.is_char_boundary(offset) {
            offset -= 1;
        }
        offset
    }

    /// A byte offset into the text as the platform counts it, in UTF-16 units.
    pub fn offset_to_utf16(&self, offset: usize) -> usize {
        self.text[..offset.min(self.text.len())]
            .chars()
            .map(char::len_utf16)
            .sum()
    }

    /// The platform's UTF-16 offset as a byte offset into the text.
    pub fn offset_from_utf16(&self, offset: usize) -> usize {
        utf16_to_byte(&self.text, offset)
    }

    pub fn range_to_utf16(&self, range: &Range<usize>) -> Range<usize> {
        self.offset_to_utf16(range.start)..self.offset_to_utf16(range.end)
    }

    pub fn range_from_utf16(&self, range: &Range<usize>) -> Range<usize> {
        self.offset_from_utf16(range.start)..self.offset_from_utf16(range.end)
    }
}

/// The byte offset in `text` at `offset` UTF-16 units from its start, or its length
/// when `offset` runs past it. Free of any input because an input method's selection is
/// relative to the composed text, not the whole.
pub fn utf16_to_byte(text: &str, offset: usize) -> usize {
    let mut seen = 0;
    for (byte, ch) in text.char_indices() {
        if seen >= offset {
            return byte;
        }
        seen += ch.len_utf16();
    }
    text.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// An input holding `text` with the cursor at `cursor`.
    fn at(text: &str, cursor: usize) -> Input {
        let mut input = Input::default();
        input.insert(text);
        input.cursor = cursor;
        input
    }

    /// An input holding `text` with `selection` selected, the cursor at its end.
    fn selected(text: &str, selection: Range<usize>) -> Input {
        let mut input = at(text, selection.end);
        input.anchor = Some(selection.start);
        input
    }

    #[test]
    fn insert_goes_at_the_cursor_and_over_the_selection() {
        let mut input = Input::default();
        assert!(input.insert("ac"));
        assert_eq!(input.text(), "ac");
        assert_eq!(input.cursor(), 2);
        input.cursor = 1;
        assert!(input.insert("b"));
        assert_eq!(input.text(), "abc");
        assert_eq!(input.cursor(), 2);
        let mut input = selected("abcd", 1..3);
        assert!(input.insert("X"));
        assert_eq!(input.text(), "aXd");
        assert_eq!(input.cursor(), 2);
        assert_eq!(input.selected_text(), None);
    }

    #[test]
    fn every_edit_says_whether_the_text_changed() {
        let mut input = Input::default();
        assert!(!input.insert(""));
        assert!(!input.delete(Motion::PreviousGrapheme));
        assert!(!input.delete(Motion::LineStart));
        assert!(!input.paste(""));
        assert!(!input.compose(None, "", None));
        assert!(input.insert("ab"));
        assert!(
            !input.delete(Motion::NextGrapheme),
            "nothing after the cursor"
        );
        assert!(!input.replace(0..2, "ab"), "the same text in place");
        assert!(input.replace(0..2, "ba"));
    }

    #[test]
    fn backspace_removes_one_grapheme() {
        let mut input = at("ae\u{301}", 4);
        assert!(input.delete(Motion::PreviousGrapheme));
        assert_eq!(input.text(), "a", "e with a combining acute goes as one");
        let family = "\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}";
        let mut input = at(&format!("x{family}"), 1 + family.len());
        assert!(input.delete(Motion::PreviousGrapheme));
        assert_eq!(input.text(), "x", "an emoji ZWJ sequence goes as one");
        assert_eq!(input.cursor(), 1);
    }

    #[test]
    fn delete_by_word_takes_the_word_and_the_spaces_after_it() {
        let mut input = at("foo bar  ", 9);
        assert!(input.delete(Motion::PreviousWord));
        assert_eq!(input.text(), "foo ");
        assert_eq!(input.cursor(), 4);
        let mut input = at("foo bar", 4);
        assert!(input.delete(Motion::PreviousWord));
        assert_eq!(input.text(), "bar");
        assert_eq!(input.cursor(), 0);
        let mut input = at("foo bar", 1);
        assert!(input.delete(Motion::NextWord));
        assert_eq!(input.text(), "f bar");
    }

    #[test]
    fn delete_to_the_line_start_keeps_the_tail() {
        let mut input = at("foo bar", 3);
        assert!(input.delete(Motion::LineStart));
        assert_eq!(input.text(), " bar");
        assert_eq!(input.cursor(), 0);
        let mut input = at("foo bar", 7);
        assert!(input.delete(Motion::LineStart));
        assert_eq!(input.text(), "", "at the end, the whole text goes");
    }

    #[test]
    fn any_delete_with_a_selection_removes_only_the_selection() {
        for motion in [
            Motion::PreviousGrapheme,
            Motion::NextGrapheme,
            Motion::PreviousWord,
            Motion::NextWord,
            Motion::LineStart,
            Motion::LineEnd,
        ] {
            let mut input = selected("foo bar baz", 4..7);
            assert!(input.delete(motion));
            assert_eq!(input.text(), "foo  baz", "{motion:?}");
            assert_eq!(input.cursor(), 4);
            assert_eq!(input.selected_text(), None);
        }
    }

    #[test]
    fn moves_by_grapheme_word_and_line() {
        let mut input = at("ae\u{301} bar", 0);
        input.move_to(Motion::NextGrapheme, false);
        assert_eq!(input.cursor(), 1);
        input.move_to(Motion::NextGrapheme, false);
        assert_eq!(input.cursor(), 4, "over the composed e");
        input.move_to(Motion::NextWord, false);
        assert_eq!(input.cursor(), 8);
        input.move_to(Motion::NextWord, false);
        assert_eq!(input.cursor(), 8, "stays at the end");
        input.move_to(Motion::PreviousWord, false);
        assert_eq!(input.cursor(), 5);
        input.move_to(Motion::PreviousGrapheme, false);
        assert_eq!(input.cursor(), 4);
        input.move_to(Motion::PreviousGrapheme, false);
        assert_eq!(input.cursor(), 1);
        input.move_to(Motion::LineEnd, false);
        assert_eq!(input.cursor(), 8);
        input.move_to(Motion::LineStart, false);
        assert_eq!(input.cursor(), 0);
        input.move_to(Motion::PreviousGrapheme, false);
        assert_eq!(input.cursor(), 0, "stays at the start");
    }

    #[test]
    fn extending_sets_the_anchor_and_reverses_across_it() {
        let mut input = at("foo bar", 4);
        input.move_to(Motion::NextWord, true);
        assert_eq!(input.selection(), 4..7);
        assert!(!input.reversed());
        assert_eq!(input.selected_text(), Some("bar"));
        input.move_to(Motion::LineStart, true);
        assert_eq!(input.selection(), 0..4);
        assert!(input.reversed());
        assert_eq!(input.selected_text(), Some("foo "));
        input.move_to(Motion::NextGrapheme, true);
        assert_eq!(input.selection(), 1..4);
        assert!(input.reversed());
    }

    #[test]
    fn a_step_without_extend_collapses_the_selection_to_its_end() {
        let mut input = selected("foo bar", 1..5);
        input.move_to(Motion::NextGrapheme, false);
        assert_eq!(input.cursor(), 5);
        assert_eq!(input.selected_text(), None);
        let mut input = selected("foo bar", 1..5);
        input.move_to(Motion::PreviousGrapheme, false);
        assert_eq!(input.cursor(), 1);
        assert_eq!(input.selected_text(), None);
        let mut input = selected("foo bar", 1..5);
        input.move_to(Motion::NextWord, false);
        assert_eq!(input.cursor(), 7, "a word motion jumps from the cursor");
        assert_eq!(input.selected_text(), None);
    }

    #[test]
    fn select_all_then_insert_replaces_everything() {
        let mut input = at("foo bar", 2);
        input.select_all();
        assert_eq!(input.selected_text(), Some("foo bar"));
        assert!(input.insert("x"));
        assert_eq!(input.text(), "x");
        assert_eq!(input.cursor(), 1);
    }

    #[test]
    fn paste_flattens_line_breaks_to_spaces() {
        let mut input = at("ab", 1);
        assert!(input.paste("x\r\ny\nz\rw"));
        assert_eq!(input.text(), "ax y z wb");
        assert_eq!(input.cursor(), 8);
    }

    #[test]
    fn compose_marks_the_text_and_places_the_cursor_from_its_selection() {
        let mut input = at("ab", 1);
        assert!(input.compose(None, "\u{3042}", Some(3..3)));
        assert_eq!(input.text(), "a\u{3042}b");
        assert_eq!(input.marked(), Some(1..4));
        assert_eq!(
            input.cursor(),
            4,
            "offset by the composition's start, not its end"
        );
        assert!(input.compose(None, "\u{3042}\u{3044}", None));
        assert_eq!(
            input.text(),
            "a\u{3042}\u{3044}b",
            "the second composition replaces the first"
        );
        assert_eq!(input.marked(), Some(1..7));
        assert_eq!(input.cursor(), 7);
        assert!(input.compose(None, "\u{611B}", Some(0..3)));
        assert_eq!(
            input.selection(),
            1..4,
            "the input method selected its candidate"
        );
        assert!(
            !input.insert("\u{611B}"),
            "the commit is the composed text, so nothing changed"
        );
        assert_eq!(
            input.text(),
            "a\u{611B}b",
            "the commit goes over the composition"
        );
        assert_eq!(input.marked(), None);
        assert_eq!(input.cursor(), 4);
    }

    #[test]
    fn an_empty_composition_clears_the_mark_and_unmark_keeps_the_text() {
        let mut input = at("ab", 2);
        input.compose(None, "xy", None);
        assert_eq!(input.marked(), Some(2..4));
        input.unmark();
        assert_eq!(input.marked(), None);
        assert_eq!(input.text(), "abxy");
        input.compose(Some(2..4), "", None);
        assert_eq!(input.text(), "ab");
        assert_eq!(input.marked(), None);
    }

    #[test]
    fn replace_takes_an_explicit_range_and_clamps_it() {
        let mut input = at("abcd", 0);
        assert!(input.replace(1..3, "X"));
        assert_eq!(input.text(), "aXd");
        assert_eq!(input.cursor(), 2);
        assert!(input.replace(2..10, "!"));
        assert_eq!(input.text(), "aX!", "a range past the end stops at the end");
        let mut input = at("a\u{1F600}b", 0);
        assert!(
            input.replace(2..3, "x"),
            "inside the emoji: pulled back onto boundaries"
        );
        assert_eq!(input.text(), "ax\u{1F600}b");
    }

    #[test]
    fn utf16_offsets_round_trip_on_text_beyond_the_basic_plane() {
        let input = at("a\u{1D11E}b", 0);
        assert_eq!(input.offset_to_utf16(0), 0);
        assert_eq!(input.offset_to_utf16(1), 1);
        assert_eq!(input.offset_to_utf16(5), 3);
        assert_eq!(input.offset_to_utf16(6), 4);
        assert_eq!(input.offset_from_utf16(3), 5);
        assert_eq!(input.offset_from_utf16(4), 6);
        assert_eq!(input.offset_from_utf16(9), 6, "past the end is the end");
        assert_eq!(input.range_to_utf16(&(1..6)), 1..4);
        assert_eq!(input.range_from_utf16(&(1..4)), 1..6);
        let mut input = at("x", 1);
        input.compose(None, "\u{1D11E}\u{3042}", None);
        assert_eq!(input.range_to_utf16(&input.marked().unwrap()), 1..4);
        assert_eq!(utf16_to_byte("\u{1D11E}\u{3042}", 2), 4);
        assert_eq!(utf16_to_byte("\u{1D11E}\u{3042}", 3), 7);
    }
}
