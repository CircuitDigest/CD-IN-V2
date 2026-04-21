import sqlite3
from typing import Optional

from .config import get_submit_project_idea_db_path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS project_idea_campaign (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    board_name TEXT NOT NULL,
    tutorial_page_url TEXT NOT NULL,
    tutorial_page_title TEXT NOT NULL DEFAULT '',
    tutorial_image_url TEXT NOT NULL,
    banner_image_url TEXT NOT NULL,
    youtube_video_url TEXT NOT NULL DEFAULT '',
    youtube_video_title TEXT NOT NULL DEFAULT '',
    registration_deadline TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_project_idea_campaign_deadline
ON project_idea_campaign(registration_deadline);

CREATE INDEX IF NOT EXISTS idx_project_idea_campaign_active
ON project_idea_campaign(is_active);

CREATE TABLE IF NOT EXISTS project_idea_lead (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    collection_date_iso TEXT NOT NULL,
    lead_source TEXT NOT NULL,
    email_consent_status TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    company TEXT NOT NULL,
    email TEXT NOT NULL,
    state_province TEXT NOT NULL,
    country TEXT NOT NULL,
    title TEXT NOT NULL,
    industry TEXT NOT NULL,
    consent_statement TEXT NOT NULL,
    city TEXT,
    phone TEXT,
    address1 TEXT,
    address2 TEXT,
    address3 TEXT,
    zip TEXT,
    additional1 TEXT,
    additional2 TEXT,
    additional3 TEXT,
    additional4 TEXT,
    additional5 TEXT,
    project_title TEXT NOT NULL DEFAULT '',
    project_idea TEXT NOT NULL DEFAULT '',
    social_linkedin TEXT NOT NULL DEFAULT '',
    social_youtube TEXT NOT NULL DEFAULT '',
    social_instagram TEXT NOT NULL DEFAULT '',
    social_x TEXT NOT NULL DEFAULT '',
    ip_address TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES project_idea_campaign(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_project_idea_lead_campaign_email
ON project_idea_lead(campaign_id, lower(email));

CREATE INDEX IF NOT EXISTS idx_project_idea_lead_campaign_id
ON project_idea_lead(campaign_id);
"""


def get_project_idea_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_submit_project_idea_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_project_idea_schema(db_path: Optional[str] = None) -> None:
    with get_project_idea_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(project_idea_campaign)").fetchall()
        }
        if "tutorial_page_title" not in columns:
            conn.execute(
                "ALTER TABLE project_idea_campaign ADD COLUMN tutorial_page_title TEXT NOT NULL DEFAULT ''"
            )
        if "youtube_video_url" not in columns:
            conn.execute(
                "ALTER TABLE project_idea_campaign ADD COLUMN youtube_video_url TEXT NOT NULL DEFAULT ''"
            )
        if "youtube_video_title" not in columns:
            conn.execute(
                "ALTER TABLE project_idea_campaign ADD COLUMN youtube_video_title TEXT NOT NULL DEFAULT ''"
            )
        lead_migrations = (
            ("project_title", "ALTER TABLE project_idea_lead ADD COLUMN project_title TEXT NOT NULL DEFAULT ''"),
            ("project_idea", "ALTER TABLE project_idea_lead ADD COLUMN project_idea TEXT NOT NULL DEFAULT ''"),
            ("social_linkedin", "ALTER TABLE project_idea_lead ADD COLUMN social_linkedin TEXT NOT NULL DEFAULT ''"),
            ("social_youtube", "ALTER TABLE project_idea_lead ADD COLUMN social_youtube TEXT NOT NULL DEFAULT ''"),
            ("social_instagram", "ALTER TABLE project_idea_lead ADD COLUMN social_instagram TEXT NOT NULL DEFAULT ''"),
            ("social_x", "ALTER TABLE project_idea_lead ADD COLUMN social_x TEXT NOT NULL DEFAULT ''"),
        )
        for col_name, ddl in lead_migrations:
            lead_cols = {
                row["name"] for row in conn.execute("PRAGMA table_info(project_idea_lead)").fetchall()
            }
            if col_name not in lead_cols:
                conn.execute(ddl)
        conn.commit()
