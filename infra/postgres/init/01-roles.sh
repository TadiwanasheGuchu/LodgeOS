#!/bin/sh
# Creates the two database roles LodgeOS uses.
#
#   lodgeos_owner  owns the schema and runs migrations. As table owner it is not
#                  subject to Row-Level Security, so it is only used by Alembic and
#                  operator CLI commands, never by the running API.
#   lodgeos_app    used by the API at runtime. It owns nothing and has NOBYPASSRLS,
#                  so every tenant table's RLS policy applies to it.
#
# Passwords come from the container environment. This script runs once, when the
# data volume is first initialised.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE lodgeos_owner LOGIN PASSWORD '${LODGEOS_OWNER_PASSWORD}' NOSUPERUSER CREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE lodgeos_app   LOGIN PASSWORD '${LODGEOS_APP_PASSWORD}'   NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE lodgeos OWNER lodgeos_owner;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname lodgeos <<SQL
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO lodgeos_owner;
GRANT USAGE ON SCHEMA public TO lodgeos_app;
SQL
