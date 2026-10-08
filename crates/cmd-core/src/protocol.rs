//! Plugin protocol v1: newline-delimited JSON over a plugin's stdin and stdout.
//!
//! The host writes one [`Request`] per line and the plugin answers with one
//! [`Response`] per line carrying the same `id`. The specification is
//! `docs/plugin-protocol.md`; this module is the Rust side of it, and
//! `cmd_sdk.protocol` is the Python side. `docs/plugin-protocol.golden.json` holds
//! exchanges both sides are tested against.

use std::ops::RangeInclusive;

use serde::de::DeserializeOwned;
use serde::{Deserialize, Deserializer, Serialize};
use thiserror::Error;

/// The protocol version this crate speaks: what the host sends in `describe`.
pub const VERSION: u32 = 1;

/// The versions a plugin may answer `describe` with and still be loaded: every one from 0
/// to this crate's own. A plugin answers with the lower of the host's version and its own,
/// so an older plugin answers with its own and a newer one with the host's. Dropping an
/// old version takes a decision (decision 9).
pub const ACCEPTED: RangeInclusive<u32> = 0..=VERSION;

/// The capabilities this host names in `describe`: behaviour a plugin may use only when
/// the host names it, because without it the plugin falls back to something else
/// (decision 9). None is built yet, so the list is empty.
pub const CAPABILITIES: &[&str] = &[];

/// One call from the host to a plugin.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Request {
    pub id: u64,
    #[serde(flatten)]
    pub method: Method,
}

/// The three things a host can ask of a plugin.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "method", content = "params", rename_all = "snake_case")]
pub enum Method {
    /// Handshake: the host's version and the capabilities it names, where a missing list
    /// is an empty one. The plugin answers with a [`Description`] whose `protocol` is the
    /// lower of the host's version and its own.
    Describe {
        protocol: u32,
        #[serde(default)]
        capabilities: Vec<String>,
    },
    /// The text the person typed, already stripped of the plugin's keyword.
    /// The plugin answers with [`Items`].
    Query { text: String },
    /// The person chose an item and an action. The plugin answers with [`Ran`].
    Run { item: String, action: String },
}

impl Method {
    /// The handshake this host sends: its [`VERSION`] and its [`CAPABILITIES`].
    pub fn describe() -> Self {
        Method::Describe {
            protocol: VERSION,
            capabilities: CAPABILITIES.iter().map(ToString::to_string).collect(),
        }
    }
}

/// What a plugin says about itself in the handshake.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Description {
    pub name: String,
    pub version: String,
    /// The version the plugin speaks with this host: the lower of the two.
    pub protocol: u32,
    /// With a keyword, the plugin sees only queries that start with it.
    /// Without one, it sees every query.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub keyword: Option<String>,
}

/// What a row shows beside its text. The window resolves it; a plugin only names it.
/// Hash because the window caches a resolved icon by this value.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Icon {
    /// The icon the system shows for whatever sits at an absolute path: an application
    /// bundle, a document, a folder.
    Path { path: String },
    /// A system symbol by name, drawn in the row's text colour.
    Symbol { name: String },
}

/// One row in the result list.
///
/// Decoding forgives what can cost only part of a row: an icon the host cannot read is
/// no icon, and a score outside `0.0..=1.0` is clamped into it. Anything else wrong
/// loses the item, and [`Items`] keeps the rest.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Item {
    pub id: String,
    pub title: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subtitle: Option<String>,
    /// Confidence in `0.0..=1.0` for fuzzy matches. Leave it out for a definite answer.
    /// A score outside the range is clamped when it is decoded, so it cannot outrank 1.0.
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "clamped_score"
    )]
    pub score: Option<f64>,
    /// The first action is the one Enter runs. Empty means the host runs
    /// [`crate::state::DEFAULT_ACTION`].
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub actions: Vec<Action>,
    /// Since version 1. A plugin that speaks version 0 never sets it. An icon of a kind
    /// this host does not know, or of a known kind in the wrong shape, decodes as none.
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "readable_icon"
    )]
    pub icon: Option<Icon>,
}

