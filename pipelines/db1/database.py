"""PostgreSQL analysis workspace, isolated from the published service schemas.

The --db argument identifies a schema, never a local database file. Connections
use the project's DB_* environment and close/commit at the context boundary.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
import re

from dotenv import load_dotenv
import psycopg2
from psycopg2 import DatabaseError, IntegrityError, OperationalError
from psycopg2.extras import DictCursor
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
SERVICE_SCHEMAS = {"public", "db1", "db1_v16", "db2", "work", "information_schema"}


def workspace(value=None):
    name = str(value or os.getenv("DB1_PIPELINE_SCHEMA") or "db1_pipeline")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name) or name in SERVICE_SCHEMAS or name.startswith("pg_"):
        raise ValueError("DB1 workspace must be a dedicated PostgreSQL schema name.")
    return name


def _open():
    options = {"host": os.environ["DB_HOST"], "port": int(os.getenv("DB_PORT") or 5432),
               "dbname": os.environ["DB_NAME"], "user": os.environ["DB_USER"],
               "password": os.environ["DB_PASSWORD"], "application_name": "welfind-analysis",
               "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT") or 10)}
    for key in ("sslmode", "sslrootcert"):
        if os.getenv("DB_" + key.upper()):
            options[key] = os.environ["DB_" + key.upper()]
    return psycopg2.connect(**options)


def ensure_workspace(name=None):
    name = workspace(name)
    raw = _open()
    try:
        with raw, raw.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(name)))
    finally:
        raw.close()
    return name


def exists(name=None):
    name = workspace(name)
    raw = _open()
    try:
        with raw.cursor() as cursor:
            cursor.execute("SELECT to_regnamespace(%s) IS NOT NULL", (name,))
            return cursor.fetchone()[0]
    finally:
        raw.close()


@contextmanager
def locked(name=None):
    name = workspace(name)
    raw = _open()
    raw.autocommit = True
    try:
        with raw.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(hashtext(%s))", ("welfind-analysis:" + name,))
            try:
                yield
            finally:
                cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", ("welfind-analysis:" + name,))
    finally:
        raw.close()


class Cursor:
    def __init__(self, cursor):
        self.raw = cursor

    def execute(self, statement, params=None):
        self.raw.execute(statement, params)
        return self

    def executemany(self, statement, rows):
        self.raw.executemany(statement, rows)
        return self

    @property
    def description(self):
        return self.raw.description

    @property
    def rowcount(self):
        return self.raw.rowcount

    def fetchone(self):
        return self.raw.fetchone()

    def fetchall(self):
        return self.raw.fetchall()

    def fetchmany(self, size=1000):
        return self.raw.fetchmany(size)

    def __iter__(self):
        return iter(self.raw)

    def close(self):
        self.raw.close()


class Connection:
    def __init__(self, name=None, *, readonly=False):
        self.schema = workspace(name)
        self.raw = _open()
        self.dict_rows = False
        self._context_depth = 0
        try:
            with self.raw.cursor() as cursor:
                cursor.execute("SELECT to_regnamespace(%s)", (self.schema,))
                if cursor.fetchone()[0] is None:
                    raise FileNotFoundError(f"PostgreSQL workspace {self.schema!r} is not initialized.")
                cursor.execute(sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(self.schema)))
            self.raw.commit()
            self.raw.set_session(readonly=readonly, isolation_level="REPEATABLE READ" if readonly else "READ COMMITTED")
        except BaseException:
            self.raw.close()
            raise

    def cursor(self):
        return Cursor(self.raw.cursor(cursor_factory=DictCursor if self.dict_rows else None))

    def execute(self, statement, params=None):
        return self.cursor().execute(statement, params)

    def executemany(self, statement, rows):
        return self.cursor().executemany(statement, rows)

    def executescript(self, statement):
        # The DDL is repository-owned SQL without bound values. PostgreSQL
        # executes the whole script inside the current transaction.
        return self.execute(statement)

    def table_names(self):
        return {row[0] for row in self.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema()")}

    def columns(self, table):
        return self.execute("""SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position""", (table,)).fetchall()

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        self._context_depth += 1
        return self

    def __exit__(self, kind, error, traceback):
        self._context_depth -= 1
        if self._context_depth:
            if kind is not None:
                self.rollback()
            return
        try:
            if kind is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


def connect(name=None, *, readonly=False, **options):
    if options:
        raise TypeError("Unsupported PostgreSQL connection options: " + ", ".join(options))
    return Connection(name, readonly=readonly)


def read_frame(statement, connection, params=None):
    """Build a dataframe directly from the PostgreSQL cursor and its columns."""
    import pandas as pd
    cursor = connection.execute(statement, params)
    try:
        return pd.DataFrame.from_records(cursor.fetchall(), columns=[item[0] for item in cursor.description])
    finally:
        cursor.close()
