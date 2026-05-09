import os
from datetime import datetime

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from .config import SUBMIT_PROJECT_IDEA_UPLOADS_DIR
from .project_idea_leads import (
    COUNTRY_OPTIONS,
    DIGIKEY_PRIVACY_POLICY_URL,
    INDUSTRY_OPTIONS,
    TITLE_OPTIONS,
    get_campaign_lead_analytics,
    insert_lead,
    lead_source_for_campaign,
    render_csv_utf8,
    validate_lead_form,
)
from .project_idea_service import (
    create_campaign,
    delete_campaign,
    get_campaign,
    get_campaign_by_slug,
    list_campaigns,
    update_campaign,
)

bp = Blueprint("project_idea_bp", __name__)


def _is_admin_authenticated() -> bool:
    return session.get("admin_authenticated", False) is True


def _allowed_image_ext(filename: str) -> str:
    safe = secure_filename(filename)
    if "." not in safe:
        return ""
    ext = safe.rsplit(".", 1)[-1].lower()
    if ext in ("jpg", "jpeg", "png", "webp"):
        return ext
    return ""


def _save_upload(file_storage) -> str:
    if not file_storage or not file_storage.filename:
        raise ValueError("Missing image file.")
    ext = _allowed_image_ext(file_storage.filename)
    if not ext:
        raise ValueError("Image must be JPG, PNG, or WebP.")
    name = f"idea_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.{ext}"
    path = os.path.join(SUBMIT_PROJECT_IDEA_UPLOADS_DIR, name)
    file_storage.save(path)
    return f"/uploads/project-idea/{name}"


@bp.route("/uploads/project-idea/<path:filename>", endpoint="project_idea_upload")
def project_idea_upload(filename):
    return send_from_directory(SUBMIT_PROJECT_IDEA_UPLOADS_DIR, filename)


@bp.route("/learn-build-win-by-digikey/<slug>/thank-you", methods=["GET"], endpoint="submit_project_idea_thank_you")
def submit_project_idea_thank_you(slug):
    campaign = get_campaign_by_slug(slug)
    if not campaign:
        abort(404)
    return render_template(
        "submit_project_idea_thank_you.html",
        campaign=campaign,
    )


@bp.route("/learn-build-win-by-digikey/<slug>/resources", methods=["GET"], endpoint="submit_project_idea_resources")
def submit_project_idea_resources(slug):
    campaign = get_campaign_by_slug(slug)
    if not campaign:
        abort(404)
    return render_template(
        "submit_project_idea_resources.html",
        campaign=campaign,
    )


@bp.route("/learn-build-win-by-digikey/<slug>/faq", methods=["GET"], endpoint="submit_project_idea_faq")
def submit_project_idea_faq(slug):
    campaign = get_campaign_by_slug(slug)
    if not campaign:
        abort(404)
    return render_template(
        "submit_project_idea_faq.html",
        campaign=campaign,
    )


@bp.route("/learn-build-win-by-digikey/<slug>", methods=["GET", "POST"], endpoint="submit_project_idea_public")
def submit_project_idea_public(slug):
    campaign = get_campaign_by_slug(slug)
    if not campaign:
        abort(404)
    status = campaign.get("registration_status", "")
    registration_open = status == "open"
    form_data: dict = {}
    submission_status = (request.args.get("submission_status") or "").strip().lower()
    preview_submission = (request.args.get("preview_submission") or "").strip().lower()
    preview_allowed = _is_admin_authenticated()
    preview_kind = preview_submission if preview_allowed and preview_submission in {"created", "updated"} else ""
    success_mode = submission_status in {"created", "updated"} or bool(preview_kind)
    success_kind = submission_status if submission_status in {"created", "updated"} else preview_kind
    success_message = (
        "Your submission has been updated successfully."
        if success_kind == "updated"
        else "Your registration was submitted successfully."
    )

    if request.method == "POST":
        if not registration_open:
            flash("Registration is not open for this campaign.", "error")
            form_data = request.form.to_dict()
        else:
            try:
                payload = validate_lead_form(request.form.to_dict(), int(campaign["id"]))
                ls = lead_source_for_campaign(campaign["board_name"], campaign["slug"])
                ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
                _, updated = insert_lead(payload, ls, ip)
                return redirect(
                    url_for(
                        "project_idea_bp.submit_project_idea_public",
                        slug=slug,
                        submission_status="updated" if updated else "created",
                    )
                )
            except Exception as exc:
                flash(str(exc), "error")
                form_data = request.form.to_dict()

    return render_template(
        "submit_project_idea_public.html",
        campaign=campaign,
        registration_open=registration_open,
        registration_status=status,
        success_mode=success_mode,
        success_message=success_message,
        success_kind=success_kind,
        form_data=form_data,
        title_options=TITLE_OPTIONS,
        industry_options=INDUSTRY_OPTIONS,
        country_options=COUNTRY_OPTIONS,
        digikey_privacy_url=DIGIKEY_PRIVACY_POLICY_URL,
    )


