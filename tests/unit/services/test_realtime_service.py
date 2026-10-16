import threading
import time
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import Mock

import pytest
from slack_sdk.socket_mode.request import SocketModeRequest

from app.client.slack_client import SlackClient
from app.services import realtime_service
from app.services.realtime_service import RealtimeService
from app.storage.checkpoint_store import CheckpointStore
from app.storage.minio_client import MinioClient

CHANNEL = "C1"


def wait_for(condition: Callable[[], Any], timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    pytest.fail("condition not met in time")


def event(payload: dict[str, Any], *, type_: str = "events_api") -> SocketModeRequest:
    return SocketModeRequest(type=type_, envelope_id="env-1", payload=payload)


def message_event(**fields: Any) -> SocketModeRequest:
    return event({"event": {"type": "message", "channel": CHANNEL, **fields}})


class Harness:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.marks: dict[str, str] = {}
        self.running = threading.Event()
        self.running.set()
        self.slack = Mock(spec=SlackClient)
        self.slack.iter_channel_messages.side_effect = lambda **_: iter([])
        self.minio = Mock(spec=MinioClient)
        self.minio.write_page.return_value = []
        self.checkpoints = Mock(spec=CheckpointStore)
        self.checkpoints.load_high_water.side_effect = self.marks.get
        self.checkpoints.save_high_water.side_effect = self.marks.__setitem__
        self.checkpoints.high_water_channels.side_effect = lambda: list(self.marks)
        self.socket = Mock()
        self.socket.socket_mode_request_listeners = []
        monkeypatch.setattr(
            realtime_service, "SocketModeClient", Mock(return_value=self.socket)
        )
        self.service = RealtimeService(
            self.slack, self.minio, self.checkpoints, self.running, "xapp-test"
        )

    def start(self) -> None:
        assert self.service.start() is True

    def send(self, request: SocketModeRequest) -> None:
        self.socket.socket_mode_request_listeners[0](self.socket, request)

    @property
    def written(self) -> list[dict[str, Any]]:
        return [c.kwargs["rows"][0] for c in self.minio.write_page.call_args_list]


@pytest.fixture
def h(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    harness = Harness(monkeypatch)
    yield harness
    harness.service.stop()


def test_new_message_is_acked_written_and_marked(h: Harness):
    h.start()
    h.send(message_event(ts="1790921000.000100", user="U1", text="hi"))

    wait_for(lambda: h.service.status()["events_written"] == 1)
    h.socket.send_socket_mode_response.assert_called_once()
    assert h.minio.write_page.call_args.kwargs["mode"] == "realtime"
    row = h.written[0]
    assert (row["ts"], row["event_type"], row["source"]) == (
        "1790921000.000100",
        "created",
        "realtime",
    )
    assert h.marks[CHANNEL] == "1790921000.000100"


def test_edit_is_written_as_a_new_version_without_moving_the_mark(h: Harness):
    h.start()
    h.send(message_event(ts="1790921000.000100", user="U1", text="hi"))
    wait_for(lambda: h.service.status()["events_written"] == 1)

    h.send(
        message_event(
            subtype="message_changed",
            message={
                "ts": "1790921000.000100",
                "user": "U1",
                "text": "hi!",
                "edited": {"user": "U1", "ts": "1790921500.000001"},
            },
        )
    )
    wait_for(lambda: h.service.status()["events_written"] == 2)

    edited = h.written[1]
    assert (edited["event_type"], edited["version_ts"]) == (
        "edited",
        "1790921500.000001",
    )
    assert h.marks[CHANNEL] == "1790921000.000100"


def test_deletes_and_non_message_events_are_acked_but_ignored(h: Harness):
    h.start()
    h.send(message_event(subtype="message_deleted", deleted_ts="1790921000.000100"))
    h.send(event({"event": {"type": "reaction_added"}}))
    h.send(event({}, type_="hello"))

    assert h.socket.send_socket_mode_response.call_count == 3
    time.sleep(0.2)
    h.minio.write_page.assert_not_called()


def test_events_wait_while_paused_and_flush_on_resume(h: Harness):
    h.start()
    h.running.clear()
    h.send(message_event(ts="1790921000.000100", user="U1", text="paused"))

    wait_for(lambda: h.service.status()["queued"] == 1)
    time.sleep(0.8)  # long enough for the worker to have taken it and be waiting
    assert h.service.status()["queued"] == 1
    h.minio.write_page.assert_not_called()

    h.running.set()
    wait_for(lambda: h.service.status()["events_written"] == 1)
    assert h.service.status()["queued"] == 0


def test_failed_write_keeps_the_stream_alive_and_the_mark_behind(h: Harness):
    h.start()
    h.minio.write_page.side_effect = ConnectionError("minio down")
    h.send(message_event(ts="1790921000.000100", user="U1", text="lost"))
    wait_for(lambda: h.service.status()["last_error"] is not None)
    assert CHANNEL not in h.marks

    h.minio.write_page.side_effect = None
    h.send(message_event(ts="1790921100.000100", user="U1", text="ok"))
    wait_for(lambda: h.marks.get(CHANNEL) == "1790921100.000100")


def test_start_catches_up_from_the_high_water_mark(h: Harness):
    h.marks[CHANNEL] = "1790921000.000100"
    h.slack.iter_channel_messages.side_effect = lambda **_: iter(
        [
            [
                {"ts": "1790921300.000100", "text": "missed 2", "user": "U1"},
                {"ts": "1790921200.000100", "text": "missed 1", "user": "U1"},
            ]
        ]
    )
    h.start()

    wait_for(lambda: h.marks[CHANNEL] == "1790921300.000100")
    assert h.slack.iter_channel_messages.call_args.kwargs["oldest"] == (
        "1790921000.000100"
    )
    rows = h.minio.write_page.call_args.kwargs["rows"]
    assert {r["ts"] for r in rows} == {"1790921200.000100", "1790921300.000100"}
    assert {r["source"] for r in rows} == {"realtime"}


def test_start_twice_and_stop_report_what_happened(h: Harness):
    assert h.service.start() is True
    assert h.service.start() is False
    assert h.service.status()["running"] is True
    assert h.service.stop() is True
    assert h.service.stop() is False
    assert h.service.status()["running"] is False


def test_without_an_app_token_nothing_starts(monkeypatch: pytest.MonkeyPatch):
    service = RealtimeService(Mock(), Mock(), Mock(), threading.Event(), app_token=None)
    assert service.configured is False
    assert service.start() is False
