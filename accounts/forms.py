from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
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
        label='Unique Code',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Unique Code (8 characters)',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['unique_code'].widget.attrs['autocomplete'] = 'off'

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        unique_code = cleaned_data.get('unique_code')

        if username and unique_code:
            print(f"DEBUG: Login attempt - Username: '{username}', Unique Code: '{unique_code}'")
            
            # Try to find user by email, username, index number, or unique code
            try:
                users = CustomUser.objects.filter(
                    models.Q(email=username) | 
                    models.Q(username=username) |
                    models.Q(username__icontains=username) |  # Allow partial username match
                    models.Q(unique_code=username.upper()) |  # Allow login with index number as username
                    models.Q(unique_code__icontains=username)  # Allow partial match for index numbers
                )
                
                print(f"DEBUG: Query returned {users.count()} results")
                if users.count() > 0:
                    print(f"DEBUG: Found users: {list(users.values_list('username', flat=True))}")
                
                if users.count() == 0:
                    print(f"DEBUG: User not found with username: '{username}'")
                    raise forms.ValidationError('Invalid credentials.')
                elif users.count() == 1:
                    user = users.first()
                else:
                    # Multiple matches found, try to find the best match
                    # Prefer exact username match
                    user = users.filter(username=username).first()
                    if not user:
                        # Then try to match username that ends with the input
                        user = users.filter(username__endswith=username).first()
                    if not user:
                        # Fall back to first result
                        user = users.first()
                
                print(f"DEBUG: Found user - Username: '{user.username}', Email: '{user.email}', Unique Code: '{user.unique_code}', Role: '{user.role}'")
                
                # Check if it's an admin (email + password)
                if user.is_admin_user():
                    print("DEBUG: User is admin, checking password")
                    # For admins, treat unique_code as password
                    if user.check_password(unique_code):
                        self.user = user
                        print("DEBUG: Admin login successful")
                    else:
                        print("DEBUG: Admin password check failed")
                        raise forms.ValidationError('Invalid credentials.')
                else:
                    print("DEBUG: User is voter, checking unique code")
                    # For voters, check unique code
                    if user.unique_code == unique_code.upper():
                        self.user = user
                        print("DEBUG: Voter login successful")
                    else:
                        print(f"DEBUG: Voter unique code mismatch - Expected: '{user.unique_code}', Got: '{unique_code.upper()}'")
                        raise forms.ValidationError('Invalid credentials.')
                
            except CustomUser.DoesNotExist:
                print(f"DEBUG: User not found with username: '{username}'")
                raise forms.ValidationError('Invalid credentials.')
        
        return cleaned_data


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'you@example.com'})
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': '••••••••'})
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': '••••••••'})
    )

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
