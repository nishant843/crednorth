from django.core.management.base import BaseCommand
from users.models import User, calculate_age_from_dob


class Command(BaseCommand):
    help = 'Update age for all leads based on their date of birth'

    def handle(self, *args, **options):
        leads = User.objects.all()
        updated_count = 0
        
        for lead in leads:
            if lead.date_of_birth:
                age = calculate_age_from_dob(lead.date_of_birth)
                # Use update to avoid triggering signals
                User.objects.filter(id=lead.id).update(age=age)
                updated_count += 1
                self.stdout.write(f'Updated Lead {lead.id}: {lead.first_name} {lead.last_name} - Age: {age}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully updated age for {updated_count} lead(s).'
            )
        )