/// A score as sent, clamped into `0.0..=1.0`. JSON has no NaN to clamp.
fn clamped_score<'de, D: Deserializer<'de>>(deserializer: D) -> Result<Option<f64>, D::Error> {
    Ok(Option::<f64>::deserialize(deserializer)?.map(|score| score.clamp(0.0, 1.0)))
}

/// The icon if this host can read it, and none otherwise: the row keeps its text.
fn readable_icon<'de, D: Deserializer<'de>>(deserializer: D) -> Result<Option<Icon>, D::Error> {
    let value = serde_json::Value::deserialize(deserializer)?;
    Ok(serde_json::from_value(value).ok())
}

/// Something that can be done with an item.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Action {
    pub id: String,
    pub title: String,
}

/// The answer to `query`, decoded item by item: an item that does not decode is left
/// out on its own, and why is kept in `dropped` so the host can say so.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(from = "WireItems")]
pub struct Items {
    pub items: Vec<Item>,
    /// Why each item that could not be decoded was left out, in the answer's order. The
    /// host's own note: it never goes on the wire.
    #[serde(skip)]
    pub dropped: Vec<String>,
}

impl Items {
    /// What to tell the person when items were left out, or `None` when none were.
    pub fn dropped_note(&self) -> Option<String> {
        let count = self.dropped.len();
        let noun = if count == 1 { "item" } else { "items" };
        (count > 0).then(|| {
            format!(
                "left out {count} {noun} it could not read: {}",
                self.dropped.join("; ")
            )
        })
    }
}

/// The answer to `query` as it arrives: a list whose elements are decoded one by one.
#[derive(Deserialize)]
struct WireItems {
    items: Vec<serde_json::Value>,
}

impl From<WireItems> for Items {
    fn from(wire: WireItems) -> Self {
        let mut items = Vec::with_capacity(wire.items.len());
        let mut dropped = Vec::new();
        for (index, value) in wire.items.into_iter().enumerate() {
            let position = index + 1;
            let label = match value.get("id").and_then(serde_json::Value::as_str) {
                Some(id) => format!("item {position} ({id:?})"),
                None => format!("item {position}"),
            };
            match serde_json::from_value::<Item>(value) {
                Ok(item) => items.push(item),
                Err(error) => dropped.push(format!("{label}: {error}")),
            }
        }
        Items { items, dropped }
    }
}

/// What the host does after an action ran. The plugin returns it; the host performs it.
/// An effect of a kind this host does not know fails the whole answer: effects stay
/// versioned (decision 9), and the host never guesses at one.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Effect {
    /// Hide the launcher.
    Close,
    /// Put text on the clipboard, then hide.
    Copy { text: String },
    /// Open a URL or a path with the system handler, then hide.
    Open { target: String },
    /// Keep the launcher open and show a message.
    Show { text: String },
}

/// The answer to `run`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Ran {
    pub effect: Effect,
}

/// A failure the plugin reports instead of a result.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Error)]
#[error("{code}: {message}")]
pub struct PluginError {
    pub code: String,
    pub message: String,
}

/// One line from the plugin: the id of the request it answers, and a result or an error.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Response {
    pub id: u64,
    #[serde(flatten)]
    pub outcome: Outcome,
}

/// A response carries exactly one of these.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Result(serde_json::Value),
    Error(PluginError),
}

