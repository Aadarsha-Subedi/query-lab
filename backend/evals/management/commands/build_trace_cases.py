from django.core.management.base import BaseCommand

from evals import candidates


class Command(BaseCommand):
    help = (
        "Turn the stored demo runs worth a look (edited SQL, thumbs down, failed, "
        "revised, declined, needs_look) into trace cases. Safe to run again."
    )

    def handle(self, *args: object, **options: object) -> None:
        made = candidates.build_candidates()
        self.stdout.write(f"{made} new trace cases.")
