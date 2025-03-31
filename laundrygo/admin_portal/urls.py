from django.urls import path
from . import views

app_name = 'admin_portal'

urlpatterns = [
    path('', views.admin_login, name='login'),
    path('logout/', views.admin_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('new-registrations/', views.new_registrations, name='new_registrations'),
    path('verify-launderer/<int:verification_id>/', views.verify_launderer, name='verify_launderer'),
    path('manage-customers/', views.manage_customers, name='manage_customers'),
    path('respond-to-customer/<int:query_id>/', views.respond_to_customer, name='respond_to_customer'),
    path('manage-laundromats/', views.manage_laundromats, name='manage_laundromats'),
    path('respond-to-launderer/<int:query_id>/', views.respond_to_launderer, name='respond_to_launderer'),
    path('analytics/', views.analytics, name='analytics'),
    # Add new URLs for contact message management
    path('contact-messages/', views.manage_contact_messages, name='manage_contact_messages'),
    path('respond-to-contact/<int:message_id>/', views.respond_to_contact, name='respond_to_contact'),
]

