import pytest
from system.commands import (
    COMMANDS,
    DARK_MODE,
    EMPTY_TRASH,
    LOCK,
    MIN_PREFIX,
    SLEEP,
    Command,
    by_id,
    matching,
)


def test_every_command_is_listed_once_with_a_title_a_subtitle_and_an_absolute_argv() -> None:
    assert len({command.id for command in COMMANDS}) == len(COMMANDS) == 4
    for command in COMMANDS:
        assert command.title
        assert command.subtitle
        assert command.names
        assert command.argv[0].startswith("/")
        assert command.symbol


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sl", (SLEEP,)),
        ("sleep", (SLEEP,)),
        ("lock screen", (LOCK,)),
        ("trash", (EMPTY_TRASH,)),
        ("empty", (EMPTY_TRASH,)),
        ("dark", (DARK_MODE,)),
        ("light", (DARK_MODE,)),
        ("  Dark   MODE ", (DARK_MODE,)),
    ],
)
def test_a_prefix_of_a_name_finds_its_command(text: str, expected: tuple[Command, ...]) -> None:
    assert matching(text) == expected


@pytest.mark.parametrize("text", ["", " ", "s", "safari", "sleeping", "2 + 2"])
def test_other_text_finds_nothing(text: str) -> None:
    assert matching(text) == ()


def test_the_floor_is_two_characters_so_a_single_letter_names_nothing() -> None:
    assert MIN_PREFIX == 2
    assert matching("l") == ()
    assert matching("lo") == (LOCK,)


def test_by_id_finds_a_command_by_the_id_the_plugin_issued() -> None:
    assert by_id("lock") is LOCK
    assert by_id("empty-trash") is EMPTY_TRASH
    assert by_id("x") is None
