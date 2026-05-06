from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('voter', 'Voter'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='voter')
    phone = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    unique_code = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def is_admin_user(self):
        return self.role == 'admin' or self.is_staff

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"