@bp.route(
    "/admin/learn-build-and-win/export/<int:campaign_id>",
    methods=["GET"],
    endpoint="admin_project_idea_export_csv",
)
def admin_project_idea_export_csv(campaign_id: int):
    if not _is_admin_authenticated():
        return redirect(url_for("admin_bp.admin"))
    campaign = get_campaign(campaign_id)
    if not campaign:
        abort(404)
    body = "\ufeff" + render_csv_utf8(campaign_id)
    fname = f"leads_{campaign['slug']}_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        body.encode("utf-8"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@bp.route(
    "/admin/learn-build-and-win/analytics/<int:campaign_id>",
    methods=["GET"],
    endpoint="admin_project_idea_analytics",
)
def admin_project_idea_analytics(campaign_id: int):
    if not _is_admin_authenticated():
        return redirect(url_for("admin_bp.admin"))
    campaign = get_campaign(campaign_id)
    if not campaign:
        abort(404)
    sort = request.args.get("sort", "").strip() or None
    analytics = get_campaign_lead_analytics(campaign_id, sort_key=sort)
    return render_template(
        "admin_submit_project_idea_analytics.html",
        campaign=campaign,
        lead_count=analytics["stats"]["total"],
        leads=analytics["leads"],
        lead_stats=analytics["stats"],
        lead_social=analytics["social"],
        title_breakdown=analytics["title_breakdown"],
        industry_breakdown=analytics["industry_breakdown"],
        country_breakdown=analytics["country_breakdown"],
        lead_sort=analytics["sort"],
    )


@bp.route("/admin/learn-build-and-win", methods=["GET", "POST"], endpoint="admin_submit_project_idea")
def admin_submit_project_idea():
    if not _is_admin_authenticated():
        return redirect(url_for("admin_bp.admin"))

    message = None
    message_type = None
    if request.method == "POST":
        action = request.form.get("action", "").strip()
        try:
            if action == "create":
                tut = _save_upload(request.files.get("tutorial_image"))
                ban = _save_upload(request.files.get("banner_image"))
                create_campaign(
                    board_name=request.form.get("board_name", ""),
                    slug_input=request.form.get("slug", ""),
                    tutorial_page_url=request.form.get("tutorial_page_url", ""),
                    tutorial_page_title=request.form.get("tutorial_page_title", ""),
                    tutorial_image_url=tut,
                    banner_image_url=ban,
                    youtube_video_url=request.form.get("youtube_video_url", ""),
                    youtube_video_title=request.form.get("youtube_video_title", ""),
                    registration_deadline=request.form.get("registration_deadline", ""),
                    is_active=request.form.get("is_active") == "on",
                )
                message = "Project idea page created."
                message_type = "success"
            elif action == "update":
                cid = int(request.form.get("campaign_id", 0) or 0)
                if not cid:
                    raise ValueError("Missing campaign.")
                tut_url = None
                ban_url = None
                ft = request.files.get("tutorial_image")
                if ft and ft.filename:
                    tut_url = _save_upload(ft)
                fb = request.files.get("banner_image")
                if fb and fb.filename:
                    ban_url = _save_upload(fb)
                update_campaign(
                    cid,
                    board_name=request.form.get("board_name", ""),
                    tutorial_page_url=request.form.get("tutorial_page_url", ""),
                    tutorial_page_title=request.form.get("tutorial_page_title", ""),
                    tutorial_image_url=tut_url,
                    banner_image_url=ban_url,
                    youtube_video_url=request.form.get("youtube_video_url", ""),
                    youtube_video_title=request.form.get("youtube_video_title", ""),
                    registration_deadline=request.form.get("registration_deadline", ""),
                    is_active=request.form.get("is_active") == "on",
                )
                message = "Project idea page updated."
                message_type = "success"
            elif action == "delete":
                cid = int(request.form.get("campaign_id", 0) or 0)
                if not cid:
                    raise ValueError("Missing campaign.")
                delete_campaign(cid)
                message = "Project idea page deleted."
                message_type = "success"
            else:
                raise ValueError("Unknown action.")
        except Exception as exc:
            message = str(exc)
            message_type = "error"

    campaigns = list_campaigns()
    edit_id = request.args.get("edit", type=int)
    edit_row = get_campaign(edit_id) if edit_id else None
    if edit_id and not edit_row:
        abort(404)

    return render_template(
        "admin_submit_project_idea.html",
        campaigns=campaigns,
        edit_row=edit_row,
        message=message,
        message_type=message_type,
    )
