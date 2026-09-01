from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """Permits any user with an administrative/management role."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_user():
            messages.error(request, 'Access denied. Administrative privileges required.')
            return redirect('elections:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def system_admin_required(view_func):
    """Permits only System Administrators and Superusers."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_user():
            messages.error(request, 'Access denied. Administrative privileges required.')
            return redirect('elections:dashboard')
        if not request.user.is_system_admin():
            messages.error(request, 'Access denied. System Administrator privileges required for this action.')
            return redirect('admin_panel:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def election_officer_required(view_func):
    """Permits Electoral Commissioners and System Administrators."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_user():
            messages.error(request, 'Access denied. Administrative privileges required.')
            return redirect('elections:dashboard')
        if not request.user.can_manage_elections():
            messages.error(request, 'Access denied. Electoral Commissioner privileges required.')
            return redirect('admin_panel:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def registrar_required(view_func):
    """Permits Voter Registrars and System Administrators."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_user():
            messages.error(request, 'Access denied. Administrative privileges required.')
            return redirect('elections:dashboard')
        if not request.user.can_manage_voters():
            messages.error(request, 'Access denied. Voter Registrar privileges required.')
            return redirect('admin_panel:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def auditor_or_admin_required(view_func):
    """Permits Auditors, Commissioners, and System Administrators (Excludes Registrars)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_user():
            messages.error(request, 'Access denied. Administrative privileges required.')
            return redirect('elections:dashboard')
        if not request.user.can_view_analytics():
            messages.error(request, 'Access denied. Election analytics and tallies are restricted to Auditors, Commissioners, and Admins.')
            if request.user.can_manage_voters():
                return redirect('admin_panel:voter_list')
            return redirect('admin_panel:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


