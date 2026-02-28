from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserMeta


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin configuration for User model.
    Provides comprehensive list view, filters, and search capabilities.
    """
    
    # Fields to display in list view
    list_display = (
        'id',
        'phone_number',
        'first_name',
        'last_name',
        'email',
        'pan_number',
        'age',
        'gender',
        'profession',
        'bureau_score',
        'consent_taken',
        'is_active',
        'is_staff',
        'created_at',
    )
    
    # Fields for search functionality
    search_fields = (
        'phone_number',
        'email',
        'first_name',
        'last_name',
        'pan_number',
        'city',
        'state',
        'pin_code',
    )
    
    # Filters for sidebar
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'gender',
        'profession',
        'income_mode',
        'consent_taken',
        'created_at',
        'updated_at',
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
            'fields': ('phone_number', 'password')
        }),
        (_('Personal Information'), {
            'fields': (
                'first_name',
                'last_name',
                'gender',
                'date_of_birth',
                'age',
            )
        }),
        (_('Contact Information'), {
            'fields': (
                'country_code',
                'email',
            )
        }),
        (_('Identity & Location'), {
            'fields': (
                'pan_number',
                'city',
                'state',
                'pin_code',
            )
        }),
        (_('Financial Information'), {
            'fields': (
                'profession',
                'monthly_income',
                'bureau_score',
                'income_mode',
            )
        }),
        (_('Consent & Permissions'), {
            'fields': (
                'consent_taken',
                'is_active',
                'is_staff',
                'is_superuser',
            )
        }),
        (_('Important Dates'), {
            'fields': (
                'created_at',
                'updated_at',
                'last_login',
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
                'password1',
                'password2',
                'first_name',
                'last_name',
                'pan_number',
            ),
        }),
        (_('Additional Information'), {
            'classes': ('wide',),
            'fields': (
                'email',
                'gender',
                'date_of_birth',
                'city',
                'state',
                'pin_code',
                'profession',
                'monthly_income',
                'bureau_score',
                'consent_taken',
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
    readonly_fields = ('age', 'created_at', 'updated_at', 'last_login')
    
    # Fields to use for filter in right sidebar
    filter_horizontal = ('groups', 'user_permissions')
    
    # Actions
    actions = ['activate_users', 'deactivate_users', 'mark_consent_taken']
    
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
    
    def mark_consent_taken(self, request, queryset):
        """Bulk action to mark consent as taken for selected users."""
        updated = queryset.update(consent_taken=True)
        self.message_user(request, f'Consent marked as taken for {updated} user(s).')
    mark_consent_taken.short_description = 'Mark consent as taken'


@admin.register(UserMeta)
class UserMetaAdmin(admin.ModelAdmin):
    """
    Admin for User Meta/Activity tracking (VIEW-ONLY in CRM).
    This shows activity timestamps and status tracking per user.
    """
    
    # List display
    list_display = (
        'user_phone',
        'user_name',
        'first_added_date',
        'last_updated_date',
        'last_login_date',
        'latest_disbursal_date',
        'data_source',
        'data_attribution',
    )
    
    # Search
    search_fields = (
        'user__phone_number',
        'user__first_name',
        'user__last_name',
        'user__pan_number',
        'data_attribution',
    )
    
    # Filters
    list_filter = (
        'data_source',
        'first_added_date',
        'last_updated_date',
        'last_login_date',
        'latest_disbursal_date',
    )
    
    # Ordering
    ordering = ('-last_updated_date',)
    
    # Items per page
    list_per_page = 50
    
    # Date hierarchy
    date_hierarchy = 'last_updated_date'
    
    # All fields are read-only (view-only in CRM)
    readonly_fields = (
        'user',
        'first_added_date',
        'first_added_time',
        'last_updated_date',
        'last_updated_time',
        'first_login_date',
        'first_login_time',
        'last_login_date',
        'last_login_time',
        'latest_disbursal_date',
        'latest_disbursal_time',
        'data_last_downloaded_date',
        'data_last_downloaded_time',
        'status_lend001',
        'status_lend002',
        'status_lend003',
        'data_source',
        'data_attribution',
    )
    
    # Fieldsets for detail view
    fieldsets = (
        ('User Link', {
            'fields': ('user',)
        }),
        ('Creation Tracking', {
            'fields': (
                'first_added_date',
                'first_added_time',
                'data_source',
                'data_attribution',
            )
        }),
        ('Update Tracking', {
            'fields': (
                'last_updated_date',
                'last_updated_time',
            )
        }),
        ('Login Activity', {
            'fields': (
                'first_login_date',
                'first_login_time',
                'last_login_date',
                'last_login_time',
            )
        }),
        ('Disbursal Activity', {
            'fields': (
                'latest_disbursal_date',
                'latest_disbursal_time',
            )
        }),
        ('Download Tracking', {
            'fields': (
                'data_last_downloaded_date',
                'data_last_downloaded_time',
            )
        }),
        ('Lender Status Tracking', {
            'fields': (
                'status_lend001',
                'status_lend002',
                'status_lend003',
            )
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual addition - auto-created with User."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion from admin."""
        return False
    
    def user_phone(self, obj):
        """Display user phone number."""
        return obj.user.phone_number
    user_phone.short_description = 'Phone Number'
    
    def user_name(self, obj):
        """Display user full name."""
        return obj.user.get_full_name()
    user_name.short_description = 'User Name'
