from django.urls import path
from . import views

app_name = 'customer'

urlpatterns = [
    path('', views.dashboard, name='home'),  
    path('register/', views.register_customer, name='register'),
    path('login/', views.login_customer, name='login'),
    path('logout/', views.logout_customer, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('launderer/<int:launderer_id>/', views.launderer_detail, name='launderer_detail'),
    path('scheduling/<int:launderer_id>/', views.scheduling, name='scheduling'),
    path('orders/', views.orders, name='orders'),
    path('order/<uuid:order_id>/', views.order_details, name='order_details'),
    path('order/<uuid:order_id>/pdf/', views.download_order_pdf, name='download_order_pdf'),
    path('order/<uuid:order_id>/review/', views.submit_review, name='submit_review'),
    path('order/<uuid:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('settings/', views.settings, name='settings'),
    path('help/', views.help, name='help'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<int:user_id>/', views.reset_password, name='reset_password'),
    path('unregistered-contact/', views.contact, name='unregistered_contact'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('order/<uuid:order_id>/tracking/', views.order_tracking, name='order_tracking'),
]


