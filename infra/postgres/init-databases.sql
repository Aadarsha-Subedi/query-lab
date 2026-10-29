-- Runs once, when the postgres volume is first created.
-- querylab_app: Django's own database (models, migrations, users, sessions).
-- querylab:     the data the agent queries (demo schema; never migrated by Django).
CREATE DATABASE querylab_app;
CREATE DATABASE querylab;
