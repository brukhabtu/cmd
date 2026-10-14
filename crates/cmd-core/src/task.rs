//! Lines a plugin starts: the reader's classification and the `task` event (decision 12),
//! which also knows the `notify` event ([`crate::notice`], decision 13).
//!
//! A line from a plugin with an `event` key and no `id` is an event; any other line is
//! a response, or not a protocol message, and the call in flight decides which. Both
//! halves here are pure: the host's reader thread calls [`classify`] on each line as it
//! arrives, and the thread and the pipe are the shell around it.

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::notice::{Notice, decode_notice};

/// The name of the capability a plugin needs the host to name before it reports a task.
pub const CAPABILITY: &str = "tasks";

/// The longest text the host keeps for a task's `id`, `label` or `detail`, in characters.
pub const MAX_TEXT: usize = 160;

/// Where a task stands.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskState {
    Running,
    Done,
    Failed,
}

/// Background work a plugin reports: the latest line per `id` is the task's state.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Task {
    /// Names the task within its plugin, so a later line replaces an earlier one.
    pub id: String,
    /// Short text for the person.
    pub label: String,
    pub state: TaskState,
    /// How far along, with `total`; `done` is at most `total`. A task with neither has no
    /// progress to show.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub done: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub total: Option<u64>,
    /// One line of text about what it is doing now.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
}

/// What a line from a plugin is, before any call has looked at it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Incoming {
    /// A line the plugin started. It never reaches a call.
    Event(Event),
    /// Any other line: a response, or not a protocol message. It goes to the call in
    /// flight, which decodes it, exactly as before events existed.
    Other,
}

/// A line the plugin started, read.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    Task(Task),
    /// A notice for the person (decision 13).
    Notice(Notice),
    /// An event the host could not use, and why. The host notes it as trouble for the
    /// plugin and drops the line; it never fails a call.
    Invalid(String),
}

/// Sort one line from a plugin: an object with an `event` key and no `id` is an event,
/// everything else is [`Incoming::Other`]. A line that is not JSON stays `Other`, so the
/// call reports it as not a protocol message.
pub fn classify(line: &str) -> Incoming {
    let Ok(Value::Object(object)) = serde_json::from_str::<Value>(line) else {
        return Incoming::Other;
    };
    if object.contains_key("id") {
        return Incoming::Other;
    }
    let Some(name) = object.get("event") else {
        return Incoming::Other;
    };
    let event = match name.as_str() {
        Some("task") => match object.get("params") {
            Some(params) => decode_task(params).map_or_else(Event::Invalid, Event::Task),
            None => Event::Invalid("a task event has no params".to_string()),
        },
        Some("notify") => match object.get("params") {
            Some(params) => decode_notice(params).map_or_else(Event::Invalid, Event::Notice),
            None => Event::Invalid("a notify event has no params".to_string()),
        },
        Some(other) => Event::Invalid(format!("unknown event {:?}", clean(other))),
        None => Event::Invalid("an event's name must be text".to_string()),
    };
    Incoming::Event(event)
}

