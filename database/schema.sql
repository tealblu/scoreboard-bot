CREATE TABLE IF NOT EXISTS `score_channels` (
  `server_id` varchar(20) NOT NULL,
  `channel_id` varchar(20) NOT NULL,
  PRIMARY KEY (`server_id`)
);

-- One row per guild: daily reminder configuration.
-- `reminder_time` is "HH:MM" in UTC (24-hour). `last_fired` stores the last
-- date (YYYY-MM-DD) the reminder was sent so it doesn't re-fire that day.
CREATE TABLE IF NOT EXISTS `daily_reminders` (
  `server_id`     varchar(20) NOT NULL,
  `enabled`       int         NOT NULL DEFAULT 0,
  `reminder_time` varchar(5)  NOT NULL DEFAULT '09:00',
  `last_fired`    varchar(10) NULL,
  `updated_at`    timestamp   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`server_id`)
);

-- One row per (guild, user, game, day): many users x many games,
-- one score per message. Re-posting a daily score overwrites the row.
-- `score` is REAL so decimal scores (e.g. dialed's 40.49/50) store exactly;
-- most games still write whole numbers.
CREATE TABLE IF NOT EXISTS `user_scores` (
  `guild_id`   varchar(20)  NOT NULL,
  `user_id`    varchar(20)  NOT NULL,
  `game`       varchar(32)  NOT NULL,
  `day`        varchar(10)  NOT NULL,
  `score`      real         NOT NULL,
  `user_name`  varchar(255) NOT NULL,
  `meta`       text         NULL,
  `created_at` timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`guild_id`, `user_id`, `game`, `day`)
);