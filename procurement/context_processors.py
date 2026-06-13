def profile(request):
    if request.user.is_authenticated:
        current_profile = getattr(request.user, "profile", None)
        current_membership = None
        if current_profile and current_profile.organization_id:
            current_membership = request.user.memberships.filter(
                organization_id=current_profile.organization_id,
                is_active=True,
            ).first()
        return {
            "current_profile": current_profile,
            "current_membership": current_membership,
            "unread_notifications": request.user.notifications.filter(is_read=False).count(),
        }
    return {"current_profile": None, "current_membership": None, "unread_notifications": 0}
