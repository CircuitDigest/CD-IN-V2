import os
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
import requests
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
    duration_raw = webinar.get("duration_minutes")

    date_display = date_raw
    day_display = ""
    day_number = ""
    month_short = ""
    year_display = ""
    time_display = time_raw
    time_end_display = ""
    duration_display = ""

    try:
        parsed_date = datetime.strptime(date_raw, "%Y-%m-%d")
        date_display = parsed_date.strftime("%d %b %Y")
        day_display = parsed_date.strftime("%A")
        day_number = parsed_date.strftime("%d").lstrip("0") or "0"
        month_short = parsed_date.strftime("%b").upper()
        year_display = parsed_date.strftime("%Y")
    except ValueError:
        parsed_date = None

    parsed_time = None
    try:
        parsed_time = datetime.strptime(time_raw, "%H:%M")
        time_display = parsed_time.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        parsed_time = None

    if parsed_time is not None and duration_raw:
        try:
            minutes = int(duration_raw)
        except (TypeError, ValueError):
            minutes = 0
        if minutes > 0:
            end = parsed_time + timedelta(minutes=minutes)
            time_end_display = end.strftime("%I:%M %p").lstrip("0")
            hours, rem_min = divmod(minutes, 60)
            if hours and rem_min:
                duration_display = f"{hours} hr {rem_min} min"
            elif hours:
                duration_display = f"{hours} hr"
            else:
                duration_display = f"{rem_min} min"

    return {
        "date_display": date_display,
        "day_display": day_display,
        "day_number": day_number,
        "month_short": month_short,
        "year_display": year_display,
        "time_display": time_display,
        "time_end_display": time_end_display,
        "duration_display": duration_display,
    }


def _msg91_diagnostics() -> dict:
    def _present(name: str) -> bool:
        return bool(os.environ.get(name, "").strip())

    def _ping(url: str) -> dict:
        try:
            resp = requests.get(url, timeout=4)
            return {"ok": True, "status": resp.status_code}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _t(name: str, default: str) -> str:
        return (os.environ.get(name) or "").strip() or default

    return {
        "env": {
            "MSG91_EMAIL_AUTHKEY": _present("MSG91_EMAIL_AUTHKEY"),
            "MSG91_EMAIL_DOMAIN": _present("MSG91_EMAIL_DOMAIN"),
            "MSG91_EMAIL_FROM": _present("MSG91_EMAIL_FROM"),
            "MSG91_WHATSAPP_AUTHKEY": _present("MSG91_WHATSAPP_AUTHKEY"),
            "MSG91_WHATSAPP_NUMBER": _present("MSG91_WHATSAPP_NUMBER"),
            "MSG91_WHATSAPP_TEMPLATE_NAMESPACE": _present("MSG91_WHATSAPP_TEMPLATE_NAMESPACE"),
            "WEBINAR_EMAIL_TEMPLATE_CONFIRMATION": _present("WEBINAR_EMAIL_TEMPLATE_CONFIRMATION"),
            "WEBINAR_WHATSAPP_TEMPLATE_CONFIRMATION": _present("WEBINAR_WHATSAPP_TEMPLATE_CONFIRMATION"),
        },
        "templates": {
            "reminder_24h": {
                "whatsapp": _t("WEBINAR_WHATSAPP_TEMPLATE_REMINDER_24H", "event_webinar_reminder"),
                "email": _t("WEBINAR_EMAIL_TEMPLATE_REMINDER_24H", "cd_webinar_reminder"),
            },
            "reminder_1h": {
                "whatsapp": "(disabled)",
                "email": _t("WEBINAR_EMAIL_TEMPLATE_REMINDER_1H", "cd_webinar_reminder"),
            },
            "reminder_live": {
                "whatsapp": _t("WEBINAR_WHATSAPP_TEMPLATE_REMINDER_LIVE", "event_webinar_reminder"),
                "email": _t("WEBINAR_EMAIL_TEMPLATE_REMINDER_LIVE", "cd_webinar_reminder"),
            },
        },
        "network": {
            "msg91_email_api": _ping("https://control.msg91.com/api/v5/email/send"),
            "msg91_whatsapp_api": _ping(
                "https://api.msg91.com/api/v5/whatsapp/whatsapp-outbound-message/bulk/"
            ),
        },
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
    registered_email = (request.args.get("email") or "").strip()
    registration_updated = request.args.get("updated") == "1"
    if request.method == "POST":
        form_data = request.form.to_dict()
        try:
            result = create_registration(
                form_data, request.headers.get("X-Forwarded-For", request.remote_addr or "")
            )
            # On update, force resend so user always receives latest confirmation email.
            send_registration_confirmation(int(result["id"]), force=bool(result.get("updated")))
            return redirect(
                url_for(
                    "webinar_bp.webinar_registration_pretty",
                    registered="1",
                    email=result.get("email", ""),
                    updated="1" if result.get("updated") else "0",
                )
            )
        except Exception as exc:
            flash(str(exc), "error")
    return render_template(
        "webinar_registration.html",
        webinar=webinar,
        webinar_meta=webinar_meta,
        form_data=form_data,
        just_registered=just_registered,
        registered_email=registered_email,
        registration_updated=registration_updated,
    )


@bp.route("/uploads/webinar/<path:filename>", endpoint="webinar_upload")
def webinar_upload(filename):
    return send_from_directory(WEBINAR_UPLOADS_DIR, filename)


@bp.route("/static/webinar/banner.jpg", endpoint="webinar_banner_static")
def webinar_banner_static():
    """
    Stable banner URL for email templates.

    Always serves the current active webinar's uploaded banner image file.
    """
    webinar = get_active_webinar()
    banner_url = (webinar or {}).get("banner_image_url") or ""
    if not banner_url:
        abort(404)

    prefix = "/uploads/webinar/"
    if not banner_url.startswith(prefix):
        abort(404)

    filename = banner_url.replace(prefix, "", 1).strip("/")
    if not filename:
        abort(404)

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
                channel = request.form.get("channel", "").strip().lower()
                if channel == "email":
                    result = trigger_manual_reminder(
                        reminder_type, channels=("email",), ignore_already_sent=True
                    )
                elif channel == "whatsapp":
                    result = trigger_manual_reminder(
                        reminder_type, channels=("whatsapp",), ignore_already_sent=True
                    )
                else:
                    result = trigger_manual_reminder(reminder_type, ignore_already_sent=True)
                message = (
                    f"Reminder sent ({channel or 'email+whatsapp'}): "
                    f"{result['sent']} | failed: {result['failed']}"
                )
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

    sort_param = request.args.get("sort", "").strip() or None
    dashboard = admin_get_dashboard_data(sort_key=sort_param)
    return render_template(
        "admin_webinar.html",
        config=dashboard["config"],
        registration_public_url=url_for("webinar_bp.webinar_registration_pretty", _external=True),
        active_registration_count=dashboard.get("active_registration_count", 0),
        registrations=dashboard["registrations"],
        stats=dashboard["stats"],
        deliveries=dashboard["deliveries"],
        webinar_analytics=dashboard.get("webinar_analytics"),
        registration_sort=dashboard.get("registration_sort", "registered_desc"),
        msg91_diag=_msg91_diagnostics(),
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
