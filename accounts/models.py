from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('voter', 'Voter'),
        ('admin', 'System Administrator'),
        ('officer', 'Electoral Commissioner'),
        ('registrar', 'Voter Registrar'),
        ('auditor', 'Election Auditor'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='voter')
    phone = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    unique_code = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def is_admin_user(self):
        """Returns True if the user has any staff or management role."""
        return self.role in ['admin', 'officer', 'registrar', 'auditor'] or self.is_staff or self.is_superuser

    def is_system_admin(self):
        """Returns True if the user is a full system administrator or superuser."""
        return self.role == 'admin' or self.is_superuser

    def can_manage_elections(self):
        """Returns True if the user can create/manage elections and candidates."""
        return self.role in ['admin', 'officer'] or self.is_superuser

    def can_manage_voters(self):
        """Returns True if the user can invite/import voters and manage voter codes."""
        return self.role in ['admin', 'registrar'] or self.is_superuser

    def can_view_analytics(self):
        """Returns True if the user can view live stats, results, and audit packs (Admin, Officer, Auditor)."""
        return self.role in ['admin', 'officer', 'auditor'] or self.is_superuser

    def can_access_maintenance(self):
        """Returns True if the user can access backup and data reset tools."""
        return self.role == 'admin' or self.is_superuser

    def get_role_badge_class(self):
        """Returns CSS class for badge rendering."""
        return self.role if self.role in ['admin', 'officer', 'registrar', 'auditor', 'voter'] else 'voter'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

