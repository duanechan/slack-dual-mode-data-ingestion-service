CREATE OR REPLACE VIEW slack.v_slack_compliance_timeline AS
SELECT
    m.message_time AS message_time,
    m.channel_id AS channel_id,
    c.name AS channel_name,
    c.is_private AS channel_is_private,
    m.user_id AS user_id,
    u.name AS user_name,
    u.real_name AS user_real_name,
    u.is_bot AS user_is_bot,
    m.ts AS ts,
    m.event_type AS event_type,
    m.text AS text,
    m.subtype AS subtype,
    m.thread_ts AS thread_ts,
    ifNull(m.thread_ts != m.ts, false) AS is_thread_reply,
    p.text AS thread_parent_text,
    m.source AS source,
    m.ingested_at AS ingested_at
FROM slack.v_slack_messages AS m
LEFT JOIN slack.v_slack_users AS u ON m.user_id = u.user_id
LEFT JOIN slack.v_slack_channels AS c ON m.channel_id = c.channel_id
LEFT JOIN slack.v_slack_messages AS p
    ON m.channel_id = p.channel_id AND m.thread_ts = p.ts
ORDER BY m.message_time DESC
SETTINGS join_use_nulls = 1;
