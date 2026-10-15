import logging
import queue
import threading
from datetime import UTC, datetime
from typing import Any

from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from app.client.slack_client import SlackClient
from app.storage.checkpoint_store import CheckpointStore
from app.storage.minio_client import MinioClient
from app.storage.storage import ts_bounds
from app.transform import message_to_row

logger = logging.getLogger(__name__)

_SKIPPED_SUBTYPES = {"message_deleted"}
_CATCH_UP_PAGE_SIZE = 200


class RealtimeService:
    """Streams Slack messages over Socket Mode (a WebSocket) into MinIO.

    The socket handler only acks and enqueues, so Slack never waits on us.
    One worker thread drains the queue, honours the shared pause switch,
    writes each message and advances the per-channel high-water mark.
    """

    def __init__(
        self,
        slack: SlackClient,
        minio: MinioClient,
        checkpoints: CheckpointStore,
        running: threading.Event,
        app_token: str | None,
    ) -> None:
        self._slack = slack
        self._minio = minio
        self._checkpoints = checkpoints
        self._running = running
        self._app_token = app_token
        self._queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._client: SocketModeClient | None = None
        self._worker: threading.Thread | None = None
        self._high_water: dict[str, str] = {}
        self._written = 0
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self._app_token is not None

    def start(self) -> bool:
        with self._lock:
            if self._client is not None or self._app_token is None:
                return False
            self._stop.clear()
            self._worker = threading.Thread(target=self._work, daemon=True)
            self._worker.start()
            client = SocketModeClient(app_token=self._app_token)
            client.socket_mode_request_listeners.append(self._on_request)
            try:
                client.connect()
            except Exception:
                self._stop.set()
                raise
            self._client = client
            return True

    def stop(self) -> bool:
        with self._lock:
            client, self._client = self._client, None
            worker = self._worker
        if client is None:
            return False
        client.close()
        self._stop.set()
        if worker is not None:
            worker.join(timeout=5)
        return True

    def status(self) -> dict[str, Any]:
        return {
            "running": self._client is not None,
            "events_written": self._written,
            "queued": self._queue.qsize(),
            "last_error": self._last_error,
        }

    def _on_request(self, client: BaseSocketModeClient, req: SocketModeRequest) -> None:
        client.send_socket_mode_response(
            SocketModeResponse(envelope_id=req.envelope_id)
        )
        if req.type != "events_api":
            return
        event = req.payload.get("event", {})
        if event.get("type") != "message":
            return
        subtype = event.get("subtype")
        if subtype in _SKIPPED_SUBTYPES:
            return
        message = event.get("message") if subtype == "message_changed" else event
        channel_id = event.get("channel")
        if not message or not channel_id or "ts" not in message:
            return
        self._queue.put((channel_id, message))

    def _work(self) -> None:
        self._catch_up()
        while not self._stop.is_set():
            try:
                channel_id, message = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            while not self._running.wait(timeout=0.5):
                if self._stop.is_set():
                    return
            self._write(channel_id, message)

    def _write(self, channel_id: str, message: dict[str, Any]) -> None:
        try:
            row = message_to_row(
                message=message,
                channel_id=channel_id,
                ingested_at=datetime.now(UTC),
                source="realtime",
            )
            self._minio.write_page(mode="realtime", rows=[row])
            self._advance(channel_id, message["ts"])
        except Exception as e:
            logger.exception("failed to write message for %s", channel_id)
            self._last_error = repr(e)
        else:
            self._written += 1

    def _advance(self, channel_id: str, ts: str) -> None:
        current = self._high_water.get(channel_id)
        if current is None:
            current = self._checkpoints.load_high_water(channel_id) or ""
        if ts > current:
            self._checkpoints.save_high_water(channel_id, ts)
            current = ts
        self._high_water[channel_id] = current

    def _catch_up(self) -> None:
        """Fetch what arrived while we were down, from each channel's mark."""
        for channel_id in self._checkpoints.high_water_channels():
            try:
                self._catch_up_channel(channel_id)
            except Exception:
                logger.exception("catch-up failed for %s", channel_id)

    def _catch_up_channel(self, channel_id: str) -> None:
        mark = self._checkpoints.load_high_water(channel_id)
        if mark is None:
            return
        newest = mark
        ingested_at = datetime.now(UTC)
        for messages in self._slack.iter_channel_messages(
            channel_id=channel_id, limit=_CATCH_UP_PAGE_SIZE, oldest=mark
        ):
            rows = [
                message_to_row(
                    message=m,
                    channel_id=channel_id,
                    ingested_at=ingested_at,
                    source="realtime",
                )
                for m in messages
            ]
            if not rows:
                continue
            self._minio.write_page(mode="realtime", rows=rows)
            newest = max(newest, ts_bounds(rows)[1])
            self._written += len(rows)
        # Saved only after every page landed, so a crash mid catch-up re-fetches.
        if newest != mark:
            self._checkpoints.save_high_water(channel_id, newest)
        self._high_water[channel_id] = newest
