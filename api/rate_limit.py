from db import get_connection

_TABLE_READY = False


def _ensure_table(cur):
    global _TABLE_READY
    if _TABLE_READY:
        return
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_limits (
            client_key TEXT PRIMARY KEY,
            window_start TIMESTAMPTZ NOT NULL DEFAULT now(),
            request_count INT NOT NULL DEFAULT 0
        )
        """
    )
    _TABLE_READY = True


def check_and_increment(client_key: str, limit: int = 20, window_minutes: int = 60) -> bool:
    """Atomically increments this client's request count for the current
    window and returns whether they're still under the limit. Backed by
    Postgres (already in use elsewhere) rather than a new service, since this
    app's traffic is small enough that a table scan-free upsert is plenty."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        _ensure_table(cur)
        cur.execute(
            """
            INSERT INTO rate_limits (client_key, window_start, request_count)
            VALUES (%s, now(), 1)
            ON CONFLICT (client_key) DO UPDATE SET
                request_count = CASE
                    WHEN rate_limits.window_start < now() - (%s || ' minutes')::interval
                        THEN 1
                    ELSE rate_limits.request_count + 1
                END,
                window_start = CASE
                    WHEN rate_limits.window_start < now() - (%s || ' minutes')::interval
                        THEN now()
                    ELSE rate_limits.window_start
                END
            RETURNING request_count
            """,
            (client_key, window_minutes, window_minutes),
        )
        request_count = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return request_count <= limit
