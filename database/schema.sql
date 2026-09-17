CREATE TABLE IF NOT EXISTS `warns` (
  `id` int(11) NOT NULL,
  `user_id` varchar(20) NOT NULL,
  `server_id` varchar(20) NOT NULL,
  `moderator_id` varchar(20) NOT NULL,
  `reason` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `score_channels` (
  `server_id` varchar(20) NOT NULL,
  `channel_id` varchar(20) NOT NULL,
  PRIMARY KEY (`server_id`)
);

-- One row per (guild, user, game, day): many users x many games,
-- one score per message. Re-posting a daily score overwrites the row.
CREATE TABLE IF NOT EXISTS `user_scores` (
  `guild_id`   varchar(20)  NOT NULL,
  `user_id`    varchar(20)  NOT NULL,
  `game`       varchar(32)  NOT NULL,
  `day`        varchar(10)  NOT NULL,
  `score`      int          NOT NULL,
  `user_name`  varchar(255) NOT NULL,
  `meta`       text         NULL,
  `created_at` timestamp    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`guild_id`, `user_id`, `game`, `day`)
);