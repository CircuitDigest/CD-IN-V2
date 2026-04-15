import re
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .webinar_db import get_webinar_connection
from .webinar_messaging import WebinarMessagingError, send_msg91_email, send_msg91_whatsapp


EMAIL_PATTERN = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
ALLOWED_DOMAINS = {
    "Embedded Systems",
    "Power Electronics",
    "IoT and Connected Devices",
    "Robotics and Automation",
    "EV and BMS",
    "Solar and Renewables",
    "AI and Edge ML",
}

ALLOWED_COUNTRIES = {
    "India",
    "United States",
    "United Kingdom",
    "Canada",
    "Germany",
    "Australia",
    "Singapore",
}


def normalize_phone(raw_phone: str) -> str:
    digits = re.sub(r"\D", "", raw_phone or "")
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    raise ValueError("Please enter a valid 10-digit phone number.")


def get_active_webinar() -> Optional[Dict[str, Any]]:
    with get_webinar_connection() as conn:
        row = conn.execute(
            "SELECT * FROM webinar_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def validate_registration_form(form: Dict[str, str]) -> Dict[str, Any]:
    full_name = form.get("full_name", "").strip()
    email = form.get("email", "").strip().lower()
    phone = form.get("phone", "").strip()
    city = form.get("city", "").strip()
    country = form.get("country", "").strip()
    occupation = form.get("occupation", "").strip()
    organization_name = form.get("organization_name", "").strip()
    domain_interest = form.get("domain_interest", "").strip()
    wants_to_present = form.get("wants_to_present", "") == "on"
    presentation_topic = form.get("presentation_topic", "").strip()
    presentation_description = form.get("presentation_description", "").strip()
    terms_accepted = form.get("terms_accepted") == "on"
    honeypot = form.get("website", "").strip()

    if honeypot:
        raise ValueError("Invalid form submission.")
    if not full_name:
        raise ValueError("Full name is required.")
    if not email or not EMAIL_PATTERN.match(email):
        raise ValueError("Valid email is required.")
    if not occupation:
        raise ValueError("Occupation is required.")
    if not organization_name:
        if occupation in {"Student", "Educator"}:
            raise ValueError("University/Institute name is required.")
        raise ValueError("Company/Organization name is required.")
    if not domain_interest:
        raise ValueError("Domain of interest is required.")
    if domain_interest not in ALLOWED_DOMAINS:
        raise ValueError("Please select a valid domain of interest from the list.")
    if not terms_accepted:
        raise ValueError("You must accept the terms to register.")
    if not country:
        raise ValueError("Country is required.")
    if country not in ALLOWED_COUNTRIES:
        raise ValueError("Please select a valid country from the list.")

    social_linkedin = form.get("social_linkedin", "").strip()
    social_instagram = form.get("social_instagram", "").strip()
    social_x = form.get("social_x", "").strip()
    social_youtube = form.get("social_youtube", "").strip()
    social_github = ""

    phone_e164 = normalize_phone(phone)
    if wants_to_present and not presentation_topic:
        raise ValueError("Presentation topic is required if you want to present.")
    if wants_to_present and not presentation_description:
        raise ValueError("Please add a short presentation description.")

    return {
        "full_name": full_name,
        "email": email,
        "phone_e164": phone_e164,
        "city": city,
        "country": country,
        "occupation": occupation,
        "organization_name": organization_name,
        "domain_interest": domain_interest,
        "social_linkedin": social_linkedin,
        "social_instagram": social_instagram,
        "social_x": social_x,
        "social_youtube": social_youtube,
        "social_github": social_github,
        "wants_to_present": 1 if wants_to_present else 0,
        "presentation_topic": presentation_topic,
        "presentation_description": presentation_description,
        "terms_accepted": 1,
    }


def _rate_limit_check(conn, ip_address: str, email: str, phone_e164: str) -> None:
    cutoff = (datetime.utcnow() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    ip_count = conn.execute(
        "SELECT COUNT(*) AS cnt FROM webinar_registration WHERE ip_address = ? AND registered_at >= ?",
        (ip_address, cutoff),
    ).fetchone()["cnt"]
    if ip_count >= 8:
        raise ValueError("Too many submissions from this IP. Please try later.")

    identity_count = conn.execute(
        """
        SELECT COUNT(*) AS cnt FROM webinar_registration
        WHERE (email = ? OR phone_e164 = ?) AND registered_at >= ?
        """,
        (email, phone_e164, cutoff),
    ).fetchone()["cnt"]
    if identity_count >= 3:
        raise ValueError("Too many attempts. Please try later.")


def _ensure_unique_for_webinar(conn, webinar_config_id: int, email: str, phone_e164: str) -> None:
    row = conn.execute(
        """
        SELECT id FROM webinar_registration
        WHERE webinar_config_id = ? AND (email = ? OR phone_e164 = ?)
        LIMIT 1
        """,
        (webinar_config_id, email, phone_e164),
    ).fetchone()
    if row:
        raise ValueError("This email or phone is already registered for the active webinar.")


def create_registration(form: Dict[str, str], ip_address: str) -> int:
    webinar = get_active_webinar()
    if not webinar:
        raise ValueError("No active webinar is available for registration.")

    payload = validate_registration_form(form)
    with get_webinar_connection() as conn:
        _rate_limit_check(conn, ip_address, payload["email"], payload["phone_e164"])
        _ensure_unique_for_webinar(
            conn, webinar["id"], payload["email"], payload["phone_e164"]
        )

        conn.execute(
            """
            INSERT INTO webinar_registration (
                webinar_config_id, full_name, email, phone_e164, city, country,
                occupation, organization_name, domain_interest, social_linkedin, social_instagram,
                social_x, social_youtube, social_github, wants_to_present,
                presentation_topic, presentation_description, terms_accepted, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                webinar["id"],
                payload["full_name"],
                payload["email"],
                payload["phone_e164"],
                payload["city"],
                payload["country"],
                payload["occupation"],
                payload["organization_name"],
                payload["domain_interest"],
                payload["social_linkedin"],
                payload["social_instagram"],
                payload["social_x"],
                payload["social_youtube"],
                payload["social_github"],
                payload["wants_to_present"],
                payload["presentation_topic"],
                payload["presentation_description"],
                payload["terms_accepted"],
                ip_address,
            ),
        )
        registration_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.commit()
    return registration_id


def _insert_delivery(
    conn,
    registration_id: int,
    channel: str,
    message_type: str,
    status: str,
    provider_message_id: str = "",
    error_message: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO webinar_message_delivery
        (registration_id, channel, message_type, status, provider_message_id, error_message, sent_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(registration_id, channel, message_type) DO UPDATE SET
            status = excluded.status,
            provider_message_id = excluded.provider_message_id,
            error_message = excluded.error_message,
            sent_at = datetime('now')
        """,
        (registration_id, channel, message_type, status, provider_message_id, error_message),
    )


def _already_sent(conn, registration_id: int, channel: str, message_type: str) -> bool:
    row = conn.execute(
        """
        SELECT id FROM webinar_message_delivery
        WHERE registration_id = ? AND channel = ? AND message_type = ? AND status = 'sent'
        LIMIT 1
        """,
        (registration_id, channel, message_type),
    ).fetchone()
    return bool(row)


def send_registration_confirmation(registration_id: int) -> None:
    with get_webinar_connection() as conn:
        row = conn.execute(
            """
            SELECT r.*, c.topic, c.webinar_date, c.webinar_time, c.meeting_link
            FROM webinar_registration r
            JOIN webinar_config c ON c.id = r.webinar_config_id
            WHERE r.id = ?
            """,
            (registration_id,),
        ).fetchone()
        if not row:
            return

        if not _already_sent(conn, registration_id, "email", "confirmation"):
            try:
                result = send_msg91_email(
                    row["email"],
                    os.environ.get("WEBINAR_EMAIL_TEMPLATE_CONFIRMATION", "cd_webinar_confirmation"),
                    {
                        "name": row["full_name"],
                        "topic": row["topic"],
                        "date": row["webinar_date"],
                        "time": row["webinar_time"],
                        "link": row["meeting_link"],
                    },
                )
                _insert_delivery(conn, registration_id, "email", "confirmation", "sent", result["provider_message_id"])
            except WebinarMessagingError as exc:
                _insert_delivery(conn, registration_id, "email", "confirmation", "failed", error_message=str(exc))

        if not _already_sent(conn, registration_id, "whatsapp", "confirmation"):
            try:
                result = send_msg91_whatsapp(
                    row["phone_e164"],
                    os.environ.get("WEBINAR_WHATSAPP_TEMPLATE_CONFIRMATION", "event_webinar_confirmation"),
                    {
                        "body_1": row["full_name"],
                        "body_2": row["topic"],
                        "body_3": f"{row['webinar_date']} {row['webinar_time']}",
                        "body_4": row["meeting_link"] or "",
                    },
                )
                _insert_delivery(conn, registration_id, "whatsapp", "confirmation", "sent", result["provider_message_id"])
            except WebinarMessagingError as exc:
                _insert_delivery(conn, registration_id, "whatsapp", "confirmation", "failed", error_message=str(exc))

        conn.commit()


def _message_type_to_delta(message_type: str) -> timedelta:
    if message_type == "reminder_24h":
        return timedelta(hours=24)
    if message_type == "reminder_1h":
        return timedelta(hours=1)
    if message_type in ("reminder_live", "reminder_10m_or_live"):
        return timedelta(minutes=10)
    raise ValueError(f"Unsupported message type: {message_type}")


def trigger_manual_reminder(message_type: str) -> Dict[str, int]:
    with get_webinar_connection() as conn:
        webinar = conn.execute(
            "SELECT * FROM webinar_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not webinar:
            raise ValueError("No active webinar configured.")
        registrations = conn.execute(
            "SELECT * FROM webinar_registration WHERE webinar_config_id = ?",
            (webinar["id"],),
        ).fetchall()

        sent_count = 0
        failed_count = 0
        for row in registrations:
            for channel in ("email", "whatsapp"):
                if _already_sent(conn, row["id"], channel, message_type):
                    continue
                try:
                    if channel == "email":
                        result = send_msg91_email(
                            row["email"],
                            os.environ.get(
                                "WEBINAR_EMAIL_TEMPLATE_" + message_type.upper(),
                                "cd_webinar_reminder",
                            ),
                            {
                                "name": row["full_name"],
                                "topic": webinar["topic"],
                                "date": webinar["webinar_date"],
                                "time": webinar["webinar_time"],
                            },
                        )
                    else:
                        template = os.environ.get(
                            "WEBINAR_WHATSAPP_TEMPLATE_" + message_type.upper(),
                            "event_webinar_reminder",
                        )
                        result = send_msg91_whatsapp(
                            row["phone_e164"],
                            template,
                            {
                                "body_1": row["full_name"],
                                "body_2": webinar["topic"],
                                "body_3": f"{webinar['webinar_date']} {webinar['webinar_time']}",
                                "body_4": webinar["meeting_link"] or "",
                            },
                        )
                    _insert_delivery(
                        conn,
                        row["id"],
                        channel,
                        message_type,
                        "sent",
                        result["provider_message_id"],
                    )
                    sent_count += 1
                except WebinarMessagingError as exc:
                    _insert_delivery(conn, row["id"], channel, message_type, "failed", error_message=str(exc))
                    failed_count += 1
        conn.commit()
    return {"sent": sent_count, "failed": failed_count}


def run_scheduled_reminders() -> Dict[str, int]:
    now = datetime.utcnow()
    results = {"sent": 0, "failed": 0}

    with get_webinar_connection() as conn:
        webinar = conn.execute(
            "SELECT * FROM webinar_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not webinar:
            return results

        event_dt = datetime.strptime(
            f"{webinar['webinar_date']} {webinar['webinar_time']}", "%Y-%m-%d %H:%M"
        )
        registrations = conn.execute(
            "SELECT * FROM webinar_registration WHERE webinar_config_id = ?",
            (webinar["id"],),
        ).fetchall()

        reminder_types = ("reminder_24h", "reminder_1h", "reminder_live")
        for reminder_type in reminder_types:
            scheduled_time = event_dt - _message_type_to_delta(reminder_type)
            # 20-minute send window to avoid misses with cron delays.
            if not (scheduled_time <= now <= scheduled_time + timedelta(minutes=20)):
                continue
            for row in registrations:
                for channel in ("email", "whatsapp"):
                    if _already_sent(conn, row["id"], channel, reminder_type):
                        continue
                    try:
                        if channel == "email":
                            result = send_msg91_email(
                                row["email"],
                                os.environ.get(
                                    "WEBINAR_EMAIL_TEMPLATE_" + reminder_type.upper(),
                                    "cd_webinar_reminder",
                                ),
                                {
                                    "name": row["full_name"],
                                    "topic": webinar["topic"],
                                    "date": webinar["webinar_date"],
                                    "time": webinar["webinar_time"],
                                },
                            )
                        else:
                            template = os.environ.get(
                                "WEBINAR_WHATSAPP_TEMPLATE_" + reminder_type.upper(),
                                "event_webinar_reminder",
                            )
                            result = send_msg91_whatsapp(
                                row["phone_e164"],
                                template,
                                {
                                    "body_1": row["full_name"],
                                    "body_2": webinar["topic"],
                                    "body_3": f"{webinar['webinar_date']} {webinar['webinar_time']}",
                                    "body_4": webinar["meeting_link"] or "",
                                },
                            )
                        _insert_delivery(
                            conn, row["id"], channel, reminder_type, "sent", result["provider_message_id"]
                        )
                        results["sent"] += 1
                    except WebinarMessagingError as exc:
                        _insert_delivery(conn, row["id"], channel, reminder_type, "failed", error_message=str(exc))
                        results["failed"] += 1
        conn.commit()

    return results


def admin_save_webinar_config(form: Dict[str, str], banner_url: str = "") -> None:
    topic = form.get("topic", "").strip()
    webinar_date = form.get("webinar_date", "").strip()
    webinar_time = form.get("webinar_time", "").strip()
    meeting_link = form.get("meeting_link", "").strip()
    description = form.get("description", "").strip()
    duration_minutes = int(form.get("duration_minutes", 60) or 60)
    is_active = 1 if form.get("is_active") == "on" else 0

    if not topic or not webinar_date or not webinar_time or not meeting_link:
        raise ValueError("Topic, date, time and meeting link are required.")

    with get_webinar_connection() as conn:
        current = conn.execute(
            "SELECT * FROM webinar_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if is_active:
            conn.execute("UPDATE webinar_config SET is_active = 0")

        if current:
            existing_banner = current["banner_image_url"] or ""
            conn.execute(
                """
                UPDATE webinar_config
                SET topic = ?, description = ?, webinar_date = ?, webinar_time = ?,
                    duration_minutes = ?, meeting_link = ?, banner_image_url = ?, is_active = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    topic,
                    description,
                    webinar_date,
                    webinar_time,
                    duration_minutes,
                    meeting_link,
                    banner_url or existing_banner,
                    is_active,
                    current["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO webinar_config
                (topic, description, banner_image_url, webinar_date, webinar_time, duration_minutes, meeting_link, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic,
                    description,
                    banner_url,
                    webinar_date,
                    webinar_time,
                    duration_minutes,
                    meeting_link,
                    is_active,
                ),
            )
        conn.commit()


def admin_get_dashboard_data() -> Dict[str, Any]:
    with get_webinar_connection() as conn:
        config = conn.execute(
            "SELECT * FROM webinar_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        registrations = conn.execute(
            """
            SELECT r.*, c.topic
            FROM webinar_registration r
            LEFT JOIN webinar_config c ON c.id = r.webinar_config_id
            ORDER BY r.registered_at DESC
            """
        ).fetchall()
        stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN wants_to_present = 1 THEN 1 ELSE 0 END) AS presenters,
                COUNT(DISTINCT webinar_config_id) AS webinar_sessions
            FROM webinar_registration
            """
        ).fetchone()
        deliveries = conn.execute(
            """
            SELECT message_type, channel, status, COUNT(*) AS cnt
            FROM webinar_message_delivery
            GROUP BY message_type, channel, status
            ORDER BY message_type, channel
            """
        ).fetchall()

    return {
        "config": config,
        "registrations": registrations,
        "stats": stats,
        "deliveries": deliveries,
    }
