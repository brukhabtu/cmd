//! The `notify` event: a plugin tells the person something (decision 13).
//!
//! Three pure pieces, with no thread, pipe or clock of their own: [`decode_notice`] reads
//! the params of the line, [`RateLimit`] decides which of a plugin's notices the host
//! keeps, and [`Recent`] is the list of the last notices across plugins. The reader
//! thread classifies the line ([`crate::task::classify`]), the host's board applies the
//! rate limit, and the window feeds the list.

use std::collections::VecDeque;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::task::clean;

/// The name of the capability a plugin needs the host to name before it sends a notice.
pub const CAPABILITY: &str = "notify";

/// How many notices the host keeps, across plugins.
pub const RECENT: usize = 20;

/// The most notices of one plugin the host passes on in one [`RATE_WINDOW`].
pub const RATE_COUNT: usize = 5;

/// The span over which a plugin may send [`RATE_COUNT`] notices.
pub const RATE_WINDOW: Duration = Duration::from_secs(10);

/// Something a plugin tells the person.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Notice {
    /// Names the thing within its plugin, so a later notice replaces an earlier one in the
    /// recent list.
    pub id: String,
    pub title: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub body: Option<String>,
    /// A target the host opens when the notice is chosen, as it opens an `Open` effect.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open: Option<String>,
}

/// Read the params of a `notify` event.
///
/// `id` and `title` are required and must have text left after cleaning (see
/// [`crate::task::clean`]). `body` is optional text, cleaned the same way and none when
/// nothing is left. `open` is optional text and must not be empty; it is kept as sent,
/// because cutting a target breaks it. Fields this host does not know are ignored.
///
/// # Errors
///
/// A message naming the first thing wrong, for the host's note about the plugin.
pub fn decode_notice(params: &Value) -> Result<Notice, String> {
    let Some(params) = params.as_object() else {
        return Err("a notify event's params must be an object".to_string());
    };
    let field = |name: &str| params.get(name).filter(|value| !value.is_null());
    let text = |name: &str| -> Result<Option<String>, String> {
        match field(name) {
            None => Ok(None),
            Some(Value::String(text)) => Ok(Some(clean(text))),
            Some(_) => Err(format!("{name} must be text")),
        }
    };
    let required = |name: &str| -> Result<String, String> {
        match text(name)? {
            Some(text) if !text.is_empty() => Ok(text),
            _ => Err(format!("{name} is required")),
        }
    };
    let id = required("id")?;
    let title = required("title")?;
    let body = text("body")?.filter(|body| !body.is_empty());
    let open = match field("open") {
        None => None,
        Some(Value::String(target)) if !target.trim().is_empty() => Some(target.clone()),
        Some(Value::String(_)) => return Err("open must not be empty".to_string()),
        Some(_) => return Err("open must be text".to_string()),
    };
    Ok(Notice {
        id,
        title,
        body,
        open,
    })
}

/// What to do with a notice a plugin sent.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    /// Pass it on.
    Keep,
    /// Drop it. `note` is true for the first drop in a window, which is the one the host
    /// says something about; the rest of that window's drops are silent.
    Drop { note: bool },
}

/// A plugin's allowance: at most [`RATE_COUNT`] notices in any [`RATE_WINDOW`].
///
/// The caller passes the time, so a test needs no clock.
#[derive(Debug, Default)]
pub struct RateLimit {
    /// When the notices that were kept arrived, oldest first.
    kept: VecDeque<Instant>,
    /// When the host last said it was dropping.
    noted: Option<Instant>,
}

impl RateLimit {
    /// Judge a notice that arrives at `now`. Times must not go backwards.
    pub fn check(&mut self, now: Instant) -> Verdict {
        while self
            .kept
            .front()
            .is_some_and(|at| now.saturating_duration_since(*at) >= RATE_WINDOW)
        {
            self.kept.pop_front();
        }
        if self.kept.len() < RATE_COUNT {
            self.kept.push_back(now);
            return Verdict::Keep;
        }
        let note = self
            .noted
            .is_none_or(|at| now.saturating_duration_since(at) >= RATE_WINDOW);
        if note {
            self.noted = Some(now);
        }
        Verdict::Drop { note }
    }
}

