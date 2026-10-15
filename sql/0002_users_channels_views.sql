CREATE OR REPLACE VIEW slack.v_slack_users AS
SELECT *
FROM s3(
    'http://minio:9000/slack-ingestion-service-dev/slack/users/*.parquet',
    'minioadmin', 'minioadmin', 'Parquet',
    'user_id String, name Nullable(String), real_name Nullable(String),
     display_name Nullable(String), is_bot Bool, deleted Bool, tz Nullable(String),
     raw_json String, ingested_at DateTime64(6, ''UTC'')'
)
ORDER BY ingested_at DESC
LIMIT 1 BY user_id;

CREATE OR REPLACE VIEW slack.v_slack_channels AS
SELECT *
FROM s3(
    'http://minio:9000/slack-ingestion-service-dev/slack/channels/*.parquet',
    'minioadmin', 'minioadmin', 'Parquet',
    'channel_id String, name Nullable(String), is_private Bool, is_archived Bool,
     created_at Nullable(DateTime64(6, ''UTC'')), creator Nullable(String),
     topic Nullable(String), purpose Nullable(String), num_members Nullable(Int32),
     raw_json String, ingested_at DateTime64(6, ''UTC'')'
)
ORDER BY ingested_at DESC
LIMIT 1 BY channel_id;
