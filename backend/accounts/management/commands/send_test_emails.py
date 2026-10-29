from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from accounts.emails import ACCOUNT_EMAILS, render_account_email


class Command(BaseCommand):
    help = "Send every account email once to ADDRESS, to check them in a real inbox."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("address")

    def handle(self, *args: Any, **options: Any) -> None:
        for template_prefix in ACCOUNT_EMAILS:
            render_account_email(template_prefix, options["address"]).send()
            self.stdout.write(f"sent {template_prefix}")
        self.stdout.write(self.style.SUCCESS(f"Sent {len(ACCOUNT_EMAILS)} emails."))
