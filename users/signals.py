from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserMeta


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_meta(sender, instance, created, **kwargs):
    """
    Auto-create UserMeta when a new User is created.
    Ensures every User has corresponding activity tracking.
    """
    if created:
        UserMeta.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_meta(sender, instance, **kwargs):
    """
    Ensure UserMeta exists for existing users.
    Handles edge cases where UserMeta might not exist.
    """
    if not hasattr(instance, 'usermeta'):
        UserMeta.objects.create(user=instance)
