from django import template

register = template.Library()


@register.filter
def display_name(user):
    """
    Returns the user's public display name based on their privacy setting.
    - show_real_name=True  → First + Last name (or username if name not set)
    - show_real_name=False → @username  (anonymous mode)
    """
    if not user:
        return "Anonymous"
    try:
        profile = user.profile
        if profile.show_real_name:
            full = user.get_full_name().strip()
            return full if full else user.username
        return user.username
    except Exception:
        return user.username
