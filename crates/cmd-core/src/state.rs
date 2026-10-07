//! The launcher as a state machine.
//!
//! The shell turns key presses and plugin answers into an [`Event`], applies it,
//! and performs the [`Step`] that comes back. Nothing here touches a window, a
//! process, or the clipboard.

use crate::protocol::Effect;
use crate::query::Hit;

/// The action id sent when an item declares no actions.
pub const DEFAULT_ACTION: &str = "default";

/// Everything the window shows.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Launcher {
    pub text: String,
    pub hits: Vec<Hit>,
    pub selected: usize,
    /// A line from a plugin or the host, shown under the input until the text changes.
    pub message: Option<String>,
    /// Bumped on every change to the text, so answers to an older query are dropped.
    pub generation: u64,
}

/// Something that happened: a key, or an answer arriving.
#[derive(Debug, Clone, PartialEq)]
pub enum Event {
    Typed(String),
    Backspace,
    Up,
    Down,
    Submit,
    Escape,
    /// The host finished a query started by [`Step::Query`] with this generation.
    Results {
        generation: u64,
        hits: Vec<Hit>,
    },
    /// The host finished a [`Step::Run`].
    Ran(Effect),
    /// The host could not complete a step.
    Failed(String),
}

/// What the shell must do next.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Step {
    Query {
        generation: u64,
        text: String,
    },
    Run {
        plugin: usize,
        item: String,
        action: String,
    },
    Hide,
    CopyAndHide(String),
    OpenAndHide(String),
    Nothing,
}

impl Launcher {
    /// Apply one event and say what to do about it.
    pub fn apply(&mut self, event: Event) -> Step {
        match event {
            Event::Typed(text) => {
                self.text.push_str(&text);
                self.requery()
            }
            Event::Backspace => {
                self.text.pop();
                self.requery()
            }
            Event::Up => {
                self.selected = self.selected.saturating_sub(1);
                Step::Nothing
            }
            Event::Down => {
                if self.selected + 1 < self.hits.len() {
                    self.selected += 1;
                }
                Step::Nothing
            }
            Event::Submit => match self.hits.get(self.selected) {
                Some(hit) => Step::Run {
                    plugin: hit.plugin,
                    item: hit.item.id.clone(),
                    action: hit
                        .item
                        .actions
                        .first()
                        .map_or_else(|| DEFAULT_ACTION.to_string(), |action| action.id.clone()),
                },
                None => Step::Nothing,
            },
            Event::Escape => {
                self.reset();
                Step::Hide
            }
            Event::Results { generation, hits } => {
                if generation == self.generation {
                    self.hits = hits;
                    self.selected = 0;
                }
                Step::Nothing
            }
            Event::Ran(effect) => self.finish(effect),
            Event::Failed(message) => {
                self.message = Some(message);
                Step::Nothing
            }
        }
    }

    fn finish(&mut self, effect: Effect) -> Step {
        match effect {
            Effect::Close => {
                self.reset();
                Step::Hide
            }
            Effect::Copy { text } => {
                self.reset();
                Step::CopyAndHide(text)
            }
            Effect::Open { target } => {
                self.reset();
                Step::OpenAndHide(target)
            }
            Effect::Show { text } => {
                self.message = Some(text);
                Step::Nothing
            }
        }
    }

    fn requery(&mut self) -> Step {
        self.generation += 1;
        self.selected = 0;
        self.message = None;
        if self.text.trim().is_empty() {
            self.hits.clear();
            return Step::Nothing;
        }
        Step::Query {
            generation: self.generation,
            text: self.text.clone(),
        }
    }

