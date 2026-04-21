"""DigiKey India lead capture: validation, storage, CSV export (per campaign doc)."""

import csv
import io
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .project_idea_db import get_project_idea_connection

IST = ZoneInfo("Asia/Kolkata")

EMAIL_PATTERN = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

# Lead Source: Media name + campaign (DigiKey doc).
LEAD_SOURCE_PREFIX = "Media India | CircuitDigest | Submit your project idea"

DIGIKEY_PRIVACY_POLICY_URL = "https://www.digikey.com/en/resources/privacy-policy"

TITLE_OPTIONS: Tuple[str, ...] = (
    "Administrative/Manager",
    "C-Level/CEO/CTO/Owner President",
    "Engineer - Hardware",
    "Engineer - Software",
    "Engineer - Design Systems",
    "Engineering Management",
    "Engineering Other",
    "Maintenance and Repair",
    "Finance/Accounting",
    "Hobbyist/Maker",
    "Buyer/Purchaser",
    "Sales & Marketing",
    "Student",
    "Other",
)

INDUSTRY_OPTIONS: Tuple[str, ...] = (
    "Aerospace & Defense",
    "Automation & Control",
    "Automotive & Transportation",
    "Military/Government",
    "Agriculture",
    "Consumer Electronics",
    "Education",
    "Utilities/Energy Suppliers",
    "Industrial Automation Technology",
    "Instrumentation & Measurement",
    "Semiconductor Equipment Manufacturing",
    "Healthcare",
    "Construction/Intelligent Buildings",
    "Other",
)

COUNTRY_OPTIONS: Tuple[str, ...] = (
    "India",
    "United States",
    "United Kingdom",
    "Canada",
    "Germany",
    "France",
    "Australia",
    "Singapore",
    "Japan",
    "China",
    "South Korea",
    "Italy",
    "Spain",
    "Netherlands",
    "Sweden",
    "Switzerland",
    "Brazil",
    "Mexico",
    "United Arab Emirates",
    "Israel",
    "Taiwan",
    "Vietnam",
    "Thailand",
    "Indonesia",
    "Malaysia",
    "Philippines",
    "Other",
)


def lead_source_for_campaign(board_name: str, slug: str) -> str:
    return f"{LEAD_SOURCE_PREFIX} | {board_name} | {slug}"


def collection_date_csv_format(iso_ts: str) -> str:
    """Render stored ISO timestamp as M/D/YY HH:MM in IST for CSV (DigiKey doc)."""
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        else:
            dt = dt.astimezone(IST)
    except ValueError:
        return iso_ts
    yy = dt.year % 100
    return f"{dt.month}/{dt.day}/{yy:02d} {dt.hour:02d}:{dt.minute:02d}"


def consent_statement_text() -> str:
    """Plain-text consent stored on the lead (matches on-page copy; Privacy Policy is linked in HTML)."""
    return (
        "Please check this box if you would like DigiKey to be provided with your email address by "
        "CircuitDigest so that they can send you direct marketing emails about their products and services. "
        "You can withdraw your consent at any time with future effect by clicking on the opt-out link contained "
        "in every direct marketing email you receive. For more information on how DigiKey handles personal data, "
        "please refer to our Privacy Policy."
    )


