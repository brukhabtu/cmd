//! Which plugins see a query, and how their answers become one list.

use crate::protocol::Item;

/// Which queries a plugin receives.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Scope {
    /// Every query.
    Global,
    /// Only queries whose first word is this keyword, which is stripped before sending.
    Keyword(String),
}

impl Scope {
    /// Build a scope from the `keyword` field of a plugin's description.
    pub fn from_keyword(keyword: Option<String>) -> Self {
        match keyword {
            Some(keyword) if !keyword.trim().is_empty() => Scope::Keyword(keyword),
            _ => Scope::Global,
        }
    }
}

/// One plugin to ask, and the text to ask it with.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Route {
    /// The plugin's position in the host's list.
    pub plugin: usize,
    pub text: String,
}

/// An item together with the plugin that produced it.
#[derive(Debug, Clone, PartialEq)]
pub struct Hit {
    pub plugin: usize,
    pub item: Item,
}

/// Decide which plugins see the input.
///
/// A first word that matches a plugin's keyword (ignoring ASCII case) sends the
/// rest of the input to that plugin alone. Otherwise every global plugin sees
/// the whole input. Blank input reaches nobody.
pub fn route(input: &str, scopes: &[Scope]) -> Vec<Route> {
    let input = input.trim();
    if input.is_empty() {
        return Vec::new();
    }
    let (head, rest) = input.split_once(char::is_whitespace).unwrap_or((input, ""));
    let keyword_owner = scopes.iter().position(
        |scope| matches!(scope, Scope::Keyword(keyword) if keyword.eq_ignore_ascii_case(head)),
    );
    if let Some(plugin) = keyword_owner {
        return vec![Route {
            plugin,
            text: rest.trim_start().to_string(),
        }];
    }
    scopes
        .iter()
        .enumerate()
        .filter(|(_, scope)| **scope == Scope::Global)
        .map(|(plugin, _)| Route {
            plugin,
            text: input.to_string(),
        })
        .collect()
}

/// The score an item has when its plugin gave none: a definite answer outranks every fuzzy match.
const DEFINITE: f64 = 1.0;

/// Merge the answers of several plugins into one list, best first.
///
/// Items are ordered by score, highest first. The sort is stable, so ties keep
/// plugin order and then the plugin's own order.
pub fn merge(batches: impl IntoIterator<Item = (usize, Vec<Item>)>) -> Vec<Hit> {
    let mut hits: Vec<Hit> = batches
        .into_iter()
        .flat_map(|(plugin, items)| items.into_iter().map(move |item| Hit { plugin, item }))
        .collect();
    hits.sort_by(|a, b| {
        let (a, b) = (
            a.item.score.unwrap_or(DEFINITE),
            b.item.score.unwrap_or(DEFINITE),
        );
        b.partial_cmp(&a).unwrap_or(std::cmp::Ordering::Equal)
    });
    hits
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scopes() -> Vec<Scope> {
        vec![Scope::Global, Scope::Keyword("calc".into()), Scope::Global]
    }

    fn item(title: &str, score: Option<f64>) -> Item {
        Item {
            id: title.into(),
            title: title.into(),
            subtitle: None,
            score,
            actions: Vec::new(),
        }
    }

    #[test]
    fn a_keyword_sends_the_rest_to_its_owner_alone() {
        assert_eq!(
            route("calc 2 + 2", &scopes()),
            vec![Route {
                plugin: 1,
                text: "2 + 2".into()
            }]
        );
    }

    #[test]
    fn keywords_ignore_case_and_may_stand_alone() {
        assert_eq!(
            route("CALC", &scopes()),
            vec![Route {
                plugin: 1,
                text: String::new()
            }]
        );
    }

    #[test]
    fn without_a_keyword_every_global_plugin_sees_the_whole_input() {
        assert_eq!(
            route("  safari ", &scopes()),
            vec![
                Route {
                    plugin: 0,
                    text: "safari".into()
                },
                Route {
                    plugin: 2,
                    text: "safari".into()
                },
            ]
        );
    }

    #[test]
    fn a_keyword_inside_the_text_is_just_text() {
        let routes = route("open calc", &scopes());
        assert_eq!(
            routes.iter().map(|r| r.plugin).collect::<Vec<_>>(),
            vec![0, 2]
        );
    }

    #[test]
    fn blank_input_reaches_nobody() {
        assert_eq!(route("   ", &scopes()), vec![]);
    }

    #[test]
    fn a_blank_keyword_means_global() {
        assert_eq!(Scope::from_keyword(Some("  ".into())), Scope::Global);
        assert_eq!(Scope::from_keyword(None), Scope::Global);
        assert_eq!(
            Scope::from_keyword(Some("c".into())),
            Scope::Keyword("c".into())
        );
    }

    #[test]
    fn merge_puts_the_best_score_first_and_definite_answers_above_fuzzy_ones() {
        let hits = merge(vec![
            (
                0,
                vec![item("fuzzy low", Some(0.2)), item("fuzzy high", Some(0.9))],
            ),
            (1, vec![item("definite", None)]),
        ]);
        let titles: Vec<&str> = hits.iter().map(|h| h.item.title.as_str()).collect();
        assert_eq!(titles, vec!["definite", "fuzzy high", "fuzzy low"]);
        assert_eq!(hits[0].plugin, 1);
    }

    #[test]
    fn merge_keeps_plugin_order_on_ties() {
        let hits = merge(vec![(2, vec![item("b", None)]), (0, vec![item("a", None)])]);
        let plugins: Vec<usize> = hits.iter().map(|h| h.plugin).collect();
        assert_eq!(plugins, vec![2, 0]);
    }
}
