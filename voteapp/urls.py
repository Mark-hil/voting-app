from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('accounts/', include('accounts.urls')),
    path('elections/', include('elections.urls')),
    path('admin-panel/', include('admin_panel.urls')),
]

urlpatterns += staticfiles_urlpatterns()

# Serve media files in development if local storage is used
if settings.DEBUG:
    urlpatterns += static('/voter_candidate/', document_root=settings.BASE_DIR / 'voter_candidate')
