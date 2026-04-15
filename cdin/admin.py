import os
from datetime import datetime, timedelta
from typing import Optional

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from .config import UPLOADS_DIR
from .db import ensure_defaults, get_connection, slugify_text


bp = Blueprint("admin_bp", __name__)


def _is_admin_authenticated() -> bool:
    return session.get("admin_authenticated", False) is True


def _require_admin():
    if not _is_admin_authenticated():
        return redirect(url_for("admin_bp.admin"))
    return None


def _validate_admin_credentials(username: str, password: str) -> bool:
    expected_username = os.environ.get("ADMIN_USERNAME")
    expected_password_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    if not expected_username or not expected_password_hash:
        return False
    if username != expected_username:
        return False
    return check_password_hash(expected_password_hash, password)


def _local_upload_path(image_url: str) -> Optional[str]:
    """Resolve local upload URL to filesystem path; ignore external URLs."""
    if not image_url or not image_url.startswith("/uploads/instagram-microsite/"):
        return None

    filename = image_url.replace("/uploads/instagram-microsite/", "", 1).strip("/")
    candidate = os.path.abspath(os.path.join(UPLOADS_DIR, filename))
    uploads_root = os.path.abspath(UPLOADS_DIR)

    # Prevent path traversal outside upload directory.
    if os.path.commonpath([candidate, uploads_root]) != uploads_root:
        return None
    return candidate


