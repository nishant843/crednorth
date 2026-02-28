from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserMeta


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_meta(sender, instance, created, **kwargs):
    """
    Ensures every user has exactly one UserMeta.
    Safe against duplicate inserts.
    """
    UserMeta.objects.get_or_create(user=instance)