/// Why a line from a plugin could not be turned into the value the host asked for.
#[derive(Debug, Error)]
pub enum DecodeError {
    #[error("not a protocol message: {0}")]
    Json(#[from] serde_json::Error),
    #[error("the plugin reported an error: {0}")]
    Plugin(#[source] PluginError),
}

/// Serialise a request as one line, newline included.
///
/// # Panics
///
/// Never for the types in this module; serialising them cannot fail.
pub fn encode_request(request: &Request) -> String {
    let mut line = serde_json::to_string(request).expect("protocol types serialise");
    line.push('\n');
    line
}

/// Parse one line from a plugin.
pub fn decode_response(line: &str) -> Result<Response, DecodeError> {
    Ok(serde_json::from_str(line)?)
}

/// Turn a response into the typed result the request expects.
pub fn result<T: DeserializeOwned>(response: Response) -> Result<T, DecodeError> {
    match response.outcome {
        Outcome::Result(value) => Ok(serde_json::from_value(value)?),
        Outcome::Error(error) => Err(DecodeError::Plugin(error)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_host_loads_every_version_from_zero_to_its_own() {
        assert_eq!(ACCEPTED, 0..=VERSION);
    }

    #[test]
    fn requests_are_one_json_line_with_method_and_params() {
        let line = encode_request(&Request {
            id: 7,
            method: Method::Query { text: "2+2".into() },
        });
        assert_eq!(
            line,
            "{\"id\":7,\"method\":\"query\",\"params\":{\"text\":\"2+2\"}}\n"
        );
    }

    #[test]
    fn describe_carries_the_version_and_the_capabilities_even_when_there_are_none() {
        let line = encode_request(&Request {
            id: 1,
            method: Method::describe(),
        });
        assert_eq!(
            line,
            "{\"id\":1,\"method\":\"describe\",\"params\":{\"protocol\":1,\"capabilities\":[]}}\n"
        );
    }

    #[test]
    fn a_describe_without_capabilities_names_none() {
        let request: Request =
            serde_json::from_str(r#"{"id": 1, "method": "describe", "params": {"protocol": 0}}"#)
                .unwrap();
        assert_eq!(
            request.method,
            Method::Describe {
                protocol: 0,
                capabilities: vec![]
            }
        );
    }

    #[test]
    fn a_result_decodes_into_the_expected_type() {
        let line = r#"{"id": 7, "result": {"items": [{"id": "4", "title": "4"}]}}"#;
        let response = decode_response(line).unwrap();
        assert_eq!(response.id, 7);
        let items: Items = result(response).unwrap();
        assert_eq!(items.items[0].title, "4");
        assert_eq!(items.items[0].actions, vec![]);
        assert_eq!(items.items[0].score, None);
        assert_eq!(items.items[0].icon, None);
        assert_eq!(items.dropped, Vec::<String>::new());
        assert_eq!(items.dropped_note(), None);
    }

    #[test]
    fn an_item_may_carry_a_path_or_a_symbol_icon() {
        let line = r#"{"items": [
            {"id": "a", "title": "a", "icon": {"kind": "path", "path": "/Applications/Safari.app"}},
            {"id": "b", "title": "b", "icon": {"kind": "symbol", "name": "globe"}},
            {"id": "c", "title": "c"}
        ]}"#;
        let items: Items = serde_json::from_str(line).unwrap();
        assert_eq!(
            items.items[0].icon,
            Some(Icon::Path {
                path: "/Applications/Safari.app".into()
            })
        );
        assert_eq!(
            items.items[1].icon,
            Some(Icon::Symbol {
                name: "globe".into()
            })
        );
        assert_eq!(items.items[2].icon, None);
        assert_eq!(
            serde_json::to_string(&items.items[1].icon).unwrap(),
            r#"{"kind":"symbol","name":"globe"}"#
        );
        assert!(
            !serde_json::to_string(&items.items[2])
                .unwrap()
                .contains("icon")
        );
    }

    #[test]
    fn an_icon_the_host_cannot_read_loses_the_icon_and_nothing_else() {
        let line = r#"{"id": 1, "result": {"items": [
            {"id": "a", "title": "a", "subtitle": "kept", "icon": {"kind": "emoji", "text": "x"}},
            {"id": "b", "title": "b", "icon": {"kind": "path"}},
            {"id": "c", "title": "c", "icon": "globe"}
        ]}}"#;
        let items = result::<Items>(decode_response(line).unwrap()).unwrap();
        assert_eq!(items.dropped, Vec::<String>::new());
        assert_eq!(items.items.len(), 3);
        assert!(items.items.iter().all(|item| item.icon.is_none()));
        assert_eq!(items.items[0].subtitle.as_deref(), Some("kept"));
    }

