import time
import json
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import redirect

def rate_limit(key_func, limit=5, duration=300, message="Too many requests. Please try again later."):
    """
    Rate limiting decorator for views.
    
    Args:
        key_func: Function to generate cache key from request
        limit: Number of allowed requests
        duration: Time window in seconds
        message: Error message to display
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Generate cache key
            cache_key = f"rate_limit:{key_func(request)}"
            
            # Get current count
            count = cache.get(cache_key, 0)
            
            if count >= limit:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return HttpResponse(
                        json.dumps({'error': message}),
                        content_type='application/json',
                        status=429
                    )
                messages.error(request, message)
                return redirect(request.META.get('HTTP_REFERER', '/'))
            
            # Increment counter
            cache.set(cache_key, count + 1, duration)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def login_rate_limit(view_func):
    """Rate limiting for login attempts."""
    def _wrapped_view(request, *args, **kwargs):
        # Only rate limit actual login POST attempts, not GET requests
        if request.method == 'POST':
            return rate_limit(
                key_func=lambda request: f"login:{get_client_ip(request)}",
                limit=5,
                duration=900,  # 15 minutes
                message="Too many login attempts. Please try again in 15 minutes."
            )(view_func)(request, *args, **kwargs)
        else:
            return view_func(request, *args, **kwargs)
    return _wrapped_view

# Removed vote_rate_limit per user request

def admin_rate_limit(view_func):
    """Rate limiting for admin actions."""
    return rate_limit(
        key_func=lambda request: f"admin:{request.user.id}:{get_client_ip(request)}",
        limit=20,
        duration=300,  # 5 minutes
        message="Too many admin actions. Please slow down."
    )(view_func)
