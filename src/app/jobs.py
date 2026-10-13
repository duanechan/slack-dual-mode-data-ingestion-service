import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from app.services.ingestion_service import IngestionService


class JobManager:
    """Owns the shared pause switch, the worker pool and per-channel progress."""

    def __init__(self, service: IngestionService, max_workers: int = 3) -> None:
        self._service = service
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._channels: dict[str, dict[str, Any]] = {}
        self.running = threading.Event()
        self.running.set()  # set = go, cleared = paused

    def start_backfill(self, channel_ids: list[str], page_size: int) -> list[str]:
        ingested_at = datetime.now(UTC)
        started: list[str] = []
        with self._lock:
            for cid in dict.fromkeys(channel_ids):
                current = self._channels.get(cid, {}).get("state")
                if current in ("pending", "running"):
                    continue
                self._channels[cid] = {"state": "pending", "messages": 0, "error": None}
                started.append(cid)
        for cid in started:
            self._pool.submit(self._run, cid, ingested_at, page_size)
        return started

    def pause(self) -> None:
        self.running.clear()

    def resume(self) -> None:
        self.running.set()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "paused": not self.running.is_set(),
                "channels": {cid: dict(info) for cid, info in self._channels.items()},
            }

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _run(self, channel_id: str, ingested_at: datetime, page_size: int) -> None:
        self._update(channel_id, state="running")
        try:
            self._service.backfill_channel(
                channel_id=channel_id,
                ingested_at=ingested_at,
                limit=page_size,
                running=self.running,
                on_page=self._on_page,
            )
        except Exception as e:  # noqa: BLE001 - one bad channel must not stop the rest
            self._update(channel_id, state="failed", error=repr(e))
        else:
            self._update(channel_id, state="done")

    def _on_page(self, channel_id: str, count: int) -> None:
        with self._lock:
            self._channels[channel_id]["messages"] += count

    def _update(self, channel_id: str, **fields: Any) -> None:
        with self._lock:
            self._channels[channel_id].update(fields)
