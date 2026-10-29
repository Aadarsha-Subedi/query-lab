#!/usr/bin/env python
"""Django's command-line utility. DJANGO_SETTINGS_MODULE must be set (no default)."""

import os
import sys


def main() -> None:
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        sys.exit("DJANGO_SETTINGS_MODULE is not set; see backend/.env.example.")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
