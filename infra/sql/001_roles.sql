-- Roles and the read-only boundary for the data database (querylab).
-- Applied by `manage.py bootstrap_data_db`, which fills in every placeholder
-- in braces from settings (see core/datadb.py for the list). Idempotent: safe
-- to run again at any time.

CREATE SCHEMA IF NOT EXISTS {schema};

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = {reader_role_name}) THEN
        CREATE ROLE {reader_role} LOGIN;
    END IF;
END
$$;

ALTER ROLE {reader_role} WITH LOGIN PASSWORD {reader_password}
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;

-- Every transaction is read-only and every statement has a time limit. These
-- are role defaults the agent could SET differently, so the privileges below
-- are what actually stop writes; these settings stop runaway reads.
ALTER ROLE {reader_role} SET default_transaction_read_only = on;
ALTER ROLE {reader_role} SET statement_timeout = {statement_timeout};

-- Nobody but the owner creates objects in public, or temp tables here.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE {data_db} FROM PUBLIC;
GRANT CONNECT ON DATABASE {data_db} TO {reader_role};

-- The reader cannot even connect to the app database (users, sessions).
REVOKE ALL ON DATABASE {app_db} FROM PUBLIC;

REVOKE ALL ON SCHEMA {schema} FROM PUBLIC;
GRANT USAGE ON SCHEMA {schema} TO {reader_role};
