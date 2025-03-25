from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        unread_notifications_count = request.user.notifications.filter(is_read=False).count()
        return {'unread_notifications_count': unread_notifications_count}
    return {'unread_notifications_count': 0}