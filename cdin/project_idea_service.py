import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from .db import slugify_text
from .project_idea_db import get_project_idea_connection

IST = ZoneInfo("Asia/Kolkata")

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
URL_PATTERN = re.compile(r"^https?://", re.I)


def validate_youtube_url(url: str) -> str:
    u = (url or "").strip()
    if not u or not URL_PATTERN.match(u):
        raise ValueError("YouTube video link must be a valid http(s) URL.")
    low = u.lower()
    if "youtube.com" not in low and "youtu.be" not in low:
        raise ValueError("YouTube link must use youtube.com or youtu.be.")
    return u


def youtube_embed_url(url: str) -> Optional[str]:
    """Return https://www.youtube.com/embed/VIDEO_ID or None."""
    u = (url or "").strip()
    if not u:
        return None
    low = u.lower()
    try:
        if "youtu.be/" in low:
            vid = u.split("youtu.be/")[-1].split("?")[0].split("/")[0].strip()
            return f"https://www.youtube.com/embed/{vid}" if vid else None
        parsed = urlparse(u)
        host = (parsed.netloc or "").lower()
        if "youtube.com" not in host and "youtube-nocookie.com" not in host:
            return None
        path = (parsed.path or "").lower()
        if path.startswith("/embed/"):
            vid = parsed.path.split("/embed/", 1)[-1].split("/")[0].strip()
            return f"https://www.youtube.com/embed/{vid}" if vid else None
        if path.startswith("/shorts/"):
            vid = path.replace("/shorts/", "").split("/")[0].strip()
            return f"https://www.youtube.com/embed/{vid}" if vid else None
        qs = parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            vid = qs["v"][0].strip()
            return f"https://www.youtube.com/embed/{vid}" if vid else None
    except (IndexError, ValueError):
        return None
    return None


def _today_ist() -> date:
    return datetime.now(IST).date()


def registration_status_for_row(row: Dict[str, Any]) -> str:
    """
    Human-facing status using IST calendar date vs registration_deadline (inclusive).
    """
    if not row.get("is_active"):
        return "disabled"
    try:
        deadline = date.fromisoformat((row.get("registration_deadline") or "").strip())
    except ValueError:
        return "unknown"
    if _today_ist() <= deadline:
        return "open"
    return "closed_deadline"


def _slug_exists(conn, slug: str, exclude_id: Optional[int] = None) -> bool:
    if exclude_id is not None:
        cur = conn.execute(
            "SELECT 1 FROM project_idea_campaign WHERE slug = ? AND id != ? LIMIT 1",
            (slug, exclude_id),
        )
    else:
        cur = conn.execute("SELECT 1 FROM project_idea_campaign WHERE slug = ? LIMIT 1", (slug,))
    return cur.fetchone() is not None


def _allocate_unique_slug(conn, base_slug: str) -> str:
    slug = base_slug or "board"
    if not _slug_exists(conn, slug):
        return slug
    n = 2
    while True:
        candidate = f"{slug}-{n}"
        if not _slug_exists(conn, candidate):
            return candidate
        n += 1


def normalize_slug(raw: str, board_name: str) -> str:
    raw = (raw or "").strip().lower()
    if raw:
        if not SLUG_PATTERN.match(raw):
            raise ValueError("Slug must be lowercase letters, numbers, and hyphens only.")
        return raw
    base = slugify_text(board_name)
    if base in ("category", ""):
        base = "board"
    return base


def list_campaigns() -> List[Dict[str, Any]]:
    with get_project_idea_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM project_idea_campaign
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        d["registration_status"] = registration_status_for_row(d)
        d["youtube_embed_url"] = youtube_embed_url(d.get("youtube_video_url") or "")
        out.append(d)
    return out


