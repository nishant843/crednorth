"""
Custom authentication backend for passwordless authentication.
This backend allows authentication with just phone_number.
Future: Will be extended to support OTP-based authentication.
"""
from django.contrib.auth.backends import BaseBackend
from users.models import User


class PasswordlessAuthBackend(BaseBackend):
    """
    Custom authentication backend that doesn't require passwords.
    Authenticates users based on phone_number only.
    """
    
    def authenticate(self, request, username=None, **kwargs):
        """
        Authenticate user by phone_number without password.
        
        Args:
            request: HTTP request object
            username: Phone number (10 digits)
            
        Returns:
            User object if found and active, None otherwise
        """
        if username is None:
            username = kwargs.get('phone_number')
        
        if username is None:
            return None
        
        try:
            user = User.objects.get(phone_number=username, is_active=True)
            return user
        except User.DoesNotExist:
            return None
    
    def get_user(self, user_id):
        """
        Get user by ID.
        Required by Django auth system.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
