#!/usr/bin/env python3
"""Run webinar reminder scheduler once."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdin.webinar_service import run_scheduled_reminders


def main() -> None:
    result = run_scheduled_reminders()
    print(f"Webinar reminder run: sent={result['sent']} failed={result['failed']}")


if __name__ == "__main__":
    main()
