from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Optimized admin configuration for User model handling 1M+ users.
    Includes query optimizations and efficient bulk operations.
    """
    
    # Fields to display in list view
    list_display = (
        'id',
        'phone_number',
        'first_name',
        'last_name',
        'status',
        'profession',
        'monthly_income',
        'is_active',
        'is_staff',
        'created_at',
    )
    
    # Fields for search functionality
    search_fields = (
        'phone_number',
        'first_name',
        'last_name',
        'pan_number',
        'email',
        'id',
    )
    
    # Filters for sidebar
    list_filter = (
        'status',
        'profession',
        'gender',
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at',
    )
    
    # Fields ordering in list view
    ordering = ('-created_at',)
    
    # Number of items per page (optimized for large datasets)
    list_per_page = 100  # Increased from 50 for better UX
    list_max_show_all = 500  # Limit to prevent SQLite "too many SQL variables" error
    
    # Enable date hierarchy navigation
    date_hierarchy = 'created_at'
    
    # Show count - disable for performance with 1M+ records
    show_full_result_count = False  # Critical for performance!
    
    # Fieldsets for add/edit forms
    fieldsets = (
        (None, {
            'fields': ('phone_number', 'email')
        }),
        (_('Personal Info'), {
            'fields': (
                'first_name',
                'last_name',
                'date_of_birth',
                'age',
                'gender',
            )
        }),
        (_('Location'), {
            'fields': ('city', 'state', 'pin_code')
        }),
        (_('Financial Info'), {
            'fields': (
                'profession',
                'monthly_income',
                'bureau_score',
                'income_mode',
            )
        }),
        (_('Status & Consent'), {
            'fields': ('status', 'consent_taken', 'pan_number')
        }),
        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
            )
        }),
        (_('Important Dates'), {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
        (_('Groups & Permissions'), {
            'classes': ('collapse',),
            'fields': ('groups', 'user_permissions')
        }),
    )
    
    # Fieldsets for adding new user
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'phone_number',
            ),
        }),
        (_('Permissions'), {
            'classes': ('wide',),
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
            )
        }),
    )
    
    # Read-only fields (auto-generated fields)
    readonly_fields = ('id', 'age', 'created_at', 'updated_at')

    # Fields to use for filter in right sidebar
    filter_horizontal = ('groups', 'user_permissions')
    
    # Query optimization for 1M+ users - use only indexed fields
    def get_queryset(self, request):
        """Optimize queryset for large datasets."""
        qs = super().get_queryset(request)
        # Don't load related data unless needed
        return qs.only(
            'id', 'phone_number', 'first_name', 'last_name', 'status',
            'profession', 'monthly_income', 'is_active', 'is_staff', 'created_at'
        )
    
    # Bulk actions optimized for large datasets
    actions = ['delete_selected_batched', 'activate_users', 'deactivate_users', 'mark_as_pending', 'mark_as_approved']
    
    def get_actions(self, request):
        """Override to remove default delete action and use our batched version."""
        actions = super().get_actions(request)
        # Remove default delete action to prevent SQLite variable limit errors
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    
    def delete_selected_batched(self, request, queryset):
        """
        Custom delete action that processes deletions in batches to avoid
        SQLite's "too many SQL variables" error.
        
        Batch size: 500 records at a time
        """
        BATCH_SIZE = 500
        total = queryset.count()
        
        if total == 0:
            self.message_user(request, "No users selected.", level=messages.WARNING)
            return
        
        # Safety check for very large deletions
        if total > 10000:
            self.message_user(
                request, 
                f"Cannot delete {total:,} users at once (max 10,000). "
                f"Please use the management command: python manage.py delete_all_users",
                level=messages.ERROR
            )
            return
        
        # Confirmation message
        if request.POST.get('post') != 'yes':
            # Show confirmation page (Django will handle this)
            from django.contrib.admin.actions import delete_selected
            return delete_selected(self, request, queryset.filter(pk__in=list(queryset.values_list('pk', flat=True)[:BATCH_SIZE])))
        
        # Process deletion in batches
        deleted_count = 0
        batch_number = 0
        
        # Get all IDs first
        ids_to_delete = list(queryset.values_list('pk', flat=True))
        
        # Process in batches
        for i in range(0, len(ids_to_delete), BATCH_SIZE):
            batch_ids = ids_to_delete[i:i + BATCH_SIZE]
            batch_number += 1
            batch_count = User.objects.filter(pk__in=batch_ids).delete()[0]
            deleted_count += batch_count
        
        self.message_user(
            request,
            f"Successfully deleted {deleted_count:,} user(s) in {batch_number} batch(es).",
            level=messages.SUCCESS
        )
    
    delete_selected_batched.short_description = 'Delete selected users (batched)'
    delete_selected_batched.allowed_permissions = ('delete',)
    
    def activate_users(self, request, queryset):
        """Bulk action to activate selected users (batched)."""
        BATCH_SIZE = 500
        total = queryset.count()
        updated_count = 0
        
        # Get all IDs first
        ids_to_update = list(queryset.values_list('pk', flat=True))
        
        # Process in batches
        for i in range(0, len(ids_to_update), BATCH_SIZE):
            batch_ids = ids_to_update[i:i + BATCH_SIZE]
            updated_count += User.objects.filter(pk__in=batch_ids).update(is_active=True)
        
        self.message_user(request, f'{updated_count:,} user(s) successfully activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        """Bulk action to deactivate selected users (batched)."""
        BATCH_SIZE = 500
        total = queryset.count()
        updated_count = 0
        
        # Get all IDs first
        ids_to_update = list(queryset.values_list('pk', flat=True))
        
        # Process in batches
        for i in range(0, len(ids_to_update), BATCH_SIZE):
            batch_ids = ids_to_update[i:i + BATCH_SIZE]
            updated_count += User.objects.filter(pk__in=batch_ids).update(is_active=False)
        
        self.message_user(request, f'{updated_count:,} user(s) successfully deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'
    
    def mark_as_pending(self, request, queryset):
        """Bulk action to mark users as pending (batched)."""
        BATCH_SIZE = 500
        total = queryset.count()
        updated_count = 0
        
        # Get all IDs first
        ids_to_update = list(queryset.values_list('pk', flat=True))
        
        # Process in batches
        for i in range(0, len(ids_to_update), BATCH_SIZE):
            batch_ids = ids_to_update[i:i + BATCH_SIZE]
            updated_count += User.objects.filter(pk__in=batch_ids).update(status='pending')
        
        self.message_user(request, f'{updated_count:,} user(s) marked as pending.')
    mark_as_pending.short_description = 'Mark as Pending'
    
    def mark_as_approved(self, request, queryset):
        """Bulk action to mark users as approved (batched)."""
        BATCH_SIZE = 500
        total = queryset.count()
        updated_count = 0
        
        # Get all IDs first
        ids_to_update = list(queryset.values_list('pk', flat=True))
        
        # Process in batches
        for i in range(0, len(ids_to_update), BATCH_SIZE):
            batch_ids = ids_to_update[i:i + BATCH_SIZE]
            updated_count += User.objects.filter(pk__in=batch_ids).update(status='approved')
        
        self.message_user(request, f'{updated_count:,} user(s) marked as approved.')
    mark_as_approved.short_description = 'Mark as Approved'

