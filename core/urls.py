"""
Loyihaning asosiy URL konfiguratsiyasi.

Bo'limlar app'lar bo'yicha ajratilgan; har app o'z `urls.py` fayliga ega.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from .views import design_system

# Admin sarlavhalari
admin.site.site_title = "Admin"
admin.site.site_header = "XIU Library"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path('admin/', admin.site.urls),

    # HEMIS oAuth
    path('auth/', include('oauth.urls')),

    # Bosh sahifa, kabinet, profil, analitika
    path('', include('dashboard_app.urls')),

    # Katalog
    path('books/', include('book_app.urls')),

    # Sirkulyatsiya (ijara/navbat)
    path('circulation/', include('circulation.urls')),

    # Raqamli kutubxona (onlayn o'qish/tinglash)
    path('reading/', include('reading.urls')),

    # Faollik (sharh/reyting/sevimli)
    path('engagement/', include('engagement.urls')),

    # Bildirishnomalar
    path('notifications/', include('notifications.urls')),

    # Xodim paneli
    path('panel/', include('panel.urls')),

    # Dizayn tizimi (style-guide) — xodim uchun, flag bilan boshqariladi
    path('_design/', design_system, name='design_system'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
