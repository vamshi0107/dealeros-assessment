from pathlib import Path
from django.core.management.base import BaseCommand
from reconcile.importer import import_all_csvs


class Command(BaseCommand):
    help = "Imports locations.csv, system_a.csv, and system_b.csv idempotently into SQLite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            type=str,
            help="Directory containing the CSV files. Defaults to backend/data.",
            default=None,
        )

    def handle(self, *args, **options):
        data_dir = options.get("data_dir")
        self.stdout.write("Starting idempotent CSV import...")

        stats = import_all_csvs(data_dir=data_dir)

        self.stdout.write(self.style.SUCCESS(
            f"Locations: {stats['locations_read']} read, {stats['locations_saved']} saved"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"A: {stats['a_read']} read, {stats['a_saved']} saved; "
            f"B: {stats['b_read']} read, {stats['b_saved']} saved; "
            f"values left empty: {stats['b_values_empty']}; "
            f"refs cleaned: {stats['b_refs_cleaned']}"
        ))

        if stats["a_read"] != stats["a_saved"] or stats["b_read"] != stats["b_saved"]:
            self.stdout.write(self.style.ERROR("Error: Read count does not match saved count!"))
        else:
            self.stdout.write(self.style.SUCCESS("Import completed successfully with zero dropped rows."))
