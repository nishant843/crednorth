from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Simplified admin configuration for User model.
    User model is now only for authentication (phone_number, id).
    No password field - authentication will be via OTP in the future.
    """
    
    # Fields to display in list view
    list_display = (
        'id',
        'phone_number',
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at',
        'updated_at',
    )
    
    # Fields for search functionality
    search_fields = (
        'phone_number',
        'id',
    )
    
    # Filters for sidebar
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at',
    )
    
    # Fields ordering in list view
    ordering = ('-created_at',)
    
    # Number of items per page
    list_per_page = 50
    
    # Enable date hierarchy navigation
    date_hierarchy = 'created_at'
    
    # Fieldsets for add/edit forms
    fieldsets = (
        (None, {
            'fields': ('phone_number',)
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
    readonly_fields = ('id', 'created_at', 'updated_at')

    # Fields to use for filter in right sidebar
    filter_horizontal = ('groups', 'user_permissions')
    
    # Actions
    actions = ['activate_users', 'deactivate_users']
    
    def activate_users(self, request, queryset):
        """Bulk action to activate selected users."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) successfully activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        """Bulk action to deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) successfully deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'

