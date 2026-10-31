-- The wall around user workspaces (step 5). Applied by `manage.py
-- bootstrap_data_db` after 001, with the same placeholders. Idempotent.
--
-- Who creates what: the platform owner role (the one in DATA_PRIMARY_URL)
-- creates every workspace schema and both of its login roles
-- (workspaces/provisioning.py), and nothing else does. Workspace roles are
-- members of nothing and nobody but the owner role is a member of them, so no
-- SET ROLE path exists from one workspace to another.
--
-- This file makes the shared parts of the database closed by default: a
-- workspace role is granted CONNECT on `querylab`, USAGE on its own schema and
-- nothing else.

-- The platform data (users, sessions, runs) is unreachable for workspace roles.
REVOKE ALL ON DATABASE {app_db} FROM PUBLIC;

-- Nobody connects to the data database unless granted: the reader here, each
-- workspace role at provisioning.
REVOKE CONNECT ON DATABASE {data_db} FROM PUBLIC;
GRANT CONNECT ON DATABASE {data_db} TO {reader_role};

-- No access to `public` or to the demo schema through PUBLIC. The Olist demo is
-- queried only as the reader role (granted in 001 and 020).
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA {schema} FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {schema} FROM PUBLIC;

-- No CREATE for PUBLIC on any schema that is not a workspace's own.
DO $$
DECLARE
    namespace record;
BEGIN
    FOR namespace IN
        SELECT nspname FROM pg_namespace
        WHERE nspname NOT LIKE 'pg\_%' ESCAPE '\'
          AND nspname <> 'information_schema'
          AND nspname NOT LIKE 'ws\_%' ESCAPE '\'
    LOOP
        EXECUTE format('REVOKE CREATE ON SCHEMA %I FROM PUBLIC', namespace.nspname);
    END LOOP;
END
$$;
