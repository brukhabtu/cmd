//! The launcher as a state machine.
//!
//! The shell turns key presses and plugin answers into an [`Event`], applies it,
//! and performs the [`Step`] that comes back. Nothing here touches a window, a
//! process, or the clipboard.

use std::collections::BTreeMap;

use crate::protocol::{Effect, Item};
use crate::query::{self, Hit};

/// The action id sent when an item declares no actions.
pub const DEFAULT_ACTION: &str = "default";

/// Everything the window shows.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Launcher {
    pub text: String,
    pub hits: Vec<Hit>,
    pub selected: usize,
    /// The first row on screen. The window shows `rows` hits from here, so the selection
    /// is kept in view without a scroll container, and Cmd-number counts from here
    /// (decision 4: once the list scrolls, Cmd-number counts the visible rows).
    pub first_visible: usize,
    /// How many rows fit on screen, as the view said. Zero means the view has not said
    /// and every row is on screen, so a default launcher behaves as it did before.
    pub rows: usize,
    /// A line from a plugin or the host, shown under the input until the text changes.
    pub message: Option<String>,
    /// Bumped on every change to the text and on every reset, so answers and effects
    /// that belong to an earlier state are dropped when they arrive.
    pub generation: u64,
    /// Plugins asked in this generation that have not answered yet.
    pub pending: Vec<usize>,
    /// A run is in flight. Enter does nothing until it finishes or the text changes.
    pub busy: bool,
    /// What each plugin answered in this generation, by plugin index. `hits` is their merge.
    answers: BTreeMap<usize, Vec<Item>>,
}

/// Something that happened: a key, or an answer arriving.
#[derive(Debug, Clone, PartialEq)]
pub enum Event {
    Typed(String),
    Backspace,
    /// Cmd-Backspace: the whole text goes.
    Clear,
    Up,
    Down,
    Submit,
    /// Cmd-1 to Cmd-9: run the item at this position, counted from zero.
    Pick(usize),
    Escape,
    /// The host routed the query of this generation to these plugins. Answers follow one by one.
    Asked {
        generation: u64,
        plugins: Vec<usize>,
    },
    /// One plugin answered the query of this generation.
    Answered {
        generation: u64,
        plugin: usize,
        items: Vec<Item>,
    },
    /// One plugin did not answer the query of this generation. The others still merge.
    Unanswered {
        generation: u64,
        plugin: usize,
        error: String,
    },
    /// The host finished the [`Step::Run`] issued in this generation.
    Ran {
        generation: u64,
        effect: Effect,
    },
    /// The host could not finish the [`Step::Run`] issued in this generation.
    Failed {
        generation: u64,
        message: String,
    },
    /// Something the host wants shown whatever the generation: a plugin restarted, say.
    Noted(String),
}

