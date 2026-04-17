#!/usr/bin/env python3
"""Copy webinar registrants from legacy old-db.db into data/webinar.db (INSERT only).

Source table: webinar_registration (legacy schema with name, phone, email, location, …).
Target table: webinar_registration (current schema). Rows are attached to the active
webinar_config row.

Deduplication:
- Latest row per email (by registration_date, id) from the legacy DB.
- Skip if the same webinar_config_id + email or + phone_e164 already exists in target.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdin.config import LEGACY_IMPORT_DB_PATH, get_webinar_db_path
from cdin.webinar_db import get_webinar_connection, initialize_webinar_schema


def normalize_phone(raw_phone: str) -> str:
    """Match cdin.webinar_service.normalize_phone (avoid importing messaging deps)."""
    digits = re.sub(r"\D", "", raw_phone or "")
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return digits
    raise ValueError("Invalid phone")

# Default for migrated rows (NOT NULL in schema; aligns with robotics webinar topic).
DEFAULT_DOMAIN_INTEREST = "Robotics and Automation"

OCCUPATION_MAP = {
    "Maker": "Hobbyist / Maker",
    "Startup Founder": "Founder",
    "Engineer": "Working Professional",
}


def _norm_country_token(raw: str) -> Optional[str]:
    t = (raw or "").strip()
    if not t:
        return None
    low = t.lower()
    if low in {"india", "in", "indian"}:
        return "India"
    if low in {"usa", "us", "united states", "united states of america"}:
        return "United States"
    if low in {"uk", "u.k.", "united kingdom", "great britain", "gb"}:
        return "United Kingdom"
    if low in {"canada"}:
        return "Canada"
    if low in {"germany", "deutschland"}:
        return "Germany"
    if low in {"australia"}:
        return "Australia"
    if low in {"singapore"}:
        return "Singapore"
    # Indian states / UTs → country India (city holds the region text).
    if low in {
        "tamilnadu",
        "tamil nadu",
        "karnataka",
        "kerala",
        "maharashtra",
        "telangana",
        "andhra pradesh",
        "gujarat",
        "rajasthan",
        "uttar pradesh",
        "madhya pradesh",
        "west bengal",
        "bihar",
        "punjab",
        "haryana",
        "delhi",
        "odisha",
        "orissa",
        "assam",
        "jharkhand",
        "chhattisgarh",
        "uttarakhand",
        "himachal pradesh",
        "goa",
        "jammu and kashmir",
        "ladakh",
    }:
        return "India"
    return t.title()


def parse_location(location: str) -> Tuple[Optional[str], Optional[str]]:
    s = re.sub(r"\s+", " ", (location or "").strip())
    if not s:
        return None, None
    low = s.lower()
    if low in {"india", "in", "indian"}:
        return None, "India"
    if low.endswith(" uk") or low == "uk":
        if low == "uk":
            return None, "United Kingdom"
        return s[:-3].strip() or None, "United Kingdom"
    if "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if len(parts) >= 2:
            city = ", ".join(parts[:-1])
            country = _norm_country_token(parts[-1])
            return city or None, country
    return s, None


def map_occupation(raw: str) -> str:
    o = (raw or "").strip()
    return OCCUPATION_MAP.get(o, o)


def _active_webinar_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM webinar_config WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        raise SystemExit("No active webinar_config row found in target DB.")
    return int(row[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=LEGACY_IMPORT_DB_PATH,
        help=f"Legacy SQLite path (default: {LEGACY_IMPORT_DB_PATH})",
    )
    parser.add_argument(
        "--target",
        default=get_webinar_db_path(),
        help="Target webinar.db path",
    )
    parser.add_argument(
        "--webinar-id",
        type=int,
        default=None,
        help="webinar_config_id to attach rows to (default: active webinar)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually insert rows (default is dry-run summary only)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.source):
        raise SystemExit(f"Source DB not found: {args.source}")

    initialize_webinar_schema(args.target)

    source = sqlite3.connect(args.source)
    source.row_factory = sqlite3.Row

    legacy_rows = list(
        source.execute(
            """
            SELECT id, name, phone, email, location, occupation, organization,
                   terms_accepted, registration_date
            FROM webinar_registration
            ORDER BY registration_date DESC, id DESC
            """
        )
    )
    source.close()

    seen_email: set[str] = set()
    deduped: list[sqlite3.Row] = []
    for row in legacy_rows:
        email = (row["email"] or "").strip().lower()
        if not email or email in seen_email:
            continue
        seen_email.add(email)
        deduped.append(row)

    with get_webinar_connection(args.target) as target:
        wid = args.webinar_id or _active_webinar_id(target)
        existing_emails = {
            (r[0] or "").strip().lower()
            for r in target.execute(
                "SELECT email FROM webinar_registration WHERE webinar_config_id = ?",
                (wid,),
            )
        }
        existing_phones = {
            r[0]
            for r in target.execute(
                "SELECT phone_e164 FROM webinar_registration WHERE webinar_config_id = ?",
                (wid,),
            )
        }

        to_insert: list[dict[str, Any]] = []
        skipped_existing_email = 0
        skipped_existing_phone = 0

        for row in deduped:
            email = (row["email"] or "").strip().lower()
            if email in existing_emails:
                skipped_existing_email += 1
                continue
            try:
                phone_e164 = normalize_phone(row["phone"] or "")
            except ValueError:
                continue
            if phone_e164 in existing_phones:
                skipped_existing_phone += 1
                continue

            city, country = parse_location(row["location"] or "")
            occ = map_occupation(row["occupation"] or "")
            org = (row["organization"] or "").strip()
            terms = 1 if row["terms_accepted"] else 0
            ra = row["registration_date"]
            if ra is None:
                registered_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            else:
                registered_at = str(ra)

            payload = {
                "webinar_config_id": wid,
                "full_name": (row["name"] or "").strip(),
                "email": email,
                "phone_e164": phone_e164,
                "city": city,
                "country": country,
                "occupation": occ,
                "organization_name": org,
                "domain_interest": DEFAULT_DOMAIN_INTEREST,
                "social_linkedin": None,
                "social_instagram": None,
                "social_x": None,
                "social_youtube": None,
                "social_github": None,
                "wants_to_present": 0,
                "presentation_topic": None,
                "presentation_description": None,
                "terms_accepted": terms,
                "ip_address": None,
                "registered_at": registered_at,
            }
            to_insert.append(payload)
            existing_emails.add(email)
            existing_phones.add(phone_e164)

    print(f"Legacy total rows:           {len(legacy_rows)}")
    print(f"After email dedupe (latest): {len(deduped)}")
    print(f"Skip (email already target): {skipped_existing_email}")
    print(f"Skip (phone already target): {skipped_existing_phone}")
    print(f"Rows to insert:              {len(to_insert)}")
    print(f"Target webinar_config_id:    {wid}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to insert.")
        return

    with get_webinar_connection(args.target) as conn:
        conn.executemany(
            """
            INSERT INTO webinar_registration (
                webinar_config_id, full_name, email, phone_e164,
                city, country, occupation, organization_name, domain_interest,
                social_linkedin, social_instagram, social_x, social_youtube, social_github,
                wants_to_present, presentation_topic, presentation_description,
                terms_accepted, ip_address, registered_at
            ) VALUES (
                :webinar_config_id, :full_name, :email, :phone_e164,
                :city, :country, :occupation, :organization_name, :domain_interest,
                :social_linkedin, :social_instagram, :social_x, :social_youtube, :social_github,
                :wants_to_present, :presentation_topic, :presentation_description,
                :terms_accepted, :ip_address, :registered_at
            )
            """,
            to_insert,
        )
        conn.commit()

    print(f"\nInserted {len(to_insert)} rows into {args.target}")


if __name__ == "__main__":
    main()