def _delete_orphan_images(conn, image_urls: list[str]) -> None:
    """Delete image files only if no project row still references them."""
    unique_urls = {url for url in image_urls if url}
    for image_url in unique_urls:
        if not image_url.startswith("/uploads/instagram-microsite/"):
            continue

        still_used = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM instagram_microsite_project
            WHERE image_url = ?
            """,
            (image_url,),
        ).fetchone()["cnt"]
        if still_used:
            continue

        local_path = _local_upload_path(image_url)
        if local_path and os.path.exists(local_path):
            os.remove(local_path)


@bp.route("/admin", methods=["GET", "POST"], endpoint="admin")
def admin():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if _validate_admin_credentials(username, password):
            session["admin_authenticated"] = True
            return redirect(url_for("admin_bp.admin"))
        flash("Invalid username or password.", "error")
        return redirect(url_for("admin_bp.admin"))

    if not _is_admin_authenticated():
        return render_template("admin_login.html")
    return render_template("admin_dashboard.html")


@bp.route("/admin/logout", methods=["GET", "POST"], endpoint="admin_logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    return redirect(url_for("admin_bp.admin"))


@bp.route("/admin/instagram-microsite", methods=["GET", "POST"], endpoint="admin_instagram_microsite")
def admin_instagram_microsite():
    guard = _require_admin()
    if guard:
        return guard

    ensure_defaults()
    message = None
    message_type = None

    if request.method == "POST":
        action = request.form.get("action", "").strip()
        try:
            with get_connection() as conn:
                if action == "save_config":
                    config = conn.execute(
                        "SELECT * FROM instagram_microsite_config WHERE is_active = 1 LIMIT 1"
                    ).fetchone()
                    heading = request.form.get("heading", "").strip()
                    subheading = request.form.get("subheading", "").strip()
                    cta_text = request.form.get("community_button_text", "").strip() or "Join Our WhatsApp Community"
                    cta_link = request.form.get("community_link", "").strip()
                    if not heading:
                        raise ValueError("Heading is required.")

                    if config:
                        conn.execute(
                            """
                            UPDATE instagram_microsite_config
                            SET heading = ?, subheading = ?, community_button_text = ?, community_link = ?, updated_at = datetime('now')
                            WHERE id = ?
                            """,
                            (heading, subheading, cta_text, cta_link, config["id"]),
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO instagram_microsite_config
                            (heading, subheading, community_button_text, community_link, is_active)
                            VALUES (?, ?, ?, ?, 1)
                            """,
                            (heading, subheading, cta_text, cta_link),
                        )
                    message = "Microsite settings updated successfully."
                    message_type = "success"

                elif action == "add_category":
                    category_name = request.form.get("category_name", "").strip()
                    display_order = int(request.form.get("category_order", 0) or 0)
                    if not category_name:
                        raise ValueError("Category name is required.")

                    base_slug = slugify_text(category_name)
                    unique_slug = base_slug
                    counter = 1
                    while conn.execute(
                        "SELECT id FROM instagram_microsite_category WHERE slug = ? LIMIT 1",
                        (unique_slug,),
                    ).fetchone():
                        unique_slug = f"{base_slug}-{counter}"
                        counter += 1

                    conn.execute(
                        """
                        INSERT INTO instagram_microsite_category (name, slug, display_order, is_active)
                        VALUES (?, ?, ?, 1)
                        """,
                        (category_name, unique_slug, display_order),
                    )
                    message = "Category added successfully."
                    message_type = "success"

                elif action == "delete_category":
                    category_id = int(request.form.get("category_id", 0) or 0)
                    if not category_id:
                        raise ValueError("Category not found.")

                    category_images = conn.execute(
                        """
                        SELECT image_url FROM instagram_microsite_project
                        WHERE category_id = ? AND image_url IS NOT NULL AND image_url != ''
                        """,
                        (category_id,),
                    ).fetchall()
                    conn.execute("DELETE FROM instagram_microsite_category WHERE id = ?", (category_id,))
                    _delete_orphan_images(conn, [row["image_url"] for row in category_images])
                    message = "Category deleted successfully."
                    message_type = "success"

                elif action == "add_project":
                    category_id = int(request.form.get("project_category_id", 0) or 0)
                    title = request.form.get("project_title", "").strip()
                    project_url = request.form.get("project_url", "").strip()
                    display_order = int(request.form.get("project_order", 0) or 0)
                    if not category_id:
                        raise ValueError("Please select a category.")
                    if not title:
                        raise ValueError("Project title is required.")
                    if not project_url:
                        raise ValueError("Project URL is required.")
                    if not project_url.startswith(("http://", "https://")):
                        project_url = f"https://{project_url}"

                    category = conn.execute(
                        "SELECT id FROM instagram_microsite_category WHERE id = ? LIMIT 1",
                        (category_id,),
                    ).fetchone()
                    if not category:
                        raise ValueError("Selected category does not exist.")

                    image_url = ""
                    image_file = request.files.get("project_image")
                    if image_file and image_file.filename:
                        safe_name = secure_filename(image_file.filename)
                        ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "jpg"
                        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        final_filename = f"microsite_{stamp}.{ext}"
                        final_path = os.path.join(UPLOADS_DIR, final_filename)
                        image_file.save(final_path)
                        image_url = f"/uploads/instagram-microsite/{final_filename}"

                    conn.execute(
                        """
                        INSERT INTO instagram_microsite_project
                        (category_id, title, project_url, image_url, display_order, is_active)
                        VALUES (?, ?, ?, ?, ?, 1)
                        """,
                        (category_id, title, project_url, image_url, display_order),
                    )
                    message = "Project card added successfully."
                    message_type = "success"

                elif action == "delete_project":
                    project_id = int(request.form.get("project_id", 0) or 0)
                    if not project_id:
                        raise ValueError("Project not found.")
                    project = conn.execute(
                        "SELECT image_url FROM instagram_microsite_project WHERE id = ? LIMIT 1",
                        (project_id,),
                    ).fetchone()
                    conn.execute("DELETE FROM instagram_microsite_project WHERE id = ?", (project_id,))
                    if project and project["image_url"]:
                        _delete_orphan_images(conn, [project["image_url"]])
                    message = "Project card deleted successfully."
                    message_type = "success"
                else:
                    message = "Unknown action."
                    message_type = "error"

                conn.commit()
        except Exception as exc:
            message = str(exc)
            message_type = "error"

    now = datetime.now()
    cutoff_30d = now - timedelta(days=30)
    cutoff_90d = now - timedelta(days=90)
    cutoff_30d_str = cutoff_30d.strftime("%Y-%m-%d %H:%M:%S")
    cutoff_90d_str = cutoff_90d.strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        config = conn.execute(
            "SELECT * FROM instagram_microsite_config WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        categories = conn.execute(
            "SELECT * FROM instagram_microsite_category ORDER BY display_order ASC, name ASC"
        ).fetchall()
        projects = conn.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM instagram_microsite_project p
            LEFT JOIN instagram_microsite_category c ON c.id = p.category_id
            ORDER BY p.display_order ASC, p.created_at DESC
            """
        ).fetchall()

        total_rows = conn.execute(
            "SELECT project_id, COUNT(id) AS cnt FROM project_click GROUP BY project_id"
        ).fetchall()
        last_30_rows = conn.execute(
            """
            SELECT project_id, COUNT(id) AS cnt FROM project_click
            WHERE clicked_at >= ?
            GROUP BY project_id
            """,
            (cutoff_30d_str,),
        ).fetchall()
        last_90_rows = conn.execute(
            """
            SELECT project_id, COUNT(id) AS cnt FROM project_click
            WHERE clicked_at >= ?
            GROUP BY project_id
            """,
            (cutoff_90d_str,),
        ).fetchall()

        totals = conn.execute(
            """
            SELECT
                SUM(CASE WHEN clicked_at >= ? THEN 1 ELSE 0 END) AS total_30d,
                SUM(CASE WHEN clicked_at >= ? THEN 1 ELSE 0 END) AS total_90d,
                COUNT(id) AS total_all_time
            FROM project_click
            """,
            (cutoff_30d_str, cutoff_90d_str),
        ).fetchone()

    click_stats: dict[int, dict[str, int]] = {}
    for row in total_rows:
        click_stats.setdefault(row["project_id"], {})["total"] = row["cnt"]
    for row in last_30_rows:
        click_stats.setdefault(row["project_id"], {})["last_30_days"] = row["cnt"]
    for row in last_90_rows:
        click_stats.setdefault(row["project_id"], {})["last_90_days"] = row["cnt"]

    return render_template(
        "admin_instagram_microsite.html",
        config=config,
        categories=categories,
        projects=projects,
        click_stats=click_stats,
        total_clicks_30d=totals["total_30d"] or 0,
        total_clicks_90d=totals["total_90d"] or 0,
        total_clicks_all_time=totals["total_all_time"] or 0,
        message=message,
        message_type=message_type,
    )