/// What the shell must do next.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Step {
    Query {
        generation: u64,
        text: String,
    },
    /// Ask a plugin to run an action. The answer must come back tagged with `generation`.
    Run {
        generation: u64,
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
    /// A launcher whose window shows `rows` hits at once.
    pub fn new(rows: usize) -> Self {
        Launcher {
            rows,
            ..Launcher::default()
        }
    }

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
            Event::Clear => {
                self.text.clear();
                self.requery()
            }
            Event::Up => {
                self.selected = self.selected.saturating_sub(1);
                self.keep_selected_on_screen();
                Step::Nothing
            }
            Event::Down => {
                if self.selected + 1 < self.hits.len() {
                    self.selected += 1;
                }
                self.keep_selected_on_screen();
                Step::Nothing
            }
            Event::Submit => self.run_at(self.selected),
            Event::Pick(position) => self.pick(position),
            Event::Escape => {
                self.reset();
                Step::Hide
            }
            Event::Asked {
                generation,
                plugins,
            } => {
                if generation == self.generation {
                    self.answers.clear();
                    if plugins.is_empty() {
                        self.hits.clear();
                    }
                    self.pending = plugins;
                }
                Step::Nothing
            }
            Event::Answered {
                generation,
                plugin,
                items,
            } => {
                if generation == self.generation {
                    self.merge_answer(plugin, items);
                }
                Step::Nothing
            }
            Event::Unanswered {
                generation,
                plugin,
                error,
            } => {
                if generation == self.generation {
                    self.pending.retain(|asked| *asked != plugin);
                    self.message = Some(error);
                }
                Step::Nothing
            }
            Event::Ran { generation, effect } => {
                if generation != self.generation {
                    return Step::Nothing;
                }
                self.busy = false;
                self.finish(effect)
            }
            Event::Failed {
                generation,
                message,
            } => {
                if generation == self.generation {
                    self.busy = false;
                    self.message = Some(message);
                }
                Step::Nothing
            }
            Event::Noted(message) => {
                self.message = Some(message);
                Step::Nothing
            }
        }
    }

    /// Cmd-number: the item at `position`, counted from the first row on screen, so the
    /// number beside a row is the number that runs it (decision 4).
    fn pick(&mut self, position: usize) -> Step {
        if self.rows > 0 && position >= self.rows {
            return Step::Nothing;
        }
        self.run_at(self.first_visible + position)
    }

    /// One plugin's answer to the current query joins the others in `hits`.
    fn merge_answer(&mut self, plugin: usize, items: Vec<Item>) {
        self.pending.retain(|asked| *asked != plugin);
        self.answers.insert(plugin, items);
        self.hits = query::merge(
            self.answers
                .iter()
                .map(|(plugin, items)| (*plugin, items.clone())),
        );
        self.selected = self.selected.min(self.hits.len().saturating_sub(1));
        self.keep_selected_on_screen();
    }

    /// The hits on screen: `rows` of them from `first_visible`, or every hit when the
    /// view has not said how many fit.
    pub fn visible(&self) -> &[Hit] {
        if self.rows == 0 {
            return &self.hits;
        }
        let start = self.first_visible.min(self.hits.len());
        let end = (start + self.rows).min(self.hits.len());
        &self.hits[start..end]
    }

    /// Slide the window onto the list by the least that keeps the selection on screen.
    /// Nothing moves while the view has not said how many rows fit.
    fn keep_selected_on_screen(&mut self) {
        if self.rows == 0 {
            return;
        }
        let last_start = self.hits.len().saturating_sub(self.rows);
        self.first_visible = self.first_visible.min(last_start);
        if self.selected < self.first_visible {
            self.first_visible = self.selected;
        } else if self.selected + 1 > self.first_visible + self.rows {
            self.first_visible = self.selected + 1 - self.rows;
        }
    }

    /// Run the first action of the item at `index`, or nothing when there is no such item
    /// or a run is already in flight.
    fn run_at(&mut self, index: usize) -> Step {
        if self.busy {
            return Step::Nothing;
        }
        match self.hits.get(index) {
            Some(hit) => {
                self.busy = true;
                Step::Run {
                    generation: self.generation,
                    plugin: hit.plugin,
                    item: hit.item.id.clone(),
                    action: hit
                        .item
                        .actions
                        .first()
                        .map_or_else(|| DEFAULT_ACTION.to_string(), |action| action.id.clone()),
                }
            }
            None => Step::Nothing,
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
        self.first_visible = 0;
        self.message = None;
        self.busy = false;
        self.pending.clear();
        self.answers.clear();
        if self.text.trim().is_empty() {
            self.hits.clear();
            return Step::Nothing;
        }
        Step::Query {
            generation: self.generation,
            text: self.text.clone(),
        }
    }

    /// Back to an empty launcher. The generation keeps climbing so late answers stay
    /// dropped, and the row count stays because the window has not changed size.
    fn reset(&mut self) {
        *self = Launcher {
            generation: self.generation + 1,
            rows: self.rows,
            ..Launcher::default()
        };
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::Action;

    fn hit(plugin: usize, id: &str, actions: Vec<Action>) -> Hit {
        Hit {
            plugin,
            item: Item {
                id: id.into(),
                title: id.into(),
                subtitle: None,
                score: None,
                actions,
                icon: None,
            },
        }
    }

    fn typed(launcher: &mut Launcher, text: &str) -> Step {
        launcher.apply(Event::Typed(text.into()))
    }

    /// Every plugin named in `hits` is asked and answers the given generation.
    fn answered(launcher: &mut Launcher, generation: u64, hits: &[Hit]) {
        let mut plugins: Vec<usize> = hits.iter().map(|hit| hit.plugin).collect();
        plugins.dedup();
        launcher.apply(Event::Asked {
            generation,
            plugins: plugins.clone(),
        });
        for plugin in plugins {
            let items = hits
                .iter()
                .filter(|hit| hit.plugin == plugin)
                .map(|hit| hit.item.clone())
                .collect();
            launcher.apply(Event::Answered {
                generation,
                plugin,
                items,
            });
        }
    }

    fn run(generation: u64, plugin: usize, item: &str, action: &str) -> Step {
        Step::Run {
            generation,
            plugin,
            item: item.into(),
            action: action.into(),
        }
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
        answered(&mut launcher, 1, &[hit(0, "a", vec![])]);
        assert_eq!(launcher.apply(Event::Backspace), Step::Nothing);
        assert_eq!(launcher.hits, []);
        assert_eq!(launcher.generation, 2);
    }

    #[test]
    fn answers_to_an_old_query_are_dropped() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        typed(&mut launcher, "b");
        answered(&mut launcher, 1, &[hit(0, "stale", vec![])]);
        assert_eq!(launcher.hits, []);
        answered(&mut launcher, 2, &[hit(0, "fresh", vec![])]);
        assert_eq!(launcher.hits[0].item.id, "fresh");
    }

    #[test]
    fn answers_merge_as_they_arrive_and_pending_shrinks() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        launcher.apply(Event::Asked {
            generation: 1,
            plugins: vec![0, 1],
        });
        assert_eq!(launcher.pending, vec![0, 1]);
        launcher.apply(Event::Answered {
            generation: 1,
            plugin: 1,
            items: vec![hit(1, "slow", vec![]).item],
        });
        assert_eq!(launcher.hits.len(), 1);
        assert_eq!(launcher.pending, vec![0]);
        launcher.apply(Event::Answered {
            generation: 1,
            plugin: 0,
            items: vec![hit(0, "fast", vec![]).item],
        });
        let order: Vec<&str> = launcher
            .hits
            .iter()
            .map(|hit| hit.item.id.as_str())
            .collect();
        assert_eq!(order, vec!["fast", "slow"]);
        assert_eq!(launcher.pending, Vec::<usize>::new());
    }

    #[test]
    fn an_unanswered_plugin_is_shown_and_the_rest_still_merge() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        launcher.apply(Event::Asked {
            generation: 1,
            plugins: vec![0, 1],
        });
        launcher.apply(Event::Unanswered {
            generation: 1,
            plugin: 0,
            error: "calc: no answer within 3s".into(),
        });
        launcher.apply(Event::Answered {
            generation: 1,
            plugin: 1,
            items: vec![hit(1, "x", vec![]).item],
        });
        assert_eq!(
            launcher.message.as_deref(),
            Some("calc: no answer within 3s")
        );
        assert_eq!(launcher.hits.len(), 1);
        assert_eq!(launcher.pending, Vec::<usize>::new());
    }

    #[test]
    fn the_old_list_stays_until_the_first_new_answer_and_asking_nobody_clears_it() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        answered(&mut launcher, 1, &[hit(0, "old", vec![])]);
        typed(&mut launcher, "b");
        launcher.apply(Event::Asked {
            generation: 2,
            plugins: vec![0],
        });
        assert_eq!(launcher.hits.len(), 1);
        launcher.apply(Event::Answered {
            generation: 2,
            plugin: 0,
            items: vec![],
        });
        assert_eq!(launcher.hits, []);
        typed(&mut launcher, "c");
        launcher.apply(Event::Asked {
            generation: 3,
            plugins: vec![],
        });
        assert_eq!(launcher.hits, []);
    }

    #[test]
    fn selection_stays_inside_the_list() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        answered(
            &mut launcher,
            1,
            &[hit(0, "x", vec![]), hit(0, "y", vec![])],
        );
        assert_eq!(launcher.apply(Event::Up), Step::Nothing);
        assert_eq!(launcher.selected, 0);
        launcher.apply(Event::Down);
        launcher.apply(Event::Down);
        assert_eq!(launcher.selected, 1);
        answered(&mut launcher, 1, &[hit(0, "only", vec![])]);
        assert_eq!(
            launcher.selected, 0,
            "a shorter list pulls the selection back inside"
        );
    }

    #[test]
    fn submit_runs_the_first_action_or_the_default_tagged_with_the_generation() {
        let mut launcher = Launcher::default();
        assert_eq!(launcher.apply(Event::Submit), Step::Nothing);
        typed(&mut launcher, "a");
        let copy = Action {
            id: "copy".into(),
            title: "Copy".into(),
        };
        answered(
            &mut launcher,
            1,
            &[hit(3, "plain", vec![]), hit(4, "rich", vec![copy])],
        );
        assert_eq!(
            launcher.apply(Event::Submit),
            run(1, 3, "plain", DEFAULT_ACTION)
        );
        launcher.apply(Event::Failed {
            generation: 1,
            message: "no".into(),
        });
        launcher.apply(Event::Down);
        assert_eq!(launcher.apply(Event::Submit), run(1, 4, "rich", "copy"));
    }

    #[test]
    fn enter_twice_runs_once_until_the_run_finishes() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        answered(&mut launcher, 1, &[hit(0, "x", vec![])]);
        assert_eq!(
            launcher.apply(Event::Submit),
            run(1, 0, "x", DEFAULT_ACTION)
        );
        assert!(launcher.busy);
        assert_eq!(launcher.apply(Event::Submit), Step::Nothing);
        assert_eq!(launcher.apply(Event::Pick(0)), Step::Nothing);
        launcher.apply(Event::Ran {
            generation: 1,
            effect: Effect::Show {
                text: "done".into(),
            },
        });
        assert!(!launcher.busy);
        assert_eq!(
            launcher.apply(Event::Submit),
            run(1, 0, "x", DEFAULT_ACTION)
        );
    }

    #[test]
    fn a_run_that_finishes_after_escape_or_more_typing_is_dropped() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        answered(&mut launcher, 1, &[hit(0, "x", vec![])]);
        launcher.apply(Event::Submit);
        assert_eq!(launcher.apply(Event::Escape), Step::Hide);
        assert_eq!(
            launcher.apply(Event::Ran {
                generation: 1,
                effect: Effect::Open {
                    target: "https://a".into()
                }
            }),
            Step::Nothing
        );
        typed(&mut launcher, "b");
        answered(&mut launcher, 3, &[hit(0, "y", vec![])]);
        launcher.apply(Event::Submit);
        typed(&mut launcher, "c");
        assert!(!launcher.busy, "typing on cancels the run");
        assert_eq!(
            launcher.apply(Event::Ran {
                generation: 3,
                effect: Effect::Copy { text: "y".into() }
            }),
            Step::Nothing
        );
        assert_eq!(
            launcher.apply(Event::Failed {
                generation: 3,
                message: "late".into()
            }),
            Step::Nothing
        );
        assert_eq!(launcher.message, None);
    }

    #[test]
    fn clear_empties_the_text_and_the_list_in_one_step() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "abc");
        answered(&mut launcher, 1, &[hit(0, "a", vec![])]);
        assert_eq!(launcher.apply(Event::Clear), Step::Nothing);
        assert_eq!(launcher.text, "");
        assert_eq!(launcher.hits, []);
        assert_eq!(launcher.generation, 2);
    }

    #[test]
    fn pick_runs_the_nth_item_without_moving_the_selection() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        answered(
            &mut launcher,
            1,
            &[hit(0, "x", vec![]), hit(1, "y", vec![])],
        );
        assert_eq!(
            launcher.apply(Event::Pick(1)),
            run(1, 1, "y", DEFAULT_ACTION)
        );
        assert_eq!(launcher.selected, 0);
        launcher.apply(Event::Failed {
            generation: 1,
            message: "no".into(),
        });
        assert_eq!(launcher.apply(Event::Pick(7)), Step::Nothing);
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
        let ran = |effect: Effect, generation: u64| Event::Ran { generation, effect };
        assert_eq!(
            launcher.apply(ran(Effect::Copy { text: "4".into() }, 1)),
            Step::CopyAndHide("4".into())
        );
        assert_eq!(launcher.text, "");
        typed(&mut launcher, "x");
        assert_eq!(
            launcher.apply(ran(
                Effect::Open {
                    target: "https://a".into()
                },
                3
            )),
            Step::OpenAndHide("https://a".into())
        );
        typed(&mut launcher, "x");
        assert_eq!(launcher.apply(ran(Effect::Close, 5)), Step::Hide);
        typed(&mut launcher, "x");
        assert_eq!(
            launcher.apply(ran(Effect::Show { text: "hi".into() }, 7)),
            Step::Nothing
        );
        assert_eq!(launcher.message.as_deref(), Some("hi"));
        assert_eq!(launcher.text, "x");
    }

    #[test]
    fn a_note_is_shown_whatever_the_generation() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "x");
        assert_eq!(
            launcher.apply(Event::Noted("calc restarted".into())),
            Step::Nothing
        );
        assert_eq!(launcher.message.as_deref(), Some("calc restarted"));
    }

    #[test]
    fn a_failure_is_shown_until_the_text_changes() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "x");
        launcher.apply(Event::Failed {
            generation: 1,
            message: "plugin timed out".into(),
        });
        assert_eq!(launcher.message.as_deref(), Some("plugin timed out"));
        typed(&mut launcher, "y");
        assert_eq!(launcher.message, None);
    }

    /// Hits from plugin 0 with these ids and no actions.
    fn hits(ids: &[&str]) -> Vec<Hit> {
        ids.iter().map(|id| hit(0, id, vec![])).collect()
    }

    /// Five hits in a window three rows high.
    fn five_in_three_rows() -> Launcher {
        let mut launcher = Launcher::new(3);
        typed(&mut launcher, "a");
        answered(&mut launcher, 1, &hits(&["a", "b", "c", "d", "e"]));
        launcher
    }

    fn visible_ids(launcher: &Launcher) -> Vec<&str> {
        launcher
            .visible()
            .iter()
            .map(|hit| hit.item.id.as_str())
            .collect()
    }

    #[test]
    fn down_past_the_last_visible_row_scrolls_by_one() {
        let mut launcher = five_in_three_rows();
        assert_eq!(visible_ids(&launcher), vec!["a", "b", "c"]);
        for _ in 0..3 {
            launcher.apply(Event::Down);
        }
        assert_eq!(launcher.selected, 3);
        assert_eq!(launcher.first_visible, 1);
        assert_eq!(visible_ids(&launcher), vec!["b", "c", "d"]);
    }

    #[test]
    fn up_above_the_first_visible_row_scrolls_back() {
        let mut launcher = five_in_three_rows();
        for _ in 0..3 {
            launcher.apply(Event::Down);
        }
        launcher.apply(Event::Up);
        launcher.apply(Event::Up);
        assert_eq!(launcher.first_visible, 1, "still on screen, nothing moves");
        launcher.apply(Event::Up);
        assert_eq!(launcher.selected, 0);
        assert_eq!(launcher.first_visible, 0);
    }

    #[test]
    fn a_shorter_answer_pulls_the_window_back() {
        let mut launcher = five_in_three_rows();
        for _ in 0..4 {
            launcher.apply(Event::Down);
        }
        assert_eq!(launcher.first_visible, 2);
        answered(
            &mut launcher,
            1,
            &[
                hit(0, "x", vec![]),
                hit(0, "y", vec![]),
                hit(0, "z", vec![]),
            ],
        );
        assert_eq!(launcher.selected, 2);
        assert_eq!(launcher.first_visible, 0);
        assert_eq!(visible_ids(&launcher), vec!["x", "y", "z"]);
    }

    #[test]
    fn pick_counts_from_the_first_visible_row() {
        let mut launcher = five_in_three_rows();
        for _ in 0..3 {
            launcher.apply(Event::Down);
        }
        assert_eq!(launcher.first_visible, 1);
        assert_eq!(
            launcher.apply(Event::Pick(0)),
            run(1, 0, "b", DEFAULT_ACTION)
        );
        launcher.apply(Event::Failed {
            generation: 1,
            message: "no".into(),
        });
        assert_eq!(
            launcher.apply(Event::Pick(3)),
            Step::Nothing,
            "the fourth row is off screen"
        );
    }

    #[test]
    fn without_a_row_count_every_row_is_visible_and_pick_counts_the_whole_list() {
        let mut launcher = Launcher::default();
        typed(&mut launcher, "a");
        answered(&mut launcher, 1, &hits(&["a", "b", "c", "d", "e"]));
        for _ in 0..4 {
            launcher.apply(Event::Down);
        }
        assert_eq!(launcher.first_visible, 0);
        assert_eq!(launcher.visible().len(), 5);
        assert_eq!(
            launcher.apply(Event::Pick(4)),
            run(1, 0, "e", DEFAULT_ACTION)
        );
    }

    #[test]
    fn typing_and_escape_scroll_back_to_the_top() {
        let mut launcher = five_in_three_rows();
        for _ in 0..3 {
            launcher.apply(Event::Down);
        }
        typed(&mut launcher, "b");
        assert_eq!(launcher.first_visible, 0);
        answered(&mut launcher, 2, &hits(&["a", "b", "c", "d", "e"]));
        for _ in 0..4 {
            launcher.apply(Event::Down);
        }
        assert_eq!(launcher.apply(Event::Escape), Step::Hide);
        assert_eq!(launcher.first_visible, 0);
        assert_eq!(launcher.rows, 3, "the window has not changed size");
    }

    #[test]
    fn visible_is_the_whole_list_when_it_is_shorter_than_the_window() {
        let mut launcher = Launcher::new(3);
        typed(&mut launcher, "a");
        answered(
            &mut launcher,
            1,
            &[hit(0, "x", vec![]), hit(0, "y", vec![])],
        );
        assert_eq!(visible_ids(&launcher), vec!["x", "y"]);
        launcher.apply(Event::Down);
        launcher.apply(Event::Down);
        assert_eq!(launcher.selected, 1);
        assert_eq!(launcher.first_visible, 0);
    }
}
