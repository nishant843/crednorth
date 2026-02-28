from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """
    Custom user manager for User model where phone_number is the unique identifier
    instead of username.
    """
    
    def create_user(self, phone_number, password=None, **extra_fields):
        """
        Create and save a regular user with the given phone number and password.
        """
        if not phone_number:
            raise ValueError('Phone number is required')
        
        # Ensure phone_number is exactly 10 digits
        if not phone_number.isdigit() or len(phone_number) != 10:
            raise ValueError('Phone number must be exactly 10 digits')
        
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user
    
    def create_superuser(self, phone_number, password=None, **extra_fields):
        """
        Create and save a superuser with the given phone number and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(phone_number, password, **extra_fields)
