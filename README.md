# Slack Dual-Mode Data Ingestion Service

Ingests Slack workspace history (**Historical Backfill**) and live channel traffic
(**Real-time Streaming**) into Parquet files on MinIO, queryable through ClickHouse views.
Built for compliance archiving: every message is kept, edits are versioned, and the
service is safe to pause, resume, kill and restart without losing or duplicating data.

```
Slack  ── conversations.history / .replies ─▶ IngestionService ──┐
Slack  ── Socket Mode (WebSocket) ──────────▶ RealtimeService ──┼─▶ MinIO (Parquet) ──s3()──▶ ClickHouse views
Slack  ── users.list / conversations.list ──▶ sync_metadata ────┘        ▲
                       checkpoints (_state/*.json) ─────────────────────┘ resume points
```

Control surface: a FastAPI app (`/docs` for Swagger). Stack: Python 3.14, uv, FastAPI,
slack-sdk, MinIO, ClickHouse.

## Quick start

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Python 3.14.

```powershell
docker compose up -d                  # MinIO (:9000, console :9001) + ClickHouse (:8123)
uv sync
Copy-Item .env.example .env           # then fill in the Slack tokens, see below
./scripts/apply-sql.ps1               # creates the ClickHouse views
uv run uvicorn app.main:app           # API on http://127.0.0.1:8000  (docs at /docs)
```

`apply-sql.ps1` just pipes each `sql/*.sql` file, in order, into `clickhouse-client` in
the container. It is safe to re-run (`CREATE OR REPLACE VIEW`).

### Slack app setup

| What                                                               | Where in the Slack app settings     |
| ------------------------------------------------------------------ | ----------------------------------- |
| Bot token scopes `channels:history`, `channels:read`, `users:read` | OAuth & Permissions                 |
| Socket Mode enabled                                                | Socket Mode                         |
| App-level token with `connections:write` (`xapp-...`)              | Basic Information, App-Level Tokens |
| Bot event `message.channels`                                       | Event Subscriptions                 |

Reinstall the app after changing scopes or events, and **invite the bot to every channel
you ingest** (`/invite @your-bot`). Private channels are not covered (see Limitations).

### Environment

Copy `.env.example` to `.env`. The ones that matter:

| Variable                                                                                 | Purpose                                                                                           |
| ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `SLACK_BOT_TOKEN`                                                                        | `xoxb-...` Web API calls (history, replies, users, channels)                                      |
| `SLACK_APP_TOKEN`                                                                        | `xapp-...` Socket Mode only. Optional: without it everything works except `/realtime/start` (503) |
| `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE` | object storage                                                                                    |
| `CLICKHOUSE_*`                                                                           | used by the SQL setup; the views read MinIO directly                                              |

## API

All routes are under `/api`. Pause and resume are **global**: one switch for both modes.

| Method and path                | What it does                                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `POST /backfill`               | `{"channel_ids": [...], "page_size": 200}`. Starts one worker per channel (3 in parallel). Returns 202 immediately |
| `POST /realtime/start`         | Opens the Socket Mode WebSocket, catches up on anything missed, then streams                                       |
| `POST /realtime/stop`          | Closes the WebSocket                                                                                               |
| `POST /pause` / `POST /resume` | Workers stop after the page they are on / continue                                                                 |
| `POST /metadata/sync`          | Snapshots users and channels (needed for names in the timeline view)                                               |
| `GET /status`                  | Per-channel backfill state and counts, real-time counters, paused flag                                             |

## Data layout

MinIO bucket (`slack-ingestion-service-dev` by default):

```
slack/historical/channel_id=C…/message_date=YYYY-MM-DD/<oldest_ts>_<newest_ts>_<hash>.parquet
slack/realtime/channel_id=C…/message_date=YYYY-MM-DD/<oldest_ts>_<newest_ts>_<hash>.parquet
slack/users/YYYY-MM-DD.parquet           # one snapshot file per day
slack/channels/YYYY-MM-DD.parquet
_state/historical/channel_id=C….json     # {"oldest_ts": ...}  backfill resume point
_state/realtime/channel_id=C….json       # {"newest_ts": ...}  real-time high-water mark
```

`_state/` sits outside `slack/` so ClickHouse never tries to read checkpoints as data.

### ClickHouse views (`sql/`)

| View                                            | Contents                                                                                                                |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `slack.v_slack_messages`                        | Messages from both modes, deduplicated: latest `version_ts` per `(channel_id, ts)`, ties broken by latest `ingested_at` |
| `slack.v_slack_users`, `slack.v_slack_channels` | Latest snapshot per user / channel                                                                                      |
| `slack.v_slack_compliance_timeline`             | Messages joined to user and channel details and to the thread parent's text. Search this one                            |

The views read Parquet straight from MinIO with `s3()`, with explicit column types so they
also work on an empty bucket. There is no insert pipeline: a file that lands in MinIO is
visible on the next query.

## How the guarantees work

| Guarantee                       | Mechanism                                                                                                                                                                                                                                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **No lost messages on crash**   | Checkpoint is written only _after_ the page (and its thread replies) landed in MinIO. A crash re-fetches at most one page                                                                                                                                                                         |
| **No duplicates after restart** | Object names are deterministic (`channel`, `message_date`, `ts` bounds, content hash that ignores `ingested_at`), so a retried page overwrites itself. Anything that still slips through (shifted page boundaries after the channel changed) is removed by the view's `LIMIT 1 BY channel_id, ts` |
| **Edits are versioned**         | Each row has `event_type` and `version_ts` (the edit time). The latest version wins in the view; older versions stay in the Parquet files for audit                                                                                                                                               |
| **Pause / resume**              | A shared `threading.Event`. Backfill workers wait after finishing a page, so pausing never interrupts a write. In real-time mode the WebSocket handler only acks and queues; a single worker writes, so events received while paused wait in the queue and flush on resume                        |
| **Real-time crash recovery**    | Each channel keeps a high-water mark. On `/realtime/start` the service fetches anything newer than the mark via `conversations.history` before streaming                                                                                                                                          |

Covered by unit tests: crash between two objects of one page, rerun after the channel
changed (documents that duplicates exist in storage and are removed by the view),
checkpointed resume.

### Design decisions

- **`message_date` partitioning instead of `processing_date`.** The brief suggests grouping
  by processing date. Partitioning by message date makes retries idempotent: a restart after
  midnight writes the same key instead of a new folder. Processing time is still recorded in
  the `ingested_at` column.
- **Views instead of an ETL into ClickHouse tables.** Less to operate, no second copy of the
  data, and dedup logic lives in one place.
- **Thread replies:** `conversations.history` returns parents only, so backfill calls
  `conversations.replies` for every parent with replies. Real-time receives replies as
  ordinary message events.

## Development

```powershell
uv run pytest tests/unit
uv run ruff check .
```

CI runs both on every push.

## Limitations and next steps

- **Not ingested yet:** file metadata, reactions, deletions (delete events are ignored).
- **Private channels and DMs:** only public channels are listed; private ones need `groups:*` scopes.
- **Replies added after a backfill** to an old thread are not picked up by re-running the
  backfill (history only reveals parents above the checkpoint). Real-time covers new replies
  while it runs.
- **Control API has no auth**, and `JWT_*` settings are leftovers from the service template.
- **Credentials** in `docker-compose.yml` and in the SQL files (`minioadmin`) are for local
  development; production would use ClickHouse named collections and a secrets store.
- **Single process.** Parallelism is thread-based within one service; scaling out would need
  per-channel work claiming.
- To re-backfill a channel from scratch, delete its `_state/historical/…` file.
