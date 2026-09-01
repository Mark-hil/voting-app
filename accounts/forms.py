import secrets
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import models
from .models import CustomUser


class LoginForm(forms.Form):
    username = forms.CharField(
        label='Username or Index Number',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username or Index Number (e.g., NMCSMRGN230001)',
            'autofocus': True,
        })
    )
    unique_code = forms.CharField(
        label='Unique Code or Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Unique Code or Password',
            'render_value': True,
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['unique_code'].widget.attrs['autocomplete'] = 'current-password'

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username', '').strip()
        unique_code = cleaned_data.get('unique_code', '').strip()

        if username and unique_code:
            # Look up user by username, email, or unique_code (exact case-insensitive match first)
            users = CustomUser.objects.filter(
                models.Q(username__iexact=username) |
                models.Q(email__iexact=username) |
                models.Q(unique_code__iexact=username)
            )

            # Fallback for student index numbers embedded in username (e.g. name+index)
            if not users.exists():
                users = CustomUser.objects.filter(username__iendswith=username)

            if not users.exists():
                raise forms.ValidationError('Invalid credentials. Please check your username and code/password.')

            # Check matching user with credentials
            authenticated_user = None
            for user in users:
                if user.is_admin_user():
                    if user.check_password(unique_code):
                        authenticated_user = user
                        break
                else:
                    # Voter: match unique code or password
                    if user.unique_code and user.unique_code.upper() == unique_code.upper():
                        authenticated_user = user
                        break
                    elif user.check_password(unique_code):
                        authenticated_user = user
                        break

            if authenticated_user:
                self.user = authenticated_user
            else:
                raise forms.ValidationError('Invalid credentials. Please try again.')

        return cleaned_data


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'you@example.com'})
    )

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email address already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data['email'].lower()
        user.username = email
        user.email = email
        user.role = 'voter'
        if not user.unique_code:
            user.unique_code = secrets.token_urlsafe(8).upper()
        if commit:
            user.save()
        return user
