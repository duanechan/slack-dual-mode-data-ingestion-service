# Demo script (review Q&A)

> "Demonstrate switching between Historical Backfill mode and Real-time Streaming mode.
> Send a live Slack message and show it appear in ClickHouse in real time.
> Prove pause/resume and crash recovery."

Two PowerShell windows: **A** runs the server, **B** runs everything else.
Have Slack, the MinIO console (http://localhost:9001, `minioadmin`/`minioadmin`) and
`http://127.0.0.1:8000/docs` open next to them.

## 0. Preflight (do this before the review)

Window A, **without `--reload`** (kill and restart behave predictably that way):

```powershell
docker compose up -d
./scripts/apply-sql.ps1
uv run uvicorn app.main:app
```

Window B, paste once. Set `$ch2` to a second channel the bot has been invited to:

```powershell
$u   = "http://127.0.0.1:8000/api"
$ch1 = "C0C6AJHP204"          # ingest-test
$ch2 = "C0XXXXXXXXXX"         # <-- set me
$raw = "s3('http://minio:9000/slack-ingestion-service-dev/slack/{historical,realtime}/**/*.parquet','minioadmin','minioadmin','Parquet')"
function ch($q) { docker exec slack-ingestion-service-clickhouse clickhouse-client --password default --query $q }
function st { Invoke-RestMethod "$u/status" | ConvertTo-Json -Depth 5 }
function backfill($ids, $size) {
    $b = @{ channel_ids = @($ids); page_size = $size } | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post "$u/backfill" -ContentType "application/json" -Body $b
}
function reset($id) { docker exec slack-ingestion-service-minio mc rm "local/slack-ingestion-service-dev/_state/historical/channel_id=$($id).json" }
function counts {
    ch "SELECT count() AS raw_rows, uniqExact(channel_id, ts) AS unique_messages FROM $raw"
    ch "SELECT count() AS view_rows FROM slack.v_slack_messages"
}
Invoke-RestMethod -Method Post "$u/metadata/sync"     # users and channels, for names in the timeline
```

Clean slate (optional, then re-run the `metadata/sync` line):

```powershell
docker exec slack-ingestion-service-minio mc rm --recursive --force local/slack-ingestion-service-dev/slack
docker exec slack-ingestion-service-minio mc rm --recursive --force local/slack-ingestion-service-dev/_state
```

## 1. Mode 1: historical backfill, two channels in parallel

```powershell
backfill @($ch1, $ch2) 1      # page size 1 only to slow it down for the demo; 200 normally
st                            # run a few times: both channels "running", counts climbing
counts                        # raw_rows vs unique_messages vs view_rows
ch "SELECT channel_name, count() FROM slack.v_slack_compliance_timeline GROUP BY channel_name"
```

Say: one worker per channel, three at a time. Each page lands in MinIO as Parquet first,
and only then is the checkpoint saved.

## 2. Mode 2: real-time streaming, live message

```powershell
Invoke-RestMethod -Method Post "$u/realtime/start"
```

Post a message in Slack, then straight away:

```powershell
ch "SELECT message_time, channel_name, user_real_name, text, source FROM slack.v_slack_compliance_timeline ORDER BY message_time DESC LIMIT 3"
```

Say: WebSocket (Socket Mode). The handler acks and queues; a worker writes one Parquet file.
There is no insert step, since ClickHouse reads MinIO in place. Edit the message in Slack and
re-run the query: still one row, new text, `event_type = edited`.

## 3. Switching modes

```powershell
st                                                       # "channels" = backfill, "realtime" = stream
Invoke-RestMethod -Method Post "$u/realtime/stop"
reset $ch1; backfill $ch1 200                            # backfill again while the stream is off
Invoke-RestMethod -Method Post "$u/realtime/start"
```

Say: the modes are independent switches over the same storage and the same views.
Pause and resume are shared by both.

## 4. Pause and resume

```powershell
reset $ch1; backfill $ch1 1; Start-Sleep 2
Invoke-RestMethod -Method Post "$u/pause" | Out-Null
st; Start-Sleep 5; st                                    # backfill count frozen
```

While paused, post a message in Slack, then:

```powershell
(Invoke-RestMethod "$u/status").realtime                 # queued = 1, and it is not in ClickHouse yet
Invoke-RestMethod -Method Post "$u/resume" | Out-Null
```

The queued message appears and the backfill finishes. Say: pause stops after the current
page, so it never interrupts a write.

## 5. Crash recovery (backfill)

```powershell
reset $ch1; backfill $ch1 1; Start-Sleep 2
Invoke-RestMethod -Method Post "$u/pause" | Out-Null
st                                                       # note messages = N, with N < total
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess -Force
docker exec slack-ingestion-service-minio mc ls --recursive local/slack-ingestion-service-dev/_state
```

Window A: `uv run uvicorn app.main:app`. Then window B:

```powershell
backfill $ch1 1; Start-Sleep 12
st                                                       # messages = total - N: only the remainder
counts                                                   # unique_messages == view_rows == total
```

Say: hard kill, not a graceful stop. The checkpoint file survived, the restart fetched only
what was missing, and no row is lost or duplicated.

## 6. Crash recovery (real-time)

With real-time running and at least one real-time message already written:

```powershell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess -Force
```

Post two messages in Slack while the server is down. Window A: restart uvicorn. Window B:

```powershell
Invoke-RestMethod -Method Post "$u/realtime/start"
ch "SELECT ts, text, source FROM slack.v_slack_messages ORDER BY ts DESC LIMIT 3"
```

Both messages appear (catch-up from each channel's high-water mark).

## 7. Dedup proof (optional)

In the MinIO console, download one Parquet file under `slack/historical/...` and upload it
again under a different name in the same folder. Then:

```powershell
counts          # raw_rows doubles for that file, unique_messages and view_rows do not
```

## If something goes wrong

| Symptom                            | Check                                                                            |
| ---------------------------------- | -------------------------------------------------------------------------------- |
| `state: failed`, `not_in_channel`  | Invite the bot: `/invite @bot`                                                   |
| `/realtime/start` returns 503      | `SLACK_APP_TOKEN` missing in `.env`; restart the server                          |
| Real-time `events_written` stays 0 | Bot not in channel, or `message.channels` event not subscribed                   |
| Backfill returns 0 messages        | Channel already finished: run `reset <id>` first                                 |
| Timeline names are NULL            | Run `POST /metadata/sync` and check the bot has `users:read` and `channels:read` |
| `last_error` in `GET /status`      | Server log shows the traceback                                                   |
