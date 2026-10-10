from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def onboarded_required(view_func):
    """Login + onboarding gate used by every seller-facing page."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if profile is None or not profile.onboarded:
            return redirect('onboarding')
        return view_func(request, *args, **kwargs)

    return wrapper
