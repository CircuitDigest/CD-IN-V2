from flask import Blueprint, jsonify, render_template, request, send_from_directory

from .config import UPLOADS_DIR
from .db import ensure_defaults, get_connection


bp = Blueprint("microsite", __name__)


@bp.route("/instagram-microsite", endpoint="instagram_microsite")
def instagram_microsite():
    ensure_defaults()
    with get_connection() as conn:
        config = conn.execute(
            "SELECT * FROM instagram_microsite_config WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        categories = conn.execute(
            """
            SELECT * FROM instagram_microsite_category
            WHERE is_active = 1
            ORDER BY display_order ASC, name ASC
            """
        ).fetchall()

        projects_by_category = {}
        for category in categories:
            projects_by_category[category["id"]] = conn.execute(
                """
                SELECT * FROM instagram_microsite_project
                WHERE category_id = ? AND is_active = 1
                ORDER BY display_order ASC, created_at DESC
                """,
                (category["id"],),
            ).fetchall()

    return render_template(
        "instagram_microsite.html",
        config=config,
        categories=categories,
        projects_by_category=projects_by_category,
    )


@bp.route("/api/microsite/click", methods=["POST"], endpoint="track_microsite_click")
def track_microsite_click():
    data = request.get_json(silent=True) or {}
    project_id = data.get("project_id")
    if not project_id:
        return jsonify({"ok": False, "error": "missing project_id"}), 400

    try:
        with get_connection() as conn:
            project = conn.execute(
                "SELECT id FROM instagram_microsite_project WHERE id = ? LIMIT 1",
                (project_id,),
            ).fetchone()
            if not project:
                return jsonify({"ok": False, "error": "not found"}), 404

            conn.execute(
                "INSERT INTO project_click (project_id, clicked_at) VALUES (?, datetime('now'))",
                (int(project_id),),
            )
            conn.commit()
    except Exception:
        return jsonify({"ok": False}), 500

    return jsonify({"ok": True}), 200


@bp.route(
    "/uploads/instagram-microsite/<path:filename>",
    endpoint="serve_instagram_microsite_file",
)
def serve_instagram_microsite_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)
