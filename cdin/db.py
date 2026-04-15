import re
import sqlite3
from typing import Iterable, Optional

from .config import get_db_path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS instagram_microsite_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    heading TEXT NOT NULL DEFAULT 'Explore CircuitDigest Projects',
    subheading TEXT DEFAULT 'Trending electronics projects, guides, and inspiration',
    community_button_text TEXT NOT NULL DEFAULT 'Join Our WhatsApp Community',
    community_link TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS instagram_microsite_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS instagram_microsite_project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    project_url TEXT NOT NULL,
    image_url TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES instagram_microsite_category(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_click (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    clicked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES instagram_microsite_project(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_project_click_project_id ON project_click(project_id);
CREATE INDEX IF NOT EXISTS idx_project_click_clicked_at ON project_click(clicked_at);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_schema(db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def slugify_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "category"


def ensure_defaults(db_path: Optional[str] = None) -> None:
    default_categories: Iterable[str] = (
        "Latest",
        "Trending",
        "Arduino Projects",
        "ESP32 Projects",
        "AI Projects",
        "Drone Projects",
    )

    with get_connection(db_path) as conn:
        category_count = conn.execute(
            "SELECT COUNT(*) AS count FROM instagram_microsite_category"
        ).fetchone()["count"]
        if category_count == 0:
            for idx, name in enumerate(default_categories):
                conn.execute(
                    """
                    INSERT INTO instagram_microsite_category (name, slug, display_order, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (name, slugify_text(name), idx),
                )

        config_row = conn.execute(
            "SELECT id FROM instagram_microsite_config WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        if not config_row:
            conn.execute(
                """
                INSERT INTO instagram_microsite_config
                (heading, subheading, community_button_text, community_link, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    "Explore CircuitDigest Projects",
                    "Handpicked electronics projects and tutorials from CircuitDigest",
                    "Join Our WhatsApp Community",
                    "",
                ),
            )

        conn.commit()
