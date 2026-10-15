CREATE OR REPLACE VIEW slack.v_slack_messages AS
SELECT *
FROM s3(
    'http://minio:9000/slack-ingestion-service-dev/slack/{historical,realtime}/**/*.parquet',
    'minioadmin', 'minioadmin', 'Parquet',
    'channel_id String, ts String, event_type String, version_ts String,
     message_time DateTime64(6, ''UTC''), message_date Date32,
     thread_ts Nullable(String), user_id Nullable(String), text Nullable(String),
     subtype Nullable(String), edited_ts Nullable(String), raw_json String,
     ingested_at DateTime64(6, ''UTC''), source String'
)
ORDER BY version_ts DESC, ingested_at DESC
LIMIT 1 BY channel_id, ts;
