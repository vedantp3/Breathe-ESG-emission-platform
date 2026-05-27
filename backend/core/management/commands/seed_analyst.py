"""
Management command: seed_analyst

Creates the prototype analyst user + client if they don't already exist.

Usage:
    python manage.py seed_analyst

Creates:
    - Client: "Acme Corp" (slug: acme-corp)
    - User: analyst / analyst123  (role: ANALYST)

TODO: Remove hardcoded credentials before any real deployment.
      Use environment variables or a proper onboarding flow.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Client, UserProfile, UserRole


class Command(BaseCommand):
    help = "Seed the prototype analyst user and default client."

    def handle(self, *args, **options):
        # ── Client ────────────────────────────────────────────────────────
        client, client_created = Client.objects.get_or_create(
            slug="acme-corp",
            defaults={
                "name": "Acme Corp",
                "grid_emission_factor_kgco2e_per_kwh": "0.233",
            },
        )
        if client_created:
            self.stdout.write(self.style.SUCCESS(f"  Created client: {client.name}"))
        else:
            self.stdout.write(f"  Client already exists: {client.name}")

        # ── Analyst user ───────────────────────────────────────────────────
        user, user_created = User.objects.get_or_create(
            username="analyst",
            defaults={
                "email": "analyst@acme-corp.example.com",
                "first_name": "Jane",
                "last_name": "Analyst",
                "is_staff": False,
            },
        )
        if user_created:
            user.set_password("analyst123")
            user.save()
            self.stdout.write(self.style.SUCCESS("  Created user: analyst / analyst123"))
        else:
            self.stdout.write("  User 'analyst' already exists.")

        # ── Profile (update client if auto-created with 'default') ─────────
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.client != client or profile.role != UserRole.ANALYST:
            profile.client = client
            profile.role   = UserRole.ANALYST
            profile.save()
            self.stdout.write(self.style.SUCCESS("  UserProfile linked to Acme Corp."))

        self.stdout.write(self.style.SUCCESS("\nDone. Login: analyst / analyst123"))
