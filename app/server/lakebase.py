"""Lakebase (Postgres) access for the Ops Console.

Reads the ML + GenAI lane action queue that Unity Catalog syncs into Lakebase
(`netopt_serving.lane_action_queue`, a synced table) and writes planner decisions
to an app-owned OLTP table (`netopt_ops.planner_actions`).

The app's `postgres` resource grants its service principal CAN_CONNECT_AND_CREATE;
LAKEBASE_ENDPOINT (app.yaml) names the compute endpoint. Host and user are taken from
PGHOST/PGUSER when the platform injects them, otherwise resolved from the endpoint and
the app's service principal. The password is a short-lived OAuth token refreshed
before its 1-hour expiry.
"""
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SERVING_SCHEMA = os.environ.get("LAKEBASE_SERVING_SCHEMA", "netopt_serving")
OPS_SCHEMA = os.environ.get("LAKEBASE_OPS_SCHEMA", "netopt_ops")
TOKEN_TTL = 45 * 60  # refresh well before the 60-minute credential expiry

_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()
_token: dict[str, Any] = {"value": None, "at": 0.0}


def enabled() -> bool:
    return bool(os.environ.get("LAKEBASE_ENDPOINT"))


def _host(w_factory: Callable) -> str:
    return os.environ.get("PGHOST") or \
        w_factory().postgres.get_endpoint(name=os.environ["LAKEBASE_ENDPOINT"]).status.hosts.host


def _password(w_factory: Callable) -> str:
    if not _token["value"] or time.time() - _token["at"] > TOKEN_TTL:
        cred = w_factory().postgres.generate_database_credential(endpoint=os.environ["LAKEBASE_ENDPOINT"])
        _token.update(value=cred.token, at=time.time())
    return _token["value"]


def pool(w_factory: Callable) -> ConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            class _TokenConnection(psycopg.Connection):
                @classmethod
                def connect(cls, conninfo: str = "", **kwargs):
                    kwargs["password"] = _password(w_factory)
                    return super().connect(conninfo, **kwargs)

            user = os.environ.get("PGUSER") or os.environ["DATABRICKS_CLIENT_ID"]
            conninfo = (f"host={_host(w_factory)} port={os.environ.get('PGPORT', '5432')} "
                        f"dbname={os.environ.get('PGDATABASE', 'databricks_postgres')} "
                        f"user={user} sslmode={os.environ.get('PGSSLMODE', 'require')}")
            _pool = ConnectionPool(conninfo, connection_class=_TokenConnection, min_size=1, max_size=5,
                                   max_lifetime=TOKEN_TTL, kwargs={"row_factory": dict_row}, open=True)
        return _pool


@contextmanager
def cursor(w_factory: Callable):
    with pool(w_factory).connection() as conn:
        with conn.cursor() as cur:
            yield cur


def init_schema(w_factory: Callable) -> None:
    """Create the app-owned operational schema (the app's service principal owns it)."""
    with cursor(w_factory) as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {OPS_SCHEMA}")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {OPS_SCHEMA}.planner_actions (
                action_id      BIGSERIAL PRIMARY KEY,
                directed_lane_id TEXT NOT NULL,
                decision       TEXT NOT NULL CHECK (decision IN ('APPROVED','REJECTED','SNOOZED')),
                action_type    TEXT,
                note           TEXT,
                expected_monthly_savings_usd NUMERIC(14,2),
                decided_by     TEXT,
                decided_at     TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
        cur.execute(f"CREATE INDEX IF NOT EXISTS planner_actions_lane_idx "
                    f"ON {OPS_SCHEMA}.planner_actions (directed_lane_id, decided_at DESC)")
