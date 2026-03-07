"""
Management command to delete all users (except superusers).
Usage: python manage.py delete_all_users
       python manage.py delete_all_users --all (includes superusers)
       python manage.py delete_all_users --keep-staff (keeps staff users)
"""
from django.core.management.base import BaseCommand
from users.models import User


class Command(BaseCommand):
    help = 'Delete all users from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete ALL users including superusers (dangerous!)',
        )
        parser.add_argument(
            '--keep-staff',
            action='store_true',
            help='Keep staff users, only delete regular users',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        # Build query based on options
        users_query = User.objects.all()
        
        if options['all']:
            # Delete ALL users (dangerous!)
            description = "ALL users including superusers"
        elif options['keep_staff']:
            # Delete only non-staff users
            users_query = users_query.filter(is_staff=False, is_superuser=False)
            description = "all NON-STAFF users"
        else:
            # Default: Delete all except superusers
            users_query = users_query.filter(is_superuser=False)
            description = "all users (except superusers)"
        
        total_count = users_query.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING('No users found to delete.'))
            return
        
        # Show what will be deleted
        self.stdout.write(self.style.WARNING(f'\nAbout to delete {total_count} users:'))
        self.stdout.write(f'  - {description}')
        
        # Show sample of users to be deleted (first 10)
        sample_users = users_query[:10]
        self.stdout.write('\nSample users to be deleted:')
        for user in sample_users:
            self.stdout.write(f'  - {user.phone_number} ({user.first_name} {user.last_name})')
        
        if total_count > 10:
            self.stdout.write(f'  ... and {total_count - 10} more')
        
        # Confirmation
        if not options['yes']:
            self.stdout.write(self.style.WARNING('\n⚠️  THIS ACTION CANNOT BE UNDONE!'))
            confirm = input('\nType "DELETE" to confirm deletion: ')
            
            if confirm != 'DELETE':
                self.stdout.write(self.style.ERROR('Deletion cancelled.'))
                return
        
        # Delete users in batches to avoid memory issues
        batch_size = 500
        deleted_count = 0
        
        self.stdout.write('\nDeleting users...')
        
        while True:
            # Get a batch of user IDs
            batch_ids = list(users_query.values_list('id', flat=True)[:batch_size])
            
            if not batch_ids:
                break
            
            # Delete this batch
            User.objects.filter(id__in=batch_ids).delete()
            deleted_count += len(batch_ids)
            
            self.stdout.write(f'  Deleted {deleted_count}/{total_count} users...', ending='\r')
            self.stdout.flush()
        
        self.stdout.write('')  # New line
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully deleted {deleted_count} users!'))
