from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, RegisterForm
from .models import CustomUser


def login_view(request):
    if request.user.is_authenticated:
        return redirect('elections:dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.user  # Get the user from the form's clean() method
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name or user.username}!')
            
            next_url = request.GET.get('next', '')
            if next_url:
                return redirect(next_url)
            if user.role == 'registrar':
                return redirect('admin_panel:voter_list')
            elif user.is_admin_user():
                return redirect('admin_panel:dashboard')
            return redirect('elections:dashboard')
        else:
            messages.error(request, 'Invalid credentials. Please try again.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('elections:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Welcome to VoteApp.')
            return redirect('elections:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'You have been securely logged out.')
        return redirect('accounts:login')
    return render(request, 'accounts/logout_confirm.html')


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})
