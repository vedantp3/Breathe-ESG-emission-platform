"""
core/signals.py

Post-save signal to automatically create a UserProfile when a new User is created.
In the prototype, the default client is the first Client in the database.
TODO: In production, assign client via invite-link or admin-controlled onboarding flow.
"""

from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver

from .models import UserProfile, Client


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, "profile"):
        # Get or create a default client for prototype use
        client, _ = Client.objects.get_or_create(
            slug="default",
            defaults={"name": "Default Client"},
        )
        UserProfile.objects.create(user=instance, client=client)
