from django.conf import settings


def site_context(request):
    profile = None
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        profile = getattr(user, 'profile', None)
    return {
        'CURRENCY': settings.CURRENCY,
        'site_profile': profile,
        'nav_section': request.path.strip('/').split('/')[0],
    }
