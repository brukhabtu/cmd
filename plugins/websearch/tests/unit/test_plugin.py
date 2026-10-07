from cmd_sdk import Copy, Open, Show
from websearch import PLUGIN, search_url


def test_a_question_becomes_one_item_whose_id_is_the_search_url() -> None:
    (item,) = PLUGIN.query("rust gpui")
    assert item.id == "https://duckduckgo.com/?q=rust+gpui"
    assert [action.id for action in item.actions] == ["open", "copy"]


def test_the_question_is_made_safe_for_a_url() -> None:
    assert search_url("a&b c") == "https://duckduckgo.com/?q=a%26b+c"


def test_the_keyword_alone_offers_a_hint_and_enter_explains() -> None:
    (item,) = PLUGIN.query("   ")
    assert not item.id
    assert isinstance(PLUGIN.run("", "default"), Show)


def test_enter_opens_and_the_second_action_copies() -> None:
    url = search_url("x")
    assert PLUGIN.run(url, "default") == Open(target=url)
    assert PLUGIN.run(url, "open") == Open(target=url)
    assert PLUGIN.run(url, "copy") == Copy(text=url)
    assert isinstance(PLUGIN.run(url, "dance"), Show)