    #[test]
    fn an_item_that_does_not_decode_is_left_out_on_its_own_and_named() {
        let line = r#"{"id": 1, "result": {"items": [
            {"id": "a", "title": "a"},
            {"id": "b"},
            "not an item",
            {"id": "d", "title": "d", "score": "high"},
            {"id": "e", "title": "e"}
        ]}}"#;
        let items = result::<Items>(decode_response(line).unwrap()).unwrap();
        let ids: Vec<&str> = items.items.iter().map(|item| item.id.as_str()).collect();
        assert_eq!(ids, ["a", "e"]);
        assert_eq!(items.dropped.len(), 3);
        assert!(
            items.dropped[0].starts_with("item 2 (\"b\"): missing field `title`"),
            "{:?}",
            items.dropped
        );
        assert!(
            items.dropped[1].starts_with("item 3: "),
            "{:?}",
            items.dropped
        );
        assert!(
            items.dropped[2].starts_with("item 4 (\"d\"): "),
            "{:?}",
            items.dropped
        );
        let note = items.dropped_note().unwrap();
        assert!(
            note.starts_with("left out 3 items it could not read: item 2"),
            "{note}"
        );
    }

    #[test]
    fn an_answer_whose_items_are_not_a_list_is_a_decode_error() {
        let line = r#"{"id": 1, "result": {"items": {"id": "a", "title": "a"}}}"#;
        let err = result::<Items>(decode_response(line).unwrap()).unwrap_err();
        assert!(matches!(err, DecodeError::Json(_)), "{err}");
    }

    #[test]
    fn a_score_outside_zero_to_one_is_clamped_and_cannot_outrank_one() {
        let line = r#"{"items": [
            {"id": "sure", "title": "sure", "score": 1.0},
            {"id": "loud", "title": "loud", "score": 7.5},
            {"id": "low", "title": "low", "score": -2},
            {"id": "mid", "title": "mid", "score": 0.5},
            {"id": "definite", "title": "definite"}
        ]}"#;
        let items: Items = serde_json::from_str(line).unwrap();
        let scores: Vec<Option<f64>> = items.items.iter().map(|item| item.score).collect();
        assert_eq!(scores, [Some(1.0), Some(1.0), Some(0.0), Some(0.5), None]);
        let ranked: Vec<String> = crate::query::merge([(0, items.items)])
            .into_iter()
            .map(|hit| hit.item.id)
            .collect();
        assert_eq!(ranked, ["definite", "sure", "loud", "mid", "low"]);
    }

    #[test]
    fn an_effect_of_an_unknown_kind_fails_the_whole_answer() {
        let line = r#"{"id": 1, "result": {"effect": {"kind": "paste", "text": "x"}}}"#;
        let err = result::<Ran>(decode_response(line).unwrap()).unwrap_err();
        assert!(matches!(err, DecodeError::Json(_)), "{err}");
    }

    #[test]
    fn an_error_decodes_as_a_plugin_error() {
        let line = r#"{"id": 2, "error": {"code": "bad_request", "message": "no such item"}}"#;
        let err = result::<Items>(decode_response(line).unwrap()).unwrap_err();
        assert!(
            matches!(err, DecodeError::Plugin(PluginError { ref code, .. }) if code == "bad_request")
        );
    }

    #[test]
    fn effects_are_tagged_by_kind() {
        let ran: Ran =
            serde_json::from_str(r#"{"effect": {"kind": "copy", "text": "4"}}"#).unwrap();
        assert_eq!(ran.effect, Effect::Copy { text: "4".into() });
        let close: Ran = serde_json::from_str(r#"{"effect": {"kind": "close"}}"#).unwrap();
        assert_eq!(close.effect, Effect::Close);
    }

    #[test]
    fn a_line_that_is_not_json_is_a_decode_error() {
        assert!(matches!(
            decode_response("hello"),
            Err(DecodeError::Json(_))
        ));
    }

    #[test]
    fn a_response_with_neither_result_nor_error_is_rejected() {
        assert!(decode_response(r#"{"id": 1}"#).is_err());
    }
}
