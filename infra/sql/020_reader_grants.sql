-- SELECT on every demo table, now and in future. Runs after the tables exist
-- (010). Idempotent. Placeholders as in 001_roles.sql.

GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {reader_role};
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT ON TABLES TO {reader_role};