def validate_lead_form(form: Dict[str, str], campaign_id: int) -> Dict[str, Any]:
    honeypot = (form.get("website") or "").strip()
    if honeypot:
        raise ValueError("Invalid form submission.")

    first = (form.get("first_name") or "").strip()
    last = (form.get("last_name") or "").strip()
    company = (form.get("company") or "").strip()
    email = (form.get("email") or "").strip().lower()
    state = (form.get("state_province") or "").strip()
    country = (form.get("country") or "").strip()
    title = (form.get("title") or "").strip()
    industry = (form.get("industry") or "").strip()
    consent = form.get("digikey_email_consent")

    if not first:
        raise ValueError("First name is required.")
    if not last:
        raise ValueError("Last name is required.")
    if not company:
        raise ValueError("Company is required.")
    if not email or not EMAIL_PATTERN.match(email):
        raise ValueError("A valid email is required.")
    if not state:
        raise ValueError("State/Province is required.")
    if not country:
        raise ValueError("Country is required.")
    if country not in COUNTRY_OPTIONS:
        raise ValueError("Please select a valid country.")
    if not title or title not in TITLE_OPTIONS:
        raise ValueError("Please select a valid title.")
    if not industry or industry not in INDUSTRY_OPTIONS:
        raise ValueError("Please select a valid industry.")
    if consent != "on":
        raise ValueError(
            "DigiKey requires explicit consent: you must check the box to agree before submitting."
        )

    project_title = (form.get("project_title") or "").strip()
    project_idea = (form.get("project_idea") or "").strip()
    if not project_title:
        raise ValueError("Project title is required.")
    if not project_idea or len(project_idea) < 40:
        raise ValueError("Please describe your project idea in at least 40 characters.")

    now_iso = datetime.now(IST).isoformat(timespec="seconds")

    return {
        "campaign_id": campaign_id,
        "collection_date_iso": now_iso,
        "email_consent_status": "Explicit",
        "first_name": first,
        "last_name": last,
        "company": company,
        "email": email,
        "state_province": state,
        "country": country,
        "title": title,
        "industry": industry,
        "consent_statement": consent_statement_text(),
        "city": (form.get("city") or "").strip(),
        "phone": (form.get("phone") or "").strip(),
        "address1": (form.get("address1") or "").strip(),
        "address2": (form.get("address2") or "").strip(),
        "address3": (form.get("address3") or "").strip(),
        "zip": (form.get("zip") or "").strip(),
        "additional1": (form.get("additional1") or "").strip(),
        "additional2": (form.get("additional2") or "").strip(),
        "additional3": (form.get("additional3") or "").strip(),
        "additional4": (form.get("additional4") or "").strip(),
        "additional5": (form.get("additional5") or "").strip(),
        "project_title": project_title,
        "project_idea": project_idea,
        "social_linkedin": (form.get("social_linkedin") or "").strip(),
        "social_youtube": (form.get("social_youtube") or "").strip(),
        "social_instagram": (form.get("social_instagram") or "").strip(),
        "social_x": (form.get("social_x") or "").strip(),
    }


def insert_lead(payload: Dict[str, Any], lead_source: str, ip_address: str) -> Tuple[int, bool]:
    with get_project_idea_connection() as conn:
        try:
            cur = conn.execute(
                """
                INSERT INTO project_idea_lead (
                    campaign_id, collection_date_iso, lead_source, email_consent_status,
                    first_name, last_name, company, email, state_province, country,
                    title, industry, consent_statement,
                    city, phone, address1, address2, address3, zip,
                    additional1, additional2, additional3, additional4, additional5,
                    project_title, project_idea,
                    social_linkedin, social_youtube, social_instagram, social_x,
                    ip_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["campaign_id"],
                    payload["collection_date_iso"],
                    lead_source,
                    payload["email_consent_status"],
                    payload["first_name"],
                    payload["last_name"],
                    payload["company"],
                    payload["email"],
                    payload["state_province"],
                    payload["country"],
                    payload["title"],
                    payload["industry"],
                    payload["consent_statement"],
                    payload["city"],
                    payload["phone"],
                    payload["address1"],
                    payload["address2"],
                    payload["address3"],
                    payload["zip"],
                    payload["additional1"],
                    payload["additional2"],
                    payload["additional3"],
                    payload["additional4"],
                    payload["additional5"],
                    payload["project_title"],
                    payload["project_idea"],
                    payload["social_linkedin"],
                    payload["social_youtube"],
                    payload["social_instagram"],
                    payload["social_x"],
                    ip_address,
                ),
            )
            conn.commit()
            return int(cur.lastrowid), False
        except sqlite3.IntegrityError as exc:
            # Existing lead for this campaign/email: update in place so users can resubmit improved ideas.
            err = str(exc).lower()
            is_duplicate_email = (
                "idx_project_idea_lead_campaign_email" in err
                or "unique constraint failed: project_idea_lead.campaign_id, project_idea_lead.email" in err
                or "unique constraint failed" in err
            )
            if not is_duplicate_email:
                conn.rollback()
                raise
            cur = conn.execute(
                """
                UPDATE project_idea_lead
                SET
                    collection_date_iso = ?,
                    lead_source = ?,
                    email_consent_status = ?,
                    first_name = ?,
                    last_name = ?,
                    company = ?,
                    state_province = ?,
                    country = ?,
                    title = ?,
                    industry = ?,
                    consent_statement = ?,
                    city = ?,
                    phone = ?,
                    address1 = ?,
                    address2 = ?,
                    address3 = ?,
                    zip = ?,
                    additional1 = ?,
                    additional2 = ?,
                    additional3 = ?,
                    additional4 = ?,
                    additional5 = ?,
                    project_title = ?,
                    project_idea = ?,
                    social_linkedin = ?,
                    social_youtube = ?,
                    social_instagram = ?,
                    social_x = ?,
                    ip_address = ?
                WHERE campaign_id = ? AND lower(email) = lower(?)
                """,
                (
                    payload["collection_date_iso"],
                    lead_source,
                    payload["email_consent_status"],
                    payload["first_name"],
                    payload["last_name"],
                    payload["company"],
                    payload["state_province"],
                    payload["country"],
                    payload["title"],
                    payload["industry"],
                    payload["consent_statement"],
                    payload["city"],
                    payload["phone"],
                    payload["address1"],
                    payload["address2"],
                    payload["address3"],
                    payload["zip"],
                    payload["additional1"],
                    payload["additional2"],
                    payload["additional3"],
                    payload["additional4"],
                    payload["additional5"],
                    payload["project_title"],
                    payload["project_idea"],
                    payload["social_linkedin"],
                    payload["social_youtube"],
                    payload["social_instagram"],
                    payload["social_x"],
                    ip_address,
                    payload["campaign_id"],
                    payload["email"],
                ),
            )
            if cur.rowcount <= 0:
                conn.rollback()
                raise ValueError("Unable to update existing submission.")
            row = conn.execute(
                "SELECT id FROM project_idea_lead WHERE campaign_id = ? AND lower(email) = lower(?)",
                (payload["campaign_id"], payload["email"]),
            ).fetchone()
            conn.commit()
            return int(row["id"]) if row else 0, True


def count_leads(campaign_id: int) -> int:
    with get_project_idea_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM project_idea_lead WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
    return int(row["c"]) if row else 0


def fetch_leads_for_export(campaign_id: int) -> List[sqlite3.Row]:
    with get_project_idea_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM project_idea_lead
            WHERE campaign_id = ?
            ORDER BY id ASC
            """,
            (campaign_id,),
        ).fetchall()