def get_campaign(campaign_id: int) -> Optional[Dict[str, Any]]:
    with get_project_idea_connection() as conn:
        row = conn.execute(
            "SELECT * FROM project_idea_campaign WHERE id = ?",
            (campaign_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["registration_status"] = registration_status_for_row(d)
    d["youtube_embed_url"] = youtube_embed_url(d.get("youtube_video_url") or "")
    return d


def get_campaign_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    slug = (slug or "").strip().lower()
    if not slug:
        return None
    with get_project_idea_connection() as conn:
        row = conn.execute(
            "SELECT * FROM project_idea_campaign WHERE slug = ?",
            (slug,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["registration_status"] = registration_status_for_row(d)
    d["youtube_embed_url"] = youtube_embed_url(d.get("youtube_video_url") or "")
    return d


def create_campaign(
    *,
    board_name: str,
    slug_input: str,
    tutorial_page_url: str,
    tutorial_page_title: str,
    tutorial_image_url: str,
    banner_image_url: str,
    youtube_video_url: str,
    youtube_video_title: str,
    registration_deadline: str,
    is_active: bool,
) -> int:
    board_name = board_name.strip()
    tutorial_page_url = tutorial_page_url.strip()
    tutorial_page_title = tutorial_page_title.strip()
    youtube_video_title = youtube_video_title.strip()
    registration_deadline = registration_deadline.strip()
    if not board_name:
        raise ValueError("Development board name is required.")
    if not tutorial_page_title:
        raise ValueError("Tutorial page title is required.")
    if not tutorial_page_url or not URL_PATTERN.match(tutorial_page_url):
        raise ValueError("Tutorial page link must be a valid http(s) URL.")
    y_url = validate_youtube_url(youtube_video_url)
    if not youtube_video_title:
        raise ValueError("YouTube video title is required.")
    if not tutorial_image_url or not banner_image_url:
        raise ValueError("Both tutorial and banner images are required when creating a page.")
    try:
        date.fromisoformat(registration_deadline)
    except ValueError:
        raise ValueError("Last date for registration must be a valid YYYY-MM-DD date.")

    with get_project_idea_connection() as conn:
        if (slug_input or "").strip():
            slug = normalize_slug(slug_input, board_name)
            if _slug_exists(conn, slug):
                raise ValueError("That slug is already in use. Choose a different slug.")
        else:
            base = normalize_slug("", board_name)
            slug = _allocate_unique_slug(conn, base)
        cur = conn.execute(
            """
            INSERT INTO project_idea_campaign (
                slug, board_name, tutorial_page_url, tutorial_page_title, tutorial_image_url, banner_image_url,
                youtube_video_url, youtube_video_title, registration_deadline, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug,
                board_name,
                tutorial_page_url,
                tutorial_page_title,
                tutorial_image_url,
                banner_image_url,
                y_url,
                youtube_video_title,
                registration_deadline,
                1 if is_active else 0,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def update_campaign(
    campaign_id: int,
    *,
    board_name: str,
    tutorial_page_url: str,
    tutorial_page_title: str,
    tutorial_image_url: Optional[str],
    banner_image_url: Optional[str],
    youtube_video_url: str,
    youtube_video_title: str,
    registration_deadline: str,
    is_active: bool,
) -> None:
    board_name = board_name.strip()
    tutorial_page_url = tutorial_page_url.strip()
    tutorial_page_title = tutorial_page_title.strip()
    youtube_video_title = youtube_video_title.strip()
    registration_deadline = registration_deadline.strip()
    if not board_name:
        raise ValueError("Development board name is required.")
    if not tutorial_page_title:
        raise ValueError("Tutorial page title is required.")
    if not tutorial_page_url or not URL_PATTERN.match(tutorial_page_url):
        raise ValueError("Tutorial page link must be a valid http(s) URL.")
    y_url = validate_youtube_url(youtube_video_url)
    if not youtube_video_title:
        raise ValueError("YouTube video title is required.")
    try:
        date.fromisoformat(registration_deadline)
    except ValueError:
        raise ValueError("Last date for registration must be a valid YYYY-MM-DD date.")

    with get_project_idea_connection() as conn:
        row = conn.execute(
            "SELECT * FROM project_idea_campaign WHERE id = ?",
            (campaign_id,),
        ).fetchone()
        if not row:
            raise ValueError("Campaign not found.")

        tut = row["tutorial_image_url"]
        ban = row["banner_image_url"]
        if tutorial_image_url:
            tut = tutorial_image_url
        if banner_image_url:
            ban = banner_image_url

        conn.execute(
            """
            UPDATE project_idea_campaign
            SET board_name = ?, tutorial_page_url = ?, tutorial_page_title = ?, tutorial_image_url = ?, banner_image_url = ?,
                youtube_video_url = ?, youtube_video_title = ?, registration_deadline = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                board_name,
                tutorial_page_url,
                tutorial_page_title,
                tut,
                ban,
                y_url,
                youtube_video_title,
                registration_deadline,
                1 if is_active else 0,
                campaign_id,
            ),
        )
        conn.commit()


def delete_campaign(campaign_id: int) -> None:
    with get_project_idea_connection() as conn:
        cur = conn.execute("DELETE FROM project_idea_campaign WHERE id = ?", (campaign_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError("Campaign not found.")
