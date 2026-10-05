from typing import Any
from unittest.mock import Mock

import pytest
from slack_sdk import WebClient

from app.client.slack_client import SlackClient


def make_web_client(pages: list[dict[str, Any]]) -> Mock:
    web_client = Mock(spec=WebClient)
    web_client.conversations_history.side_effect = pages
    return web_client


def cursors_sent(web_client: Mock) -> list[str | None]:
    calls = web_client.conversations_history.call_args_list
    return [call.kwargs["cursor"] for call in calls]


def make_messages(count: int) -> list[dict[str, str]]:
    return [{"ts": str(i)} for i in range(count)]


def test_pages_are_yielded_until_cursor_is_missing():
    web_client = make_web_client(
        [
            {"messages": make_messages(5), "response_metadata": {"next_cursor": "c1"}},
            {"messages": make_messages(5), "response_metadata": {"next_cursor": "c2"}},
            {"messages": make_messages(3)},
        ]
    )
    client = SlackClient(client=web_client)

    pages = list(client.iter_channel_messages("C0C6AJHP204", limit=5))

    assert [len(page) for page in pages] == [5, 5, 3]
    assert cursors_sent(web_client) == [None, "c1", "c2"]


@pytest.mark.parametrize(
    "last_page",
    [
        {"messages": make_messages(2)},
        {"messages": make_messages(2), "response_metadata": {"next_cursor": ""}},
    ],
    ids=["no-response-metadata", "empty-string-cursor"],
)
def test_last_page_is_delivered_and_loop_stops(last_page):
    web_client = make_web_client(
        [
            {"messages": make_messages(5), "response_metadata": {"next_cursor": "c1"}},
            last_page,
        ]
    )
    client = SlackClient(client=web_client)

    pages = list(client.iter_channel_messages("C0C6AJHP204", limit=5))

    assert [len(page) for page in pages] == [5, 2]
    assert cursors_sent(web_client) == [None, "c1"]


def test_single_page_channel_makes_one_call():
    web_client = make_web_client([{"messages": make_messages(4)}])
    client = SlackClient(client=web_client)

    pages = list(client.iter_channel_messages("C0C6AJHP204"))

    assert [len(page) for page in pages] == [4]
    assert cursors_sent(web_client) == [None]
