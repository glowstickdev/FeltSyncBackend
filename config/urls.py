from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("csvapp.urls")),
    path('api/v1/', include('csvapp.api_urls')),
]

# Serve media files in development (in production, serve via nginx/whitenoise)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
