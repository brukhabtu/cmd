//! Plugin protocol v0: newline-delimited JSON over a plugin's stdin and stdout.
//!
//! The host writes one [`Request`] per line and the plugin answers with one
//! [`Response`] per line carrying the same `id`. The specification is
//! `docs/plugin-protocol.md`; this module is the Rust side of it, and
//! `cmd_sdk.protocol` is the Python side.

use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// The protocol version this crate speaks. Sent in `describe`, echoed back by the plugin.
pub const VERSION: u32 = 0;

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
    /// Handshake. The plugin answers with a [`Description`].
    Describe { protocol: u32 },
    /// The text the person typed, already stripped of the plugin's keyword.
    /// The plugin answers with [`Items`].
    Query { text: String },
    /// The person chose an item and an action. The plugin answers with [`Ran`].
    Run { item: String, action: String },
}

/// What a plugin says about itself in the handshake.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Description {
    pub name: String,
    pub version: String,
    pub protocol: u32,
    /// With a keyword, the plugin sees only queries that start with it.
    /// Without one, it sees every query.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub keyword: Option<String>,
}

/// One row in the result list.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Item {
    pub id: String,
    pub title: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subtitle: Option<String>,
    /// Confidence in `0.0..=1.0` for fuzzy matches. Leave it out for a definite answer.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub score: Option<f64>,
    /// The first action is the one Enter runs. Empty means the host runs
    /// [`crate::state::DEFAULT_ACTION`].
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub actions: Vec<Action>,
}

/// Something that can be done with an item.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Action {
    pub id: String,
    pub title: String,
}

/// The answer to `query`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Items {
    pub items: Vec<Item>,
}

/// What the host does after an action ran. The plugin returns it; the host performs it.
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
    #[error("plugin reported an error")]
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
    fn describe_carries_the_protocol_version() {
        let line = encode_request(&Request {
            id: 1,
            method: Method::Describe { protocol: VERSION },
        });
        assert_eq!(
            line,
            "{\"id\":1,\"method\":\"describe\",\"params\":{\"protocol\":0}}\n"
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
