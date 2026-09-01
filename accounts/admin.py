from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'unique_code', 'is_verified', 'is_staff')
    list_filter = ('role', 'is_verified', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('VoteApp Info', {'fields': ('role', 'unique_code', 'phone', 'is_verified')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('VoteApp Info', {'fields': ('role', 'unique_code', 'phone', 'is_verified')}),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name', 'unique_code')

