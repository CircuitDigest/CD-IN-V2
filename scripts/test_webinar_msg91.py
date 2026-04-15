#!/usr/bin/env python3
"""Manual MSG91 verification for webinar templates.

Usage:
  source .venv/bin/activate
  export TEST_EMAIL='you@example.com'
  export TEST_PHONE='919876543210'
  python scripts/test_webinar_msg91.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdin.webinar_messaging import WebinarMessagingError, send_msg91_email, send_msg91_whatsapp


def main() -> None:
    test_email = os.environ.get("TEST_EMAIL", "").strip()
    test_phone = os.environ.get("TEST_PHONE", "").strip()

    if not test_email or not test_phone:
        print("Set TEST_EMAIL and TEST_PHONE environment variables first.")
        return

    print("Sending test webinar confirmation email...")
    try:
        email_result = send_msg91_email(
            to_email=test_email,
            template_name=os.environ.get("WEBINAR_EMAIL_TEMPLATE_CONFIRMATION", "cd_webinar_confirmation"),
            variables={
                "name": "Test User",
                "topic": "Webinar Test",
                "date": "31 Dec 2026",
                "time": "06:30 PM",
                "duration": "90",
                "meet_link": "https://meet.google.com/test-webinar",
                "banner_url": "https://circuitdigest.in/static/webinar/banner.jpg",
                "google_cal_link": "https://calendar.google.com",
                "outlook_cal_link": "https://outlook.live.com",
                "ics_link": "https://circuitdigest.in/webinar-calendar.ics",
            },
        )
        print("EMAIL OK:", email_result)
    except WebinarMessagingError as exc:
        print("EMAIL FAILED:", exc)

    print("Sending test webinar confirmation WhatsApp...")
    try:
        wa_result = send_msg91_whatsapp(
            phone_e164=test_phone,
            template_name=os.environ.get("WEBINAR_WHATSAPP_TEMPLATE_CONFIRMATION", "event_webinar_confirmation"),
            params={
                "body_1": "Test User",
                "body_2": "Webinar Test",
                "body_3": "31 Dec 2026 06:30 PM",
                "body_4": "https://meet.google.com/test-webinar",
            },
        )
        print("WHATSAPP OK:", wa_result)
    except WebinarMessagingError as exc:
        print("WHATSAPP FAILED:", exc)


if __name__ == "__main__":
    main()
