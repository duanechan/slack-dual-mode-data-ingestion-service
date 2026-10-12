CREATE OR REPLACE VIEW slack.v_slack_messages AS
SELECT *
FROM s3(
    'http://minio:9000/slack-ingestion-service-dev/slack/**/*.parquet',
    'minioadmin', 'minioadmin', 'Parquet'
)
ORDER BY version_ts DESC
LIMIT 1 BY channel_id, ts;
