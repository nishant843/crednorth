from django.core.management.base import BaseCommand
from loans.models import Lead


class Command(BaseCommand):
    help = 'Delete all leads from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all leads',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will delete ALL leads from the database.\n'
                    'To confirm, run: python manage.py delete_all_leads --confirm'
                )
            )
            return

        # Get count before deletion
        lead_count = Lead.objects.count()
        
        if lead_count == 0:
            self.stdout.write(self.style.SUCCESS('No leads found in the database.'))
            return

        # Delete all leads
        Lead.objects.all().delete()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {lead_count} lead(s) from the database.'
            )
        )
