# itServProject/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import itServ.routing  # We'll create this file in the next step

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'itServProject.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            itServ.routing.websocket_urlpatterns  # Reference WebSocket URL patterns
        )
    ),
})