def leads_to_csv_rows(campaign_id: int) -> Tuple[List[str], List[List[str]]]:
    """Headers and rows per DigiKey lead spec (UTF-8 CSV)."""
    headers = [
        "Collection Date",
        "Lead Source",
        "Email Consent Status",
        "First Name",
        "Last Name",
        "Company",
        "Email",
        "State/Province",
        "Country",
        "Title",
        "Industry",
        "Consent Statement",
        "City",
        "Phone (mobile)",
        "Address 1",
        "Address 2",
        "Address 3",
        "Zip/Postal Code",
        "Additional Field 1",
        "Additional Field 2",
        "Additional Field 3",
        "Additional Field 4",
        "Additional Field 5",
        "Project Title",
        "Project Idea",
        "LinkedIn",
        "YouTube",
        "Instagram",
        "Twitter/X",
    ]
    rows: List[List[str]] = []
    for row in fetch_leads_for_export(campaign_id):
        d = dict(row)
        rows.append(
            [
                collection_date_csv_format(d["collection_date_iso"]),
                d["lead_source"],
                d["email_consent_status"],
                d["first_name"],
                d["last_name"],
                d["company"],
                d["email"],
                d["state_province"],
                d["country"],
                d["title"],
                d["industry"],
                "Yes, I agree.",
                d.get("city") or "",
                d.get("phone") or "",
                d.get("address1") or "",
                d.get("address2") or "",
                d.get("address3") or "",
                d.get("zip") or "",
                d.get("additional1") or "",
                d.get("additional2") or "",
                d.get("additional3") or "",
                d.get("additional4") or "",
                d.get("additional5") or "",
                d.get("project_title") or "",
                d.get("project_idea") or "",
                d.get("social_linkedin") or "",
                d.get("social_youtube") or "",
                d.get("social_instagram") or "",
                d.get("social_x") or "",
            ]
        )
    return headers, rows


def render_csv_utf8(campaign_id: int) -> str:
    headers, rows = leads_to_csv_rows(campaign_id)
    buf = io.StringIO()
    writer = csv.writer(buf, dialect="excel", lineterminator="\r\n")
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


