import os
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from .config import WEBINAR_UPLOADS_DIR
from .webinar_db import get_webinar_connection
from .webinar_service import (
    admin_get_dashboard_data,
    admin_save_webinar_config,
    create_registration,
    get_active_webinar,
    run_scheduled_reminders,
    send_registration_confirmation,
    trigger_manual_reminder,
)


bp = Blueprint("webinar_bp", __name__)


def _is_admin_authenticated() -> bool:
    return session.get("admin_authenticated", False) is True


def _webinar_display_meta(webinar):
    if not webinar:
        return {}

    date_raw = (webinar.get("webinar_date") or "").strip()
    time_raw = (webinar.get("webinar_time") or "").strip()
    date_display = date_raw
    day_display = ""
    time_display = time_raw

    try:
        parsed_date = datetime.strptime(date_raw, "%Y-%m-%d")
        date_display = parsed_date.strftime("%d %b %Y")
        day_display = parsed_date.strftime("%A")
    except ValueError:
        pass

    try:
        parsed_time = datetime.strptime(time_raw, "%H:%M")
        time_display = parsed_time.strftime("%I:%M %p")
    except ValueError:
        pass

    return {
        "date_display": date_display,
        "day_display": day_display,
        "time_display": time_display,
    }


@bp.route("/webinar-registration", methods=["GET", "POST"], endpoint="webinar_registration")
@bp.route(
    "/circuitdigest-community-webinar",
    methods=["GET", "POST"],
    endpoint="webinar_registration_pretty",
)
def webinar_registration():
    webinar = get_active_webinar()
    webinar_meta = _webinar_display_meta(webinar)
    form_data = {}
    just_registered = request.args.get("registered") == "1"
    if request.method == "POST":
        form_data = request.form.to_dict()
        try:
            registration_id = create_registration(
                form_data, request.headers.get("X-Forwarded-For", request.remote_addr or "")
            )
            send_registration_confirmation(registration_id)
            return redirect(url_for("webinar_bp.webinar_registration", registered="1"))
        except Exception as exc:
            flash(str(exc), "error")
    return render_template(
        "webinar_registration.html",
        webinar=webinar,
        webinar_meta=webinar_meta,
        form_data=form_data,
        just_registered=just_registered,
    )


@bp.route("/uploads/webinar/<path:filename>", endpoint="webinar_upload")
def webinar_upload(filename):
    return send_from_directory(WEBINAR_UPLOADS_DIR, filename)


@bp.route("/admin/webinar", methods=["GET", "POST"], endpoint="admin_webinar")
def admin_webinar():
    if not _is_admin_authenticated():
        return redirect(url_for("admin_bp.admin"))

    message = None
    message_type = None
    if request.method == "POST":
        action = request.form.get("action", "").strip()
        try:
            if action == "save_config":
                banner_url = ""
                file = request.files.get("banner_image")
                if file and file.filename:
                    safe_name = secure_filename(file.filename)
                    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "jpg"
                    name = f"webinar_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
                    file_path = os.path.join(WEBINAR_UPLOADS_DIR, name)
                    file.save(file_path)
                    banner_url = f"/uploads/webinar/{name}"
                admin_save_webinar_config(request.form.to_dict(), banner_url)
                message = "Webinar settings updated."
                message_type = "success"
            elif action == "send_test_confirmation":
                registration_id = int(request.form.get("registration_id", 0) or 0)
                if not registration_id:
                    raise ValueError("Select a registration to send test confirmation.")
                send_registration_confirmation(registration_id)
                message = "Test confirmation triggered."
                message_type = "success"
            elif action == "manual_reminder":
                reminder_type = request.form.get("reminder_type", "").strip()
                result = trigger_manual_reminder(reminder_type)
                message = f"Reminder sent: {result['sent']} | failed: {result['failed']}"
                message_type = "success"
            elif action == "run_scheduler_now":
                result = run_scheduled_reminders()
                message = f"Scheduler run complete: {result['sent']} sent, {result['failed']} failed."
                message_type = "success"
            else:
                raise ValueError("Unknown action.")
        except Exception as exc:
            message = str(exc)
            message_type = "error"

    dashboard = admin_get_dashboard_data()
    return render_template(
        "admin_webinar.html",
        config=dashboard["config"],
        registration_public_url=url_for("webinar_bp.webinar_registration_pretty", _external=True),
        registrations=dashboard["registrations"],
        stats=dashboard["stats"],
        deliveries=dashboard["deliveries"],
        message=message,
        message_type=message_type,
    )


@bp.route("/admin/webinar/delete-registration/<int:registration_id>", methods=["POST"], endpoint="delete_webinar_registration")
def delete_webinar_registration(registration_id: int):
    if not _is_admin_authenticated():
        return redirect(url_for("admin_bp.admin"))
    with get_webinar_connection() as conn:
        conn.execute("DELETE FROM webinar_registration WHERE id = ?", (registration_id,))
        conn.commit()
    return redirect(url_for("webinar_bp.admin_webinar"))