/// A notice and the plugin (by index) that sent it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Recorded {
    pub plugin: usize,
    pub notice: Notice,
}

/// The last [`RECENT`] notices across plugins, newest first. Memory only: it starts empty
/// with the app and a plugin's restart leaves it alone, because what was delivered is
/// history.
#[derive(Debug, Default, Clone)]
pub struct Recent {
    list: VecDeque<Recorded>,
}

impl Recent {
    /// Record a notice as the newest. One with the same plugin and id replaces the earlier
    /// one, which leaves its place; the oldest falls off past [`RECENT`].
    pub fn push(&mut self, plugin: usize, notice: Notice) {
        self.list
            .retain(|held| !(held.plugin == plugin && held.notice.id == notice.id));
        self.list.push_front(Recorded { plugin, notice });
        self.list.truncate(RECENT);
    }

    /// The notices, newest first.
    pub fn iter(&self) -> impl Iterator<Item = &Recorded> {
        self.list.iter()
    }

    pub fn len(&self) -> usize {
        self.list.len()
    }

    pub fn is_empty(&self) -> bool {
        self.list.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn notice(id: &str) -> Notice {
        Notice {
            id: id.into(),
            title: format!("title {id}"),
            body: None,
            open: None,
        }
    }

    fn ids(recent: &Recent) -> Vec<(usize, &str)> {
        recent
            .iter()
            .map(|held| (held.plugin, held.notice.id.as_str()))
            .collect()
    }

    fn why(params: &Value) -> String {
        decode_notice(params).unwrap_err()
    }

    #[test]
    fn a_full_notice_decodes() {
        let params = json!({"id": "PROJ-12", "title": "PROJ-12 moved", "body": "In Review", "open": "https://example.test/PROJ-12"});
        assert_eq!(
            decode_notice(&params),
            Ok(Notice {
                id: "PROJ-12".into(),
                title: "PROJ-12 moved".into(),
                body: Some("In Review".into()),
                open: Some("https://example.test/PROJ-12".into()),
            })
        );
    }

    #[test]
    fn a_notice_needs_an_id_and_a_title_with_text_in_them() {
        assert!(why(&json!({"title": "T"})).contains("id is required"));
        assert!(why(&json!({"id": "i"})).contains("title is required"));
        assert!(why(&json!({"id": "", "title": "T"})).contains("id is required"));
        assert!(why(&json!({"id": "i", "title": " \u{7} "})).contains("title is required"));
        assert!(why(&json!({"id": 3, "title": "T"})).contains("id must be text"));
        assert!(why(&json!({"id": "i", "title": ["T"]})).contains("title must be text"));
        assert!(why(&json!("notify")).contains("params must be an object"));
    }

    #[test]
    fn text_is_cleaned_and_cut_at_160_but_the_open_target_is_kept_whole() {
        let target = format!("https://example.test/{}", "x".repeat(300));
        let n = decode_notice(&json!({
            "id": "i",
            "title": "Moved\u{0}\u{1b}[31m\nnow",
            "body": "é".repeat(400),
            "open": target,
        }))
        .unwrap();
        assert_eq!(n.title, "Moved[31m now");
        assert_eq!(n.body.as_deref().map(|b| b.chars().count()), Some(160));
        assert_eq!(n.open.as_deref(), Some(target.as_str()));
        let long_title = decode_notice(&json!({"id": "i", "title": "t".repeat(500)})).unwrap();
        assert_eq!(long_title.title.chars().count(), 160);
    }

    #[test]
    fn body_and_open_are_optional_but_not_wrong() {
        let plain =
            decode_notice(&json!({"id": "i", "title": "T", "body": " ", "open": null, "x": 1}));
        assert_eq!(plain, Ok(notice_with_title("i", "T")));
        assert!(why(&json!({"id": "i", "title": "T", "body": 3})).contains("body must be text"));
        assert!(why(&json!({"id": "i", "title": "T", "open": 3})).contains("open must be text"));
        assert!(
            why(&json!({"id": "i", "title": "T", "open": "  "})).contains("open must not be empty")
        );
    }

    fn notice_with_title(id: &str, title: &str) -> Notice {
        Notice {
            id: id.into(),
            title: title.into(),
            body: None,
            open: None,
        }
    }

    #[test]
    fn a_plugin_may_send_five_in_ten_seconds_and_the_sixth_is_dropped_with_one_note() {
        let start = Instant::now();
        let mut limit = RateLimit::default();
        for n in 0..5 {
            assert_eq!(limit.check(start + Duration::from_secs(n)), Verdict::Keep);
        }
        assert_eq!(
            limit.check(start + Duration::from_secs(5)),
            Verdict::Drop { note: true }
        );
        for n in 6..10 {
            assert_eq!(
                limit.check(start + Duration::from_secs(n)),
                Verdict::Drop { note: false },
                "one note per window of dropping"
            );
        }
    }

    #[test]
    fn the_window_slides_and_a_new_window_of_dropping_is_noted_again() {
        let start = Instant::now();
        let at = |ms: u64| start + Duration::from_millis(ms);
        let mut limit = RateLimit::default();
        for _ in 0..5 {
            assert_eq!(limit.check(at(0)), Verdict::Keep);
        }
        assert_eq!(limit.check(at(9_999)), Verdict::Drop { note: true });
        // Ten seconds after the five, there is room again.
        for _ in 0..5 {
            assert_eq!(limit.check(at(10_000)), Verdict::Keep);
        }
        assert_eq!(limit.check(at(10_002)), Verdict::Drop { note: false });
        // The note was at 9.999 s; ten seconds on, a drop is a new window of dropping.
        for _ in 0..5 {
            assert_eq!(limit.check(at(20_000)), Verdict::Keep);
        }
        assert_eq!(limit.check(at(20_001)), Verdict::Drop { note: true });
    }

    #[test]
    fn dropped_notices_do_not_count_against_the_next_window() {
        let start = Instant::now();
        let mut limit = RateLimit::default();
        for _ in 0..1000 {
            limit.check(start);
        }
        assert_eq!(
            limit.check(start + RATE_WINDOW),
            Verdict::Keep,
            "only the five that were kept are remembered"
        );
    }

    #[test]
    fn the_recent_list_is_newest_first_and_keeps_twenty() {
        let mut recent = Recent::default();
        for n in 0..25 {
            recent.push(0, notice(&format!("n{n:02}")));
        }
        assert_eq!(recent.len(), RECENT);
        let held = ids(&recent);
        assert_eq!(held.first(), Some(&(0, "n24")));
        assert_eq!(held.last(), Some(&(0, "n05")));
    }

    #[test]
    fn a_notice_with_the_same_plugin_and_id_replaces_the_earlier_and_moves_to_newest() {
        let mut recent = Recent::default();
        recent.push(0, notice("a"));
        recent.push(1, notice("a"));
        recent.push(0, notice("b"));
        let mut again = notice("a");
        again.title = "newer".into();
        recent.push(0, again);
        assert_eq!(ids(&recent), [(0, "a"), (0, "b"), (1, "a")]);
        assert_eq!(recent.iter().next().unwrap().notice.title, "newer");
    }

    #[test]
    fn replacing_a_notice_does_not_push_another_off_the_end() {
        let mut recent = Recent::default();
        for n in 0..RECENT {
            recent.push(0, notice(&format!("n{n:02}")));
        }
        recent.push(0, notice("n00"));
        assert_eq!(recent.len(), RECENT);
        assert_eq!(ids(&recent).first(), Some(&(0, "n00")));
        assert!(ids(&recent).contains(&(0, "n01")));
    }
}
