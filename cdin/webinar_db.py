import sqlite3
from typing import Optional

from .config import get_webinar_db_path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS webinar_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    description TEXT,
    banner_image_url TEXT,
    webinar_date TEXT NOT NULL,
    webinar_time TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    meeting_link TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS webinar_registration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webinar_config_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone_e164 TEXT NOT NULL,
    city TEXT,
    country TEXT,
    occupation TEXT NOT NULL,
    organization_name TEXT NOT NULL DEFAULT '',
    domain_interest TEXT NOT NULL,
    social_linkedin TEXT,
    social_instagram TEXT,
    social_x TEXT,
    social_youtube TEXT,
    social_github TEXT,
    wants_to_present INTEGER NOT NULL DEFAULT 0,
    presentation_topic TEXT,
    presentation_description TEXT,
    terms_accepted INTEGER NOT NULL DEFAULT 0,
    ip_address TEXT,
    registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (webinar_config_id) REFERENCES webinar_config(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS webinar_message_delivery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    message_type TEXT NOT NULL,
    status TEXT NOT NULL,
    provider_message_id TEXT,
    error_message TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (registration_id) REFERENCES webinar_registration(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_webinar_delivery_unique
ON webinar_message_delivery(registration_id, channel, message_type);

CREATE INDEX IF NOT EXISTS idx_webinar_registration_event_email
ON webinar_registration(webinar_config_id, email);

CREATE INDEX IF NOT EXISTS idx_webinar_registration_event_phone
ON webinar_registration(webinar_config_id, phone_e164);

CREATE INDEX IF NOT EXISTS idx_webinar_registration_registered_at
ON webinar_registration(registered_at);
"""


def get_webinar_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_webinar_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_webinar_schema(db_path: Optional[str] = None) -> None:
    with get_webinar_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(webinar_registration)").fetchall()
        }
        if "organization_name" not in columns:
            conn.execute(
                "ALTER TABLE webinar_registration ADD COLUMN organization_name TEXT NOT NULL DEFAULT ''"
            )
        conn.commit()
