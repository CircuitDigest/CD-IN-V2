#!/usr/bin/env python3
"""Initialize submit-project-idea database schema."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdin.config import ensure_runtime_dirs, get_submit_project_idea_db_path
from cdin.project_idea_db import initialize_project_idea_schema


def main() -> None:
    ensure_runtime_dirs()
    initialize_project_idea_schema()
    print(f"Submit project idea DB initialized at: {get_submit_project_idea_db_path()}")


if __name__ == "__main__":
    main()
