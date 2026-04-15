#!/usr/bin/env python3
"""Import Instagram microsite data from legacy SQLite DB."""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdin.config import LEGACY_IMPORT_DB_PATH, ensure_runtime_dirs, get_db_path
from cdin.db import get_connection, initialize_schema


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]


def main() -> None:
    ensure_runtime_dirs()
    initialize_schema()

    source_path = LEGACY_IMPORT_DB_PATH
    target_path = get_db_path()
    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row

    with get_connection(target_path) as target:
        target.execute("DELETE FROM project_click")
        target.execute("DELETE FROM instagram_microsite_project")
        target.execute("DELETE FROM instagram_microsite_category")
        target.execute("DELETE FROM instagram_microsite_config")

        configs = source.execute("SELECT * FROM instagram_microsite_config").fetchall()
        for row in configs:
            target.execute(
                """
                INSERT INTO instagram_microsite_config
                (id, heading, subheading, community_button_text, community_link, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["heading"],
                    row["subheading"],
                    row["community_button_text"],
                    row["community_link"],
                    row["is_active"],
                    row["updated_at"],
                ),
            )

        categories = source.execute("SELECT * FROM instagram_microsite_category").fetchall()
        for row in categories:
            target.execute(
                """
                INSERT INTO instagram_microsite_category
                (id, name, slug, display_order, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["name"],
                    row["slug"],
                    row["display_order"],
                    row["is_active"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

        projects = source.execute("SELECT * FROM instagram_microsite_project").fetchall()
        for row in projects:
            target.execute(
                """
                INSERT INTO instagram_microsite_project
                (id, category_id, title, project_url, image_url, display_order, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["category_id"],
                    row["title"],
                    row["project_url"],
                    row["image_url"],
                    row["display_order"],
                    row["is_active"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

        target.commit()

        print("Imported rows:")
        print(f"- config: {_count(target, 'instagram_microsite_config')}")
        print(f"- categories: {_count(target, 'instagram_microsite_category')}")
        print(f"- projects: {_count(target, 'instagram_microsite_project')}")

    source.close()


if __name__ == "__main__":
    main()
