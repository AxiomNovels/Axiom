[
  {
    "table_name": "friendships",
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": "gen_random_uuid()"
  },
  {
    "table_name": "friendships",
    "column_name": "user_id_1",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "friendships",
    "column_name": "user_id_2",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "friendships",
    "column_name": "requested_by",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "friendships",
    "column_name": "status",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'pending'::text"
  },
  {
    "table_name": "friendships",
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "friendships",
    "column_name": "responded_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "home_feature",
    "column_name": "id",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "true"
  },
  {
    "table_name": "home_feature",
    "column_name": "novel_id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "home_feature",
    "column_name": "inquiry",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "home_feature",
    "column_name": "description",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "home_feature",
    "column_name": "tags",
    "data_type": "ARRAY",
    "is_nullable": "NO",
    "column_default": "'{}'::text[]"
  },
  {
    "table_name": "home_feature",
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "notifications",
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": "gen_random_uuid()"
  },
  {
    "table_name": "notifications",
    "column_name": "user_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "notifications",
    "column_name": "subject",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "notifications",
    "column_name": "body",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "notifications",
    "column_name": "is_read",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "false"
  },
  {
    "table_name": "notifications",
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "notifications",
    "column_name": "type",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'system'::text"
  },
  {
    "table_name": "notifications",
    "column_name": "data",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'{}'::jsonb"
  },
  {
    "table_name": "novels",
    "column_name": "id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "novels",
    "column_name": "title",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "novels",
    "column_name": "author",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "novels",
    "column_name": "cover_image_url",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "novels",
    "column_name": "synopsis",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "novels",
    "column_name": "status",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'ongoing'::text"
  },
  {
    "table_name": "novels",
    "column_name": "tags",
    "data_type": "ARRAY",
    "is_nullable": "NO",
    "column_default": "'{}'::text[]"
  },
  {
    "table_name": "novels",
    "column_name": "reading_links",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": "'[]'::jsonb"
  },
  {
    "table_name": "novels",
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "novels",
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "novels",
    "column_name": "chapter_count",
    "data_type": "integer",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "novels",
    "column_name": "genres",
    "data_type": "ARRAY",
    "is_nullable": "NO",
    "column_default": "'{}'::text[]"
  },
  {
    "table_name": "profiles",
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "username",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "profiles",
    "column_name": "about_me",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "gender",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'Prefer not to say'::text"
  },
  {
    "table_name": "profiles",
    "column_name": "city",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "country",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "tag_preferences",
    "data_type": "ARRAY",
    "is_nullable": "NO",
    "column_default": "'{}'::text[]"
  },
  {
    "table_name": "profiles",
    "column_name": "avatar_url",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "novels_uploaded",
    "data_type": "ARRAY",
    "is_nullable": "NO",
    "column_default": "'{}'::bigint[]"
  },
  {
    "table_name": "profiles",
    "column_name": "discord_username",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "discord_visibility",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'friends_only'::text"
  },
  {
    "table_name": "profiles",
    "column_name": "instagram_username",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "instagram_visibility",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'friends_only'::text"
  },
  {
    "table_name": "profiles",
    "column_name": "reddit_username",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "reddit_visibility",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'friends_only'::text"
  },
  {
    "table_name": "profiles",
    "column_name": "tiktok_username",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "profiles",
    "column_name": "tiktok_visibility",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'friends_only'::text"
  },
  {
    "table_name": "profiles",
    "column_name": "online_status_visibility",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'public'::text"
  },
  {
    "table_name": "protagonist_baselines",
    "column_name": "novel_id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_baselines",
    "column_name": "scores",
    "data_type": "jsonb",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_baselines",
    "column_name": "generated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "novel_id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "protagonist_name",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "impulsivity",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "arrogance_pride",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "kinship_friendship",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "romantic_attachment",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "sexual_desire",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "selflessness",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "scores_locked",
    "data_type": "boolean",
    "is_nullable": "NO",
    "column_default": "false"
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "intellectual_drive",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "selflessness_selfishness",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "pragmatism_morality",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "individualist_collectivist",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "ambition",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "cautious_risk_taker",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_profiles",
    "column_name": "leadership",
    "data_type": "smallint",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "job_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "novel_id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "status",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'queued'::text"
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "error",
    "data_type": "text",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "started_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_items",
    "column_name": "finished_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": "gen_random_uuid()"
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "requested_by",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "mode",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "status",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": "'queued'::text"
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "total",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "processed",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "succeeded",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "failed",
    "data_type": "integer",
    "is_nullable": "NO",
    "column_default": "0"
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "started_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_rebuild_jobs",
    "column_name": "finished_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "YES",
    "column_default": null
  },
  {
    "table_name": "protagonist_votes",
    "column_name": "id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_votes",
    "column_name": "novel_id",
    "data_type": "bigint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_votes",
    "column_name": "user_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_votes",
    "column_name": "trait",
    "data_type": "text",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_votes",
    "column_name": "score",
    "data_type": "smallint",
    "is_nullable": "NO",
    "column_default": null
  },
  {
    "table_name": "protagonist_votes",
    "column_name": "created_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "protagonist_votes",
    "column_name": "updated_at",
    "data_type": "timestamp with time zone",
    "is_nullable": "NO",
    "column_default": "now()"
  },
  {
    "table_name": "reading_list_likes",
    "column_name": "id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": "gen_random_uuid()"
  },
  {
    "table_name": "reading_list_likes",
    "column_name": "reading_list_id",
    "data_type": "uuid",
    "is_nullable": "NO",
    "column_default": null
  }
]