    /// Back to an empty launcher. The generation keeps climbing so late answers stay dropped.
    fn reset(&mut self) {
        *self = Launcher {
            generation: self.generation + 1,
            ..Launcher::default()
        };
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{Action, Item};

    fn hit(plugin: usize, id: &str, actions: Vec<Action>) -> Hit {
        Hit {
            plugin,
            item: Item {
                id: id.into(),
                title: id.into(),
                subtitle: None,
                score: None,
                actions,
            },
        }
    }

    fn typed(launcher: &mut Launcher, text: &str) -> Step {
        launcher.apply(Event::Typed(text.into()))
    }

    #[test]
    fn typing_asks_for_a_query_with_a_fresh_generation() {
        let mut launcher = Launcher::default();
        assert_eq!(
            typed(&mut launcher, "2"),
            Step::Query {
                generation: 1,
                text: "2".into()
            }
        );
        assert_eq!(
            typed(&mut launcher, "+"),
            Step::Query {
                generation: 2,
                text: "2+".into()
            }
        );
    }

    #[test]
    fn blank_text_clears_the_list_and_asks_nothing() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        launcher.apply(Event::Results {
            generation: 1,
            hits: vec![hit(0, "a", vec![])],
        });
        assert_eq!(launcher.apply(Event::Backspace), Step::Nothing);
        assert_eq!(launcher.hits, []);
        assert_eq!(launcher.generation, 2);
    }

    #[test]
    fn answers_to_an_old_query_are_dropped() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        typed(&mut launcher, "b");
        launcher.apply(Event::Results {
            generation: 1,
            hits: vec![hit(0, "stale", vec![])],
        });
        assert_eq!(launcher.hits, []);
        launcher.apply(Event::Results {
            generation: 2,
            hits: vec![hit(0, "fresh", vec![])],
        });
        assert_eq!(launcher.hits[0].item.id, "fresh");
    }

    #[test]
    fn selection_stays_inside_the_list() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        launcher.apply(Event::Results {
            generation: 1,
            hits: vec![hit(0, "x", vec![]), hit(0, "y", vec![])],
        });
        assert_eq!(launcher.apply(Event::Up), Step::Nothing);
        assert_eq!(launcher.selected, 0);
        launcher.apply(Event::Down);
        launcher.apply(Event::Down);
        assert_eq!(launcher.selected, 1);
    }

    #[test]
    fn submit_runs_the_first_action_or_the_default() {
        let mut launcher = Launcher::default();
        assert_eq!(launcher.apply(Event::Submit), Step::Nothing);
        typed(&mut launcher, "a");
        let copy = Action {
            id: "copy".into(),
            title: "Copy".into(),
        };
        launcher.apply(Event::Results {
            generation: 1,
            hits: vec![hit(3, "plain", vec![]), hit(4, "rich", vec![copy])],
        });
        assert_eq!(
            launcher.apply(Event::Submit),
            Step::Run {
                plugin: 3,
                item: "plain".into(),
                action: DEFAULT_ACTION.into()
            }
        );
        launcher.apply(Event::Down);
        assert_eq!(
            launcher.apply(Event::Submit),
            Step::Run {
                plugin: 4,
                item: "rich".into(),
                action: "copy".into()
            }
        );
    }

    #[test]
    fn escape_hides_and_forgets_everything_but_the_generation() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "abc");
        assert_eq!(launcher.apply(Event::Escape), Step::Hide);
        assert_eq!(
            launcher,
            Launcher {
                generation: 2,
                ..Launcher::default()
            }
        );
    }

    #[test]
    fn effects_become_shell_steps() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "x");
        assert_eq!(
            launcher.apply(Event::Ran(Effect::Copy { text: "4".into() })),
            Step::CopyAndHide("4".into())
        );
        assert_eq!(launcher.text, "");
        typed(&mut launcher, "x");
        assert_eq!(
            launcher.apply(Event::Ran(Effect::Open {
                target: "https://a".into()
            })),
            Step::OpenAndHide("https://a".into())
        );
        assert_eq!(launcher.apply(Event::Ran(Effect::Close)), Step::Hide);
        typed(&mut launcher, "x");
        assert_eq!(
            launcher.apply(Event::Ran(Effect::Show { text: "hi".into() })),
            Step::Nothing
        );
        assert_eq!(launcher.message.as_deref(), Some("hi"));
        assert_eq!(launcher.text, "x");
    }

    #[test]
    fn a_failure_is_shown_until_the_text_changes() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "x");
        launcher.apply(Event::Failed("plugin timed out".into()));
        assert_eq!(launcher.message.as_deref(), Some("plugin timed out"));
        typed(&mut launcher, "y");
        assert_eq!(launcher.message, None);
    }
}
