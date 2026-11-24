-- LodgeOS database setup for Neon (or any hosted PostgreSQL without superuser access).
-- Run once in the Neon SQL editor, connected to the "neondb" database as its owner.
-- Replace both passwords with long random ones first (for example from a password manager).
--
--   lodgeos_owner  owns the tables and runs migrations; as owner it is not subject to RLS.
--   lodgeos_app    used by the running app; owns nothing and cannot bypass Row-Level Security.

CREATE ROLE lodgeos_owner LOGIN PASSWORD 'REPLACE-WITH-OWNER-PASSWORD' NOSUPERUSER NOCREATEROLE NOBYPASSRLS;
CREATE ROLE lodgeos_app   LOGIN PASSWORD 'REPLACE-WITH-APP-PASSWORD'   NOSUPERUSER NOCREATEROLE NOBYPASSRLS;

-- Needed by the booking tables' exclusion constraints (no double-booked rooms).
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Hand the public schema to the migration role; the app role may only use it.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO lodgeos_owner;
GRANT USAGE ON SCHEMA public TO lodgeos_app;
GRANT CONNECT ON DATABASE neondb TO lodgeos_owner, lodgeos_app;