/// Read the params of a `task` event.
///
/// `id`, `label` and `state` are required. `done` and `total` are given together or not
/// at all, whole numbers with `done` at most `total`. Text is cleaned (see [`clean`]), and
/// a label or id left empty by it is no label or id. Fields this host does not know are
/// ignored.
///
/// # Errors
///
/// A message naming the first thing wrong, for the host's note about the plugin.
pub fn decode_task(params: &Value) -> Result<Task, String> {
    let Some(params) = params.as_object() else {
        return Err("a task's params must be an object".to_string());
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
    let count = |name: &str| -> Result<Option<u64>, String> {
        match field(name) {
            None => Ok(None),
            Some(value) => value
                .as_u64()
                .map(Some)
                .ok_or_else(|| format!("{name} must be a whole number, 0 or more")),
        }
    };
    let id = required("id")?;
    let label = required("label")?;
    let state = match field("state").and_then(Value::as_str) {
        Some("running") => TaskState::Running,
        Some("done") => TaskState::Done,
        Some("failed") => TaskState::Failed,
        Some(other) => {
            return Err(format!(
                "state must be running, done or failed, not {:?}",
                clean(other)
            ));
        }
        None => return Err("state is required, one of running, done or failed".to_string()),
    };
    let (done, total) = (count("done")?, count("total")?);
    match (done, total) {
        (Some(done), Some(total)) if done > total => {
            return Err(format!("done ({done}) is more than total ({total})"));
        }
        (Some(_), None) => return Err("done needs a total".to_string()),
        (None, Some(_)) => return Err("total needs a done".to_string()),
        _ => {}
    }
    let detail = text("detail")?.filter(|detail| !detail.is_empty());
    Ok(Task {
        id,
        label,
        state,
        done,
        total,
        detail,
    })
}

/// Text as the person sees it: whitespace controls become a space, every other control
/// character is dropped, the ends are trimmed, and what is left is cut at [`MAX_TEXT`]
/// characters.
pub fn clean(text: &str) -> String {
    let spaced: String = text
        .chars()
        .filter_map(|c| match c {
            '\t' | '\n' | '\r' => Some(' '),
            c if c.is_control() => None,
            c => Some(c),
        })
        .collect();
    spaced.trim().chars().take(MAX_TEXT).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn event(params: &Value) -> Incoming {
        classify(&json!({"event": "task", "params": params}).to_string())
    }

    fn task(params: &Value) -> Task {
        match event(params) {
            Incoming::Event(Event::Task(task)) => task,
            other => panic!("expected a task, got {other:?}"),
        }
    }

    fn invalid(params: &Value) -> String {
        match event(params) {
            Incoming::Event(Event::Invalid(why)) => why,
            other => panic!("expected an invalid event, got {other:?}"),
        }
    }

    #[test]
    fn a_line_with_an_event_and_no_id_is_an_event() {
        let line = r#"{"event": "task", "params": {"id": "index", "label": "Indexing notes", "state": "running", "done": 120, "total": 900, "detail": "meetings/2026"}}"#;
        assert_eq!(
            classify(line),
            Incoming::Event(Event::Task(Task {
                id: "index".into(),
                label: "Indexing notes".into(),
                state: TaskState::Running,
                done: Some(120),
                total: Some(900),
                detail: Some("meetings/2026".into()),
            }))
        );
    }

    #[test]
    fn every_other_line_goes_to_the_call() {
        for line in [
            r#"{"id": 1, "result": {}}"#,
            r#"{"id": 0, "error": {"code": "x", "message": "y"}}"#,
            r#"{"event": "task", "id": 3, "params": {}}"#,
            r#"{"result": {}}"#,
            r"{}",
            r"[1]",
            r#""event""#,
            "debugging...",
            "",
        ] {
            assert_eq!(classify(line), Incoming::Other, "{line}");
        }
    }

    #[test]
    fn a_task_needs_an_id_a_label_and_a_state() {
        assert!(invalid(&json!({"label": "L", "state": "running"})).contains("id is required"));
        assert!(invalid(&json!({"id": "i", "state": "running"})).contains("label is required"));
        assert!(invalid(&json!({"id": "i", "label": "L"})).contains("state is required"));
        assert!(invalid(&json!({"id": "i", "label": "L", "state": 3})).contains("state is"));
        assert!(
            invalid(&json!({"id": "i", "label": "L", "state": "paused"})).contains("\"paused\"")
        );
        assert!(
            invalid(&json!({"id": "i", "label": 4, "state": "done"}))
                .contains("label must be text")
        );
        assert!(
            invalid(&json!({"id": "i", "label": " \u{7} ", "state": "done"}))
                .contains("label is required"),
            "a label with nothing left after cleaning is none"
        );
        assert!(invalid(&json!("task")).contains("params must be an object"));
    }

    #[test]
    fn all_three_states_decode() {
        for (name, state) in [
            ("running", TaskState::Running),
            ("done", TaskState::Done),
            ("failed", TaskState::Failed),
        ] {
            assert_eq!(
                task(&json!({"id": "i", "label": "L", "state": name})).state,
                state
            );
        }
    }

    #[test]
    fn progress_is_whole_numbers_with_done_at_most_total_and_both_or_neither() {
        let with = |extra: Value| {
            let mut params = json!({"id": "i", "label": "L", "state": "running"});
            for (key, value) in extra.as_object().unwrap() {
                params[key] = value.clone();
            }
            params
        };
        let finished = task(&with(json!({"done": 900, "total": 900})));
        assert_eq!((finished.done, finished.total), (Some(900), Some(900)));
        let none = task(&with(json!({"done": null})));
        assert_eq!((none.done, none.total), (None, None));
        assert!(invalid(&with(json!({"done": 901, "total": 900}))).contains("more than total"));
        assert!(invalid(&with(json!({"done": -1, "total": 9}))).contains("done must be"));
        assert!(invalid(&with(json!({"done": 1.5, "total": 9}))).contains("done must be"));
        assert!(invalid(&with(json!({"done": "1", "total": 9}))).contains("done must be"));
        assert!(invalid(&with(json!({"done": 1}))).contains("needs a total"));
        assert!(invalid(&with(json!({"total": 1}))).contains("needs a done"));
    }

    #[test]
    fn text_is_cleaned_of_control_characters_and_cut_at_160() {
        let long = "x".repeat(500);
        let t = task(&json!({
            "id": "i",
            "label": "Index\u{0}ing\u{1b}[31m notes\nnow",
            "state": "running",
            "detail": long,
        }));
        assert_eq!(t.label, "Indexing[31m notes now");
        assert_eq!(t.detail.as_deref().map(|d| d.chars().count()), Some(160));
        let wide = task(&json!({"id": "i", "label": "é".repeat(200), "state": "done"}));
        assert_eq!(
            wide.label.chars().count(),
            160,
            "cut by characters, not bytes"
        );
    }

    #[test]
    fn an_empty_detail_is_none_and_unknown_fields_are_ignored() {
        let t = task(&json!({"id": "i", "label": "L", "state": "done", "detail": "  ", "x": 1}));
        assert_eq!(t.detail, None);
    }

    #[test]
    fn an_event_that_is_not_a_task_is_invalid_and_never_a_response() {
        for line in [
            r#"{"event": "spinner", "params": {}}"#,
            r#"{"event": 3}"#,
            r#"{"event": "task"}"#,
            r#"{"event": "notify"}"#,
        ] {
            assert!(
                matches!(classify(line), Incoming::Event(Event::Invalid(_))),
                "{line}"
            );
        }
    }

    #[test]
    fn a_notify_event_is_a_notice_or_invalid_and_names_stay_exact() {
        let line =
            r#"{"event": "notify", "params": {"id": "a", "title": "T", "body": "B", "open": "x"}}"#;
        let Incoming::Event(Event::Notice(notice)) = classify(line) else {
            panic!("expected a notice");
        };
        assert_eq!(notice.id, "a");
        assert_eq!(notice.open.as_deref(), Some("x"));
        let bad = classify(r#"{"event": "notify", "params": {"id": "a"}}"#);
        assert!(matches!(&bad, Incoming::Event(Event::Invalid(why)) if why.contains("title")));
        let with_id =
            classify(r#"{"event": "notify", "id": 2, "params": {"id": "a", "title": "T"}}"#);
        assert_eq!(with_id, Incoming::Other, "a line with an id is a response");
        let unknown = classify(r#"{"event": "notification", "params": {}}"#);
        assert!(
            matches!(&unknown, Incoming::Event(Event::Invalid(why)) if why.contains("unknown event"))
        );
    }

    #[test]
    fn a_task_serialises_without_its_empty_fields() {
        let t = task(&json!({"id": "i", "label": "L", "state": "failed"}));
        assert_eq!(
            serde_json::to_value(&t).unwrap(),
            json!({"id": "i", "label": "L", "state": "failed"})
        );
    }
}
