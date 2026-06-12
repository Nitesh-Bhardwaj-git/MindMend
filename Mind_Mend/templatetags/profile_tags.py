from django import template

register = template.Library()


@register.filter
def display_name(user):
    """
    Returns the user's public display name based on their privacy settings.
    - show_username=False  → 'Anonymous'
    - show_username=True + show_real_name=True → Full name (or username fallback)
    - show_username=True + show_real_name=False → @username
    """
    if not user:
        return "Anonymous"
    try:
        profile = user.profile
        if not profile.show_username:
            return "Anonymous"
        if profile.show_real_name:
            full = user.get_full_name().strip()
            return full if full else user.username
        return user.username
    except Exception:
        return user.username
