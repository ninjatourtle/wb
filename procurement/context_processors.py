def profile(request):
    if request.user.is_authenticated:
        return {
            "current_profile": getattr(request.user, "profile", None),
            "unread_notifications": request.user.notifications.filter(is_read=False).count(),
        }
    return {"current_profile": None, "unread_notifications": 0}
