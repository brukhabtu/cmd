from calculator import PLUGIN
from cmd_sdk import Copy, Item, Show


def test_an_expression_becomes_one_item() -> None:
    assert PLUGIN.query("6 * 7") == (Item(id="42", title="42", subtitle="Press Enter to copy"),)


def test_other_text_yields_nothing() -> None:
    assert PLUGIN.query("open safari") == ()


def test_enter_copies_the_answer() -> None:
    assert PLUGIN.run("42", "default") == Copy(text="42")
    assert PLUGIN.run("42", "copy") == Copy(text="42")


def test_an_unknown_action_is_shown_not_raised() -> None:
    assert isinstance(PLUGIN.run("42", "dance"), Show)
