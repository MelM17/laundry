from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import render

urlpatterns = [
    path('django-admin/', admin.site.urls),  # Rename Django's admin to avoid conflict
    path('', TemplateView.as_view(template_name='landing.html'), name='landing'), 
    path('customer/', include('customer.urls')),  # Changed from '' to 'customer/'
    path('admin/', include('admin_portal.urls')),  # Admin portal URLs
    path('launderer/', include('launderer.urls')),  # Launderer portal URLs
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),  # About page
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

