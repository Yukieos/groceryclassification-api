import os
import requests

from db import get_connection, normalize, search_price

RESEND_API_URL = "https://api.resend.com/emails"
NOTIFY_COOLDOWN_HOURS = 24


def create_alert(email: str, item: str, target_price: float) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO price_alerts (email, search_term, normalized_term, target_price)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (email, item, normalize(item), target_price),
        )
        alert_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    return alert_id


def list_alerts(email: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, search_term, target_price, active, last_notified_at
            FROM price_alerts WHERE email = %s ORDER BY created_at DESC
            """,
            (email,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0],
            "item": r[1],
            "target_price": float(r[2]),
            "active": r[3],
            "last_notified_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


def delete_alert(alert_id: int, email: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM price_alerts WHERE id = %s AND email = %s", (alert_id, email))
        deleted = cur.rowcount > 0
        conn.commit()
    finally:
        conn.close()
    return deleted


def _send_email(to: str, subject: str, html: str):
    api_key = os.environ["RESEND_API_KEY"]
    resp = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": os.environ.get("RESEND_FROM", "GroceryScan <onboarding@resend.dev>"),
            "to": [to],
            "subject": subject,
            "html": html,
        },
        timeout=10,
    )
    resp.raise_for_status()


def check_alerts() -> dict:
    """Meant to be hit by a Vercel Cron job. For each active alert, looks up
    the current cheapest match and emails the owner if it's at or under
    their target - at most once per NOTIFY_COOLDOWN_HOURS so a deal that
    lasts a week doesn't spam them every run."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, search_term, target_price
            FROM price_alerts
            WHERE active = true
              AND (last_notified_at IS NULL OR last_notified_at < now() - (%s || ' hours')::interval)
            """,
            (NOTIFY_COOLDOWN_HOURS,),
        )
        alerts = cur.fetchall()
    finally:
        conn.close()

    notified = []
    for alert_id, email, search_term, target_price in alerts:
        target_price = float(target_price)
        matches = search_price(search_term, limit=1)
        if not matches or matches[0]["price"] > target_price:
            continue

        best = matches[0]
        try:
            _send_email(
                email,
                f"{search_term} is now ${best['price']:.2f} at {best['vendor']}",
                f"<p><b>{best['product_name']}</b> at <b>{best['vendor']}</b> is now "
                f"${best['price']:.2f}, at or under your ${target_price:.2f} target for "
                f"\"{search_term}\".</p>",
            )
        except Exception:
            continue

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE price_alerts SET last_notified_at = now() WHERE id = %s", (alert_id,))
            conn.commit()
        finally:
            conn.close()
        notified.append(alert_id)

    return {"checked": len(alerts), "notified": notified}