_LEAD_ORDER_BY = {
    "submitted_desc": "collection_date_iso DESC, id DESC",
    "submitted_asc": "collection_date_iso ASC, id ASC",
    "name_asc": "LOWER(first_name) ASC, LOWER(last_name) ASC, id ASC",
    "email_asc": "LOWER(email) ASC, id ASC",
    "title_asc": "LOWER(title) ASC, LOWER(first_name) ASC, id ASC",
    "industry_asc": "LOWER(industry) ASC, LOWER(first_name) ASC, id ASC",
    "country_asc": "LOWER(country) ASC, LOWER(first_name) ASC, id ASC",
}


def normalize_lead_sort(sort_key: Optional[str]) -> str:
    if sort_key and sort_key in _LEAD_ORDER_BY:
        return sort_key
    return "submitted_desc"


def _bucket_label_expr(column: str) -> str:
    return (
        f"CASE WHEN COALESCE(TRIM({column}), '') = '' THEN '(not set)' "
        f"ELSE TRIM({column}) END"
    )


def _breakdown_for_column(conn: sqlite3.Connection, campaign_id: int, column: str) -> List[Dict[str, Any]]:
    label_sql = _bucket_label_expr(column)
    rows = conn.execute(
        f"""
        SELECT {label_sql} AS label, COUNT(*) AS cnt
        FROM project_idea_lead
        WHERE campaign_id = ?
        GROUP BY label
        ORDER BY cnt DESC, label ASC
        """,
        (campaign_id,),
    ).fetchall()
    total = sum(int(r["cnt"]) for r in rows)
    if not total:
        return []
    return [
        {
            "label": r["label"],
            "count": int(r["cnt"]),
            "pct": round((int(r["cnt"]) / total) * 100, 1),
        }
        for r in rows
    ]


def get_campaign_lead_analytics(campaign_id: int, sort_key: Optional[str] = None) -> Dict[str, Any]:
    sort = normalize_lead_sort(sort_key)
    order_by = _LEAD_ORDER_BY[sort]
    with get_project_idea_connection() as conn:
        leads = conn.execute(
            f"""
            SELECT *
            FROM project_idea_lead
            WHERE campaign_id = ?
            ORDER BY {order_by}
            """,
            (campaign_id,),
        ).fetchall()
        total = len(leads)
        social = conn.execute(
            """
            SELECT
                SUM(CASE WHEN COALESCE(TRIM(social_linkedin), '') != '' THEN 1 ELSE 0 END) AS linkedin,
                SUM(CASE WHEN COALESCE(TRIM(social_youtube), '') != '' THEN 1 ELSE 0 END) AS youtube,
                SUM(CASE WHEN COALESCE(TRIM(social_instagram), '') != '' THEN 1 ELSE 0 END) AS instagram,
                SUM(CASE WHEN COALESCE(TRIM(social_x), '') != '' THEN 1 ELSE 0 END) AS x,
                SUM(CASE
                    WHEN COALESCE(TRIM(social_linkedin), '') != ''
                      OR COALESCE(TRIM(social_youtube), '') != ''
                      OR COALESCE(TRIM(social_instagram), '') != ''
                      OR COALESCE(TRIM(social_x), '') != ''
                    THEN 1 ELSE 0 END) AS any_channel
            FROM project_idea_lead
            WHERE campaign_id = ?
            """,
            (campaign_id,),
        ).fetchone()
        title_breakdown = _breakdown_for_column(conn, campaign_id, "title")
        industry_breakdown = _breakdown_for_column(conn, campaign_id, "industry")
        country_breakdown = _breakdown_for_column(conn, campaign_id, "country")

    return {
        "leads": leads,
        "sort": sort,
        "stats": {
            "total": total,
            "with_social": int(social["any_channel"] or 0) if social else 0,
            "without_social": max(total - int(social["any_channel"] or 0), 0) if social else total,
        },
        "social": {
            "linkedin": int(social["linkedin"] or 0) if social else 0,
            "youtube": int(social["youtube"] or 0) if social else 0,
            "instagram": int(social["instagram"] or 0) if social else 0,
            "x": int(social["x"] or 0) if social else 0,
            "any_channel": int(social["any_channel"] or 0) if social else 0,
        },
        "title_breakdown": title_breakdown,
        "industry_breakdown": industry_breakdown,
        "country_breakdown": country_breakdown,
    }
